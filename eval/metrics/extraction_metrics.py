"""
LOCUS RAG extraction-quality report (comprehensive).

Per spec §20 (integrity audit), §61 (failure attribution), §84 (reliability
targets), this produces a complete per-document + corpus-level report covering:

  1. Corpus coverage (file mix across all processable LOCUS types)
  2. Extraction quality per document
  3. Raw file size <-> extraction quality correlation
  4. Integrity audit findings on every document
  5. Failing-case deep dive (REQUIRES_REVIEW / FAILED)
  6. Metric totals against spec §84 targets
"""

import json
import math
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add src to path so the auditor imports work when run as a script
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from src.integrity.audit import IntegrityAuditor, AuditStatus


def _quality_order(q: str) -> int:
    return {"high": 3, "medium": 2, "low": 1, "failed": 0}.get(q, -1)


def _mime_class(mime: str) -> str:
    """Classify a mime type into a broad family."""
    if mime == "application/pdf":
        return "pdf"
    if "spreadsheet" in mime or "excel" in mime or mime == "text/csv":
        return "spreadsheet"
    if "document" in mime or "word" in mime or "plain" in mime or "markdown" in mime or "rtf" in mime:
        return "document"
    if "presentation" in mime:
        return "presentation"
    if "form" in mime:
        return "form"
    return "other"


def _load_extracted(data_dir: str) -> List[Dict[str, Any]]:
    """Load all extracted JSON artifacts."""
    d = Path(data_dir) / "extracted"
    if not d.exists():
        return []
    docs = []
    for f in sorted(d.glob("*.json")):
        try:
            docs.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            continue
    return docs


def _reconstruct_result(d: Dict, pages: List, ocr_meta: Dict, mime: str, drive_id: str):
    """Reconstruct a minimal ExtractionResult for the auditor."""
    from src.extraction.router import (
        ExtractionResult,
        ExtractedPage,
        TableBlock,
        ExtractionQuality,
    )

    quality = ExtractionQuality(d.get("extraction_quality", "failed"))
    epages = []
    for p in pages:
        epages.append(ExtractedPage(
            page_number=p.get("page_number", 1),
            blocks=[
                type("B", (), {
                    "block_id": b.get("block_id", ""),
                    "block_type": b.get("block_type", "paragraph"),
                    "text": b.get("text", ""),
                    "level": b.get("level", 1),
                })()
                for b in p.get("blocks", [])
            ],
        ))

    # Rebuild TableBlock objects (the auditor needs .row_count/.col_count/.headers)
    tables = [
        TableBlock(
            table_id=t.get("table_id", ""),
            page_number=t.get("page_number", 1),
            row_count=t.get("row_count", 0),
            col_count=t.get("col_count", 0),
            headers=t.get("headers", []),
            rows=t.get("rows", []),
        )
        for t in d.get("tables", [])
    ]

    return ExtractionResult(
        doc_id=drive_id,
        provenance={"mime_type": mime},
        metadata={},
        pages=epages,
        tables=tables,
        full_text=d.get("full_text", ""),
        extraction_quality=quality,
        ocr_used=d.get("ocr_used", False),
        ocr_metadata=ocr_meta,
        parser_warnings=d.get("parser_warnings", []),
        error_message=d.get("error_message"),
    )


def collect_records(data_dir: str = "data") -> List[Dict[str, Any]]:
    """Build structured per-document records with audit findings."""
    docs = _load_extracted(data_dir)

    raw_dir = Path(data_dir) / "raw"
    raw_sizes: Dict[str, int] = {}
    if raw_dir.exists():
        for r in raw_dir.iterdir():
            if r.is_file():
                raw_sizes[r.stem] = r.stat().st_size

    records = []
    for d in docs:
        prov = d.get("provenance", {})
        meta = d.get("metadata", {})
        pages = d.get("pages", [])
        tables = d.get("tables", [])
        full_text = d.get("full_text", "")
        ocr_meta = d.get("ocr_metadata", {})
        headings = sum(
            1 for p in pages
            for b in p.get("blocks", [])
            if b.get("block_type") == "heading"
        )
        blocks = sum(len(p.get("blocks", [])) for p in pages)
        scanned = ocr_meta.get("scanned_pages", [])
        mime = prov.get("mime_type", "?")
        drive_id = prov.get("drive_file_id", d.get("doc_id", "?"))

        # Integrity audit replay
        result = _reconstruct_result(d, pages, ocr_meta, mime, drive_id)
        audit = IntegrityAuditor().audit_extraction(result)
        fail_msgs = [f.message for f in audit.findings if f.severity == AuditStatus.FAIL]
        warn_msgs = [f.message for f in audit.findings if f.severity == AuditStatus.WARN]

        records.append({
            "drive_file_id": drive_id,
            "filename": meta.get("title") or prov.get("filename", "?"),
            "mime_type": mime,
            "mime_class": _mime_class(mime),
            "quality": d.get("extraction_quality", "?"),
            "chars": len(full_text),
            "raw_size": raw_sizes.get(drive_id),
            "pages": len(pages),
            "blocks": blocks,
            "headings": headings,
            "tables": len(tables),
            "ocr_used": d.get("ocr_used", False),
            "scanned_pages": len(scanned),
            "parser_warnings": d.get("parser_warnings", []),
            "error": d.get("error_message"),
            "audit_status": audit.overall_status.value,
            "audit_failures": fail_msgs,
            "audit_warnings": warn_msgs,
        })
    return records


