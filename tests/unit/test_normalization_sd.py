"""
Phase 3 tests: normalization + structured data engine.
"""

import sys
import unittest
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.normalization.text import (
    parse_number,
    parse_date,
    normalize_text,
    normalize_devanagari_digits,
    is_mixed_script,
    Normalizer,
    NumberFormat,
)
from src.structured_data.engine import (
    StructuredDataEngine,
    ComputationEngine,
    StructuredTable,
)


class TestNumberNormalization(unittest.TestCase):
    """Test number parsing (spec §21)."""

    def test_western_grouped(self):
        """100,000 → 100000.0, western grouping"""
        n = parse_number("100,000")
        self.assertEqual(n.parsed_numeric_value, 100000.0)
        self.assertEqual(n.format_style, NumberFormat.WESTERN_GROUPED.value)

    def test_indian_grouped(self):
        """12,34,567 → interprets correctly"""
        n = parse_number("12,34,567")
        self.assertEqual(n.parsed_numeric_value, 1234567.0)
        self.assertEqual(n.format_style, NumberFormat.INDIAN_GROUPED.value)

    def test_currency_npr(self):
        n = parse_number("NPR 100,000")
        self.assertEqual(n.parsed_numeric_value, 100000.0)
        self.assertEqual(n.currency, "NPR")

    def test_currency_rs(self):
        n = parse_number("Rs. 50000")
        self.assertEqual(n.parsed_numeric_value, 50000.0)
        self.assertEqual(n.currency, "NPR")

    def test_lakh(self):
        n = parse_number("NPR 1 lakh")
        self.assertEqual(n.parsed_numeric_value, 100000.0)
        self.assertEqual(n.unit, "lakh")

    def test_crore(self):
        n = parse_number("Rs. 2 crore")
        self.assertEqual(n.parsed_numeric_value, 20000000.0)

    def test_devanagari_digits(self):
        n = parse_number("५०,०००")
        self.assertEqual(n.parsed_numeric_value, 50000.0)

    def test_preserves_raw(self):
        n = parse_number("BR 100,000")
        self.assertEqual(n.raw_value, "BR 100,000")
        self.assertEqual(n.source_text, "BR 100,000")

    def test_no_assumption_npr(self):
        """We don't assume currency='NPR' for bare numbers."""
        n = parse_number("50000")
        self.assertEqual(n.parsed_numeric_value, 50000.0)
        self.assertIsNone(n.currency)


class TestDateNormalization(unittest.TestCase):
    """Test date parsing."""

    def test_iso(self):
        d = parse_date("2024-01-15")
        self.assertIsNotNone(d.parsed_date)
        self.assertEqual(d.parsed_date.year, 2024)
        self.assertEqual(d.parsed_date.month, 1)
        self.assertEqual(d.parsed_date.day, 15)

    def test_us_style(self):
        d = parse_date("01/15/2024")
        self.assertEqual(d.parsed_date.year, 2024)
        self.assertEqual(d.parsed_date.month, 1)
        self.assertEqual(d.parsed_date.day, 15)

    def test_long_form(self):
        d = parse_date("15 January 2024")
        self.assertEqual(d.parsed_date.month, 1)
        self.assertEqual(d.parsed_date.day, 15)

    def test_month_name_first(self):
        d = parse_date("January 15, 2024")
        self.assertEqual(d.parsed_date.month, 1)
        self.assertEqual(d.parsed_date.day, 15)

    def test_with_time(self):
        d = parse_date("2024-01-15T10:30:00")
        self.assertEqual(d.parsed_date.day, 15)

    def test_invalid(self):
        d = parse_date("not a date")
        self.assertIsNone(d.parsed_date)


class TestTextNormalization(unittest.TestCase):
    """Test text normalization + mixed script."""

    def test_unicode_nfc(self):
        text = "café"  # cafe + combining acute
        out = normalize_text(text, lower=False)
        # Should be single é after NFKC
        self.assertIn("é", out)
        self.assertNotIn("café", out)

    def test_whitespace_collapse(self):
        out = normalize_text("a   b\n\n\n  c", lower=False)
        self.assertEqual(out, "a b c")

    def test_lowercase(self):
        out = normalize_text("LOCUS CLUB", lower=True)
        self.assertEqual(out, "locus club")

    def test_curly_quotes(self):
        out = normalize_text("LOCUS’s club", lower=False)
        self.assertIn("LOCUS's", out)

    def test_preserves_meaning(self):
        out = normalize_text("Sponsorship   Revenue:", lower=False)
        self.assertIn("Sponsorship Revenue", out)

    def test_devanagari_digits_conversion(self):
        self.assertEqual(normalize_devanagari_digits("१२३"), "123")

    def test_mixed_script_detection(self):
        text = "LOCUS क्लब 2027"
        self.assertTrue(is_mixed_script(text))

    def test_latin_only_not_mixed(self):
        self.assertFalse(is_mixed_script("LOCUS club 2027"))


