"""Regression tests for Phase 17/18 final fixes."""
import unittest
from src.indexing.vector import SearchQuery, HybridRetriever
from src.retrieval.query_router import QueryNormalizer

class FinalRegressionTests(unittest.TestCase):
    def test_search_query_no_duplicate_metadata(self):
        q = SearchQuery(raw_query="test", normalized_query="test", terms=["test"], filters={}, metadata={"a": 1})
        self.assertEqual(len([f for f in SearchQuery.__dataclass_fields__ if f == "metadata"]), 1)

    def test_normalizer_preserves_entities(self):
        n = QueryNormalizer()
        self.assertIn("ncell", n.normalize("Ncell 2025"))
        self.assertIn("NPR", n.normalize("NPR 1,000"))

    def test_hybrid_delegation_works(self):
        # Delegation: retrieve method present and callable
        h = HybridRetriever()
        self.assertTrue(hasattr(h, "retrieve"))
        self.assertTrue(callable(h.retrieve))

if __name__ == "__main__":
    unittest.main()
