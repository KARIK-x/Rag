"""
Unit tests for ingestion, extraction, integrity audit, and state machine.
"""

import sys
import unittest
import tempfile
import shutil
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.ingestion.client import IngestionClient, IngestedFile
from src.extraction.router import (
    ExtractionPipeline,
    ExtractionResult,
    ExtractionQuality,
    ExtractedPage,
    TextBlock,
)
from src.integrity.audit import IntegrityAuditor, AuditStatus
from src.pipeline.statemachine import DocumentStateMachine, DocumentState


class TestIngestionClient(unittest.TestCase):
    """Test ingestion client helpers and catalog queries."""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="locus_ingest_"))
        self.client = IngestionClient(
            catalog_path="/Users/ashim/locus_drive/locus_drive.db",
            data_dir=str(self.tmp_dir),
        )

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_is_supported(self):
        self.assertTrue(self.client.is_supported("application/pdf"))
        self.assertTrue(self.client.is_supported("text/plain"))
        self.assertTrue(self.client.is_supported("application/vnd.google-apps.document"))
        self.assertFalse(self.client.is_supported("image/jpeg"))
        self.assertFalse(self.client.is_supported("application/x-executable"))

    def test_is_workspace_native(self):
        self.assertTrue(self.client.is_workspace_native("application/vnd.google-apps.document"))
        self.assertTrue(self.client.is_workspace_native("application/vnd.google-apps.spreadsheet"))
        # PDF is supported, but NOT workspace native
        self.assertTrue(self.client.is_supported("application/pdf"))
        self.assertFalse(self.client.is_workspace_native("application/pdf"))

    def test_query_catalog(self):
        rows = self.client.query_catalog(max_files=5)
        self.assertIsInstance(rows, list)
        self.assertLessEqual(len(rows), 5)
        if rows:
            r = rows[0]
            self.assertIn("drive_file_id", r)
            self.assertIn("filename", r)
            self.assertIn("mime_type", r)


class TestExtractionPipeline(unittest.TestCase):
    """Test text and CSV extractors."""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="locus_extract_"))
        self.pipeline = ExtractionPipeline()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_extract_text(self):
        # Create a sufficiently long document (>500 chars, >10 blocks) for HIGH quality
        paragraphs = [f"Paragraph {i}: This is a detailed technical report about LOCUS institutional knowledge retrieval systems, architecture, and engineering." for i in range(15)]
        long_text = "\n\n".join(paragraphs)

        txt_path = self.tmp_dir / "test.txt"
        txt_path.write_text(long_text)

        meta = {
            "doc_id": "doc_txt_1",
            "mime_type": "text/plain",
            "provenance": {"drive_file_id": "d1"},
            "doc_metadata": {"title": "Test"},
        }

        result = self.pipeline.extract(str(txt_path), meta)
        self.assertEqual(result.doc_id, "doc_txt_1")
        self.assertEqual(result.extraction_quality, ExtractionQuality.HIGH)
        self.assertGreater(len(result.full_text), 500)
        self.assertEqual(len(result.pages), 1)
        self.assertGreater(len(result.pages[0].blocks), 10)

    def test_extract_csv(self):
        csv_path = self.tmp_dir / "test.csv"
        csv_path.write_text("Name,Role,Contribution\nAlice,President,50000\nBob,Treasurer,30000")

        meta = {
            "doc_id": "doc_csv_1",
            "mime_type": "text/csv",
            "provenance": {"drive_file_id": "d2"},
            "doc_metadata": {"title": "Sponsors"},
        }

        result = self.pipeline.extract(str(csv_path), meta)
        self.assertEqual(result.doc_id, "doc_csv_1")
        self.assertEqual(len(result.tables), 1)
        table = result.tables[0]
        self.assertEqual(table.row_count, 2)
        self.assertEqual(table.col_count, 3)
        self.assertEqual(table.headers, ["Name", "Role", "Contribution"])


class TestIntegrityAuditor(unittest.TestCase):
    """Test integrity audit checks."""

    def test_auditor_passes_good_extraction(self):
        # Need >100 chars to pass the text_yield threshold check
        paragraph_text = (
            "LOCUS is the ICT Club of Summit Higher Secondary School. "
            "This institutional knowledge system archives events, sponsorship records, "
            "and technical documentation for long-term institutional memory."
        )
        page = ExtractedPage(
            page_number=1,
            blocks=[
                TextBlock(
                    block_id="b1",
                    block_type="paragraph",
                    text=paragraph_text,
                )
            ]
        )
        result = ExtractionResult(
            doc_id="doc_good",
            provenance={"drive_file_id": "d1"},
            metadata={},
            pages=[page],
            tables=[],
            full_text=paragraph_text,
            extraction_quality=ExtractionQuality.MEDIUM,
            ocr_used=False,
        )

        auditor = IntegrityAuditor()
        audit = auditor.audit_extraction(result)
        self.assertTrue(audit.passed())
        self.assertEqual(len(audit.failures()), 0)


class TestDocumentStateMachine(unittest.TestCase):
    """Test per-document state machine and transitions."""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="locus_sm_"))
        self.db_path = str(self.tmp_dir / "rag_state.db")
        self.sm = DocumentStateMachine(db_path=self.db_path)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_initial_state_none(self):
        self.assertIsNone(self.sm.get_state("doc_999"))

    def test_valid_transitions(self):
        doc_id = "doc_100"
        self.assertTrue(self.sm.transition(doc_id, DocumentState.DISCOVERED))
        self.assertEqual(self.sm.get_state(doc_id), DocumentState.DISCOVERED)

        self.assertTrue(self.sm.transition(doc_id, DocumentState.DOWNLOADING))
        self.assertEqual(self.sm.get_state(doc_id), DocumentState.DOWNLOADING)

        self.assertTrue(self.sm.transition(doc_id, DocumentState.DOWNLOADED))
        self.assertEqual(self.sm.get_state(doc_id), DocumentState.DOWNLOADED)

    def test_invalid_transition_rejected(self):
        doc_id = "doc_101"
        self.sm.transition(doc_id, DocumentState.DISCOVERED)
        # Cannot jump from DISCOVERED to INDEXED directly
        success = self.sm.transition(doc_id, DocumentState.INDEXED)
        self.assertFalse(success)
        self.assertEqual(self.sm.get_state(doc_id), DocumentState.DISCOVERED)

    def test_force_transition(self):
        doc_id = "doc_102"
        self.sm.transition(doc_id, DocumentState.DISCOVERED)
        # Force jump to INDEXED
        success = self.sm.transition(doc_id, DocumentState.INDEXED, force=True)
        self.assertTrue(success)
        self.assertEqual(self.sm.get_state(doc_id), DocumentState.INDEXED)


if __name__ == "__main__":
    unittest.main(verbosity=2)
