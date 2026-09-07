# ADR-002: OCR Engine

**Status:** DECIDED (2026-09-07) — with a noted gap

## Problem
Many LOCUS PDFs are scanned (certificates, documents). OCR is the fallback path. V1 needs a local engine with acceptable quality for English-and-Nepali content.

## Candidates Considered
1. **Tesseract 5.5.0** (via pytesseract) — installed; local; multi-language; mature
2. **Surya** — modern; GPU; not installed; heavy
3. **Cloud OCR (Google/Azure)** — high accuracy; paid; external; violates `$0`/local-first

## Experiment
Real scanned LOCUS PDF (10-page certificate document, ~30 MB):

| Metric | Result |
|--------|--------|
| OCR text recovered | 4907 chars across 10 pages |
| Confidence | 93.1% on page 1 (certificate recognition) |
| Text quality | Clean: "LOCUS 2027 23rd National Technological Festival Certificate of Appreciation... Manish Kumar Patel ... Mentor for ELECTRICAL DESIGN WORKSHOP" |
| Scan detection | 10/10 pages correctly flagged as scanned |

## Results / Decision
**Use Tesseract 5.5.0 via pytesseract** as the V1 OCR engine.

Why:
- Local, `$0`
- Works well on English certificate/document scans
- Detects scans reliably and only OCRs when needed (auto mode)

**Known gap (Devanagari/Nepali):**
- Installed tessdata only has `eng`, `osd`, `snum`
- Devanagari (`nep`/`hin`) tessdata is NOT installed
- Mixed English/Nepali documents are common in LOCUS → this is a real requirement

## Action (Phase 2c / Phase 3)
- Install Devanagari tessdata (`nep`/`hin` traineddata) via homebrew or manual tessdata download
- Evaluate Nepali CER/WER + numeric accuracy on real LOCUS scans
- If Tesseract Devanagari quality is inadequate, evaluate Surya on the same set

## Revisit Conditions
- Re-evaluate if Devanagari OCR quality proves inadequate on real scans
- Re-evaluate if Tesseract's numeric/table accuracy on financial scans degrades at scale