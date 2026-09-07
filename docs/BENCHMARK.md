# Benchmark — LOCUS RAG

## 1. Purpose

The LOCUS RAG benchmark establishes ground truth for retrieval quality, answer faithfulness, and system reliability. It is the authoritative measurement framework against which every architectural change is evaluated.

## 2. Benchmark Structure

Each case contains:

```json
{
  "case_id": "LOC-001",
  "question": "string",
  "gold_answer": "string (verified against actual source)",
  "gold_sources": [
    {
      "drive_file_id": "string",
      "filename": "string",
      "page": 3,
      "row": 5,
      "cell": "B5",
      "table_id": "string|null",
      "heading_path": ["3.2", "Sponsorship Revenue"],
      "source_text": "exact text excerpt"
    }
  ],
  "gold_locator": "string (human-readable)",
  "category": "exact|entity|semantic|numeric|date|currency|comparison|aggregation|temporal|spreadsheet|negative|conflict|nepali",
  "split": "development|validation|held_out_test",
  "author": "string",
  "verification_status": "verified|needs_review",
  "version": 1,
  "note": "string|null"
}
```

## 3. Categories (Minimum Coverage)

| Category | Min Cases | Description |
|----------|-----------|-------------|
| Exact lookup | 8 | Names, IDs, acronyms, exact amounts |
| Semantic question | 8 | "What is LOCUS?", "Describe the event..." |
| Numeric | 5 | Budget figures, counts, percentages |
| Currency | 5 | NPR amounts, multiple currency formats |
| Date/Temporal | 5 | Event dates, deadlines, reporting periods |
| Spreadsheet query | 5 | Row filtering, aggregations from tables |
| Buried answer | 5 | Answer in long document, mid-paragraph |
| Misspelling/abbreviation | 5 | Query formulation errors |
| Comparison | 4 | Compare two years, two sponsors, etc. |
| Multi-document | 4 | Cross-document synthesis |
| Negative/unanswerable | 4 | "Who was LOCUS president in 2019?" |
| Conflicting sources | 3 | Draft vs final, duplicate versions |
| Nepali/English mixed | 3 | Mixed-script queries and content |
| **Total** | **~65** | |

## 4. Evaluation Metrics

### 4.1 Retrieval Metrics
- **Recall@K**: Fraction of gold chunks appearing in top-K candidates
- **MRR**: Mean reciprocal rank of first correct chunk
- **NDCG**: Normalized discounted cumulative gain
- **Candidate-pool recall**: Gold in any retrieval candidate (not just top-K)

### 4.2 Answer Metrics
- **Faithfulness**: All claims verifiable against evidence
- **Completeness**: All sub-answers supported
- **Citation correctness**: Every citation points to the correct source
- **Abstention accuracy**: Correct abstention rate on unanswerable queries

### 4.3 System Metrics
- **Extraction success rate**: Clean extraction (no OCR) %
- **OCR-inclusive extraction**: With OCR fallback %
- **Processing throughput**: Documents/hour
- **Query latency**: p50, p95, p99

## 5. Calibration

For confidence scores (HIGH/MEDIUM/LOW/ABSTAIN):
- Construct reliability diagrams
- Measure Brier score and calibration error
- Ensure abstention rate does not exceed actual unanswerable fraction

## 6. Benchmark Phases

| Phase | Focus | When |
|-------|-------|------|
| A | Baseline (dense only) | Before Phase 5 |
| B | Hybrid retrieval | After Phase 6 |
| C | Reranking | After Phase 7 |
| D | Safety net | After Phase 8 |
| E | Generation + verification | After Phase 10 |
| F | Full system | After Phase 12 |

Every phase produces a delta report: `"Recall@20: 72% → 86% (+14pp)"`

## 7. Curation Rules

1. Gold answers are verified against actual source documents — never authored from memory
2. Sources reference real Drive file IDs from the existing catalog
3. Negative cases are verified to have no supportable answer in the corpus
4. Development cases are iterated on during development; held-out test is never touched until final evaluation
5. Production user feedback enters development split, not held-out

## 8. Failure Attribution

Each failed case is assigned to the earliest causal stage:
1. Corpus coverage (document not in catalog)
2. Extraction (document not properly read)
3. Normalization/chunking (text broken, heading lost)
4. Retrieval (correct chunk not in candidate pool)
5. Reranking (correct chunk in pool but not surfaced)
6. Evidence assembly (context lost)
7. Generation (LLM misuses evidence)
8. Verification (false claim not caught)

## 9. Seed Benchmark (Phase 1)

Phase 1 seed cases are derived from the corpus mime-type distribution:
- 2,766 PDFs → document Q&A cases
- 631 Google Sheets → spreadsheet query cases
- 951 Google Docs → structured document cases
- 169 CSVs → tabular data cases

Initial seed cases will be curated in `eval/benchmark/seed_cases.json`.
