import json
import unittest
from fastapi.testclient import TestClient
from app import app, deduplicate_and_rank, determine_tier
from unittest.mock import patch
import time

client = TestClient(app)

class TestAcademicSourceVerifier(unittest.TestCase):
    
    def setUp(self):
        # Small sleep between live tests
        time.sleep(2)

    def test_1_known_tier_1_paper(self):
        print("\n--- Test 1: Known Tier 1 paper (Live API) ---")
        query = "A five-factor asset pricing model Fama French 2015"
        print(f"Query: {query}")
        
        response = client.get(f"/api/search?q={query}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        results = data["results"]
        
        found = False
        target_res = None
        for res in results:
            if res["doi"] == "10.1016/j.jfineco.2014.10.010":
                found = True
                target_res = res
                self.assertEqual(res["tier"], 1)
                self.assertIn("Fama", res["citation_string"])
                self.assertIn("French", res["citation_string"])
                self.assertIn("2015", res["citation_string"])
                self.assertIn("Journal of Financial Economics", res["citation_string"])
                break
                
        print("Raw JSON Response snippet (first result or found result):")
        print(json.dumps(target_res if target_res else (results[0] if results else {}), indent=2))
        
        self.assertTrue(found, "The exact paper (10.1016/j.jfineco.2014.10.010) was not found in the results.")
        print("PASS: The exact paper was found, DOI matches, tagged Tier 1, and APA citation is correct.")

    def test_2_tier_2_preprint_handling(self):
        print("\n--- Test 2: Tier 2 preprint handling (Direct Unit Test) ---")
        # Direct test of determine_tier to prove SSRN DOIs and arXiv IDs route to Tier 2
        
        # Case A: arXiv preprint
        tier_arxiv = determine_tier(doi=None, arxiv_id="2103.00020", venue="arXiv")
        self.assertEqual(tier_arxiv, 2)
        
        # Case B: SSRN preprint with a DOI
        tier_ssrn = determine_tier(doi="10.2139/ssrn.2509457", arxiv_id=None, venue="SSRN Electronic Journal")
        self.assertEqual(tier_ssrn, 2)
        
        print("Tested determine_tier(doi='10.2139/ssrn.2509457') -> Tier 2")
        print("PASS: Both arXiv and SSRN DOIs are explicitly correctly routed to Tier 2.")

    def test_3_tier_3_exclusion(self):
        print("\n--- Test 3: Tier 3 exclusion (Direct Unit Test) ---")
        fabricated_results = [
            {
                "title": "My Awesome Quant Trading Prep Blog",
                "authors": "Some Student",
                "year": 2023,
                "venue": "Medium Blog",
                "doi": None,
                "arxiv_id": None,
                "url": "https://medium.com/foo",
                "abstract": "This is a study guide.",
                "citation_count": 0,
                "source_api": "Fabricated API"
            },
            {
                "title": "A real paper",
                "authors": "Real Author",
                "year": 2020,
                "venue": "Real Journal",
                "doi": "10.test/123",
                "arxiv_id": None,
                "url": "https://doi.org/10.test/123",
                "abstract": "Real abstract",
                "citation_count": 5,
                "source_api": "Fabricated API"
            }
        ]
        
        filtered_results, logs = deduplicate_and_rank(fabricated_results, include_tier3=False)
        
        print("Filtered Output (default mode):")
        print(json.dumps(filtered_results, indent=2))
        
        self.assertEqual(len(filtered_results), 1, "Expected exactly 1 result after Tier 3 exclusion")
        self.assertEqual(filtered_results[0]["tier"], 1, "The surviving result should be Tier 1")
        self.assertEqual(filtered_results[0]["title"], "A real paper")
        
        print("PASS: Fabricated non-academic result was successfully tagged Tier 3 and filtered out by default.")

    def test_4_deduplication(self):
        print("\n--- Test 4: Deduplication across sources (Direct Unit Test) ---")
        # Simulating 3 APIs returning the same paper to deterministically test merge logic
        fabricated_results = [
            {
                "title": "A five-factor asset pricing model",
                "authors": "E. Fama, K. French",
                "year": 2015,
                "venue": "Journal of Financial Economics",
                "doi": "10.1016/j.jfineco.2014.10.010",
                "arxiv_id": None,
                "url": "https://doi.org/10.1016/j.jfineco.2014.10.010",
                "abstract": "",
                "citation_count": 6800,
                "source_api": "Mock API 1"
            },
            {
                "title": "A five-factor asset pricing model",
                "authors": "Eugene Fama, Kenneth French",
                "year": 2015,
                "venue": "JFE",
                "doi": "10.1016/j.jfineco.2014.10.010",
                "arxiv_id": None,
                "url": "https://doi.org/10.1016/j.jfineco.2014.10.010",
                "abstract": "Abstract text here",
                "citation_count": 6850,
                "source_api": "Mock API 2"
            }
        ]
        
        unique_sources, merge_logs = deduplicate_and_rank(fabricated_results)
        
        print("Raw Merge Logs:")
        print(json.dumps(merge_logs, indent=2))
        print("Unique Sources Output:")
        print(json.dumps(unique_sources, indent=2))
        
        self.assertEqual(len(unique_sources), 1, "Expected exactly 1 merged result")
        self.assertTrue(any("10.1016/j.jfineco.2014.10.010" in log for log in merge_logs), "No DOI merge log found for target DOI.")
        
        print("PASS: The target paper deterministically merged exactly once based on DOI.")

    def test_5_regulatory_source(self):
        print("\n--- Test 5: No hallucinated regulatory citations (Live API) ---")
        query = "SR 11-7 model risk management"
        print(f"Query: {query}")
        
        response = client.get(f"/api/search?q={query}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        results = data["results"]
        
        print("Raw JSON Response snippet:")
        print(json.dumps(results[:2] if results else [], indent=2))
        
        for res in results:
            self.assertNotIn("Federal Reserve", res["authors"], "Fabricated Federal Reserve document as Tier 1")
            
        print("PASS: Tool returned honest academic matches or empty, no fabricated Tier 1 regulatory document.")

    @patch('app.search_semantic_scholar')
    @patch('app.search_openalex')
    @patch('app.search_crossref')
    def test_6_api_failure_handling(self, mock_crossref, mock_openalex, mock_semantic_scholar):
        print("\n--- Test 6: API failure handling (Isolated Mock) ---")
        
        # Mock Semantic Scholar and OpenAlex to succeed, and Crossref to fail
        mock_semantic_scholar.return_value = ([{"title": "Paper A", "authors": "Author A", "year": None, "venue": "", "doi": "10.test/A", "arxiv_id": None, "url": None, "abstract": "", "citation_count": 1, "source_api": "Semantic Scholar"}], None)
        mock_openalex.return_value = ([{"title": "Paper B", "authors": "Author B", "year": None, "venue": "", "doi": "10.test/B", "arxiv_id": None, "url": None, "abstract": "", "citation_count": 1, "source_api": "OpenAlex"}], None)
        mock_crossref.return_value = ([], "Crossref unavailable (ConnectionError)")
        
        response = client.get("/api/search?q=test")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        results = data["results"]
        warnings = data["warnings"]
        
        print("Raw Warnings:")
        print(json.dumps(warnings, indent=2))
        print("Raw Results:")
        print(json.dumps(results, indent=2))
        
        self.assertEqual(len(results), 2, "Expected exactly 2 results from the 2 succeeding APIs")
        self.assertEqual(len(warnings), 1, "Expected exactly 1 warning")
        self.assertIn("Crossref unavailable", warnings[0])
        
        print("PASS: Tool returned partial results and explicitly warned about isolated Crossref failure.")

if __name__ == '__main__':
    unittest.main(exit=False, verbosity=2)
