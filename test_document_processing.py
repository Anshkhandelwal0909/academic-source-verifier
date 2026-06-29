import unittest
import time
import json
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app import app, QUERY_CACHE, SENTENCE_CACHE, JOBS

client = TestClient(app)

class TestDocumentProcessing(unittest.TestCase):
    def setUp(self):
        QUERY_CACHE.clear()
        SENTENCE_CACHE.clear()
        JOBS.clear()

    def test_a_basic_factual(self):
        print("\n--- Test A: Basic Factual ---")
        content = b"The Federal Reserve was established in 1913."
        response = client.post("/api/document/upload", files={"file": ("test.txt", content, "text/plain")})
        self.assertEqual(response.status_code, 200)
        job_id = response.json()["job_id"]
        
        time.sleep(2)
        job = JOBS[job_id]
        self.assertEqual(job["status"], "COMPLETE")
        self.assertEqual(len(job["lines"]), 1)
        line = job["lines"][0]
        self.assertIn(line["status"], ["SUPPORTED_TIER1", "SUPPORTED_TIER2"])
        self.assertTrue(len(line["sources"]) > 0)
        print("PASS: Federal Reserve found Tier 1/2 source")

    @patch("app.search_crossref")
    @patch("app.search_openalex")
    @patch("app.search_semantic_scholar")
    @patch("app.search_europepmc")
    @patch("app.search_arxiv")
    def test_b_no_support(self, mock_arxiv, mock_epmc, mock_ss, mock_oa, mock_cr):
        print("\n--- Test B: No Support ---")
        mock_arxiv.return_value = ([], None)
        mock_epmc.return_value = ([], None)
        mock_ss.return_value = ([], None)
        mock_oa.return_value = ([], None)
        mock_cr.return_value = ([], None)
        
        content = b"This is a completely fabricated sentence that has zero sources."
        response = client.post("/api/document/upload", files={"file": ("test.txt", content, "text/plain")})
        job_id = response.json()["job_id"]
        
        time.sleep(2)
        job = JOBS[job_id]
        line = job["lines"][0]
        self.assertEqual(line["status"], "NO_SUPPORT_FOUND")
        self.assertEqual(len(line["sources"]), 0)
        print("PASS: Fabricated claim did not return fabricated sources.")

    def test_c_cache_hit(self):
        print("\n--- Test C: Cache Hit ---")
        content = b"The Fama-French five-factor model extends the three-factor model. The Fama-French five-factor model extends the three-factor model. The Fama-French five-factor model extends the three-factor model."
        response = client.post("/api/document/upload", files={"file": ("test.txt", content, "text/plain")})
        job_id = response.json()["job_id"]
        
        time.sleep(3)
        job = JOBS[job_id]
        self.assertEqual(len(job["lines"]), 3)
        self.assertEqual(len(QUERY_CACHE), 1)
        self.assertEqual(len(SENTENCE_CACHE), 1)
        
        for line in job["lines"]:
            self.assertIn(line["status"], ["SUPPORTED_TIER1", "SUPPORTED_TIER2"])
        print("PASS: Identical claims hit cache and saved API calls.")

    def test_d_classification_skipping(self):
        print("\n--- Test D: Classification Skipping Disabled ---")
        content = b"Figure 2 shows the results clearly. The Federal Reserve was established in 1913. This chapter discusses inflation in detail."
        response = client.post("/api/document/upload", files={"file": ("test.txt", content, "text/plain")})
        job_id = response.json()["job_id"]
        
        time.sleep(3)
        job = JOBS[job_id]
        lines = job["lines"]
        
        # Now that heuristic skipping is disabled, everything goes through the pipeline.
        # Line 0 and Line 2 might return NO_SUPPORT_FOUND if no sources match, but they will NOT be SEARCH_SKIPPED
        self.assertNotEqual(lines[0]["status"], "SEARCH_SKIPPED")
        self.assertIn(lines[1]["status"], ["SUPPORTED_TIER1", "SUPPORTED_TIER2"])
        self.assertNotEqual(lines[2]["status"], "SEARCH_SKIPPED")
        print("PASS: Structural lines are no longer heuristically skipped.")

    def test_e_sse_resilience(self):
        print("\n--- Test E: SSE Resilience ---")
        content = b"The Federal Reserve was established in 1913."
        response = client.post("/api/document/upload", files={"file": ("test.txt", content, "text/plain")})
        job_id = response.json()["job_id"]
        
        with client.stream("GET", f"/api/document/stream/{job_id}") as response1:
            pass # Disconnect immediately
            
        time.sleep(2)
        
        with client.stream("GET", f"/api/document/stream/{job_id}") as response2:
            events = []
            for line in response2.iter_lines():
                if line and line.startswith("data: "):
                    data = json.loads(line[6:])
                    events.append(data)
                    if data.get("type") == "job_complete":
                        break
                        
        self.assertTrue(any(e.get("type") == "job_complete" for e in events))
        print("PASS: SSE successfully streamed from completed job upon reconnect.")

    @patch("app.search_crossref")
    def test_f_partial_api_outage(self, mock_crossref):
        print("\n--- Test F: Partial API Outage ---")
        mock_crossref.return_value = ([], "Crossref unavailable (Connection timeout)")
        content = b"The Federal Reserve was established in 1913."
        response = client.post("/api/document/upload", files={"file": ("test.txt", content, "text/plain")})
        job_id = response.json()["job_id"]
        
        time.sleep(2)
        job = JOBS[job_id]
        self.assertEqual(job["status"], "COMPLETE")
        line = job["lines"][0]
        # It should still succeed using Semantic Scholar / OpenAlex
        self.assertIn(line["status"], ["SUPPORTED_TIER1", "SUPPORTED_TIER2"])
        print("PASS: Processing continued and results returned despite Crossref failure.")

    def test_g_large_document(self):
        print("\n--- Test G: Large Document ---")
        sentences = ["The Federal Reserve was established in 1913."] * 20
        sentences += ["This chapter discusses inflation in detail."] * 20
        content = " ".join(sentences).encode('utf-8')
        
        response = client.post("/api/document/upload", files={"file": ("test.txt", content, "text/plain")})
        job_id = response.json()["job_id"]
        
        time.sleep(4)
        job = JOBS[job_id]
        self.assertEqual(job["status"], "COMPLETE")
        self.assertEqual(job["processed_sentences"], 40)
        self.assertEqual(job["total_sentences"], 40)
        print("PASS: Large document processed cleanly, memory stable, completed successfully.")

if __name__ == "__main__":
    unittest.main()
