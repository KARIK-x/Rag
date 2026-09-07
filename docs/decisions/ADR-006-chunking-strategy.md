# ADR-006: Chunking Strategy

**Status:** Proposed

## Problem
Chunk quality directly determines retrieval quality. Naive fixed-size chunking loses heading context, splits tables, and creates incoherent chunks. LOCUS documents have significant structural hierarchy (headings, sections, tables, lists).

## Candidates Considered
1. **Heading-aware recursive splitting** — Split on heading boundaries; respect document hierarchy; recurse on long sections
2. **Page-aware chunking** — One page = one chunk; fast; preserves reading order; may split semantic units
3. **Table-aware chunking** — Keep tables intact; split only surrounding text; special handling for multi-page tables
4. **Sentence-level splitting with sliding window** — Fine-grained; good for buried answers; high chunk count; may lose context
5. **Heading + table hybrid** — Heading context prefixed to table; table kept intact; text split by heading

## Experiment Plan
1. Apply each strategy to 50 diverse LOCUS documents
2. Human evaluation: coherence, context preservation, table integrity
3. Automated evaluation: compare chunk text to gold passage retrieval
4. Measure: average chunk length, chunk count, table preservation rate, heading preservation rate

## Decision Criteria
- Heading context preserved in ≥ 95% of chunks
- Tables kept intact in ≥ 90% of cases
- Average chunk length 300–800 tokens (adjustable)
- Retrieval recall improvement vs fixed-size baseline ≥ 5pp

## Revisit Conditions
- Re-evaluate if LOCUS document format mix changes significantly
- Re-evaluate if embedding model context window changes
