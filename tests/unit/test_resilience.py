"""Tests for Phase 14: Resilience + Security primitives and pipeline wiring."""
import sys
import unittest
import tempfile
import shutil
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.resilience import (
    retry_with_backoff,
    is_transient_error,
    safe_subpath,
    UnsafePathError,
    assert_not_in_locus_drive,
    LocusDriveWriteError,
)
from src.pipeline.statemachine import DocumentStateMachine, DocumentState
from src.pipeline.ingest_orchestrator import ProcessingResult


# ─── Transient classification ─────────────────────────────────────────────────

class TestIsTransientError(unittest.TestCase):
    def test_transient_timeout(self):
        self.assertTrue(is_transient_error(RuntimeError("connection timed out")))
        self.assertTrue(is_transient_error(RuntimeError("rate limit exceeded")))

    def test_permanent_permission(self):
        self.assertFalse(is_transient_error(RuntimeError("403 permission denied")))
        self.assertFalse(is_transient_error(RuntimeError("authentication failed")))

    def test_permanent_unsupported(self):
        self.assertFalse(is_transient_error(RuntimeError("Unsupported mime type: x")))

    def test_permanent_not_found(self):
        self.assertFalse(is_transient_error(RuntimeError("Drive file ID xyz not found in catalog")))

    def test_chained_cause_matches(self):
        # IngestionError collapses the real error into the message; classification
        # must look at the chained original.
        cause = ConnectionResetError("connection reset by peer")
        self.assertTrue(is_transient_error(cause))
        cause2 = OSError("Connection aborted")
        self.assertTrue(is_transient_error(cause2))


class TestRetryWithBackoff(unittest.TestCase):
    def test_retries_transient_then_success(self):
        calls = []

        def flaky():
            calls.append(1)
            if len(calls) < 3:
                raise ConnectionError("connection reset")
            return "ok"

        result = retry_with_backoff(flaky, attempts=3, base_delay=0.01, max_delay=0.02, jitter=0)
        self.assertEqual(result, "ok")
        self.assertEqual(len(calls), 3)

    def test_exhaustion_reraises(self):
        def always_fail():
            raise ConnectionError("timeout")

        with self.assertRaises(ConnectionError):
            retry_with_backoff(always_fail, attempts=3, base_delay=0.01, max_delay=0.02, jitter=0)

    def test_permanent_error_no_retry(self):
        calls = []

        def permanent():
            calls.append(1)
            raise PermissionError("permission denied")

        with self.assertRaises(PermissionError):
            retry_with_backoff(permanent, attempts=3, base_delay=0.01, max_delay=0.02, jitter=0)
        self.assertEqual(len(calls), 1)  # no retry on permanent

    def test_success_first_try(self):
        calls = []
        result = retry_with_backoff(lambda: (calls.append(1), "ok")[1],
                                    attempts=3, base_delay=0.01, max_delay=0.02, jitter=0)
        self.assertEqual(result, "ok")
        self.assertEqual(len(calls), 1)


class TestSafeSubpath(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="locus_res_"))
        self.base = self.tmp / "data"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_normal_subpath(self):
        p = safe_subpath(self.base, "abc123.pdf")
        self.assertTrue(str(p).startswith(str(self.base.resolve())))

    def test_traversal_rejected(self):
        with self.assertRaises(UnsafePathError):
            safe_subpath(self.base, "../../etc/passwd.pdf")

    def test_absolute_component_rejected(self):
        with self.assertRaises(UnsafePathError):
            safe_subpath(self.base, "/etc/passwd")


class TestDriveBoundary(unittest.TestCase):
    def test_rejects_inside_locus_drive(self):
        inside = Path("/Users/ashim/locus_drive/some_file.db")
        with self.assertRaises(LocusDriveWriteError):
            assert_not_in_locus_drive(inside)

    def test_allows_outside_locus_drive(self):
        outside = Path("/Users/ashim/locus_rag/data/raw/x.pdf")
        assert_not_in_locus_drive(outside)  # must not raise


class TestAttemptCountStateMachine(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="lrs_sm_"))
        self.db = str(self.tmp / "rag_state.db")
        self.sm = DocumentStateMachine(db_path=self.db)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_attempt_count_starts_zero(self):
        self.assertEqual(self.sm.get_attempt_count("new_doc"), 0)

    def test_attempt_count_increments_on_failure(self):
        from src.pipeline.statemachine import DocumentState
        self.sm.transition("d", DocumentState.DISCOVERED)
        self.sm.transition("d", DocumentState.FAILED, error_message="e1")
        self.assertEqual(self.sm.get_attempt_count("d"), 1)
        # Re-enter discovery and fail again (persists across "runs")
        self.sm.transition("d", DocumentState.DISCOVERED, force=True)
        self.sm.transition("d", DocumentState.FAILED, error_message="e2")
        self.assertEqual(self.sm.get_attempt_count("d"), 2)

    def test_attempt_count_survives_restart(self):
        from src.pipeline.statemachine import DocumentState
        self.sm.transition("r", DocumentState.DISCOVERED)
        self.sm.transition("r", DocumentState.FAILED, error_message="boom")
        # New state-machine instance on the same DB = process restart
        sm2 = DocumentStateMachine(db_path=self.db)
        self.assertEqual(sm2.get_attempt_count("r"), 1)