class TestNormalizerFacade(unittest.TestCase):
    """Test the top-level Normalizer."""

    def setUp(self):
        self.norm = Normalizer()

    def test_normalize_document(self):
        raw = {
            "doc_id": "doc1",
            "full_text": "Sponsors contributed Rs. 50,000 in 2024.",
            "metadata": {"title": "Test"},
            "provenance": {"drive_file_id": "d1"},
        }
        out = self.norm.normalize(raw)
        self.assertEqual(out["doc_id"], "doc1")
        self.assertEqual(len(out["extracted_numbers"]), 1)
        self.assertEqual(
            out["extracted_numbers"][0]["parsed_numeric_value"], 50000.0
        )
        # Bare "2024" is a year, not a date — no dates expected
        self.assertEqual(len(out["extracted_dates"]), 0)

    def test_no_numbers(self):
        raw = {"doc_id": "doc2", "full_text": "Just words.", "metadata": {}, "provenance": {}}
        out = self.norm.normalize(raw)
        self.assertEqual(out["extracted_numbers"], [])


class TestStructuredDataEngine(unittest.TestCase):
    """Test DuckDB + Parquet structured engine."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="locus_sd_"))
        self.state_db = str(self.tmp / "rag_state.db")
        self.engine = StructuredDataEngine(
            data_dir=str(self.tmp / "data"),
            state_db_path=self.state_db,
        )
        self.compute = ComputationEngine(
            engine=self.engine, data_dir=str(self.tmp / "data")
        )

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _sample_extraction(self):
        return {
            "doc_id": "sheet_sponsors",
            "tables": [{
                "table_id": "sponsors_2024",
                "page_number": 1,
                "row_count": 3,
                "col_count": 3,
                "headers": ["sponsor", "category", "amount"],
                "rows": [
                    {"0": "Ncell", "1": "Gold", "2": 500000},
                    {"0": "CG", "1": "Gold", "2": 300000},
                    {"0": "DFT", "1": "Silver", "2": 150000},
                ],
            }],
            "provenance": {
                "drive_file_id": "d_sheet",
                "filename": "sponsors.csv",
            },
            "full_text": "",
        }

    def test_import_to_parquet(self):
        st = self.engine.import_table_from_extraction(self._sample_extraction())
        self.assertIsNotNone(st)
        self.assertTrue(Path(st.parquet_path).exists())
        self.assertEqual(len(st.rows), 3)

    def test_query_table(self):
        self.engine.import_table_from_extraction(self._sample_extraction())
        res = self.compute.query_table(
            "sponsors_2024",
            "SELECT * FROM read_parquet('{}')".format(
                self.compute._parquet_path("sponsors_2024")
            ),
        )
        self.assertIsNone(res.error)
        self.assertEqual(len(res.rows), 3)
        self.assertIn("sponsor", res.columns)

    def test_aggregation_sum(self):
        self.engine.import_table_from_extraction(self._sample_extraction())
        res = self.compute.aggregate(
            "sponsors_2024", group_col="category", agg_col="amount", agg_func="SUM"
        )
        self.assertIsNone(res.error)
        # Gold=800000, Silver=150000
        by_cat = {r["category"]: r["sum"] for r in res.rows}
        self.assertEqual(by_cat["Gold"], 800000)
        self.assertEqual(by_cat["Silver"], 150000)

    def test_total_of(self):
        self.engine.import_table_from_extraction(self._sample_extraction())
        total = self.compute.total_of("sponsors_2024", "amount")
        self.assertEqual(total, 950000)

    def test_filter(self):
        self.engine.import_table_from_extraction(self._sample_extraction())
        res = self.compute.filter_rows(
            "sponsors_2024", "amount > 200000"
        )
        self.assertIsNone(res.error)
        self.assertEqual(len(res.rows), 2)
        for r in res.rows:
            self.assertGreater(r["amount"], 200000)

    def test_sort(self):
        self.engine.import_table_from_extraction(self._sample_extraction())
        res = self.compute.sort("sponsors_2024", "amount", descending=True)
        self.assertIsNone(res.error)
        amounts = [r["amount"] for r in res.rows]
        self.assertEqual(amounts, sorted(amounts, reverse=True))

    def test_missing_table(self):
        res = self.compute.query_table("nope", "SELECT 1")
        self.assertIsNotNone(res.error)

    def test_provenance_sidecar(self):
        self.engine.import_table_from_extraction(self._sample_extraction())
        prov_path = self.tmp / "data" / "structured" / "sponsors_2024.provenance.json"
        self.assertTrue(prov_path.exists())
        import json
        prov = json.loads(prov_path.read_text())
        self.assertEqual(prov["drive_file_id"], "d_sheet")
        self.assertEqual(prov["headers"], ["sponsor", "category", "amount"])


if __name__ == "__main__":
    unittest.main(verbosity=2)