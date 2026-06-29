# Academic Source Verifier

An intelligent academic citation and claim-verification engine. This tool processes raw text or PDF documents, extracts factual claims, and cross-references them against five of the world's largest academic databases in real time to provide line-by-line verification.

## Features

- **Document Parsing:** Upload `.txt` or `.pdf` files.
- **Line-by-line Verification:** NLP-powered keyword extraction identifies claims and queries academic databases.
- **Massive Global Library:** Searches concurrently across:
  - Semantic Scholar
  - OpenAlex
  - Crossref
  - Europe PMC
  - arXiv
- **Tier-based Confidence Scoring:** Sources are deduplicated and tiered (e.g. Peer-reviewed DOIs vs. Preprints) for trustworthiness.
- **Privacy First:** Anonymous API requests. No tracking, no telemetry, no API keys required.
- **Real-Time Streaming:** Built with FastAPI and Server-Sent Events (SSE) to render processing results live in the browser.

## Ideal Use Cases (Where this shines)
- **Academic Peer Review:** Quickly fact-checking claims in a submitted paper before publication.
- **Journalism & Investigative Reporting:** Verifying scientific or economic claims in long-form articles.
- **Student Research:** Finding primary sources for claims made in textbooks or lecture notes.
- **Grant Proposals:** Ensuring every factual assertion in a funding application is backed by a highly-cited paper.

## Limitations (Where this struggles)
- **Non-Academic Claims:** This tool strictly queries academic databases. It will fail to verify pop-culture claims, news events, or opinions (e.g. "The iPhone 15 was released in 2023").
- **Highly Specific/Novel Data:** If a claim relies on a brand-new dataset that hasn't been published in a journal yet, it will return `No Support Found`.
- **Complex Mathematical Proofs:** The NLP engine extracts standard text keywords; it cannot parse or verify the correctness of a mathematical equation.

## Running Locally

### Option 1: Docker (Recommended)

1. Build the image:
   ```bash
   docker build -t academic-verifier .
   ```
2. Run the container:
   ```bash
   docker run -d -p 8000:8000 academic-verifier
   ```
3. Open `http://localhost:8000` in your browser.

### Option 2: Python Environment

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Run the server:
   ```bash
   python app.py
   ```
3. Open `http://localhost:8000` in your browser.