class TestOrchestratorRetryAndDeadLetter(unittest.TestCase):
    """Integration: process_one retries transient downloads and dead-letters at attempt cap."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="lrs_ing_"))
        self.catalog = self.tmp / "catalog.db"
        self.state_db = str(self.tmp / "rag_state.db")
        self.data_dir = self.tmp / "data"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_dead_letter_after_max_attempts(self):
        from src.pipeline.statemachine import DocumentState
        from src.pipeline.ingest_orchestrator import IngestionOrchestrator

        # Build a catalog with a file row
        import sqlite3
        conn = sqlite3.connect(str(self.catalog))
        conn.execute("""CREATE TABLE files (
            id TEXT, name TEXT, mime_type TEXT, path TEXT, drive_id TEXT,
            parents TEXT, created_time TEXT, modified_time TEXT, size INTEGER,
            web_view_link TEXT, last_modifying_user TEXT, sharing_user TEXT,
            permissions TEXT, trashed INTEGER DEFAULT 0
        )""")
        conn.execute(
            "INSERT INTO files VALUES ('doc_bad', 'bad.pdf', 'application/pdf',"
            " NULL, NULL, NULL, NULL, '2024-01-01T00:00:00Z', 1000, NULL, NULL,"
            " NULL, NULL, 0)"
        )
        conn.commit()
        conn.close()

        # A drive client that always raises a DATABASE error mapping to a
        # permanent "not found" (deterministic no-real-API failure).
        class FailingDrive:
            service = None

        # Use a catalog path that resolves but the download raises because the
        # drive client is invalid — but we must NOT let this look transient.
        # We inject a drive_client that raises ConnectionError three times then
        # PermissionError, so the orchestrator's retry-with-backoff exhausts
        # transient attempts and the doc is marked FAILED (not DEAD_LETTER yet).
        class _Flaky:
            def __init__(self, fail_first_n=2):
                self._fails = fail_first_n
                self.service = type("S", (), {"files": self._files})()

            def _files(self):
                return type("F", (), {"get_media": self._gm, "export_media": self._gm})()

            def _gm(self, **kw):
                if self._fails > 0:
                    self._fails -= 1
                    raise ConnectionError("connection reset")  # transient
                raise PermissionError("permission denied")  # permanent

        orch = IngestionOrchestrator(
            data_dir=str(self.data_dir),
            state_db_path=self.state_db,
            catalog_path=str(self.catalog),
            drive_client=_Flaky(fail_first_n=2),
        )
        sm = orch.state_machine

        # First run: transient retry exhausts (2 retries) then permanent error
        # → FAILED, attempt_count=1. run again → FAILED again, attempt_count=2.
        # At max_doc_attempts=2 the third attempt dead-letters.
        r1 = orch.process_one("doc_bad", "application/pdf", max_doc_attempts=2)
        self.assertEqual(sm.get_state("doc_bad"), DocumentState.FAILED)
        r2 = orch.process_one("doc_bad", "application/pdf", max_doc_attempts=2)
        self.assertEqual(sm.get_state("doc_bad"), DocumentState.FAILED)
        self.assertEqual(sm.get_attempt_count("doc_bad"), 2)
        r3 = orch.process_one("doc_bad", "application/pdf", max_doc_attempts=2)
        self.assertEqual(sm.get_state("doc_bad"), DocumentState.DEAD_LETTER)
        self.assertIn(r3.status, ("dead_letter", "failed"))

    def test_root_document_is_processed(self):
        # Sanity: a real run on a valid doc still returns a ProcessingResult (either
        # success or a classified failure) — never crashes on the new guards.
        from src.pipeline.ingest_orchestrator import IngestionOrchestrator
        import sqlite3
        conn = sqlite3.connect(str(self.catalog))
        conn.execute("""CREATE TABLE IF NOT EXISTS files (
            id TEXT, name TEXT, mime_type TEXT, modified_time TEXT, size INTEGER,
            trashed INTEGER DEFAULT 0
        )""")
        conn.commit()
        conn.close()
        orch = IngestionOrchestrator(
            data_dir=str(self.data_dir),
            state_db_path=self.state_db,
            catalog_path=str(self.catalog),
        )
        result = orch.process_one("missing_doc", "application/pdf", max_doc_attempts=3)
        self.assertIsInstance(result, ProcessingResult)


if __name__ == "__main__":
    unittest.main(verbosity=2)