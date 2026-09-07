"""Phase 3 tests: structured query router (deterministic spreadsheet queries)."""
import sys
import unittest
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.structured_data.engine import StructuredDataEngine
from src.structured_data.query import StructuredQueryRouter, StructuredIntent


class TestStructuredQueryRouter(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="locus_qr_"))
        self.data_dir = str(self.tmp / "data")
        self.state_db = str(self.tmp / "db" / "rag_state.db")
        self.engine = StructuredDataEngine(data_dir=self.data_dir, state_db_path=self.state_db)
        self.router = StructuredQueryRouter(data_dir=self.data_dir, state_db_path=self.state_db)

        # Sample sponsorship extraction
        ex = {
            "doc_id": "sheet_sponsors",
            "tables": [{
                "table_id": "sponsorship_2024",
                "page_number": 1,
                "row_count": 4,
                "col_count": 3,
                "headers": ["sponsor", "category", "amount"],
                "rows": [
                    {"0": "Ncell", "1": "Gold", "2": 500000},
                    {"0": "CG", "1": "Gold", "2": 300000},
                    {"0": "DFT", "1": "Silver", "2": 150000},
                    {"0": "Worldlink", "1": "Bronze", "2": 80000},
                ],
            }],
            "provenance": {"drive_file_id": "d_sheet", "filename": "sponsors.csv"},
            "full_text": "",
        }
        self.engine.import_table_from_extraction(ex)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_list_tables(self):
        tables = self.router.list_tables()
        self.assertEqual(len(tables), 1)
        self.assertEqual(tables[0]["table_id"], "sponsorship_2024")
        self.assertEqual(tables[0]["row_count"], 4)
        self.assertIn("headers", tables[0])

    def test_plan_total_sponsorship(self):
        plan = self.router.plan("sponsorship_2024", "What was the total sponsorship amount?")
        self.assertEqual(plan["intent"], StructuredIntent.TOTAL)
        self.assertEqual(plan["amount_col"], "amount")
        self.assertIn("SUM", plan["sql"].upper())

    def test_execute_total(self):
        plan = self.router.plan("sponsorship_2024", "What was the total sponsorship amount?")
        res = self.router.execute(plan)
        self.assertIsNone(res.error)
        self.assertEqual(len(res.rows), 1)
        self.assertEqual(res.rows[0]["total"], 1030000)

    def test_plan_aggregate_by_category(self):
        plan = self.router.plan("sponsorship_2024", "Group sponsors by category and sum the amount")
        self.assertEqual(plan["intent"], StructuredIntent.AGGREGATE_GROUP)
        self.assertEqual(plan["group_col"], "category")
        self.assertIn("GROUP BY", plan["sql"].upper())

    def test_execute_aggregate(self):
        plan = self.router.plan("sponsorship_2024", "Group sponsors by category and sum the amount")
        res = self.router.execute(plan)
        self.assertIsNone(res.error)
        by_cat = {r["category"]: r["total"] for r in res.rows}
        self.assertEqual(by_cat["Gold"], 800000)
        self.assertEqual(by_cat["Silver"], 150000)

    def test_plan_filter_above(self):
        plan = self.router.plan("sponsorship_2024", "Give me sponsors with contributions above 200000")
        self.assertEqual(plan["intent"], StructuredIntent.FILTER)
        res = self.router.execute(plan)
        self.assertIsNone(res.error)
        self.assertEqual(len(res.rows), 2)
        for r in res.rows:
            self.assertGreater(r["amount"], 200000)

    def test_plan_sort_by_amount(self):
        plan = self.router.plan("sponsorship_2024", "Sort sponsors by contribution amount")
        self.assertEqual(plan["intent"], StructuredIntent.SORT)
        res = self.router.execute(plan)
        self.assertIsNone(res.error)
        amounts = [r["amount"] for r in res.rows]
        self.assertEqual(amounts, sorted(amounts, reverse=True))

    def test_deterministic_computation(self):
        """The engine computes, never the LLM."""
        total = self.router.compute.total_of("sponsorship_2024", "amount")
        self.assertEqual(total, 1030000)


if __name__ == "__main__":
    unittest.main(verbosity=2)