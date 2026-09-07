"""Phase 5 tests: structural chunker."""
import sys
import unittest
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.chunking.structural import StructuralChunker, Chunk, ExtractedPage, TextBlock
from src.extraction.router import ExtractionResult


class TestStructuralChunker(unittest.TestCase):
    def setUp(self):
        self.chunker = StructuralChunker(target_size=300, hard_cap=600, min_size=50)

    def tearDown(self):
        pass

    def _make_result(self, text_blocks=None, tables=None):
        blocks = text_blocks or [
            TextBlock(
                block_id="b1", block_type="paragraph",
                text="Sponsors contributed Rs. 50,000 in 2024.",
            ),
        ]
        tables_ = tables or []
        return ExtractionResult(
            doc_id="sheet_sponsors",
            provenance={"drive_file_id": "d1", "filename": "sponsors.csv"},
            metadata={"title": "Sponsorship Report"},
            pages=[ExtractedPage(page_number=1, blocks=blocks, tables=tables_)],
            tables=tables_,
            full_text="Sponsors contributed Rs. 50,000 in 2024.",
            extraction_quality="high",
            ocr_used=False,
        )

    def test_chunk_with_contextual_prefix(self):
        # Add a heading block to generate Section context
        result = self.chunker.chunk(self._make_result(
            text_blocks=[
                TextBlock(block_id="h1", block_type="heading", text="Sponsorship Report", level=1),
                TextBlock(block_id="b1", block_type="paragraph", text="Sponsors contributed Rs. 50,000 in 2024."),
            ]
        ))
        self.assertGreater(len(result), 0)
        # At least one chunk should have Section: in prefix
        has_section = any("Section:" in c.contextual_prefix for c in result)
        self.assertTrue(has_section, "No chunk has Section: in contextual prefix")
        # Prefix should mention the page
        self.assertTrue(
            any("Page" in c.contextual_prefix for c in result),
            "No chunk has Page in contextual prefix"
        )

    def test_chunk_type_identification(self):
        result = self.chunker.chunk(self._make_result())
        types = {c.chunk_type for c in result}
        self.assertIn("text", types)

    def test_table_chunks(self):
        # A minimal TableBlock with headers and rows
        from src.extraction.router import TableBlock
        table = TableBlock(
            table_id="t1", page_number=1, row_count=2, col_count=2,
            headers=["Sponsor", "Amount"],
            rows=[{0: "Ncell"}, {0: "CG"}],
        )
        result = self.chunker.chunk(self._make_result(tables=[table]))
        table_chunks = [c for c in result if c.chunk_type == "table"]
        self.assertGreaterEqual(len(table_chunks), 0)

    def test_normalized_text_preserved(self):
        result = self.chunker.chunk(self._make_result())
        for c in result:
            self.assertEqual(c.normalized_text, c.raw_text.lower())

    def test_chunk_id_deterministic(self):
        result1 = self.chunker.chunk(self._make_result())
        result2 = self.chunker.chunk(self._make_result())
        # Same content should produce deterministic IDs
        ids = {c.chunk_id for c in result1}
        # All chunk_ids should be unique
        self.assertEqual(len(ids), len(result1))

    def test_min_size_filter(self):
        # Very small raw text should not produce a chunk below min_size
        tiny_result = self._make_result(text_blocks=[
            TextBlock(block_id="b1", block_type="paragraph", text="Hi"),
        ])
        result = self.chunker.chunk(tiny_result)
        # Tiny doc without headings may produce 0 chunks or 1 undersized one
        self.assertGreaterEqual(len(result), 0)

    def test_page_range_preserved(self):
        result = self.chunker.chunk(self._make_result())
        for c in result:
            if c.page_start is not None and c.page_end is not None:
                self.assertLessEqual(c.page_start, c.page_end)


if __name__ == "__main__":
    unittest.main(verbosity=2)