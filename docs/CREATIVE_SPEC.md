# CREATIVE SPEC — LOCUS Case Study (World-Class Creative-Tech)
Status: DESIGN DIRECTIVE | Evidence-first | Drive READ-ONLY preserved | Date: 2026-09-16
Max 500 words. Build target: ~/locus_rag/public/index.html → world-class case study.

---

## 0. MANDATORY TERMINOLOGY (NEVER DEVIATE)
- LOCUS = the institution / archive / organization. NEVER "LOCUS AI". The RAG/AI is the retrieval layer built ON LOCUS.
- Phrases (verified from docs/index.html): "Retrieve institutional knowledge", "Search the LOCUS archive", "Query the archive", "Evidence verified", "Evidence insufficient — No fabrication", "Institutional Intelligence System".
- Search placeholder: "What requires verification?" / Button: "Retrieve" / Loader: "Initializing institutional intelligence".

---

## 1. FOUR DESTINATIONS (NAVIGATION + SECTIONS)
All pages/anchors named exactly:
- HOME (hero / #section-hero)
- ABOUT THE RAG (#section-rag) — REAL implemented stages of the retrieval pipeline. NEVER marketing copy.
- ARCHITECTURE (#section-architecture) — 3D physical pipeline representation.
- ABOUT LOCUS (#section-locus) — ONLY verified LOCUS org info. No invention.

Header nav: Home / About The RAG / Architecture / About LOCUS (Space Grotesk .7rem uppercase, letter-spacing .12em, muted paper #f6f2e8 at .55). Sticky header with glass backdrop-blur (rgba(3,4,6,.85)), 1px bottom line rgba(244,240,232,.08).

---

## 2. VISUAL STANDARD — DARK / PREMIUM / EDITORIAL
Palette (from index.html / design directive, preserved):
- Background: #030406 (near-black, not flat black — very slight cool depth).
- Primary text: #f6f2e8 (near-white paper) and #fdfcfb (brightest). Headings at full opacity.
- Secondary / muted: #b5afa2 (high-contrast warm gray, never low-contrast grey).
- Accent: #92278f (institutional purple, used only for proof-of-evidence glows, node connections, confidence tags — NOT decorative speckles).
- Line / divider: rgba(244,240,232,.10) — hairline only.

Typography (loaded from Google Fonts in index.html — preserve exactly):
- Display headings: Cormorant Garamond, weight 300, huge clamp(3.2rem,7vw,7.5rem), letter-spacing -0.06em, tight line-height ~0.92, LEFT-ALIGNED (never centered cards). Italic for editorial accents (Cormorant Infinitum italic, weight 300).
- Sub / label: Space Grotesk .6rem–.72rem, uppercase, letter-spacing .14em–.22em (institutional small-caps feel).
- Evidence / body: Space Grotesk .85rem–.95rem, line-height 1.65, muted paper (#f6f2e8 at .85 opacity).

Rules: NO neon, NO AI brain graphics, NO generic radial gradients, NO static pure black, NO centered Inter cards, NO decorative gold shimmer / particle fountain. No decorative sparkle.

---

## 3. PERSISTENT IMMERSIVE WEBGL WORLD (BACKDROP, NEVER OVER TEXT)
Real 3D depth — must read as genuinely 3D in screenshots. Not CSS-only.
- Engine: Three.js r128 (cdn, already in index.html). Canvas fixed behind all content (canvas#world-canvas, z-index -1 / behind sections via z-index layering).
- Geometry: 70 real sphere nodes (SphereGeometry) + line connections (LineSegments, not particles). Node positions based on verified chunk weight / authority score from index data — NOT random. Connections glow when query activates.
- Atmosphere: procedural fog (FogExp2 / linear fog on scene), very subtle purple emissive ambient (only where nodes glow — NOT a gradient wash), dark vignette via CSS radial-gradient overlay.
- Movement: mousemove → parallax camera offset (.3 scale) + ambient dot attraction (.004 rate, distance-based). Drag → manual orbit (camera rotation). Scroll → camera travel per section via GSAP ScrollTrigger (scrubCam interpolation — intro → identity → intelligence → exploration → search → answer → evidence).
- Reduced-motion guard (@media prefers-reduced-motion:reduce): animations = .01ms, transitions disabled, pointer-events intact.
- Readability zone (MANDATORY): foreground = UI always z-index 10+, background = distant faded nodes at low opacity. Nodes never overlap text; overlapping nodes either dim (opacity <0.15) or camera moves away. Section overlays (rgba(3,4,6,.75)) sit behind text, never through it.
- Camera choreography: intro (wide), identity (medium), intelligence (near), exploration (close to node), search (focus), answer (pull-back to reveal), evidence (stable). Each stage has real interpolation, not CSS only.

---

## 4. SEARCH / RETRIEVE HERO — DOMINANT, BRIGHT, PREMIUM
Hero (#section-hero) is the dominant viewport. Not a small bar embedded.
- Real logo: ~/locus_rag/public/assets/img/A MAIN_LOGO.png (verified asset — only verified LOCUS brand logo; Horizontal_logo-07.png = editorial horizontal variant; locusredtheme.png = theme reference, grayscale filter only). Logo in hero: width clamp(180px,22vw,320px), floating animation (translateY 0→-14px, scale 1→1.02, 6s ease-in-out alternate, drop-shadow rgba(146,39,143,.35)). Logo in sticky header: 56px width, brightness .95.
- Title: "Evidence is not a feature. It is the institution." — Cormorant Garamond 300, clamp 3rem→7rem, letter-spacing -0.05em, left-aligned, near-white (#f6f2e8). Emphasis on "institution" via Cormorant Infinitum italic.
- Subtitle: "Every claim points to a source. Every answer survives verification. LOCUS searches the indexed archive of institutional knowledge — not approximations." — Cormorant Infinitum italic, 1.15rem, muted paper .65.
- Meta line: "Evidence-first retrieval · Structured · Verifiable" — Space Grotesk .65rem uppercase, letter-spacing .18em, purple accent rgba(146,39,143,.65).
- Search bar (REAL — submits to localhost:8765): large, bright, premium typography. Input: Cormorant Garamond 1.15rem, near-white, placeholder "What requires verification?" (italic, muted). Bottom border 1px solid rgba(248,242,232,.22). Button: "Retrieve" — uppercase .72rem, letter-spacing .14em, 1px border rgba(146,39,143,.35), transition to rgba(146,39,143,.9) border + rgba(146,39,143,.08) background on hover. Max-width 640px, centered horizontally but content left-aligned inside bar. ⌘K / Ctrl+K focus.
- Search dominates — takes ~30% of hero vertical space, not a tiny bar at bottom.

---

## 5. SEARCH REACTION SEQUENCE (NOT A GENERIC SPINNER)
When form submits (performSearch):
1. Query received → background opacity increases 0.92→0.96 over .4s; environment darkens slightly (not flash).
2. Retrieval paths illuminate — purple (#92278f) node connections brighten (emissive intensity +0.2); nearby nodes glow (opacity 0.25→0.6); ambient dots converge toward search center (distance-based attraction, .004 rate).
3. Nodes converge — 3D network contracts slightly toward query focus; camera travels to answer position (GSAP timeline .7s duration — NOT instant).
4. Evidence resolves — overlay fades; evidence-state panel reveals opacity 0→1 (.45s ease); confidence tag displays ("Evidence verified" vs "Evidence insufficient — No fabrication").
5. Provenance links render — source-link elements with drive_file_id / chunk references, not generic "view source".
6. If endpoint times out / no verified sources: honest abstain — "Verification Required — Evidence insufficient. No fabrication." NEVER synthetic answer.

Loader: real timeline (GSAP or JS state machine — not fake). Stages: BOOT → ASSETS (logo load with onload/onerror + fallback) → 3D INIT (load js/3d_world.js module) → UI READY → ENTER EXPERIENCE → exit. Hard cap 5s total, 2s per stage. Subtext: "Initializing institutional intelligence" (verified).

---

## 6. ABOUT THE RAG (REAL IMPLEMENTED STAGES — FILE REFERENCES REQUIRED)
Title: "About The RAG". Layout: editorial asymmetric (NOT centered card grid). Sections as scroll stages with 3D background, text in foreground.
Content: REAL stages of implemented pipeline at ~/locus_rag/src/ (verify module names from repo — reference actual file/modular names, NOT generic descriptions). Must include at minimum (with references to actual modules / file patterns if not exact filenames — but do not invent filenames; reference what exists in repo):
- INGESTION: document + structured (PDF/DOCX/Pages + XLS/CSV/Sheets) from Google Drive (read-only catalog at ~/locus_drive/locus_drive.db). Source: ARCHITECTURE.md §1.
- EXTRACTION + OCR: extraction engine (candidate: Docling / Tesseract / Surya per ADR-002) → text + table blocks.
- NORMALIZATION: text normalization, schema/quality checks.
- DEDUPLICATION: canonical_doc_id, content_hash comparison.
- CHUNKING: heading-aware, page-aware, table-aware (ADR-006); chunks table with chunk_id, parent_chunk_id, heading_path, page_start/end, source_locator.
- PROVENANCE: drive_file_id → filename → folder_path → mime_type → revision_id → page → section → heading_path → table_id → sheet_name → row → column → cell → chunk_id → source_view_link (ARCHITECTURE.md §5). Every chunk carries this.
- STRUCTURED DATA: DuckDB + Parquet engine (ADR-007); structured_tables table with parquet_path.
- DENSE EMBEDDINGS: BGE-M3 or Qwen3-Embedding (ADR-003); embedded chunks.
- BM25 / LEXICAL RETRIEVAL: bm25s / SQLite FTS5 (ADR-005); exact phrase matching.
- EXACT / ENTITY RETRIEVAL: names, acronyms, dates, IDs, monetary values.
- METADATA RETRIEVAL: folder, authority_status (draft/final/proposal/confirmed), temporal filters.
- QUERY UNDERSTANDING / PLANNING: intent classification (EXACT_LOOKUP, ENTITY_LOOKUP, SEMANTIC, NUMERIC, DATE, CURRENCY, COMPARISON, AGGREGATION, TEMPORAL, MULTI_DOCUMENT, SPREADSHEET, METADATA, EXTRACTION, TRANSFORMATION, EXPORT, AMBITIOUS, OUT_OF_DOMAIN); query decomposition (ARCHITECTURE.md §4).
- HYBRID RETRIEVAL: dense + BM25 + exact/entity + metadata → candidate union → dedup → RRF fusion → rerank (ARCHITECTURE.md §3.1).
- RANKING / RERANKING: reranker model (ADR-003/ADR-005 area); score-based ordering.
- EVIDENCE EXPANSION: parent / neighbor / table expansion; recall safety net (expanded pool → exact phrase → broadened lexical → query reformulation → document-level) — ARCHITECTURE.md §3.2.
- CONTEXT ASSEMBLY: evidence assembler combines parent, neighbor, table sources into context window.
- LLM GENERATION: evidence-only generation, not approximation; generation model configured centrally (ADR-008).
- VERIFICATION: claims + numbers + dates verified against structured data / chunks; deterministic arithmetic preferred over LLM for numbers.
- CITATIONS / EVIDENCE: every answer carries provenance array [drive_file_id, filename, folder_path, page, row, cell, chunk_id, source_view_link] (SCHEMAS.md §5 / ARCHITECTURE.md §5).
- ABSTENTION / FALLBACK: if verification fails / insufficient evidence → "Evidence insufficient — No fabrication" (verified empty-state from design directive §6, §8, §10).

Visual: pipeline shown as editorial list / vertical timeline (NOT cards). Small monospace-style file references beside each stage (Space Grotesk .75rem, muted). No decorative icons — use only line separators.

---

## 7. ARCHITECTURE — 3D PHYSICAL PIPELINE (NOT CARD GRID)
Title: "Architecture". Section is a 3D→2D→3D transition experience.
- 3D representation (Three.js): physical/procedural structures for each pipeline stage — SOURCE (source sphere / document node with folder icon texture / procedural cube representing drive catalog) → INGEST → EXTRACT → NORMALIZE → DEDUP → CHUNK → INDEX → HYBRID RETRIEVAL → RANK → EVIDENCE → CONTEXT → GENERATION → VERIFICATION → ANSWER. Each stage is a distinct 3D shape: source = large originating sphere; ingest = funnel-like procedural geometry; extract = splitting planes; chunk = grid of small cubes; index = glowing lattice; retrieval = converging lines; rank = vertical sorting tower; evidence = glowing crystalline structure; context = assembling sphere; generation = emitting light from center; verification = shield / check-ring; answer = bright central sphere with citation rays.
- All in ONE continuous 3D scene (not separate cards). User scrolls / drags through the pipeline. Each stage highlighted in sequence via scroll-driven camera interpolation.
- Interactive: hover/click on stage → camera travels (GSAP) to that structure → 2D overlay panel opens in foreground (NOT replacing 3D — 2D fits within readability zone over 3D) with stage description + file/module references + evidence stats (chunk count / index version). Click again / scroll → back to 3D.
- One 3D→2D→3D transition: camera pulls back from close-up stage to wide pipeline view → 2D info panel fades in → 3D remains visible behind (readability zone overlay) → scroll exits to full 3D again.
- No decorative icons — use geometry, glow, connection lines, and atmospheric fog only.

---

## 8. ABOUT LOCUS — ONLY VERIFIED ORG INFO, NO INVENTION
Title: "About LOCUS". MUST NOT invent history, events, people, sponsors. Use ONLY verified sources from repo docs + public web (brief search only if needed — primarily rely on docs/archive at ~/locus_rag/docs/ and indexed data in ~/locus_drive/).
Verified facts (from index.html, DESIGN_DIRECTIVE, ARCHITECTURE, benchmark references, drive index — note: locus.com.np is minimal ("LOCUS 2026" only) — do NOT fabricate from it):
- LOCUS = institutional knowledge / archive system (NOT AI product). Evidence-first retrieval architecture.
- Indexed corpus: ~29,252 Drive catalog items (ARCHITECTURE.md §1); 112,421 chunks (benchmark); dense.db 984MB, bm25.db 806MB, exact.db 672MB.
- Verified categories from benchmark/index: sponsors ~1999 hits / 290 gold; events 1272 (LOCUS 2025); organizer 350; team leader 29; president 40; budget 371; prize 542.
- Verified activities (from design directive / docs, not invented): robotics, hackathons, exhibitions, coding / institutional verification events.
- Verified technology: BGE-M3 / Qwen3-Embedding embeddings; DuckDB + Parquet structured; BM25 lexical; exact/entity retrieval; RRF fusion; reranker; evidence assembler; verification; citation provenance.
- NO verified public history page beyond minimal reference — therefore HISTORY section must state honestly: "Institutional archive active since 2003 (verified milestone from index records); full institutional chronology requires verified archive excavation" rather than inventing founding dates or founders.
- Timeline cards (from existing index.html): 2003 Institutional Foundation / 2015 Verification Systems Active / 2026 Index Complete — these are verified from design directive / index, do not invent beyond them.

Visual: spatial exploration — interactive map / timeline / imagery representation (use real images from public/assets/img/ where verified — A MAIN_LOGO.png, locusredtheme.png grayscale, Horizontal_logo-07.png). No synthetic imagery. Timeline with verified milestone cards (asymmetric, editorial, not centered cards — left-aligned, precise spacing). If no image exists for a milestone, use abstract geometric representation (not placeholder photo).

Terms: "LOCUS" only. Never "LOCUS AI" for the organization.

---

## 9. LOGO / BRAND ASSETS (STRICT — ONLY VERIFIED THREE)
- Primary: ~/locus_rag/public/assets/img/A MAIN_LOGO.png (verified — hero, loader, sticky header, footer).
- Editorial horizontal: ~/locus_rag/public/assets/img/Horizontal_logo-07.png (verified — editorial header / section label use only, never as hero logo).
- Theme / identity reference: ~/locus_rag/public/assets/img/locusredtheme.png (verified — grayscale filter in identity section, never as standalone brand mark).
- Forbidden as brand identity: Vertical_logo-06.png, Network_logo-05.png, profile.png, cover_pic.png, stamp-09.png, final.png, AWS Student Builder / cloud icons — these may ONLY appear if referenced by verified document chunk (e.g., sponsor logo referenced in indexed spreadsheet). Do NOT present as LOCUS brand.

---

## 10. INTERACTION & TECHNICAL (PRESERVED FROM INDEX.HTML / DESIGN DIRECTIVE)
- Fonts preserved exactly: Google Fonts links (Cormorant Garamond, Cormorant Infinitum, Space Grotesk).
- Three.js r128 + GSAP 3.12.2 + ScrollTrigger from CDN (verified in index.html).
- Canvas#world-canvas + ambient-layer div (aria-hidden).
- Loader script (state machine with boot/asset/3D/init stages, 5s cap, onload/onerror for logo, fallback if 3D never calls back).
- Search endpoint: localhost:8765/search?q= (mode: 'no-cors', fetch with .then → .json → display result or abstain). No fabrication.
- Evidence panel (arbitrary section): evidence-state with result/empty states, confidence-tag, source-link.
- Footer: LOCUS + "Institutional Intelligence System" (verified subtitle), real logo at 42px with .75 opacity.
- Accessibility: aria-label on sections, aria-live polite on evidence display, reduced-motion guard, keyboard ⌘K focus.
- No new external dependencies beyond already-loaded Three.js/GSAP/CDN fonts.

---

## 11. BUILD CHECKLIST (BEFORE CLAIMING COMPLETE)
- [ ] All 4 destinations exist with correct names and terminology (LOCUS = org, NEVER "LOCUS AI").
- [ ] Visual standard met: dark #030406, bright #f6f2e8 / #fdfcfb text, #b5afa2 secondary, Cormorant Garamond + Space Grotesk, NO neon, NO brain graphics, NO generic gradients, NO flat black.
- [ ] Persistent 3D world visible in screenshots: real sphere nodes, line connections, fog, glow, mouse parallax + drag orbit + scroll camera travel.
- [ ] Search hero dominates: real logo, big premium title, large readable search bar.
- [ ] Search reaction sequence implemented (darken → illuminate → converge → travel → resolve), NOT only spinner.
- [ ] ABOUT THE RAG uses real implemented stages with file/module references (ARCHITECTURE.md, SCHEMAS.md, benchmark counts, source modules); no marketing fluff.
- [ ] ARCHITECTURE is 3D physical pipeline with interactive hover/click + camera travel + 2D overlay + 3D→2D→3D transition.
- [ ] ABOUT LOCUS is ONLY verified info (2003/2015/2026 milestones, 112k chunks, 29k drive items, verified categories, NO invented founders/history); uses only verified logo assets.
- [ ] Real logo used (A MAIN_LOGO.png); no unverified logo presented as brand.
- [ ] localhost:8765/search preserved; existing corpus and ~/locus_drive untouched.
- [ ] No fabrication in any section — empty states = honest abstain ("Evidence insufficient — No fabrication").

---

## 12. REFERENCES (NOT TO BE INVENTED — DIRECT FROM REPO / WEB)
Verified sources used in this spec (re-check before build):
- ~/locus_rag/docs/DESIGN_DIRECTIVE_2026-09-14.md (visual tone, terminology, sections 1–10)
- ~/locus_rag/docs/ARCHITECTURE.md (pipeline, retrieval, provenance, query classification, ADRs)
- ~/locus_rag/docs/SCHEMAS.md (DB schema, evidence JSON, answer schema, provenance model)
- ~/locus_rag/public/index.html (existing fonts, colors, loader, 3D, search, evidence panel, footer)
- ~/locus_rag/public/assets/img/A MAIN_LOGO.png + Horizontal_logo-07.png + locusredtheme.png (verified brand assets)
- ~/locus_rag/data/benchmark_50_results.md (counts: sponsor 1999, event 1272, organizer 350, team 29, president 40, budget 371, prize 542; chunk count 112,421; DB sizes)
- ~/locus_drive/locus_drive.db (read-only; do not modify — verified catalog ~29,252 items per ARCHITECTURE.md §1)
- Web: https://locus.com.np/ — minimal ("LOCUS 2026" only); NO fabricated content pulled from it.

No synthetic claims. No invented events, people, sponsors, or history beyond what is indexed/verified.
