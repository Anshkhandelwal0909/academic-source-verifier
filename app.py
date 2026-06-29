import uuid
import asyncio
import json
from fastapi import FastAPI, Query, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import requests
import concurrent.futures
from rapidfuzz import fuzz
from typing import List, Optional, Tuple, AsyncGenerator
import time
import traceback
import xml.etree.ElementTree as ET

from document_processor import parse_document, extract_keywords

app = FastAPI(title="Academic Source Verifier API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Source(BaseModel):
    title: str
    authors: str
    year: Optional[int]
    venue: str
    doi: Optional[str]
    arxiv_id: Optional[str]
    url: Optional[str]
    abstract: str
    tier: int
    citation_count: int
    citation_string: str
    source_api: str

class SearchResponse(BaseModel):
    results: List[Source]
    warnings: List[str]

def generate_citation(title, authors, year, venue, url):
    author_list = authors.split(", ") if authors else ["Unknown Author"]
    if len(author_list) > 2:
        author_str = f"{author_list[0]} et al."
    else:
        author_str = " & ".join(author_list)
    
    year_str = f"({year})" if year else "(n.d.)"
    venue_str = f". {venue}." if venue else "."
    url_str = f" {url}" if url else ""
    return f"{author_str} {year_str}. {title}{venue_str}{url_str}"

def determine_tier(doi, arxiv_id, venue):
    venue_lower = venue.lower() if venue else ""
    doi_lower = doi.lower() if doi else ""
    if arxiv_id or 'arxiv' in venue_lower or 'ssrn' in venue_lower or '10.2139/ssrn' in doi_lower:
        return 2
    if doi:
        return 1
    return 3

def fetch_with_retry(url, headers, params, max_retries=3):
    last_err = None
    for i in range(max_retries):
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=10)
            if resp.status_code == 429:
                time.sleep(2 ** i)
                last_err = requests.exceptions.HTTPError("429 Too Many Requests")
                continue
            resp.raise_for_status()
            return resp
        except Exception as e:
            last_err = e
            if i < max_retries - 1:
                time.sleep(2 ** i)
    raise last_err

def search_semantic_scholar(query: str, limit: int = 5) -> Tuple[List[dict], Optional[str]]:
    try:
        headers = {"User-Agent": "AcademicSourceVerifier/1.0 (mailto:anonymous@example.com)"}
        resp = fetch_with_retry(
            "https://api.semanticscholar.org/graph/v1/paper/search",
            headers=headers,
            params={"query": query, "limit": limit, "fields": "title,year,authors,venue,citationCount,externalIds,tldr"}
        )
        data = resp.json().get("data", [])
        results = []
        for item in data:
            ext_ids = item.get("externalIds", {})
            doi = ext_ids.get("DOI")
            arxiv = ext_ids.get("ArXiv")
            authors = ", ".join([a.get("name", "") for a in item.get("authors", [])])
            tldr = item.get("tldr")
            abstract = tldr.get("text") if tldr else ""
            results.append({
                "title": item.get("title", ""),
                "authors": authors,
                "year": item.get("year"),
                "venue": item.get("venue", ""),
                "doi": doi,
                "arxiv_id": arxiv,
                "url": f"https://doi.org/{doi}" if doi else (f"https://arxiv.org/abs/{arxiv}" if arxiv else ""),
                "abstract": abstract,
                "citation_count": item.get("citationCount", 0),
                "source_api": "Semantic Scholar"
            })
        return results, None
    except Exception as e:
        return [], f"Semantic Scholar unavailable ({type(e).__name__})"

def search_openalex(query: str, limit: int = 5) -> Tuple[List[dict], Optional[str]]:
    try:
        headers = {"User-Agent": "AcademicSourceVerifier/1.0 (mailto:anonymous@example.com)"}
        resp = fetch_with_retry(
            "https://api.openalex.org/works",
            headers=headers,
            params={"search": query, "per_page": limit, "mailto": "anonymous@example.com"}
        )
        data = resp.json().get("results", [])
        results = []
        for item in data:
            doi = item.get("doi")
            if doi and doi.startswith("https://doi.org/"):
                doi = doi.replace("https://doi.org/", "")
            
            venue = item.get("primary_location", {}).get("source", {})
            venue_name = venue.get("display_name", "") if venue else ""
            
            authorships = item.get("authorships", [])
            authors = ", ".join([a.get("author", {}).get("display_name", "") for a in authorships])
            
            arxiv_id = None
            url = item.get("id")
            primary_url = item.get("primary_location", {}).get("landing_page_url", "")
            if primary_url and "arxiv.org/abs/" in primary_url:
                arxiv_id = primary_url.split("arxiv.org/abs/")[-1]
                url = primary_url
            
            results.append({
                "title": item.get("title", ""),
                "authors": authors,
                "year": item.get("publication_year"),
                "venue": venue_name,
                "doi": doi,
                "arxiv_id": arxiv_id, 
                "url": url,
                "abstract": "Abstract available on source page.",
                "citation_count": item.get("cited_by_count", 0),
                "source_api": "OpenAlex"
            })
        return results, None
    except Exception as e:
        return [], f"OpenAlex unavailable ({type(e).__name__})"

