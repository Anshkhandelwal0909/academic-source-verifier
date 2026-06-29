# Tech Stack: AI Research-Sourcing Agent
### A tool that finds, validates, and returns citable sources for thesis/academic work

---

## 1. What This Tool Does

Given a claim or topic (e.g., "overfitting in backtests" or "regime-switching portfolio allocation"), the tool:
1. Searches multiple **primary, citable** academic/regulatory databases (not just generic web search)
2. Returns structured metadata: title, authors, DOI, abstract, publication venue, citation count
3. Flags source quality (peer-reviewed journal vs. preprint vs. working paper vs. non-academic)
4. Outputs ready-to-use citations in the format you need (APA/MLA/Chicago)

This directly solves the problem from your thesis work: distinguishing a real, citable source (a journal paper, a regulatory document) from a derivative/non-citable one (a student study guide, an AI chat summary).

---

## 2. Core Data Sources (the actual APIs — all real, verified, documented below)

| Source | Coverage | Cost | API Key Needed? | Best For |
|---|---|---|---|---|
| **Semantic Scholar Academic Graph API** | ~200M papers, all fields | Free | No (optional, for higher rate limit) | General academic search, AI-generated TLDR summaries, citation counts |
| **OpenAlex API** | 250M+ scholarly works | Free | No | Large-scale search, author/institution data, citation metrics |
| **Crossref REST API** | 150M+ works (DOI registry) | Free | No | DOI resolution, definitive bibliographic metadata, citation counts |
| **arXiv API** | 2M+ preprints (physics, CS, quant-finance, stats) | Free | No | Pre-print ML/quant-finance papers (note: not peer-reviewed) |

**Why these four specifically:** Key APIs such as Crossref's REST API, Semantic Scholar's Graph API, the OpenAlex API, PubMed's E-utilities, and arXiv's API provide free or low-cost access to millions or even hundreds of millions of scholarly records, and researchers commonly combine them rather than relying on one alone. One practitioner's stated workflow: Semantic Scholar for discovery, Crossref for DOI metadata, and CORE for full text — using each toolkit for its specific strength.

### Source details

**Semantic Scholar**
- Most endpoints are available to the public without authentication, rate-limited to 1000 requests per second shared among all unauthenticated users; an API key raises the per-user rate limit and is requested via email.
- Base URL: `http://api.semanticscholar.org/graph/v1/`
- Built by the Allen Institute for AI; unlike Crossref or OpenAlex, it generates AI-based TLDR summaries and performs author disambiguation — useful for quickly triaging which papers are worth a closer read.

**OpenAlex**
- Aggregates and standardizes data primarily from Microsoft Academic Graph and Crossref, as well as ORCID, Unpaywall, and institutional repositories; the API is free, and including an email parameter (mailto=) puts requests in a faster "polite pool".
- Important caveat for your use case: OpenAlex prioritizes accurate metadata sourced from trusted organizations like Crossref, but does not verify the content of indexed works — it is up to the user to critically assess the reliability of the publications retrieved. This matters: the API finding a paper doesn't mean the paper is good; your tool still needs a quality filter (Section 4).

**Crossref**
- Crossref, launched in 1999, is the official DOI registration agency of the International DOI Foundation and works with thousands of publishers to provide authorized metadata including DOI, publication date, and related bibliographic information, made available via free public API.
- This is your most authoritative source for "is this a real, registered, citable publication" — if something has a Crossref-registered DOI, it's a legitimate publication record, not a blog post or AI-generated summary.

**arXiv**
- Good for cutting-edge quant-finance/ML papers, but **not peer-reviewed** — flag these distinctly in your tool's output (see Section 4) so they're not presented with the same confidence as a journal article.

---

## 3. Recommended Architecture

```
┌─────────────────────┐
│   User Query/Claim   │   e.g. "overfitting in quant backtests"
└──────────┬───────────┘
           │
           ▼
┌─────────────────────┐
│   Query Expansion     │   LLM generates 2-4 search variants
│   (LLM call)          │   (synonyms, related terms)
└──────────┬───────────┘
           │
           ▼
┌─────────────────────────────────────────────┐
│         Parallel Multi-Source Search          │
│  ┌────────────┐ ┌──────────┐ ┌──────────┐    │
│  │ Semantic   │ │ OpenAlex │ │ Crossref │    │
│  │ Scholar    │ │   API    │ │   API    │    │
│  └────────────┘ └──────────┘ └──────────┘    │
└──────────────────────┬────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────┐
│           Deduplication & Merge                │
│   (match by DOI where available)               │
└──────────────────────┬────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────┐
│         Source Quality Scoring (Section 4)      │
└──────────────────────┬────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────┐
│      Citation Formatter (APA/MLA/Chicago)       │
└──────────────────────┬────────────────────────┘
                        │
                        ▼
┌─────────────────────┐
│   Structured Output   │
└─────────────────────┘
```

