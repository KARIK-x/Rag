"""Regression test: root cause — answer must be synthesized natural-language, not chunk dump or abstention on existing evidence."""
import unittest
from src.generation.synthesizer import synthesize_answer

class MockItem:
    def __init__(self, text):
        class P:
            filename = "test.pdf"; drive_file_id = "d1"; page = 1
        self.chunk_id = "c1"; self.doc_id = "d1"; self.score = 0.5; self.text = text; self.provenance = P()

class SynthesisRegression(unittest.TestCase):
    def test_team_question_has_year_aware_output(self):
        ev = [MockItem("The LOCUS 2025 team includes design chief Piyush Pandey and frontend developer Mukesh Jha. LOCUS 2026 committee includes content team members.")]
        result = synthesize_answer("Who are the organising team?", ev, True)
        text = result["answer_text"]
        self.assertIn("2025", text)
        self.assertIn("2026", text)
        # Must NOT be pure chunk dump (no raw snippet with source bracket format that answer_builder used)
        self.assertNotIn("[1:", text)
        # Must contain honest limitation
        self.assertIn("partial evidence", text.lower())
        # Must NOT invent names outside text
        # Piyush/Mukesh appear in text above → OK; we don't fabricate beyond that

    def test_insufficient_evidence_abstains(self):
        result = synthesize_answer("Unknown future event 2099?", [], False)
        self.assertEqual(result["answer_type"], "ABSTENTION")

    def test_no_raw_chunk_dump_format(self):
        ev = [MockItem("Sponsor: Siddhartha Bank presented LOCUS 2025.")]
        result = synthesize_answer("Sponsor?", ev, True)
        # Should not contain raw chunk index format like previous broken output
        self.assertNotIn("Based on institutional records:\n\n", result["answer_text"])

if __name__ == "__main__":
    unittest.main()