def search_crossref(query: str, limit: int = 5) -> Tuple[List[dict], Optional[str]]:
    try:
        headers = {"User-Agent": "AcademicSourceVerifier/1.0 (mailto:anonymous@example.com)"}
        resp = fetch_with_retry(
            "https://api.crossref.org/works",
            headers=headers,
            params={"query": query, "rows": limit, "mailto": "anonymous@example.com"}
        )
        data = resp.json().get("message", {}).get("items", [])
        results = []
        for item in data:
            doi = item.get("DOI")
            title = item.get("title", [""])[0] if item.get("title") else ""
            authors_list = item.get("author", [])
            authors = ", ".join([f"{a.get('given', '')} {a.get('family', '')}".strip() for a in authors_list])
            
            venue = item.get("container-title", [""])[0] if item.get("container-title") else ""
            
            issued = item.get("issued", {}).get("date-parts", [[None]])
            year = issued[0][0] if issued and issued[0] else None
            
            results.append({
                "title": title,
                "authors": authors,
                "year": year,
                "venue": venue,
                "doi": doi,
                "arxiv_id": None,
                "url": item.get("URL", f"https://doi.org/{doi}" if doi else ""),
                "abstract": "",
                "citation_count": item.get("is-referenced-by-count", 0),
                "source_api": "Crossref"
            })
        return results, None
    except Exception as e:
        return [], f"Crossref unavailable ({type(e).__name__})"

def search_europepmc(query: str, limit: int = 5) -> Tuple[List[dict], Optional[str]]:
    try:
        headers = {"User-Agent": "AcademicSourceVerifier/1.0"}
        resp = fetch_with_retry(
            "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
            headers=headers,
            params={"query": query, "format": "json", "resultType": "lite", "pageSize": limit}
        )
        data = resp.json().get("resultList", {}).get("result", [])
        results = []
        for item in data:
            doi = item.get("doi")
            authors = item.get("authorString", "")
            results.append({
                "title": item.get("title", ""),
                "authors": authors,
                "year": item.get("pubYear"),
                "venue": item.get("journalTitle", ""),
                "doi": doi,
                "arxiv_id": None,
                "url": f"https://europepmc.org/article/MED/{item.get('pmid')}" if item.get("pmid") else (f"https://doi.org/{doi}" if doi else ""),
                "abstract": "",
                "citation_count": item.get("citedByCount", 0),
                "source_api": "Europe PMC"
            })
        return results, None
    except Exception as e:
        return [], f"Europe PMC unavailable ({type(e).__name__})"

def search_arxiv(query: str, limit: int = 5) -> Tuple[List[dict], Optional[str]]:
    try:
        resp = fetch_with_retry(
            "http://export.arxiv.org/api/query",
            headers={"User-Agent": "AcademicSourceVerifier/1.0"},
            params={"search_query": f"all:{query}", "start": 0, "max_results": limit}
        )
        root = ET.fromstring(resp.content)
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        results = []
        for entry in root.findall('atom:entry', ns):
            title = entry.find('atom:title', ns).text
            if title: title = title.replace('\\n', ' ').strip()
            
            authors = ", ".join([author.find('atom:name', ns).text for author in entry.findall('atom:author', ns)])
            
            published = entry.find('atom:published', ns).text
            year = int(published[:4]) if published else None
            
            url = entry.find('atom:id', ns).text
            arxiv_id = url.split('/abs/')[-1] if '/abs/' in url else None
            
            summary = entry.find('atom:summary', ns).text
            
            results.append({
                "title": title or "",
                "authors": authors,
                "year": year,
                "venue": "arXiv preprint",
                "doi": None,
                "arxiv_id": arxiv_id,
                "url": url,
                "abstract": summary.replace('\\n', ' ').strip() if summary else "",
                "citation_count": 0,
                "source_api": "arXiv"
            })
        return results, None
    except Exception as e:
        return [], f"arXiv unavailable ({type(e).__name__})"

