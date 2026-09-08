"""Tests for Phase 8-10: Evidence Assembly, Verification, Generation, Export."""
import sys
import unittest
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.indexing.vector import RetrievalCandidate
from src.evidence.assembler import EvidenceAssembler
from src.verification.verifier import Verifier
from src.generation.answer_builder import AnswerBuilder
from src.export.exporters import Exporter


class TestEvidenceAssembler(unittest.TestCase):
    def test_assemble_basic(self):
        assembler = EvidenceAssembler()
        candidates = [
            RetrievalCandidate(
                chunk_id="c1", doc_id="d1", score=0.9, text="Ncell sponsored event",
                source_locator={"drive_file_id": "abc", "filename": "sponsor.pdf", "page": 3},
                index_name="bm25",
                metadata={"doc_type": "sponsorship", "authority_status": "confirmed"},
            )
        ]
        evidence = assembler.assemble("Ncell", candidates)
        self.assertTrue(evidence.is_sufficient)
        self.assertEqual(len(evidence.items), 1)
        self.assertEqual(evidence.items[0].provenance.filename, "sponsor.pdf")
        self.assertEqual(evidence.items[0].provenance.drive_file_id, "abc")
        self.assertEqual(evidence.items[0].authority_score, 1.0)

    def test_assemble_insufficient(self):
        assembler = EvidenceAssembler(sufficiency_min_items=3)
        candidates = [
            RetrievalCandidate("c1", "d1", 0.9, "text", {}, "bm25"),
        ]
        evidence = assembler.assemble("q", candidates)
        self.assertFalse(evidence.is_sufficient)
        self.assertIn("insufficient_retrieval_volume", evidence.missing_aspects)

    def test_conflict_detected_draft_vs_final(self):
        assembler = EvidenceAssembler()
        candidates = [
            RetrievalCandidate("c1", "d1", 0.9, "text", {}, "bm25",
                               metadata={"authority_status": "draft"}),
            RetrievalCandidate("c2", "d2", 0.8, "text", {}, "bm25",
                               metadata={"authority_status": "confirmed"}),
        ]
        evidence = assembler.assemble("q", candidates)
        self.assertTrue(evidence.conflicts_detected)
        self.assertTrue(evidence.conflict_notes)

    def test_low_score_filtered(self):
        assembler = EvidenceAssembler(min_score_threshold=0.5)
        candidates = [
            RetrievalCandidate("c1", "d1", 0.2, "text", {}, "bm25"),
        ]
        evidence = assembler.assemble("q", candidates)
        self.assertEqual(len(evidence.items), 0)
        self.assertFalse(evidence.is_sufficient)


class TestVerifier(unittest.TestCase):
    def setUp(self):
        from src.pipeline.models import SourceProvenance
        self.evidence = None
        self.verifier = Verifier()

    def _make_evidence(self, high_score=True, n_items=3, draft=False):
        from src.pipeline.models import EvidenceItem, EvidenceSet, SourceProvenance
        items = []
        for i in range(n_items):
            prov = SourceProvenance(
                drive_file_id=f"id{i}", filename=f"doc{i}.pdf", folder_path="/",
                mime_type="application/pdf", page=1,
            )
            items.append(EvidenceItem(
                chunk_id=f"c{i}", doc_id=f"d{i}",
                score=0.9 if high_score else 0.3,
                text=f"LOCUS event held in Kathmandu sponsored by Ncell in {2024+i}.",
                provenance=prov,
                authority_score=0.6 if draft else 1.0,
            ))
        return EvidenceSet(
            query="LOCUS sponsored event",
            items=items,
            is_sufficient=True,
            missing_aspects=[],
            conflicts_detected=False,
            conflict_notes=None,
        )

    def test_high_confidence_faithful(self):
        evidence = self._make_evidence(high_score=True)
        result = self.verifier.verify("LOCUS event Ncell Kathmandu", evidence)
        self.assertTrue(result.is_faithful)
        self.assertIn(result.confidence_level, ("HIGH", "MEDIUM"))
        self.assertGreater(result.completeness_score, 0.0)

    def test_abstain_on_insufficient(self):
        from src.pipeline.models import EvidenceSet
        empty = EvidenceSet(query="q", items=[], is_sufficient=False,
                            missing_aspects=["x"], conflicts_detected=False)
        result = self.verifier.verify("Nothing here", empty)
        self.assertEqual(result.confidence_level, "ABSTAIN")
        self.assertFalse(result.is_faithful)

    def test_contradiction_lowers_confidence(self):
        from src.pipeline.models import EvidenceItem, EvidenceSet, SourceProvenance
        items = [
            EvidenceItem("c1", "d1", 0.9, "LOCUS budget is 1 million", SourceProvenance(drive_file_id="a", filename="a.pdf", folder_path="/", mime_type="pdf"), 0.6),
            EvidenceItem("c2", "d2", 0.8, "LOCUS budget is 5 million", SourceProvenance(drive_file_id="b", filename="b.pdf", folder_path="/", mime_type="pdf"), 1.0),
        ]
        evidence = EvidenceSet(
            query="LOCUS budget", items=items, is_sufficient=True,
            missing_aspects=[], conflicts_detected=True,
            conflict_notes="Draft vs final conflict",
        )
        result = self.verifier.verify("LOCUS budget is 5 million", evidence)
        self.assertTrue(result.contradictions)


