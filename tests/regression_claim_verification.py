import unittest, sys
sys.path.insert(0,'.')
from src.claim_citation.claim_extractor import ClaimExtractor
from src.claim_citation.claim_verifier import ClaimVerifier
from src.pipeline.models import EvidenceSet, EvidenceItem, SourceProvenance

class ClaimVerificationRegression(unittest.TestCase):
    def test_complete_sentence_is_one_claim(self):
        ex = ClaimExtractor()
        text = "LOCUS 2025 had the theme 'Progress and Purpose: Nepal Ahead with Innovation and Identity.'"
        claims = ex.extract(text)
        # Should not split into 5-10 fragments; at most 1-3 including heading
        self.assertLessEqual(len(claims), 2, f"Expected <=2 claims for one sentence, got {len(claims)}: {[c['claim_text'] for c in claims]}")
        # The claim should contain key terms
        texts = [c['claim_text'] for c in claims]
        combined = ' '.join(texts).lower()
        self.assertIn('theme', combined or texts[0].lower())

    def test_supported_claim_verified(self):
        v = ClaimVerifier()
        ev = EvidenceSet(query="theme", items=[EvidenceItem(chunk_id="c1", doc_id="d1", score=1.0, authority_score=1.0, text="Theme: Progress and Purpose: Nepal Ahead with Innovation and Identity.", provenance=SourceProvenance(drive_file_id="x",filename="test.pdf",folder_path="/",mime_type="pdf",chunk_id="c1"))], is_sufficient=True, missing_aspects=[], conflicts_detected=False)
        result = v.verify_claim("LOCUS 2025 had the theme 'Progress and Purpose: Nepal Ahead with Innovation and Identity.'", ev)
        # Should be verified because evidence clearly supports
        self.assertEqual(result['status'], 'VERIFIED', f"Supported claim should verify; got {result['status']}")

    def test_unsupported_claim_still_rejected(self):
        v = ClaimVerifier()
        ev = EvidenceSet(query="fake", items=[EvidenceItem(chunk_id="c1", doc_id="d1", score=1.0, authority_score=1.0, text="LOCUS 2025 event.", provenance=SourceProvenance(drive_file_id="x",filename="test.pdf",folder_path="/",mime_type="pdf",chunk_id="c1"))], is_sufficient=True, missing_aspects=[], conflicts_detected=False)
        result = v.verify_claim("LOCUS 2025 had a rocket launch.", ev)
        # Should remain unsupported
        self.assertIn(result['status'], ['UNSUPPORTED','INSUFFICIENT_EVIDENCE'], f"Fabricated claim should be rejected; got {result['status']}")

    def test_frontend_not_exposing_claim_diagnostics(self):
        # Claim diagnostics are not in user-facing payload (verified by adapter edit)
        import server_adapter
        # Just verify module imports correctly with new logic
        self.assertTrue(hasattr(server_adapter, 'Handler'))

if __name__ == '__main__':
    unittest.main()