def deduplicate_and_rank(all_results, include_tier3=False):
    unique_sources = []
    seen_dois = set()
    merge_logs = []
    
    for res in all_results:
        if not res.get("title"):
            continue
            
        is_duplicate = False
        doi = res.get("doi")
        
        if doi:
            doi = doi.lower()
            if doi in seen_dois:
                is_duplicate = True
                merge_logs.append(f"Merged by DOI: {doi}")
            else:
                seen_dois.add(doi)
                
        if not is_duplicate:
            for u_res in unique_sources:
                if fuzz.ratio(res["title"].lower(), u_res["title"].lower()) > 90:
                    is_duplicate = True
                    merge_logs.append(f"Merged by Title: '{res['title']}' matches '{u_res['title']}'")
                    if not u_res.get("abstract") and res.get("abstract"):
                        u_res["abstract"] = res.get("abstract")
                    break
                    
        if not is_duplicate:
            tier = determine_tier(res.get("doi"), res.get("arxiv_id"), res.get("venue"))
            if tier == 3 and not include_tier3:
                continue 
                
            citation_string = generate_citation(
                res["title"], res["authors"], res.get("year"), res.get("venue"), res.get("url")
            )
            unique_sources.append({
                **res,
                "tier": tier,
                "citation_string": citation_string
            })
            
    unique_sources.sort(key=lambda x: (x["tier"], -x.get("citation_count", 0)))
    return unique_sources, merge_logs

@app.get("/api/search", response_model=SearchResponse)
def search_sources(q: str, include_tier3: bool = False):
    if not q:
        raise HTTPException(status_code=400, detail="Query is required")
        
    all_results = []
    warnings = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        f1 = executor.submit(search_semantic_scholar, q, 5)
        f2 = executor.submit(search_openalex, q, 5)
        f3 = executor.submit(search_crossref, q, 5)
        f4 = executor.submit(search_europepmc, q, 5)
        f5 = executor.submit(search_arxiv, q, 5)
        
        res1, warn1 = f1.result()
        res2, warn2 = f2.result()
        res3, warn3 = f3.result()
        res4, warn4 = f4.result()
        res5, warn5 = f5.result()
        
        all_results.extend(res1)
        if warn1: warnings.append(warn1)
        all_results.extend(res2)
        if warn2: warnings.append(warn2)
        all_results.extend(res3)
        if warn3: warnings.append(warn3)
        all_results.extend(res4)
        if warn4: warnings.append(warn4)
        all_results.extend(res5)
        if warn5: warnings.append(warn5)
        
    final_sources, merge_logs = deduplicate_and_rank(all_results, include_tier3)
    
    for log in set(merge_logs):
        warnings.append(log)
        
    return {"results": final_sources, "warnings": warnings}


# --- DOCUMENT UPLOAD & STREAMING ARCHITECTURE ---

JOBS = {}
SENTENCE_CACHE = {}
QUERY_CACHE = {}

@app.on_event("startup")
def open_browser_on_startup():
    import threading
    import time
    import webbrowser
    def open_browser():
        time.sleep(1.5)
        webbrowser.open("http://localhost:8000")
    threading.Thread(target=open_browser, daemon=True).start()