### Component stack

| Layer | Recommended Tool | Why |
|---|---|---|
| Orchestration | Python script or LangGraph/simple agent loop | You already work in this ecosystem (Antigravity is Python-based) |
| Query expansion | Claude/GPT API call | Generates better search variants than the raw user query alone |
| API clients | `requests` (Python) — all 3 APIs are plain REST/JSON | No special SDK needed; Semantic Scholar also has an official Python client if preferred |
| Deduplication | Match on DOI; fallback to fuzzy title match (`rapidfuzz` library) | Same paper often appears in multiple sources with slightly different metadata |
| Storage | SQLite or a simple JSON file for your thesis's reference list | No need for a full database for single-user thesis work |
| Output formatting | `pybtex` or hand-rolled string templates per citation style | Converts structured metadata into APA/Chicago formatted citations |

---

## 4. Source Quality Scoring (the part that matters most for your use case)

Given the OpenAlex caveat above (the API doesn't vouch for content quality, only that the record exists), your tool needs its own tiering logic. Suggested tiers:

**Tier 1 — Always citable as primary evidence**
- Has a Crossref-registered DOI in a recognized peer-reviewed journal
- Government/regulatory documents (Federal Reserve, SEC, RBI, SEBI, BIS) — these won't appear in academic APIs at all; fetch directly from the issuing body's website
- Output flag: ✅ Peer-reviewed / Primary regulatory source

**Tier 2 — Usable, but cite with care**
- arXiv/SSRN preprints — real research, often by credible authors, but not peer-reviewed
- Output flag: ⚠️ Preprint / Working paper — not peer-reviewed

**Tier 3 — Background only, not for citation**
- Student-made study guides, blog posts, non-peer-reviewed compilations (like the MIT Sloan "Quant Bible" you asked about earlier)
- Output flag: 🚫 Not citable as academic evidence — background reading only

This tiering directly encodes the lesson from your thesis work: a confident-sounding document isn't automatically a valid source, and your tool should make that distinction explicit in its output rather than returning a flat list.

---

## 5. What This Tool Does NOT Replace

- **Your university library's institutional access** (JSTOR, ScienceDirect, Springer) — these often have content not in any free API; check there first for anything paywalled.
- **Human judgment on relevance** — the APIs return what matches the query; you still need to read abstracts and decide what's actually relevant to your specific claim.
- **SSRN coverage** — SSRN doesn't have a public API; for SSRN papers, search via Google Scholar/SSRN's own site search and pull metadata manually, or use Crossref if the paper has since received a DOI.

---

## 6. Minimal Working Example (Python, no API key required)

```python
import requests

def search_semantic_scholar(query, limit=5):
    resp = requests.get(
        "https://api.semanticscholar.org/graph/v1/paper/search",
        params={"query": query, "limit": limit,
                "fields": "title,year,authors,venue,citationCount,externalIds,tldr"}
    )
    return resp.json().get("data", [])

def search_openalex(query, limit=5):
    resp = requests.get(
        "https://api.openalex.org/works",
        params={"search": query, "per_page": limit,
                "mailto": "your_email@example.com"}  # joins "polite pool" for faster response
    )
    return resp.json().get("results", [])

def search_crossref(query, limit=5):
    resp = requests.get(
        "https://api.crossref.org/works",
        params={"query": query, "rows": limit,
                "mailto": "your_email@example.com"}
    )
    return resp.json()["message"]["items"]
```

This is enough to build the "parallel multi-source search" block in Section 3's architecture diagram. Deduplication and quality scoring would sit on top of this as the next build step.

---

## Sources used in this document
- Semantic Scholar Academic Graph API documentation — semanticscholar.org/product/api
- OpenAlex API documentation and University of Calgary library guide — libguides.ucalgary.ca; docs.openalex.org
- Crossref REST API — api.crossref.org
- IntuitionLabs 2026 overview of scholarly API landscape — intuitionlabs.ai
