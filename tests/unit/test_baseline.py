"""
Unit tests for LOCUS RAG baseline retrieval pipeline.

Uses only stdlib (no pytest) to keep Phase 0 / Phase 1 testable
without external dependencies.
"""

import sys
import unittest
import tempfile
import shutil
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.retrieval.baseline import (
    BaselinePipeline,
    BaselineChunk,
)


class TestBaselinePipeline(unittest.TestCase):
    """Test the baseline retrieval pipeline."""

    def setUp(self):
        """Set up test pipeline with isolated temporary data directory."""
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="locus_test_"))
        self.data_dir = self.tmp_dir / "data"
        self.data_dir.mkdir()

        self.pipeline = BaselinePipeline(
            catalog_path="/Users/ashim/locus_drive/locus_drive.db",
            data_dir=str(self.data_dir),
        )

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_initialization(self):
        """Test that pipeline initializes correctly."""
        self.assertEqual(
            self.pipeline.catalog_path,
            "/Users/ashim/locus_drive/locus_drive.db",
        )
        self.assertTrue(self.pipeline.db_path.parent.exists())

    def test_normalize_text_unicode(self):
        """Test Unicode normalization produces stable, lowercase form."""
        # Note: current baseline uses NFKC + lowercase + whitespace collapse.
        # Smart-quote folding is a future enhancement tracked in a TODO below.
        text = "LOCUS Club"
        normalized = self.pipeline._normalize_text(text)
        self.assertEqual(normalized, "locus club")

        # Verify NFKC normalization is applied (combining marks decomposed)
        text_decomposed = "café"  # 'café' with combining acute
        normalized = self.pipeline._normalize_text(text_decomposed)
        # After NFKC + lowercase, é is a single character
        self.assertNotIn("́", normalized)

    def test_normalize_text_whitespace(self):
        """Test whitespace collapse."""
        text = "LOCUS    Club\n\n\n  of SS  "
        normalized = self.pipeline._normalize_text(text)
        self.assertNotIn("  ", normalized)
        self.assertIn("locus", normalized)

    def test_make_chunk_id_deterministic(self):
        """Test that same content produces same ID."""
        id1 = self.pipeline._make_chunk_id("doc1", "Hello world")
        id2 = self.pipeline._make_chunk_id("doc1", "Hello world")
        id3 = self.pipeline._make_chunk_id("doc1", "Different text")

        self.assertEqual(id1, id2)
        self.assertNotEqual(id1, id3)
        self.assertEqual(len(id1), 16)

    def test_simple_chunk_text_creates_chunks(self):
        """Test that chunking produces non-empty chunks."""
        text = """
LOCUS Club

This is the ICT Club of SS.

Mission

Our mission is to promote technology.
        """
        chunks = self.pipeline.simple_chunk_text(
            text=text,
            doc_id="test_doc",
            drive_file_id="drive_123",
            max_chunk_size=100,
        )

        self.assertGreater(len(chunks), 0)
        for chunk in chunks:
            self.assertIsInstance(chunk, BaselineChunk)
            self.assertEqual(chunk.doc_id, "test_doc")
            self.assertTrue(len(chunk.raw_text) > 0)

    def test_chunk_preserves_text(self):
        """Test that chunks contain the original text content."""
        text = "LOCUS is the ICT Club of SS."
        chunks = self.pipeline.simple_chunk_text(
            text=text,
            doc_id="doc_a",
            drive_file_id="drive_xyz",
            max_chunk_size=500,
        )

        combined = " ".join(c.raw_text for c in chunks)
        self.assertIn("LOCUS", combined)

    def test_get_catalog_stats(self):
        """Test reading from existing Drive catalog."""
        stats = self.pipeline.get_catalog_stats()

        self.assertIn("total_files", stats)
        self.assertIn("mime_types", stats)
        self.assertGreater(stats["total_files"], 0)
        self.assertIsInstance(stats["mime_types"], dict)

    def test_discover_documents(self):
        """Test document discovery from catalog."""
        docs = self.pipeline.discover_documents()

        self.assertIsInstance(docs, list)
        self.assertGreater(len(docs), 0)

    def test_discover_specific_types(self):
        """Test discovering only PDFs."""
        docs = self.pipeline.discover_documents(
            doc_types=["application/pdf"]
        )

        for doc in docs:
            self.assertEqual(doc["mime_type"], "application/pdf")

    def test_store_chunks(self):
        """Test chunk storage."""
        chunks = [
            BaselineChunk(
                chunk_id="t1",
                doc_id="doc1",
                raw_text="LOCUS is the ICT Club of SS.",
                normalized_text="locus is the ict club of ss.",
                heading_path="[]",
                page_start=1,
                drive_file_id="drive_123",
                source_locator='{"drive_file_id": "drive_123"}',
            ),
            BaselineChunk(
                chunk_id="t2",
                doc_id="doc1",
                raw_text="We organize tech events.",
                normalized_text="we organize tech events.",
                heading_path="[]",
                page_start=1,
                drive_file_id="drive_123",
                source_locator='{"drive_file_id": "drive_123"}',
            ),
        ]
        count = self.pipeline.store_chunks(chunks)
        self.assertEqual(count, 2)

    def test_search_returns_results(self):
        """Test that search returns matching chunks."""
        chunks = [
            BaselineChunk(
                chunk_id="s1",
                doc_id="doc_search",
                raw_text="LOCUS is the ICT Club of SS.",
                normalized_text="locus is the ict club of ss.",
                heading_path="[]",
                page_start=1,
                drive_file_id="drive_s",
                source_locator="{}",
            ),
        ]
        self.pipeline.store_chunks(chunks)
        results = self.pipeline.search_chunks("LOCUS", top_k=10)
        self.assertGreater(len(results), 0)

    def test_search_includes_provenance(self):
        """Test that search results carry provenance fields."""
        chunks = [
            BaselineChunk(
                chunk_id="p1",
                doc_id="doc_prov",
                raw_text="LOCUS annual report 2024.",
                normalized_text="locus annual report 2024.",
                heading_path="[]",
                page_start=5,
                drive_file_id="drive_prov",
                source_locator='{"page": 5}',
            ),
        ]
        self.pipeline.store_chunks(chunks)
        results = self.pipeline.search_chunks("LOCUS", top_k=1)
        self.assertGreater(len(results), 0)
        r = results[0]
        for field in ["chunk_id", "doc_id", "text", "drive_file_id", "score", "rank"]:
            self.assertIn(field, r)

    def test_search_ranking(self):
        """Test that results are ranked by score."""
        chunks = [
            BaselineChunk(
                chunk_id="r1",
                doc_id="doc_rank",
                raw_text="LOCUS.",
                normalized_text="locus.",
                heading_path="[]",
                page_start=1,
                drive_file_id="drive_r",
                source_locator="{}",
            ),
            BaselineChunk(
                chunk_id="r2",
                doc_id="doc_rank",
                raw_text="LOCUS LOCUS LOCUS.",
                normalized_text="locus locus locus.",
                heading_path="[]",
                page_start=1,
                drive_file_id="drive_r",
                source_locator="{}",
            ),
        ]
        self.pipeline.store_chunks(chunks)
        results = self.pipeline.search_chunks("LOCUS", top_k=10)
        self.assertEqual(len(results), 2)
        self.assertGreaterEqual(results[0]["score"], results[1]["score"])

    def test_empty_query_returns_empty(self):
        """Test that empty query returns no results."""
        results = self.pipeline.search_chunks("", top_k=10)
        self.assertEqual(results, [])

    def test_chunk_count_tracks_inserts(self):
        """Test chunk count increments after stores."""
        initial = self.pipeline.get_chunk_count()
        chunks = [
            BaselineChunk(
                chunk_id=f"c{i}",
                doc_id="d",
                raw_text=f"chunk {i}",
                normalized_text=f"chunk {i}",
                heading_path="[]",
                page_start=1,
                drive_file_id="dv",
                source_locator="{}",
            )
            for i in range(5)
        ]
        self.pipeline.store_chunks(chunks)
        self.assertEqual(self.pipeline.get_chunk_count(), initial + 5)


class TestDriveSafety(unittest.TestCase):
    """Tests to ensure Drive remains read-only."""

    def test_catalog_exists(self):
        catalog_path = Path("/Users/ashim/locus_drive/locus_drive.db")
        self.assertTrue(catalog_path.exists())
        self.assertGreater(catalog_path.stat().st_size, 0)

    def test_catalog_has_expected_tables(self):
        import sqlite3
        conn = sqlite3.connect("/Users/ashim/locus_drive/locus_drive.db")
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()
        for expected in ["files", "sync_state", "folder_queue"]:
            self.assertIn(expected, tables)

    def test_catalog_not_mutated_after_read(self):
        """Reading the catalog must not change it."""
        import sqlite3
        path = "/Users/ashim/locus_drive/locus_drive.db"
        size_before = Path(path).stat().st_size
        mtime_before = Path(path).stat().st_mtime

        conn = sqlite3.connect(path)
        conn.execute("SELECT COUNT(*) FROM files").fetchone()
        conn.close()

        size_after = Path(path).stat().st_size
        mtime_after = Path(path).stat().st_mtime
        self.assertEqual(size_before, size_after)
        self.assertEqual(mtime_before, mtime_after)


if __name__ == "__main__":
    unittest.main(verbosity=2)
