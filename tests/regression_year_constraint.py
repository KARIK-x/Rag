"""Regression: year-constraint prevents cross-year contamination."""
import sys, unittest
sys.path.insert(0,'.')
from src.indexing.vector import RetrievalCandidate
from src.evidence.assembler import EvidenceAssembler

class RegressionYearConstraint(unittest.TestCase):
    def test_2027_missing_abstains(self):
        c = RetrievalCandidate(chunk_id="c", doc_id="d", score=0.9,
            text="Ncell sponsored LOCUS 2024 event.",
            source_locator={"filename":"2024.pdf","drive_file_id":"id"},
            index_name="bm25", metadata={"authority_status":"confirmed"})
        ev = EvidenceAssembler().assemble("2027 sponsors list", [c])
        self.assertFalse(ev.is_sufficient)
        self.assertIn("requested_year_2027_not_found_in_evidence", ev.missing_aspects)

    def test_2024_present_sufficient(self):
        c = RetrievalCandidate(chunk_id="c", doc_id="d", score=0.9,
            text="Ncell sponsored LOCUS 2024 event.",
            source_locator={"filename":"2024.pdf","drive_file_id":"id"},
            index_name="bm25", metadata={"authority_status":"confirmed"})
        ev = EvidenceAssembler().assemble("2024 sponsors", [c])
        self.assertTrue(ev.is_sufficient)
        self.assertEqual(ev.missing_aspects, [])

    def test_2025_evidence_answers_2025(self):
        c = RetrievalCandidate(chunk_id="c", doc_id="d", score=0.9,
            text="LOCUS president 2025 confirmed.",
            source_locator={"filename":"2025.pdf","drive_file_id":"id"},
            index_name="bm25", metadata={"authority_status":"confirmed"})
        ev = EvidenceAssembler().assemble("president 2025", [c])
        self.assertTrue(ev.is_sufficient)
