"""Inspect failing extraction cases and their raw files."""
import sys
import json
import os
from pathlib import Path

sys.path.insert(0, "/Users/ashim/locus_rag/src")
from extraction.router import _extract_pdf_pymupdf

raw_dir = Path("/Users/ashim/locus_rag/data/raw")
extracted_dir = Path("/Users/ashim/locus_rag/data/extracted")

# The 3 text/plain failures (1 char each)
failed_ids = [
    "1TdEcYJmDbs_qUb3WFMtmquLwbtQHmoscDfxSFgjXdZ8",
    "1jYh49Gm5ddnPi4A9r_mjO94R-9AGOZX2wvPkfsLFr2M",
    "1vePFovCMfIKaVU2vIuYbAyJpKlJzjAFnMCfYucEoCQQ",
]

for fid in failed_ids:
    print(f"\n=== FAILED: {fid} ===")
    # Raw files
    raw_files = list(raw_dir.glob(f"{fid}.*"))
    for r in raw_files:
        data = r.read_bytes()
        print(f"  raw: {r.name}  size={r.stat().st_size}  content={data[:60]!r}")

    # Extracted JSON
    ext_file = extracted_dir / f"{fid}.json"
    if ext_file.exists():
        d = json.loads(ext_file.read_text())
        print(f"  extracted: quality={d.get('extraction_quality')}")
        print(f"    metadata prov: {d.get('provenance', {})}")
        print(f"    warnings: {d.get('parser_warnings', [])}")
        print(f"    error: {d.get('error_message')}")
        print(f"    ocr_meta: {d.get('ocr_metadata', {})}")