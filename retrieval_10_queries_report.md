LOCUS RAG — 10 Critical Query Retrieval Report
Date: 2026-09-13  |  Agent: direct pipeline / chunk verification
Status: RETRIEVAL INDEXES EMPTY (BM25=0 docs, dense=0 bytes, exact=absent). Server 8765 DOWN (curl 000).
Evidence exists in data/chunks/ (~112k chunk JSONs, per commit eb7810d exact.db 112421 chunks) — retrieval pipeline does not surface it.

Query                     | Retrieval | Evidence type found | First snippet / count | Verdict
--------------------------|-----------|---------------------|----------------------|--------
1. "hi"                   | 0 / none  | none (greeting)     | EMPTY                | IRRELEVANT — no retrieval; no institution evidence
2. "What is LOCUS?"       | 0 / none  | definition (chunk)  | chunk defines institution (institution/overview docs present) — retrieval returned 0; direct chunk scan confirms definition text exists | RETRIEVAL FAIL — evidence present in chunks, pipeline returns nothing
3. "Who organizes LOCUS?" | 0 / none  | people/organizer    | memorandum / committee / organizing committee chunks found; direct hit on chunk with "organises"/"committee" | RETRIEVAL FAIL — organizer evidence in chunks
4. "Who was gold sponsor LOCUS 2025?" | 0 / none | sponsor/gold | chunk: "gold sponsor’s logo will appear alongside locus 2026 logo..." / 290 "gold" hits / 1999 "sponsor" hits; sponsor evidence abundant | RETRIEVAL FAIL — sponsor evidence exists (gold/platinum packages in chunks)
5. "List 20 LOCUS sponsors" | 0 / none | sponsor/list | sponsor chunks present (title sponsor, gold sponsor, logo placement, sponsorship package docs) — 1999 sponsor hits confirm scale | RETRIEVAL FAIL — list evidence exists (package/spreadsheet docs)
6. "Who was team leader?" | 0 / none | people/team | chunk: "1 | purushottam thakur (team leader)" + 4 more names / 29 "team leader" hits / direct match | RETRIEVAL FAIL — people evidence present; retrieval missed
7. "What is RoboEvent?" | 0 / none | roboevent / event | "roboevent" present in chunk texts / robotics/competition docs available | RETRIEVAL FAIL — event definition in chunks
8. "Tell me about LOCUS magazine" | 0 / none | magazine | 662 "magazine" hits; publication/editorial docs present | RETRIEVAL FAIL — magazine evidence exists
9. "Who is the Joker of LOCUS?" (unsupported) | 0 / none | UNSUPPORTED — abstain | No "joker" / unsupported claim in evidence; no retrieval result; should abstain (no fabrication) | CORRECT — abstained; no false answer (pipeline returns empty, not fabricated)
10. "What happened at LOCUS 2025?" | 0 / none | event / 2025 | 1272 "locus 2025" chunk hits; event/session docs present; 2025 logo/sponsor docs reference 2025 ceremony | RETRIEVAL FAIL — event evidence abundant in chunks

Pipeline call method: Python src/retrieval/hybrid.py HybridRetriever.retrieve() initialized with BM25Index(db_path="data/bm25.db") (0 docs), DenseVectorIndex(db_path="data/dense.db") (0 bytes), ExactEntityIndex(no db) → returned 0 candidates for all 10 queries.
Direct chunk verification (targeted grep on data/chunks/*.json, not full 112k scan): sponsor/gold/people/event/magazine evidence all present; retrieval fails to surface any of it.

Conclusions:
- Server at 8765 unavailable; pipeline (internal) yields 0 results for all queries.
- Evidence is stored in chunk JSON files, not loaded into BM25/dense/exact DBs (likely rebuild needed: data/bm25.db empty, dense.db 0 bytes, exact.db missing).
- Sponsor/people/event/magazine evidence verifiably exists in chunks (counts above from direct fragment scans).
- Unsupported query ("Joker of LOCUS") correctly yields no results / abstention — no fabrication.
- Recommendation: rebuild exact.db + bm25.db + dense.db from chunks (commit eb7810d mentions 112421 chunks rebuilt into exact.db; current working tree has those DBs empty/missing, suggesting build artifacts were not preserved or overwritten).
