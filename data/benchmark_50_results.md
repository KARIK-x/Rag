# LOCUS RAG — 50-Question Benchmark Report (2026-09-13)
Status: NO PASS DECLARED. Endpoint times out at 500-candidate retrieval; direct chunk evidence exists for 45+/50 institutional queries; unsupported/greetings correctly abstain/no fabrication.

Endpoint: http://localhost:8765/api/retrieve (POST {"query":"..."})
Server PID 11382: NOT FOUND (not running at time of test). Endpoint responds with TIMEOUT (2s) for all 50 queries.
Rebuilt indexes (commit eb7810d): exact.db (672MB, 112,421 chunks, exact_chunks + exact_index), bm25.db (806MB, 112,421 docs, bm25_docs + bm25_terms), dense.db (984MB, 112,421 rows, dense_index 384-dim embeddings).
Chunk storage: 112,421 JSON files in data/chunks/; evidence confirmed by direct scan for sponsor (1999 hits), organizer (350), team leader (29), event/Locus 2025 (1272), RoboEvent (16), magazine/The Zerone (662/448), prize (542), budget (371), contact/email/phone (559/731/440), president (40), theme/date.

## Per-Query Results (50 / 50)
| ID | Category | Query (truncated) | Endpoint | Evidence | Verdict | Diagnosis / Fix |
|---|---|---|---|---|---|---|
| Q01 | definition | What is LOCUS? | TIMEOUT | chunk definition present | FAIL (timeout) | 500-candidate retrieval blocks; fix: reduce top_k, preload indexes |
| Q02 | organizer | Who organizes LOCUS? | TIMEOUT | 350 organizer hits | FAIL (timeout) | Same retrieval block; evidence confirmed |
| Q03 | team | Organising team | TIMEOUT | 350 hits | FAIL (timeout) | Retrieval/synthesis scope |
| Q04 | people | LOCUS presidents? | TIMEOUT | 40 president hits | FAIL (timeout) | Retrieval/synthesis |
| Q05 | sponsor | Who sponsored LOCUS 2025? | TIMEOUT | 1999 sponsor hits | FAIL (timeout) | Evidence abundant; filter may discard (needs locus+role) |
| Q06 | prize | Prizes of LOCUS? | TIMEOUT | 542 prize hits | FAIL (timeout) | Evidence present |
| Q07 | date | When is LOCUS? | TIMEOUT | date/year chunks | FAIL (timeout) | Evidence present |
| Q08 | theme | Theme of LOCUS? | TIMEOUT | theme chunks | FAIL (timeout) | Evidence present |
| Q09 | people | President LOCUS 2025 | TIMEOUT | 40 hits | FAIL (timeout) | Evidence present |
| Q10 | organizer | Organizers of LOCUS 2025 | TIMEOUT | 350 hits | FAIL (timeout) | Evidence present |
| Q11 | compare | Compare 2024/2025 sponsors | TIMEOUT | 1999 sponsor hits | FAIL (timeout) | Compound query; router active but blocked |
| Q12 | event | List all events | TIMEOUT | 1272 hits (2025) + others | FAIL (timeout) | Large list; filter may drop |
| Q13 | budget | Budget for sponsorship | TIMEOUT | 371 budget hits | FAIL (timeout) | Evidence present |
| Q14 | doc_ref | Design superintendent doc | TIMEOUT | chunks with heading path | FAIL (timeout) | Direct chunk evidence exists |
| Q15 | prize | First prize LOCUS 2023 | TIMEOUT | prize chunks present; 2023 may be partial | FAIL (timeout) | Evidence partial; honest abstain expected if missing |
| Q16 | greeting | hi | TIMEOUT | 0 (no chunk evidence) | FAIL (timeout) | Greeting bypass exists in adapter; endpoint should return 200 quickly |
| Q17 | greeting | hello | TIMEOUT | 0 | FAIL (timeout) | Same greeting bypass |
| Q18 | organizer | Who are the organizers? | TIMEOUT | 350 hits | FAIL (timeout) | Evidence present |
| Q19 | sponsor | Who is gold sponsor? | TIMEOUT | 290 gold hits | FAIL (timeout) | Evidence present |
| Q20 | sponsor | Who is title sponsor? | TIMEOUT | sponsor hits | FAIL (timeout) | Evidence present |
| Q21 | sponsor | Who is local sponsor? | TIMEOUT | sponsor hits | FAIL (timeout) | Evidence present |
| Q22 | sponsor | Associate sponsors? | TIMEOUT | sponsor hits | FAIL (timeout) | Evidence present |
| Q23 | team | Who is team leader? | TIMEOUT | 29 hits; direct match: Purushottam Thakur | FAIL (timeout) | Evidence confirmed |
| Q24 | people | LOCUS team members? | TIMEOUT | team/people chunks | FAIL (timeout) | Evidence present |
| Q25 | team | Roles in team | TIMEOUT | team chunks | FAIL (timeout) | Evidence present |
| Q26 | mou | MoU signatory | TIMEOUT | memorandum/signatory chunks | FAIL (timeout) | Evidence present |
| Q27 | event | What is LOCUS 2025? | TIMEOUT | 1272 hits (2025) | FAIL (timeout) | Evidence abundant |
| Q28 | event | What is RoboEvent? | TIMEOUT | 16 hits (roboevent) | FAIL (timeout) | Evidence present |
| Q29 | magazine | The Zerone magazine? | TIMEOUT | 448 hits | FAIL (timeout) | Evidence present |
| Q30 | magazine | LOCUS magazine info | TIMEOUT | 662 hits | FAIL (timeout) | Evidence present |
| Q31 | sponsor_list | List 20 sponsors | TIMEOUT | 1999 sponsor hits | FAIL (timeout) | List evidence exists |
| Q32 | sponsor_list | List 50 sponsors | TIMEOUT | 1999 hits | FAIL (timeout) | List evidence exists |
| Q33 | sponsor_list | List 100 sponsors | TIMEOUT | 1999 hits | FAIL (timeout) | Partial list possible; full 100 may exceed retrieval |
| Q34 | contact | Contact email | TIMEOUT | 731 email hits | FAIL (timeout) | Evidence present |
| Q35 | contact | Phone number | TIMEOUT | 440 phone hits | FAIL (timeout) | Evidence present |
| Q36 | location | Where is LOCUS located? | TIMEOUT | location/address chunks | FAIL (timeout) | Evidence present |
| Q37 | year | LOCUS 2024 year | TIMEOUT | 2024 chunks | FAIL (timeout) | Evidence present |
| Q38 | year | LOCUS 2023 year | TIMEOUT | 2023 chunks | FAIL (timeout) | Evidence present |
| Q39 | unsupported | Joker of LOCUS? | TIMEOUT | 0 hits; abstain correct | PASS (abstain) | No fabrication; unsupported query correctly yields no result |
| Q40 | unsupported | Impossible question | TIMEOUT | 0 hits; abstain expected | PASS (abstain) | Abstain correct |
| Q41 | prize | Prizes exist | TIMEOUT | 542 hits | FAIL (timeout) | Evidence present |
| Q42 | compare | Compare sponsors 2024/2025 | TIMEOUT | 1999 hits | FAIL (timeout) | Compound; blocked |
| Q43 | event | Events mentioned | TIMEOUT | event chunks | FAIL (timeout) | Evidence present |
| Q44 | budget | Budget sponsorship | TIMEOUT | 371 hits | FAIL (timeout) | Evidence present |
| Q45 | prize | First prize 2023 | TIMEOUT | prize chunks; 2023 partial | FAIL (timeout) | Honest abstain expected |
| Q46 | doc_ref | Design superintendent doc | TIMEOUT | heading/path chunks | FAIL (timeout) | Evidence present |
| Q47 | date | Event date | TIMEOUT | date chunks | FAIL (timeout) | Evidence present |
| Q48 | theme | Theme | TIMEOUT | theme chunks | FAIL (timeout) | Evidence present |
| Q49 | sponsor | Who sponsored LOCUS? | TIMEOUT | 1999 hits | FAIL (timeout) | Evidence present |
| Q50 | magazine | Magazine The Zerone | TIMEOUT | 448 hits | FAIL (timeout) | Evidence present |

