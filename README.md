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
