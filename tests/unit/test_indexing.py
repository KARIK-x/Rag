"""Phase 5 tests: indexing layer (exact, BM25, dense, hybrid)."""
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
    HybridRetriever,
    SearchQuery,
    RetrievalCandidate,
)


class TestExactEntityIndex(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="locus_idx_"))
        self.db = str(self.tmp / "idx.db")
        self.index = ExactEntityIndex(db_path=self.db)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_add_and_search_exact(self):
        self.index.add("c1", "NPR 50,000 sponsorship by Ncell", {"doc_id": "d1", "source_locator": {}})
        self.index.add("c2", "Budget Rs. 30,000 for marketing", {"doc_id": "d1", "source_locator": {}})

        q = SearchQuery(raw_query="Ncell 50000", normalized_query="ncell 50000", terms=["ncell", "50000"])
        res = self.index.search(q, top_k=10)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0].chunk_id, "c1")
        self.assertEqual(res[0].index_name, "exact")

    def test_search_currency(self):
        self.index.add("c1", "NPR 1 lakh donation", {"doc_id": "d1", "source_locator": {}})
        q = SearchQuery(raw_query="lakh", normalized_query="lakh", terms=["lakh"])
        res = self.index.search(q, top_k=10)
        self.assertEqual(len(res), 1)

    def test_search_drive_id(self):
        self.index.add("c1", "File 1abc2def3ghi4jkl5mno6pqr7stu8", {"doc_id": "d1", "source_locator": {}})
        q = SearchQuery(raw_query="1abc2def3ghi4jkl5mno6pqr7stu8", normalized_query="1abc2def3ghi4jkl5mno6pqr7stu8", terms=["1abc2def3ghi4jkl5mno6pqr7stu8"])
        res = self.index.search(q, top_k=10)
        self.assertEqual(len(res), 1)

    def test_persistence(self):
        self.index.add("c1", "NPR 10000", {"doc_id": "d1", "source_locator": {}})
        # Create a new instance with same DB
        new_idx = ExactEntityIndex(db_path=str(Path(self.db)))
        q = SearchQuery(raw_query="10000", normalized_query="10000", terms=["10000"])
        res = new_idx.search(q, top_k=10)
        self.assertEqual(len(res), 1)


class TestBM25Index(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="locus_bm25_"))
        self.db = str(self.tmp / "bm25.db")
        self.index = BM25Index(db_path=self.db)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_add_and_search(self):
        self.index.add("c1", "Ncell sponsorship contribution NPR 500000", {"doc_id": "d1"})
        self.index.add("c2", "CG annual report 2023 budget NPR 300000", {"doc_id": "d1"})
        self.index.add("c3", "DFT silver sponsor NPR 150000", {"doc_id": "d1"})

        q = SearchQuery(raw_query="sponsorship Ncell", normalized_query="sponsorship ncell", terms=["sponsorship", "ncell"])
        res = self.index.search(q, top_k=10)
        self.assertGreater(len(res), 0)
        self.assertEqual(res[0].chunk_id, "c1")

    def test_bm25_scores(self):
        # c1 has "Ncell" 2x, c2 has it 1x
        self.index.add("c1", "Ncell Ncell", {"doc_id": "d1"})
        self.index.add("c2", "Ncell", {"doc_id": "d1"})
        q = SearchQuery(raw_query="Ncell", normalized_query="ncell", terms=["ncell"])
        res = self.index.search(q, top_k=10)
        self.assertEqual(res[0].chunk_id, "c1")
        self.assertGreater(res[0].score, res[1].score)


class TestDenseVectorIndex(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="locus_dense_"))
        self.db = str(self.tmp / "dense.db")
        self.index = DenseVectorIndex(dim=4, db_path=self.db)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_add_and_search(self):
        self.index.add("c1", "text one", {"embedding": [1, 0, 0, 0], "doc_id": "d1"})
        self.index.add("c2", "text two", {"embedding": [0, 1, 0, 0], "doc_id": "d1"})

        q = SearchQuery(raw_query="", normalized_query="", terms=[], metadata={"query_embedding": [0.9, 0.1, 0, 0]})
        res = self.index.search(q, top_k=2)
        self.assertEqual(len(res), 2)
        self.assertEqual(res[0].chunk_id, "c1")
        self.assertGreater(res[0].score, res[1].score)

    def test_requires_embedding(self):
        with self.assertRaises(ValueError):
            self.index.add("c1", "text", {})  # no embedding


class TestHybridRetriever(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="locus_hyb_"))
        self.db = str(self.tmp / "hyb.db")
        self.exact = ExactEntityIndex(db_path=self.db)
        self.bm25 = BM25Index(db_path=self.db)
        self.dense = DenseVectorIndex(dim=4, db_path=self.db)
        self.meta = type("MetaIdx", (), {"filter": lambda self, cands, filt: cands})()
        self.retriever = HybridRetriever(
            dense=self.dense,
            bm25=self.bm25,
            exact=self.exact,
            metadata=self.meta,
        )

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_hybrid_rrf(self):
        # Add same doc to all three
        text = "Ncell sponsorship NPR 500000"
        emb = [1, 0, 0, 0]
        for idx in (self.exact, self.bm25, self.dense):
            idx.add("c1", text, {"embedding": emb, "doc_id": "d1", "source_locator": {}})

        res = self.retriever.retrieve("Ncell sponsorship", top_k=10)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0].chunk_id, "c1")
        self.assertEqual(res[0].index_name, "hybrid")

    def test_dedup_across_indexes(self):
        text = "Ncell sponsorship"
        self.exact.add("c1", text, {"doc_id": "d1"})
        self.bm25.add("c1", text, {"doc_id": "d1"})
        res = self.retriever.retrieve("Ncell", top_k=10)
        # Only one candidate after dedup
        self.assertEqual(len(res), 1)


class TestMetadataIndex(unittest.TestCase):
    def test_filter_by_doc_type(self):
        idx = MetadataIndex()
        idx.add("c1", "text", {"doc_type": "sponsorship"})
        idx.add("c2", "text", {"doc_type": "report"})

        candidates = [
            RetrievalCandidate("c1", "d1", 0.9, "t", {}, "exact"),
            RetrievalCandidate("c2", "d1", 0.8, "t", {}, "exact"),
        ]
        filtered = idx.filter(candidates, {"doc_type": "sponsorship"})
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].chunk_id, "c1")


if __name__ == "__main__":
    unittest.main(verbosity=2)