"""Phase 4 tests: classification + dedup + authority."""
import sys
import unittest
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.classification.classifier import (
    DocumentClassifier,
    DocDomain,
    AuthorityStatus,
)
from src.dedup.deduplicator import (
    Deduplicator,
    DedupCandidate,
    DedupIndex,
    DedupCluster,
)


class TestDocumentClassifier(unittest.TestCase):
    def setUp(self):
        self.classifier = DocumentClassifier()

    def test_classify_sponsorship(self):
        doc = {
            "doc_id": "doc_sponsor",
            "full_text": (
                "Call for Sponsorship 2024. We invite gold, silver, and bronze "
                "sponsors to contribute. Sponsorship revenue supports the "
                "national technological festival."
            ),
            "metadata": {"title": "Sponsorship Proposal 2024.docx"},
            "provenance": {},
        }
        c = self.classifier.classify(doc)
        self.assertIn(DocDomain.SPONSORSHIP.value, c.domains)
        self.assertIn(DocDomain.EVENT.value, c.domains)
        self.assertEqual(c.primary_domain, DocDomain.SPONSORSHIP.value)

    def test_classify_cv(self):
        doc = {
            "doc_id": "doc_cv",
            "full_text": (
                "Curriculum Vitae — Software Engineer. Work experience at XYZ. "
                "Skills: Python, JavaScript, Machine Learning."
            ),
            "metadata": {"title": "Aman CV.pdf"},
            "provenance": {},
        }
        c = self.classifier.classify(doc)
        self.assertIn(DocDomain.MEMBER_CV.value, c.domains)

    def test_classify_authority_draft(self):
        doc = {
            "doc_id": "doc_draft",
            "full_text": "This is a draft proposal for the sponsorship package.",
            "metadata": {"title": "draft proposal.docx"},
            "provenance": {},
        }
        c = self.classifier.classify(doc)
        self.assertEqual(c.authority_status, AuthorityStatus.DRAFT.value)

    def test_classify_authority_mou(self):
        doc = {
            "doc_id": "doc_mou",
            "full_text": (
                "Memorandum of Understanding. The parties have agreed and "
                "signed this document on this day."
            ),
            "metadata": {"title": "MoU LOCUS signed.pdf"},
            "provenance": {},
        }
        c = self.classifier.classify(doc)
        self.assertEqual(c.authority_status, AuthorityStatus.SIGNED.value)

    def test_classify_authority_unknown(self):
        doc = {
            "doc_id": "doc_x",
            "full_text": "Some generic content here.",
            "metadata": {"title": "Notes.txt"},
            "provenance": {},
        }
        c = self.classifier.classify(doc)
        self.assertEqual(c.authority_status, AuthorityStatus.UNKNOWN.value)

    def test_temporal_dates(self):
        doc = {
            "doc_id": "doc_dates",
            "full_text": (
                "The 2024 annual event ran from 2024-03-15 to 2024-03-17. "
                "Planning began January 12, 2023."
            ),
            "metadata": {"title": "Event Plan"},
            "provenance": {},
        }
        c = self.classifier.classify(doc)
        self.assertIn("2024-03-15", c.content_dates)
        self.assertIn("2024-03-17", c.content_dates)


class TestDeduplicator(unittest.TestCase):
    def setUp(self):
        # Near-duplicate threshold (candidate signal; exact hashes handled separately)
        self.dedup = Deduplicator(similarity_threshold=0.60)

    def _candidate(self, doc_id, text, modified=None):
        import hashlib
        from src.normalization.text import normalize_text

        normalized = normalize_text(text, lower=True)
        return DedupCandidate(
            doc_id=doc_id,
            drive_file_id=f"drive_{doc_id}",
            filename=f"{doc_id}.txt",
            content_hash=hashlib.sha256(text.encode()).hexdigest(),
            normalized_hash=hashlib.sha256(normalized.encode()).hexdigest(),
            size_bytes=len(text),
            modified_time=modified,
            text=text,
        )

    def test_exact_duplicate(self):
        text = "LOCUS is the ICT Club of Summit Higher Secondary School."
        c1 = self._candidate("a", text, modified="2024-01-01T00:00:00")
        c2 = self._candidate("b", text, modified="2024-02-01T00:00:00")
        clusters = self.dedup.cluster([c1, c2])
        self.assertEqual(len(clusters), 1)
        self.assertEqual(clusters[0].relation, "exact_duplicate")
        self.assertEqual(clusters[0].similarity, 1.0)
        self.assertEqual(set(clusters[0].member_ids), {"a", "b"})
        # Canonical = most recently modified
        self.assertEqual(clusters[0].canonical_id, "b")

    def test_near_duplicate(self):
        text1 = "LOCUS is the ICT Club of Summit Higher Secondary School. We organize tech events every year."
        text2 = "LOCUS is the ICT Club of Summit School. We organize tech events every year for students."
        c1 = self._candidate("a", text1)
        c2 = self._candidate("b", text2)
        clusters = self.dedup.cluster([c1, c2])
        self.assertEqual(len(clusters), 1)
        self.assertEqual(clusters[0].relation, "near_duplicate")

    def test_different_docs_not_deduped(self):
        c1 = self._candidate("a", "Report about the 2024 sponsorship revenues and budget.")
        c2 = self._candidate("b", "Resume of a software engineer with 5 years experience.")
        clusters = self.dedup.cluster([c1, c2])
        self.assertEqual(len(clusters), 0)

    def test_provenance_preserved(self):
        text = "Same content here."
        c1 = self._candidate("a", text, modified="2024-01-01")
        c2 = self._candidate("b", text, modified="2024-02-01")
        clusters = self.dedup.cluster([c1, c2])
        cluster = clusters[0]
        self.assertIn("drive_a", cluster.member_drive_ids)
        self.assertIn("drive_b", cluster.member_drive_ids)
        self.assertIn("a", cluster.provenance_map)
        self.assertIn("b", cluster.provenance_map)


class TestDedupIndex(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="locus_di_"))
        self.db_path = str(self.tmp / "rag_state.db")
        self.index = DedupIndex(db_path=self.db_path)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_save_and_lookup_canonical(self):
        cluster = DedupCluster(
            cluster_id="cl_1",
            canonical_id="doc_final",
            member_ids=["doc_draft", "doc_final"],
            member_drive_ids=["d1", "d2"],
            relation="exact_duplicate",
            similarity=1.0,
            provenance_map={},
        )
        saved = self.index.save_clusters([cluster])
        self.assertEqual(saved, 1)

        self.assertEqual(self.index.canonical_for("doc_draft"), "doc_final")
        self.assertEqual(self.index.canonical_for("doc_final"), "doc_final")
        aliases = self.index.aliases_for("doc_final")
        self.assertIn("doc_draft", aliases)
        self.assertIn("doc_final", aliases)


if __name__ == "__main__":
    unittest.main(verbosity=2)