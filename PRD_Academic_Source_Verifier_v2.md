# Product Requirements Document: Academic Source Verifier
### v2 — Scoped for actual build, not aspirational platform

---

## 0. What Changed From v1, and Why

The original draft described a general-purpose misinformation/fact-checking platform — web crawlers, knowledge graphs, multimodal input, real-time news monitoring, veracity assessment for arbitrary claims. That's a venture-scale product, not something one person builds and uses. This version narrows scope to **one job, done well**: given a claim or topic, return real, citable, quality-tiered academic/regulatory sources — the exact problem you hit repeatedly while sourcing your thesis (e.g., realizing the "Quant Bible" wasn't a citable primary source).

Everything cut from v1 is listed in Section 7 as explicit non-goals, not forgotten — just deferred.

---

## 1. Problem Statement

When writing a thesis (or any research requiring real citations), it's slow and error-prone to manually determine:
- Whether a source is a primary academic source vs. a derivative/non-citable compilation
- Whether a claim is actually supported by what a paper says, or just sounds plausible
- What the correctly formatted citation is

This tool automates steps 1–3 for a single query at a time, using real, documented, free academic APIs — not general web search, which returns blogs and AI-generated content indistinguishable from primary sources without manual vetting.

---

## 2. Goals (Measurable)

| Goal | How it's measured |
|---|---|
| Return only real, traceable sources | Every result has a DOI, arXiv ID, or direct .gov/regulatory URL — no result without one of these three |
| Distinguish source quality automatically | Every result tagged Tier 1/2/3 (Section 5) — no untagged results |
| Save manual lookup time | Single query returns merged, deduplicated results from 3 APIs in one call, vs. manually checking 3 sites |
| Produce ready-to-use citations | Output includes pre-formatted APA citation string per source |

## 2.1 Explicit Non-Goals (cut from v1)

- ❌ Veracity assessment / fact-checking of arbitrary internet claims
- ❌ General web crawling or news monitoring
- ❌ Multimodal (image/audio) input
- ❌ Personalization or user accounts
- ❌ Knowledge graph / ontology construction
- ❌ Real-time monitoring of emerging topics

These aren't ruled out forever — they're correctly identified in v1 as "future considerations," and they belong there, not in an MVP.

---

## 3. User & Use Case (singular, specific)

**User:** A student/researcher writing a paper or thesis who needs to find real, citable sources for a specific claim, and avoid accidentally citing a non-authoritative source.

**Primary use case:** "I want to claim X in my thesis — find me real sources that support, refute, or relate to X, tell me how credible each one is, and give me the citation."

This is deliberately narrower than v1's four user types (researchers, journalists, content creators, general public) — building for one user type well beats building for four shallowly.

---

## 4. Core Functionality (MVP)

1. **Input:** a claim or topic, in plain text (e.g., "regime-switching improves risk-adjusted returns during market crashes")
2. **Query expansion:** one LLM call generates 2–3 alternate phrasings/keyword variants to widen search coverage
3. **Multi-source retrieval:** parallel calls to Semantic Scholar, OpenAlex, and Crossref APIs (see Section 6 — all free, no key required for baseline use)
4. **Deduplication:** merge results across sources by matching DOI; fall back to fuzzy title match
5. **Quality tiering:** auto-tag each result (Section 5)
6. **Citation formatting:** output each result with a ready-to-paste APA citation
7. **Output:** ranked list — title, authors, year, venue, tier tag, one-line abstract/TLDR, formatted citation, direct link

That's the whole MVP. No UI polish, no accounts, no veracity engine.

---

## 5. Source Quality Tiering (the actual differentiator)

| Tier | Criteria | Display |
|---|---|---|
| **1 — Primary/Peer-reviewed** | Has Crossref-registered DOI in a recognized journal, OR is a .gov/regulatory body publication (Fed, SEC, RBI, SEBI, BIS) | ✅ green |
| **2 — Preprint/Working paper** | arXiv ID present, no journal DOI yet | ⚠️ amber — "not peer-reviewed" |
| **3 — Not citable as evidence** | No DOI, no arXiv ID, not a regulatory source (e.g., blog, student compilation, forum post) | 🚫 red — excluded from default results, shown only if user explicitly asks for background reading |

This logic exists because an API returning a result is not the same as that result being a valid academic source — OpenAlex's own documentation states it aggregates metadata but does not vouch for the content quality of indexed works. Tiering is the feature, not retrieval — retrieval is solved by existing free APIs; deciding what's actually citable is the gap this tool fills.

---

## 6. Technical Architecture

```
Query → Query Expansion (LLM) → Parallel API calls → Dedup → Tier scoring → Citation format → Output
```

| Layer | Tool | Notes |
|---|---|---|
| Query expansion | Claude/GPT API, single call | Keep cheap — one short call, not a multi-step agent |
| Retrieval | Semantic Scholar API, OpenAlex API, Crossref API | All free, documented, no key required for baseline rate limits |
| Regulatory sources | Direct fetch from federalreserve.gov, sec.gov, rbi.org.in, sebi.gov.in as needed | Not in academic APIs — must be fetched separately when query is finance/regulatory |
| Dedup | Match on DOI; `rapidfuzz` for fallback title matching | |
| Citation formatting | `pybtex` or hand-rolled APA template | |
| Storage | SQLite or flat JSON | No need for anything heavier at this scale |
| Interface | CLI script or simple local web form | Skip building a polished UI until the retrieval+tiering logic is proven useful |

No vector database, no knowledge graph, no web crawler infrastructure needed for this scope — those were appropriate for v1's larger vision, not for this tool.

---

## 7. Success Metrics (cut down to what's actually checkable by one person)

| Metric | Target |
|---|---|
| % of Tier 1/2 results with a valid, resolvable DOI/arXiv link | 100% (non-negotiable — a broken link defeats the purpose) |
| Time to return results for one query | Under ~5 seconds (3 parallel API calls + 1 LLM call) |
| Manual correction rate | Spot-check 10 queries against doing it by hand; tool should reduce manual lookup time meaningfully |

Dropped from v1: "user satisfaction surveys," "coverage breadth" — not measurable for a single-user tool at this stage.

---

## 8. Build Order (so this is actually achievable)

1. Get the three API calls working standalone (you already have working code for this — see prior tech stack doc, Section 6)
2. Add DOI-based deduplication
3. Add tier-scoring logic (rule-based, not ML — just check for DOI/arXiv ID/domain)
4. Add citation formatting
5. Wrap in a CLI or simple script you run per-query
6. (Optional, later) simple web form if CLI becomes annoying

Steps 1–5 are a few hours of work each, not a multi-month build — this is intentionally sized to fit alongside your thesis and CAT prep, not compete with them.

---

## 9. Future Considerations (deferred, not deleted)

Everything cut in Section 2.1, plus: SSRN integration (no public API — would need manual/scraping approach), PubMed for any health-adjacent claims, API access for others to use this tool, regulatory-source auto-detection (currently manual trigger).