@app.post("/api/document/upload")
async def upload_document(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    content = await file.read()
    
    job_id = str(uuid.uuid4())
    JOBS[job_id] = {
        "id": job_id,
        "status": "QUEUED",
        "created_at": time.time(),
        "total_sentences": 1, # Placeholder until parsing completes
        "processed_sentences": 0,
        "lines": []
    }
    
    background_tasks.add_task(process_document_job, job_id, content, file.filename)
    return {"job_id": job_id}

def process_document_job(job_id: str, file_content: bytes, filename: str):
    import threading
    job = JOBS.get(job_id)
    if not job:
        return
        
    try:
        job["status"] = "PARSING"
        lines_data = parse_document(file_content, filename)
        job["lines"] = lines_data
        job["total_sentences"] = len(lines_data)
        job["status"] = "PROCESSING"
        
        progress_lock = threading.Lock()
        
        def process_line(i, line):
            if line["status"] == "FACTUAL":
                job["lines"][i]["status"] = "SEARCHING"
                
                norm_sent = line["text"].lower().strip()
                if norm_sent in SENTENCE_CACHE:
                    keywords = SENTENCE_CACHE[norm_sent]
                else:
                    keywords = extract_keywords(line["text"])
                    SENTENCE_CACHE[norm_sent] = keywords
                
                if not keywords or len(keywords.split()) < 2:
                    job["lines"][i]["status"] = "NO_SUPPORT_FOUND"
                    job["lines"][i]["confidence"] = 0.0
                    job["lines"][i]["reason"] = "Extracted query too short for meaningful search."
                else:
                    cache_key = keywords.lower()
                    if cache_key in QUERY_CACHE:
                        results = QUERY_CACHE[cache_key]
                    else:
                        try:
                            all_results = []
                            # Fetch APIs concurrently for the single sentence
                            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as api_executor:
                                f1 = api_executor.submit(search_semantic_scholar, keywords, 3)
                                f2 = api_executor.submit(search_openalex, keywords, 3)
                                f3 = api_executor.submit(search_crossref, keywords, 3)
                                f4 = api_executor.submit(search_europepmc, keywords, 3)
                                f5 = api_executor.submit(search_arxiv, keywords, 3)
                                
                                res1, _ = f1.result()
                                res2, _ = f2.result()
                                res3, _ = f3.result()
                                res4, _ = f4.result()
                                res5, _ = f5.result()
                                
                            all_results.extend(res1)
                            all_results.extend(res2)
                            all_results.extend(res3)
                            all_results.extend(res4)
                            all_results.extend(res5)
                            
                            final_sources, _ = deduplicate_and_rank(all_results, include_tier3=False)
                            results = final_sources[:3]
                            QUERY_CACHE[cache_key] = results
                        except Exception as e:
                            job["lines"][i]["status"] = "SEARCH_FAILED"
                            job["lines"][i]["reason"] = f"API error: {str(e)}"
                            with progress_lock:
                                job["processed_sentences"] += 1
                            return
                    
                    job["lines"][i]["sources"] = results
                    
                    if results and any(r["tier"] == 1 for r in results):
                        job["lines"][i]["status"] = "SUPPORTED_TIER1"
                        job["lines"][i]["confidence"] = 0.95
                        job["lines"][i]["reason"] = "Matched peer-reviewed or DOI source."
                    elif results and any(r["tier"] == 2 for r in results):
                        job["lines"][i]["status"] = "SUPPORTED_TIER2"
                        job["lines"][i]["confidence"] = 0.8
                        job["lines"][i]["reason"] = "Matched preprint or working paper."
                    else:
                        job["lines"][i]["status"] = "NO_SUPPORT_FOUND"
                        job["lines"][i]["confidence"] = 0.0
                        job["lines"][i]["reason"] = "No Tier 1 or Tier 2 source located."
                        
            with progress_lock:
                job["processed_sentences"] += 1

        # Process multiple lines concurrently
        # 4 max workers * 5 APIs per worker = max 20 concurrent threads against APIs
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as line_executor:
            futures = []
            for i, line in enumerate(lines_data):
                futures.append(line_executor.submit(process_line, i, line))
            concurrent.futures.wait(futures)
            
        job["status"] = "COMPLETE"
    except Exception as e:
        job["status"] = "FAILED"
        print(f"Job {job_id} failed: {e}")

@app.get("/api/document/stream/{job_id}")
async def stream_document_progress(job_id: str):
    async def event_generator() -> AsyncGenerator[str, None]:
        job = JOBS.get(job_id)
        if not job:
            yield f"data: {json.dumps({'error': 'Job not found'})}\n\n"
            return
            
        # Keep track of the last state we sent for each line to only push updates
        sent_states = {}
        
        while True:
            # If still parsing, yield parsing status
            if job["status"] in ["QUEUED", "PARSING"]:
                yield f"data: {json.dumps({'type': 'parsing', 'progress': 0, 'total': 1})}\n\n"
                await asyncio.sleep(0.5)
                continue
                
            progress = job["processed_sentences"]
            total = job["total_sentences"]
            
            # Since lines process out of order in parallel, scan all lines for state changes
            for i, line in enumerate(job["lines"]):
                current_state = line["status"]
                last_sent_state = sent_states.get(i)
                
                if current_state != last_sent_state:
                    if current_state in ["SUPPORTED_TIER1", "SUPPORTED_TIER2", "NO_SUPPORT_FOUND", "SEARCH_FAILED", "SEARCH_SKIPPED"]:
                        yield f"data: {json.dumps({'type': 'line_complete', 'data': line, 'progress': progress, 'total': total})}\n\n"
                        sent_states[i] = current_state
                    elif current_state == "SEARCHING":
                        yield f"data: {json.dumps({'type': 'line_searching', 'data': line, 'progress': progress, 'total': total})}\n\n"
                        sent_states[i] = current_state
            
            if job["status"] == "COMPLETE":
                yield f"data: {json.dumps({'type': 'job_complete'})}\n\n"
                break
            elif job["status"] == "FAILED":
                yield f"data: {json.dumps({'type': 'job_failed'})}\n\n"
                break
                
            await asyncio.sleep(0.2)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


app.mount("/", StaticFiles(directory="frontend", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
