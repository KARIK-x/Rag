# ADR-009 — Retrieval defect fixes + QueryAnalyzer filter removal

**Status:** Accepted  
**Date:** 2026-09-08  
**Related:** ADR-004 (vector store), ADR-005 (BM25), ADR-006 (chunking)

## Context

During master-build validation of Phase 6 (Hybrid Retrieval), several real defects
were found in the retrieval code that would cause false negatives (missed answers)
for legitimate queries:

1. **BM25 dropped provenance.** `BM25Index.add()` stored only text + length, and
   `search()` returned candidates with `doc_id=""` and `source_locator={}`. Retrieved
   evidence therefore had no path back to the source document — a violation of the
   provenance-preservation rule ("Every output must remain traceable to its source").

2. **`QueryAnalyzer` auto-injected metadata filters.** `analyze("Ncell sponsorship")`
   set `filters["doc_type"]="sponsorship"` via a keyword heuristic. That caused the
   HybridRetriever to post-filter candidates to only documents carrying the
   `doc_type=sponsorship` metadata tag, discarding the very chunk containing
   "Ncell sponsorship NPR 500000" when the label was absent or slightly different.
   This is the "premature closure" failure the spec forbids: *"If uncertain about
   routing, retrieve broadly rather than prematurely skipping evidence."*

3. **`rrf_fusion` contained dead duplicate code** — two consecutive identical loops
   computing the same fused scores, with the first result discarded.

4. **`HybridRetriever` used a naive `query.lower().split()` term analysis** instead of
   the rich `SearchQuery` analysis, so currency/amount queries like "NPR 50,000"
   produced terms `['npr', '50,000']` that the exact index could not match against
   its normalized token `"npr 50000"`. This is the known "NPR" exact-match issue
   previously flagged in PROGRESS.md as unresolved.

5. **`hybrid.py` `retrieve()` convenience wrapper used the constructor kwarg
   `metadata_index=` which does not exist** (constructor takes `metadata=`), so the
   public helper crashed whenever metadata was supplied.

6. **Dead duplicate `_load`/`_persist_chunk` definitions** in `ExactEntityIndex`
   shadowed persistence behavior.

## Decision

- `BM25Index` now stores per-chunk metadata (`doc_meta`) and `search()` returns
  `doc_id` + `source_locator` derived from it.
- `QueryAnalyzer` no longer infers filters from keywords. Filter routing is the
  exclusive responsibility of the Phase 7 `QueryRouter`, which applies explicit
  filters only.
- `HybridRetriever` now uses `QueryAnalyzer.analyze()` for terms/entities/dates/
  amounts, runs dense *and* BM25 *and* exact through RRF, drops the dead code, and
  post-filters with `search_query.filters` only.
- Duplicate method definitions removed.

## Consequences

- Correctness improves where it matters most: the founding failure (an indexed,
  retrievable answer being missed) is directly reduced.
- The auto-filter removal means no premature closure on "Ncell sponsorship"-type
  queries; `doc_type` filters still work when explicitly requested by the router.
- Regression coverage: `test_retrieve_sponsorship_query`,
  `test_exact_match_protected`, `test_recall_safety_net_*` all pass (114 unit tests).