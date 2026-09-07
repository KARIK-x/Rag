"""Phase 6 tests: hybrid retrieval + RRF fusion."""
import sys
import unittest
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.indexing.vector import (
    ExactEntityIndex,
    BM25Index,
    DenseVectorIndex,
    MetadataIndex,
    RetrievalCandidate,
    SearchQuery,
)
from src.retrieval.hybrid import HybridRetriever, rrf_fusion, retrieve


class TestRRFFusion(unittest.TestCase):
    def test_rrf_merges_two_lists(self):
        list1 = [
            RetrievalCandidate("c1", "d1", 0.9, "text1", {}, "dense"),
            RetrievalCandidate("c2", "d1", 0.8, "text2", {}, "dense"),
        ]
        list2 = [
            RetrievalCandidate("c2", "d1", 0.85, "text2", {}, "bm25"),
            RetrievalCandidate("c3", "d1", 0.7, "text3", {}, "bm25"),
        ]
        fused = rrf_fusion([list1, list2])
        # c2 appears in both lists, should be ranked high
        self.assertEqual(len(fused), 3)
        self.assertEqual(fused[0].chunk_id, "c2")

    def test_rrf_preserves_all_unique(self):
        list1 = [RetrievalCandidate("c1", "d1", 0.9, "t", {}, "dense")]
        list2 = [RetrievalCandidate("c2", "d1", 0.9, "t", {}, "bm25")]
        list3 = [RetrievalCandidate("c3", "d1", 0.9, "t", {}, "exact")]
        fused = rrf_fusion([list1, list2, list3])
        self.assertEqual(len(fused), 3)

    def test_rrf_empty(self):
        self.assertEqual(rrf_fusion([]), [])


class TestHybridRetriever(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="locus_hyb_"))
        self.db = str(self.tmp / "idx.db")
        self.exact = ExactEntityIndex(db_path=self.db)
        self.bm25 = BM25Index(db_path=self.db)
        self.metadata = MetadataIndex()
        self.retriever = HybridRetriever(
            bm25=self.bm25,
            exact=self.exact,
            metadata=self.metadata,
        )

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_retrieve_sponsorship_query(self):
        self.bm25.add("c1", "Ncell sponsorship NPR 500000", {"doc_id": "d1"})
        self.bm25.add("c2", "CG annual report budget", {"doc_id": "d1"})

        self.exact.add("c1", "Ncell NPR 500000", {"doc_id": "d1"})
        self.exact.add("c2", "CG annual report", {"doc_id": "d1"})

        results = self.retriever.retrieve("Ncell sponsorship", top_k=5)
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0].chunk_id, "c1")

    def test_retrieve_filters_by_metadata(self):
        # Add chunk with metadata
        self.bm25.add("c1", "Ncell sponsorship", {"doc_id": "d1", "doc_type": "sponsorship"})
        self.bm25.add("c2", "Ncell report", {"doc_id": "d1", "doc_type": "report"})

        # Add metadata
        self.metadata.chunk_meta["c1"] = {"doc_id": "d1", "doc_type": "sponsorship"}
        self.metadata.chunk_meta["c2"] = {"doc_id": "d1", "doc_type": "report"}

        results = self.retriever.retrieve("Ncell", top_k=5, filters={"doc_type": "sponsorship"})
        # c1 should match (sponsorship), c2 should be filtered out
        chunk_ids = [r.chunk_id for r in results]
        self.assertIn("c1", chunk_ids)
        self.assertNotIn("c2", chunk_ids)

    def test_retrieve_provenance_preserved(self):
        self.bm25.add("c1", "NPR 500000 sponsorship", {"doc_id": "d1", "source_locator": {"page": 5}})
        results = self.retriever.retrieve("sponsorship", top_k=5)
        self.assertGreater(len(results), 0)
        # Provenance should be in metadata
        self.assertIsNotNone(results[0].source_locator)

    def test_exact_match_protected(self):
        # Source has "NPR 50,000"
        # Query has "50000"
        self.exact.add("c1", "NPR 50,000 by Ncell", {"doc_id": "d1"})
        self.exact.add("c2", "Ncell was founded 1990", {"doc_id": "d1"})

        results = self.retriever.retrieve("50000", top_k=5)
        # Should match c1 via exact index (currency prefix + comma stripped)
        chunk_ids = [r.chunk_id for r in results]
        self.assertIn("c1", chunk_ids)


if __name__ == "__main__":
    unittest.main(verbosity=2)