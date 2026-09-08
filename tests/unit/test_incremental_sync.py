"""Tests for Phase 12: Incremental Sync Engine."""
import sys
import unittest
import tempfile
import shutil
import sqlite3
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.sync.incremental_sync import IncrementalSyncEngine, ChangedDoc


class TestIncrementalSync(unittest.TestCase):
    """Tests for the incremental sync engine."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="locus_sync_"))
        self.catalog_path = str(self.tmp / "test_catalog.db")
        self.rag_state_db = str(self.tmp / "rag_state.db")
        self.data_dir = str(self.tmp / "data")

        # Create a test catalog
        self._create_catalog()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _create_catalog(self):
        """Create a test catalog with files and sync_state matching real schema."""
        conn = sqlite3.connect(self.catalog_path)
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE files (
                id TEXT PRIMARY KEY,
                name TEXT,
                mime_type TEXT,
                path TEXT,
                drive_id TEXT,
                parents TEXT,
                created_time TEXT,
                modified_time TEXT,
                viewed_by_me TEXT,
                size INTEGER,
                quota_bytes INTEGER,
                web_view_link TEXT,
                web_content_link TEXT,
                owned_by_me INTEGER,
                trashed INTEGER DEFAULT 0,
                last_modifying_user TEXT,
                sharing_user TEXT,
                permissions TEXT,
                raw_metadata TEXT,
                synced_at TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE sync_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                account_email TEXT,
                last_init_sync_at TEXT,
                last_inc_sync_at TEXT,
                init_sync_complete INTEGER,
                init_in_progress INTEGER,
                total_files_seen INTEGER
            )
        """)

        # Insert initial sync state with baseline BEFORE file modified times
        cur.execute(
            "INSERT INTO sync_state (id, last_inc_sync_at) VALUES (1, ?)",
            ("2024-01-01T00:00:00Z",),  # Baseline: all files modified after this
        )

        # Insert files with modified_time AFTER baseline (simulating changes for tests that expect them)
        # These match the real locus_drive.db schema: no revision_id, no content_hash column.
        cur.execute(
            "INSERT INTO files (id, name, mime_type, modified_time, size) VALUES (?, ?, ?, ?, ?)",
            ("file_1", "doc1.pdf", "application/pdf", "2024-01-02T00:00:00Z", 1000),
        )
        cur.execute(
            "INSERT INTO files (id, name, mime_type, modified_time, size) VALUES (?, ?, ?, ?, ?)",
            ("file_2", "doc2.pdf", "application/pdf", "2024-01-03T00:00:00Z", 2000),
        )
        cur.execute(
            "INSERT INTO files (id, name, mime_type, modified_time, size) VALUES (?, ?, ?, ?, ?)",
            ("file_3", "doc3.pdf", "application/pdf", "2024-01-04T00:00:00Z", 3000),
        )

        # No fictional documents table — the engine creates/checks its own sync checkpoints
        # in the rag_state DB via the sync_state system, not a separate documents table.

        conn.commit()
        conn.close()

    def test_get_changed_docs_returns_all(self):
        """get_changed_docs() returns all docs modified since last sync."""
        engine = IncrementalSyncEngine(
            catalog_path=self.catalog_path,
            rag_state_db=self.rag_state_db,
            data_dir=self.data_dir,
        )
        changed = engine.get_changed_docs()
        # All 3 files are modified after the baseline
        self.assertEqual(len(changed), 3)
        self.assertTrue(all(isinstance(c, ChangedDoc) for c in changed))

    def test_get_changed_docs_with_since(self):
        """get_changed_docs(since=timestamp) returns only newer files."""
        engine = IncrementalSyncEngine(
            catalog_path=self.catalog_path,
            rag_state_db=self.rag_state_db,
            data_dir=self.data_dir,
        )
        # Only files modified after 2024-01-02 (strictly after, not including)
        since = datetime(2024, 1, 2, 0, 0, 0, tzinfo=timezone.utc).timestamp()
        changed = engine.get_changed_docs(since=since)
        # file_1: "2024-01-02T00:00:00Z" is NOT after since → exclude
        # file_2: "2024-01-03T00:00:00Z" is after since → include
        # file_3: "2024-01-05T00:00:00Z" is after since → include
        self.assertEqual(len(changed), 2)

    def test_detect_significant_changes(self):
        """detect_significant_changes() flags only docs with new content."""
        engine = IncrementalSyncEngine(
            catalog_path=self.catalog_path,
            rag_state_db=self.rag_state_db,
            data_dir=self.data_dir,
        )
        changed = engine.get_changed_docs()
        significant = engine.detect_significant_changes(changed)
        # file_1 has old_hash_1, so it should be flagged if content changed
        # file_2 and file_3 are new, so they should be flagged
        self.assertEqual(len(significant), 3)
        self.assertTrue(all(c.needs_reprocess for c in significant))

    def test_run_incremental_sync_no_changes(self):
        """run_incremental_sync() returns 'nothing_changed' when no files changed."""
        engine = IncrementalSyncEngine(
            catalog_path=self.catalog_path,
            rag_state_db=self.rag_state_db,
            data_dir=self.data_dir,
        )
        # Update the catalog to have no files modified after the baseline
        conn = sqlite3.connect(self.catalog_path)
        cur = conn.cursor()
        cur.execute("UPDATE files SET modified_time = '2024-01-01T00:00:00Z'")
        conn.commit()
        conn.close()

        result = engine.run_incremental_sync()
        self.assertEqual(result["status"], "nothing_changed")

    def test_run_incremental_sync_with_changes(self):
        """run_incremental_sync() processes changed files and reports errors."""
        engine = IncrementalSyncEngine(
            catalog_path=self.catalog_path,
            rag_state_db=self.rag_state_db,
            data_dir=self.data_dir,
        )
        # Update sync state to have no baseline
        conn = sqlite3.connect(self.catalog_path)
        cur = conn.cursor()
        cur.execute("UPDATE sync_state SET last_inc_sync_at = NULL")
        conn.commit()
        conn.close()

        # Run sync — should process all 3 files
        # In the test environment, Drive download will fail (not real files),
        # so status should be 'completed_with_errors' and baseline not advanced.
        result = engine.run_incremental_sync()
        self.assertEqual(result["status"], "completed_with_errors")
        self.assertEqual(result["total_changed"], 3)
        self.assertEqual(result["failed"], 3)

    def test_get_changed_docs_excludes_trashed_files(self):
        """get_changed_docs() must not return trashed/deleted files."""
        engine = IncrementalSyncEngine(
            catalog_path=self.catalog_path,
            rag_state_db=self.rag_state_db,
            data_dir=self.data_dir,
        )
        # Mark file_2 as trashed (it was modified after baseline)
        conn = sqlite3.connect(self.catalog_path)
        cur = conn.cursor()
        cur.execute("UPDATE files SET trashed = 1 WHERE id = 'file_2'")
        conn.commit()
        conn.close()

        changed = engine.get_changed_docs()
        ids = {c.drive_file_id for c in changed}
        # Trashed file must never flow downstream
        self.assertNotIn("file_2", ids)
        self.assertEqual(len(changed), 2)

    def test_detect_significant_changes_unchanged_files_skipped(self):
        """Files whose (modified_time, size) match their checkpoint are skipped."""
        engine = IncrementalSyncEngine(
            catalog_path=self.catalog_path,
            rag_state_db=self.rag_state_db,
            data_dir=self.data_dir,
        )
        # Pre-seed a checkpoint for file_1 matching its current catalog state
        engine._update_sync_checkpoint("file_1", "2024-01-02T00:00:00Z", 1000)

        changed = engine.get_changed_docs()
        significant = engine.detect_significant_changes(changed)
        # file_1 is unchanged since its checkpoint → must NOT be flagged
        self.assertEqual(len(significant), 2)
        self.assertFalse(any(c.drive_file_id == "file_1" for c in significant))

    def test_failed_files_do_not_advance_baseline(self):
        """A failed file must remain retryable: baseline is not advanced on error."""
        engine = IncrementalSyncEngine(
            catalog_path=self.catalog_path,
            rag_state_db=self.rag_state_db,
            data_dir=self.data_dir,
        )
        # No baseline → all 3 files are detected as changed
        conn = sqlite3.connect(self.catalog_path)
        cur = conn.cursor()
        cur.execute("UPDATE sync_state SET last_inc_sync_at = NULL")
        conn.commit()
        conn.close()

        # First run: all 3 fail (no real Drive files). Baseline must stay None
        # so the files are re-detected next cycle.
        result = engine.run_incremental_sync()
        self.assertEqual(result["status"], "completed_with_errors")
        self.assertEqual(result["failed"], 3)
        self.assertIsNone(engine._read_last_run_at())

        # Second run: the same 3 files must still be detected (not dropped)
        changed = engine.get_changed_docs()
        self.assertEqual(len(changed), 3)

    def test_changed_doc_dataclass(self):
        """ChangedDoc dataclass has expected fields."""
        doc = ChangedDoc(
            drive_file_id="abc",
            filename="test.pdf",
            mime_type="application/pdf",
            modified_time="2024-01-01T00:00:00Z",
            synced_at=None,
            size_bytes=1000,
            processing_state="unknown",
            needs_reprocess=True,
        )
        self.assertEqual(doc.drive_file_id, "abc")
        self.assertEqual(doc.filename, "test.pdf")
        self.assertTrue(doc.needs_reprocess)


if __name__ == "__main__":
    unittest.main(verbosity=2)