def print_report(records: List[Dict[str, Any]]):
    n = len(records)
    print("\n" + "=" * 80)
    print("LOCUS RAG — COMPREHENSIVE EXTRACTION QUALITY REPORT")
    print("=" * 80)

    # 1) Corpus coverage
    print(f"\n[1] CORPUS COVERAGE (n={n})")
    mime_classes = Counter(r["mime_class"] for r in records)
    for cls, cnt in sorted(mime_classes.items(), key=lambda x: -x[1]):
        print(f"  {cls:12}: {cnt:3}")

    mime_quality = Counter(f'{r["mime_class"]}|{r["quality"]}' for r in records)
    print("\n  MIME class x quality:")
    for key, cnt in sorted(mime_quality.items()):
        print(f"    {key:25}: {cnt}")

    # 2) Failing cases
    fails = [
        r for r in records
        if r["quality"] in ("failed", "low") or r["audit_failures"]
    ]
    print(f"\n[2] FAILING / REVIEW CASES ({len(fails)})")
    print(f"  {'FILENAME':30} {'MIME':12} {'QUAL':6} {'CHARS':>6} {'AUDIT':6} REASON")
    for r in sorted(fails, key=lambda x: _quality_order(x["quality"])):
        mime_short = r["mime_type"].split("/")[-1][:12]
        reason = (
            "; ".join(r["audit_failures"])
            or r["error"]
            or (r["audit_warnings"][0] if r["audit_warnings"] else "")
            or (r["parser_warnings"][0] if r["parser_warnings"] else "?")
        )
        print(
            f"  {r['filename'][:30]:30} {mime_short:12} {r['quality']:6} "
            f"{r['chars']:6} {r['audit_status']:6} {reason[:60]}"
        )

    # 3) Size <-> quality correlation
    print(f"\n[3] RAW SIZE <-> EXTRACTION QUALITY")
    size_by_quality: Dict[str, List[int]] = {q: [] for q in ("high", "medium", "low", "failed")}
    for r in records:
        if r["raw_size"] is not None and r["quality"] in size_by_quality:
            size_by_quality[r["quality"]].append(r["raw_size"])
    for q in ("high", "medium", "low", "failed"):
        sizes = size_by_quality[q]
        if sizes:
            print(
                f"  {q:8}: n={len(sizes):2}  "
                f"min={min(sizes):>8}  med={statistics.median(sizes):>8}  "
                f"max={max(sizes):>8} bytes"
            )
        else:
            print(f"  {q:8}: n=0")

    ranked = [
        (r["raw_size"], _quality_order(r["quality"]))
        for r in records
        if r["raw_size"] is not None and r["quality"] in size_by_quality
    ]
    if len(ranked) > 1:
        xs = [math.log(x + 1) for x, _ in ranked]
        ys = [y for _, y in ranked]
        mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
        cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
        vx = sum((x - mx) ** 2 for x in xs)
        vy = sum((y - my) ** 2 for y in ys)
        r = cov / math.sqrt(vx * vy) if vx and vy else 0.0
        print(f"  Correlation(log(size) vs quality rank): r={r:.3f}")

    # 4) Integrity audit summary
    print(f"\n[4] INTEGRITY AUDIT SUMMARY")
    audit_statuses = Counter(r["audit_status"] for r in records)
    print(f"  Audit statuses: {dict(audit_statuses)}")

    all_warnings: Counter = Counter()
    for r in records:
        key = "; ".join(r["audit_warnings"]) if r["audit_warnings"] else "(none)"
        all_warnings[key] += 1
    print("\n  Recurring audit warnings:")
    for msg, cnt in all_warnings.most_common(8):
        print(f"    {cnt:2}x {msg[:78]}")

    # 5) Spec §84 targets
    print(f"\n[5] SPEC §84 RELIABILITY TARGETS")
    clean = sum(1 for r in records if r["quality"] == "high") / n if n else 0
    ocr_incl = (
        sum(1 for r in records if r["quality"] in ("high", "medium", "low")) / n
        if n else 0
    )
    print(f"  Clean extraction success:     {100*clean:.1f}%  (target >= 98%)")
    print(f"  OCR-inclusive extraction:     {100*ocr_incl:.1f}%  (target >= 90%)")

    print("\n" + "=" * 80 + "\n")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="LOCUS extraction quality report")
    parser.add_argument("--data-dir", default="data", help="Path to data directory")
    args = parser.parse_args()

    records = collect_records(data_dir=args.data_dir)
    print_report(records)