class TestAnswerBuilder(unittest.TestCase):
    def setUp(self):
        self.builder = AnswerBuilder()

    def _make_evidence(self):
        from src.pipeline.models import EvidenceItem, EvidenceSet, SourceProvenance
        items = [
            EvidenceItem("c1", "d1", 0.9, "Ncell sponsored the LOCUS event 2024.",
                         SourceProvenance(drive_file_id="id1", filename="ncell.pdf",
                                         folder_path="/sponsors", mime_type="pdf", page=2),
                         1.0),
        ]
        return EvidenceSet(query="Ncell sponsor", items=items, is_sufficient=True,
                           missing_aspects=[], conflicts_detected=False)

    def test_build_answer_with_citations(self):
        evidence = self._make_evidence()
        from src.verification.verifier import Verifier
        verification = Verifier().verify("Ncell sponsored LOCUS event", evidence)
        result = self.builder.build_answer(evidence, verification)
        self.assertEqual(result["answer_type"], "FACTUAL")
        self.assertIn("[1", result["answer"])
        self.assertEqual(len(result["provenance"]), 1)
        self.assertEqual(result["provenance"][0]["drive_file_id"], "id1")
        self.assertEqual(result["provenance"][0]["filename"], "ncell.pdf")

    def test_build_abstention(self):
        from src.pipeline.models import EvidenceSet, VerificationResult
        empty = EvidenceSet(query="q", items=[], is_sufficient=False,
                            missing_aspects=["x"], conflicts_detected=False)
        verification = VerificationResult(
            is_faithful=False, unsupported_claims=["no evidence"], contradictions=[],
            numeric_checks_passed=True, completeness_score=0.0,
            confidence_level="ABSTAIN", reasoning="no evidence",
        )
        result = self.builder.build_answer(empty, verification)
        self.assertEqual(result["answer_type"], "ABSTENTION")


class TestExporter(unittest.TestCase):
    def test_to_csv(self):
        csv_out = Exporter.to_csv(["a", "b"], [[1, 2], [3, 4]])
        self.assertIn("a,b", csv_out)
        self.assertIn("1,2", csv_out)

    def test_to_tsv(self):
        tsv_out = Exporter.to_tsv(["a", "b"], [[1, 2]])
        self.assertIn("a\tb", tsv_out)

    def test_to_markdown(self):
        md = Exporter.to_markdown(["Name", "Amount"], [["Ncell", "500000"]])
        self.assertIn("| Name | Amount |", md)
        self.assertIn("| --- |", md)
        self.assertIn("Ncell", md)

    def test_to_json(self):
        js = Exporter.to_json({"key": "value"})
        self.assertIn('"key": "value"', js)

    def test_export_artifact_csv(self):
        data = {"headers": ["a"], "rows": [[1]]}
        artifact = Exporter.export_artifact("csv", data)
        self.assertEqual(artifact["format"], "csv")
        self.assertEqual(artifact["mime_type"], "text/csv")
        self.assertEqual(artifact["filename"], "locus_export.csv")

    def test_export_artifact_markdown(self):
        data = {"headers": ["a"], "rows": [[1]]}
        artifact = Exporter.export_artifact("md", data)
        self.assertEqual(artifact["format"], "md")


if __name__ == "__main__":
    unittest.main(verbosity=2)