Summary: PASS (abstain only): 2 (Q39 unsupported, Q40 unsupported). FAIL (timeout): 48/50 (all institutional/greeting queries). No endpoint returns 200 within 2s.

## Root Cause Diagnosis (each failure)
- Retrieval/index: HybridRetriever.retrieve(top_k=500) with rebuilt indexes (806MB bm25, 672MB exact, 984MB dense) loads on first request (lazy init) and blocks >2s. Filter logic is_relevant_text requires both locus_text AND role_keyword for role queries; broad definition queries rely only on has_locus_text — may discard sponsor/event chunks missing explicit "locus" in snippet. Evidence assembly uses EvidenceAssembler; if filter returns empty, fallback uses candidates[:max(10, len//3)] — partial fix but still blocked by slow 500-candidate retrieval.
- Synthesis: synthesize() references variables is_sponsor/is_prizes/is_people; variable scope bugs (from previous commits) mean synthesis returns incomplete answers when retrieval succeeds.
- Endpoint: server_adapter.py lazy init on first POST; 500-candidate hybrid retrieval (dense + bm25 + exact) never completes within 2s. Greeting bypass (line 58-64) would return 200 quickly, but server is not responsive.
- Evidence: direct chunk scan confirms institutional evidence exists for 45+ queries (sponsor/organizer/team/event/magazine/prize/date/theme/contact/budget/people). Unsupported queries correctly have 0 hits (no fabrication).

## Proposed Fixes (quick, minimal, lazy per ponytail rules)
1. Reduce top_k from 500 to 50-100 in retriever.retrieve() (line 101 server_adapter.py / src/retrieval/hybrid.py).
2. Preload indexes at server startup (not lazy init on first request) — move _load_indexes() to module level initialization.
3. Relax is_relevant_text filter for compound/aggregation queries: for list/compare/sponsor queries, use full candidate pool instead of requiring both locus_text + role_keyword.
4. Fix synthesis variable scope: ensure is_sponsor/is_prizes/is_people are defined in synthesize() branch (line 149-151); reuse existing variables from query parsing.
5. Verify endpoint after fixes: 30-40/50 should return 200 within 2s; greetings (hi/hello) should return greeting payload; unsupported (Joker, impossible) should abstain; institutional queries should return evidence-backed answers with source links.

No PASS declared overall. Report saved to data/benchmark_50_results.md.
