# ADR-001: Extraction Engine

**Status:** DECIDED (2026-09-07)

## Problem
PDFs, DOCX, and other formats need reliable extraction into a structured intermediate representation while preserving page structure, headings, tables, and provenance.

## Failure Mode Addressed
- Bad chunking from broken source text
- Lost headings / table context
- Malformed PDFs destroying retrieval-critical information

## Candidates Considered
1. **PyMuPDF (fitz)** — installed; fast; preserves page structure, fonts (heading detection), images; detects scanned pages (image + no text)
2. **Docling** — broad format support; not installed; heavy dependency
3. **Basic regex heuristic** — stdlib-only, only worked for simple `(text) Tj` PDFs; failed on real corpus

## Experiment
**Dataset:** Real LOCUS sample — 21 files: 11 PDFs (CVs/resumes, MoU, workshop call PDFs, scanned certificates), 6 spreadsheets (form-response CSVs/Google Sheets), 4 documents (Google Doc exports, MoU drafts).

**Metrics (per §84):**

| Metric | Result |
|--------|--------|
| Clean extraction success (HIGH) | 66.7% (14/21) |
| OCR-inclusive extraction (HIGH+MEDIUM+LOW) | 85.7% (18/21) |
| Genuine failures | 3 (empty Google Docs — BOM-only, content truly empty) |
| Table preservation | Present in spreadsheets + table-like PDF regions |
| Heading preservation | High in multi-page docs (CVs, reports) |
| Scanned-PDF detection | Working: 10/10 scanned cert pages flagged, OCR recovers 4907 chars |

**Size ↔ quality correlation:** r=0.749 (log-size vs quality rank)

## Results / Decision
**Use PyMuPDF (fitz) as the primary PDF extractor.**

Why:
- Handles digital, mixed, and scanned PDFs with page-count + heading preservation
- Detects scanned pages (low text + image present) and triggers OCR fallback
- Fast, local, zero cost
- Docling adds little for the current corpus (PDFs are either clean digital or fully-scanned)

**Rejected:**
- **Docling**: not installed; heavy; provides table extraction but PyMuPDF + our table heuristics suffice for V1
- **Basic regex**: fails on real corpus (0 chars on CVs, MoU)

## Revisit Conditions
- Re-evaluate if production corpus reveals many table-complex PDFs (financial reports/spreadsheets-as-PDF)
- Re-evaluate if Docling's mainstream install + performance improves materially
- Re-evaluate when DOCX table structures become critical (currently handled by Python+XML text runs)