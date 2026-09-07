# ADR-003: Embedding Model

**Status:** Proposed

## Problem
Dense semantic retrieval requires an embedding model. The model must perform well on LOCUS's multilingual (English/Nepali), acronym-heavy, numeric-rich, and entity-centric content.

## Candidates Considered
1. **BGE-M3** — Multilingual; dense/sparse/hybrid support; strong on 100+ languages; local
2. **Qwen3-Embedding** — Multilingual; competitive benchmarks; local
3. **multilingual-e5** — Good multilingual performance; local
4. **text-embedding-3-large (API)** — High quality; external dependency; paid

## Experiment Plan
1. Create a retrieval evaluation set from LOCUS corpus (100 query-chunk pairs with relevance labels)
2. Include: English queries, Nepali queries, mixed-script, acronym queries, numeric queries, buried answers
3. Evaluate each model: Recall@K, MRR, NDCG, candidate-pool recall
4. Measure: indexing speed, query latency, memory footprint, index size
5. Evaluate on low-memory hardware (8GB RAM target for local deployment)

## Decision Criteria
- Recall@20 ≥ 85% on LOCUS evaluation set
- Supports both English and Nepali without separate models
- Runs locally on representative hardware
- Index size manageable for corpus growth (target: < 5GB for 30k documents)

## Revisit Conditions
- Re-evaluate if corpus significantly expands in language coverage
- Re-evaluate if embedding model quality degrades on new LOCUS content
