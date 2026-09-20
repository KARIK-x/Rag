# LOCUS DESIGN DIRECTIVE — Award Redesign (2026-09-14)
For: 3D Engineer, GSAP/Interaction, UX Architect, Frontend, QA
Status: IN PROGRESS | Evidence-first | Drive READ-ONLY preserved

---

## 1. VISUAL TONE (CONFIRMED)

Real terms only: abstract geometric core, institutional intelligence, evidence-first retrieval architecture.
NOT "SaaS landing page". NOT "AI chatbot". NOT a marketing funnel.

REJECTED (verified in spec): beige cartoon head, gold shimmer particle fountain, decorative sparkle, generic SaaS gradients.
PRESERVED (from docs/assets/index.html): dark institutional palette — #030406 background, #92278f purple accent, #f6f2e8 paper text. Low ambient light. High contrast only where evidence resolves. Glass surfaces only where they reflect real document provenance (not decorative).

Mood: institutional memory being consulted, not a product being sold.
No decorative particle fountains. No gold shimmer. No beige cartoon head.

---

## 2. 10-SECTION NARRATIVE ARC (ONE SENTENCE EACH — VISUAL IDENTITY)

Every section is a full-viewport scroll stage with 3D network in the BACKGROUND and UI always IN FRONT (see Section 3).

1. HERO — Large animated A MAIN_LOGO.png (real), massive Cormorant Garamond title ("Evidence is not a feature. It is the institution."), real RAG search bar (fetches localhost:8765), loader timeline via GSAP.
2. WORLD — Persistent Three.js geometric core: 70 sphere nodes + line connections (real geometry, not particles), subtle ambient dot layer, camera responds to mouse/scroll.
3. HISTORY — Deep background network fades to fog; editorial asymmetric typography, no centered cards; verified LOCUS context only.
4. EVENTS — Verified indexed events from data (e.g., LOCUS 2025, 1272 hits in chunks; LOCUS 2027 partnership/spreadsheet records). If specific event categories have no chunk evidence for a given query, graceful empty state — NO FABRICATION.
5. PEOPLE — Verified people data only: organizer hits (350), team leader (29), president (40), mentor/instructor (from 2027 spreadsheets). No synthetic profiles.
6. SPONSORS — Verified sponsor data exists (1999 sponsor hits, 290 gold hits). Show real sponsorship categories; never invent sponsor names.
7. INNOVATION — Retrieval architecture visualization (dense + BM25 + exact/entity paths). Not decorative — shows the evidence pipeline from ARCHITECTURE.md.
8. KNOWLEDGE — Evidence-first claim: the system retrieves ABOUT LOCUS from verified Drive-indexed records, not approximations. Typography: "Retrieve institutional knowledge."
9. SEARCH — Real interactive query form (⌘K focus, submit triggers fetch to localhost:8765). Retrieval moment described in Section 6.
10. ANSWER + EVIDENCE — Evidence panel with verification tags, provenance links, source citations, confidence indicators. If no verified sources present, display honest abstain: "Verification Required — Evidence insufficient. No fabrication."

---

## 3. PROTECTED READABILITY ZONE RULE (MANDATORY)

This is the single most important spatial rule. Break it = redesign request.

- FOREGROUND = UI (text, buttons, evidence panels, labels). Always highest z-index. Always fully readable. No exception.
- MIDGROUND = interactive objects (3D node geometry, hover-glow connections, camera-travel targets). Nodes never overlap text blocks. Connections glow behind text, never through it.
- BACKGROUND = distant network (faded, low opacity nodes at z = distance). Only atmospheric.
- FAR = fog / atmosphere (#030406 gradient, minimal purple emissive, reduced-motion guard active).

Text always visually IN FRONT of 3D network. The network never crosses text. If a node's projected screen position overlaps a text block, the node either dims (opacity < 0.15) or the camera moves.

---

## 4. TYPOGRAPHY DIRECTIVE (REAL FONTS FROM INDEX.HTML)

Fonts (confirmed loaded): Cormorant Garamond (font-d), Cormorant Infinitum (font-s), Space Grotesk (font-b).

- Display headings: Cormorant Garamond, weight 300, HUGE (clamp(3.2rem, 7vw, 7.5rem) minimum), tight tracking (-.06em), asymmetric left-aligned layouts preferred (not centered cards).
- Sub/display: Cormorant Infinitum italic for editorial accents (hero-sub, labels).
- UI / labels: Space Grotesk .6rem–.72rem, uppercase, letter-spacing .14em–.22em (institutional small-caps feel).
- Evidence body: Space Grotesk .85rem–.95rem, line-height 1.65, muted paper (#f6f2e8 at .85 opacity).
- Never: generic centered Inter cards, generic sans-serif hero, decorative serif without tracking control.

Spacing: precise (not generous-generic). Label → content gap = 2rem. Section padding = 10vh 6vw. No auto-centered cards.

---

## 5. REAL INTERACTION LANGUAGE (NOT CSS-ONLY)

Every interaction must use real event handling or GSAP — NO fake CSS-only hover.

- MOUSE MOVE (mousemove event) → parallax camera offset (.3 scale) + ambient dot follow (distance-based attraction, .004 rate). Verified in index.html.
- HOVER (mouseenter/mouseleave) → nearby nodes brighten (emissive intensity +0.2), connections glow (opacity 0.25 → 0.6), tooltip appears with verified provenance snippet. Not decorative — tooltip pulls from indexed chunk data.
- CLICK → focus mode: camera travels to target node via GSAP ScrollTrigger or direct timeline; node details panel opens in foreground; evidence state updates.
- DRAG (mousedown/mousemove/mouseup) → rotate 3D world (camera orbit, manual control). Confirmed by 3D scene setup.
- SCROLL (ScrollTrigger) → travel through environment: camera positions interpolate per section (intro, identity, intelligence, exploration, search, answer, evidence). Real scroll-choreography (scrubCam), NOT CSS smooth-scroll only.
- ⌘K (keydown metaKey + k) → focus evidence-query input; open command palette behavior (search-first).

Reduced-motion guard (@media prefers-reduced-motion:reduce): animations disabled, transitions = .01ms, pointer-events unchanged.

---

## 6. RETRIEVAL MOMENT (MANDATORY SEQUENCE — NOT A SPINNER ONLY)

When a query is submitted: the environment responds. There is NEVER only a "Loading..." spinner.

Sequence (verified from index.html retrieve overlay + 3D world):
1. Query received → environment darkens (background opacity increases from 0.92 to 0.96 over .4s).
2. Retrieval paths illuminate — purple node connections brighten; nearby nodes glow; ambient dots converge toward search center.
3. Nodes converge — 3D network contracts slightly toward query focus; camera travels (GSAP timeline, .7s duration) to answer position.
4. Evidence resolves — overlay fades out; evidence-state panel reveals with opacity 0 → 1 (.45s ease); confidence tag displays ("Evidence verified" OR "Evidence insufficient — No fabrication").
5. Provenance links render (source-link elements) pointing to verified drive_file_id / chunk references.

If endpoint times out (confirmed in benchmark_50_results.md): graceful abstain message — NEVER fabricate. System must say: "No verified sources present" or "Verification Required — Evidence insufficient."

---

## 7. ONE UNUSUAL FEATURE RECOMMENDATION (JUSTIFIED FROM ASSETS/DOCS)

From verified options (navigable miniature LOCUS world, interactive knowledge constellation, gravitational node system, memory excavation, spatial archive timeline):

RECOMMENDATION: Interactive Knowledge Constellation (gravitational node system + spatial archive timeline hybrid).

Justification: The 3D world in index.html already implements 70 real sphere nodes with line connections, mouse parallax, and scroll-controlled camera travel. The benchmark confirms 112,421 indexed chunks with real provenance (chunk_id, source_locator, heading_path, page, row). A gravitational constellation extends the existing geometry: nodes have verified institutional weight (chunk count per doc, authority_score, evidence frequency) rather than random positions. Click = travel to node + reveal its verified chunk list + provenance. Drag = manual orbit. Scroll = travel through the archive timeline. This is NOT decorative — it is the indexed dataset visualized.

Alternative option (memory excavation) requires synthetic excavation UI with no verified data — REJECTED. Miniature world requires synthetic terrain — REJECTED. Spatial timeline alone lacks interaction depth — partial only.

---

## 8. NO FABRICATION RULES (MANDATORY — VERIFIED DATA ONLY)

Every category below is confirmed from real docs/assets/indexed data. If empty for a specific query or section, handle gracefully — never invent.

SPONSORS: Verified — 1999 sponsor hits, 290 gold hits, budget chunks (371). Source: eligible_sources.csv + benchmark_50_results.md. REAL NAMES exist (e.g., from indexed documents). If a query asks for sponsors with no verified match, return abstain.
EVENTS: Verified — 1272 event hits (LOCUS 2025), 2027 spreadsheet records (Ambassadors, Instructors/Mentors, Software Fellowship, Community Partnership FINAL SIGNED). REAL events confirmed.
PEOPLE: Verified — organizer (350 hits), team leader (29), president (40), mentor/instructor (2027 spreadsheets). REAL people from verified records.
INNOVATION / RETRIEVAL / EVIDENCE / SEARCH / ANSWER: Defined in ARCHITECTURE.md, SCHEMAS.md, index.html RAG pipeline (localhost:8765 endpoint), benchmark files (112,421 chunks, dense.db 984MB, bm25.db 806MB, exact.db 672MB).

BRAND ASSETS ONLY (confirmed): A MAIN_LOGO.png (assets/logo/A MAIN_LOGO.png + root assets/img/), Horizontal_logo-07.png, locusredtheme.png. Any other logo file (e.g., Network_logo-05.png, AWS icons, Vertical_logo-06.png) must NOT be presented as LOCUS brand — only reference if relevant to a verified document.

IF A CATEGORY IS EMPTY for a query: display honest message — "No verified sources present at this time. Evidence requires confirmation." (verified from index.html empty state). NO synthetic profiles, NO placeholder names, NO fabricated events.

---

## 9. BRAND ASSETS (CONFIRMED FROM ASSETS/LOGO/)

Only these three are verified LOCUS brand assets:
- A MAIN_LOGO.png (assets/img/A MAIN_LOGO.png; assets/logo/A MAIN_LOGO.png) — used in hero, loader, header.
- Horizontal_logo-07.png (assets/img/Horizontal_logo-07.png; assets/logo/Horizontal_logo-07.png) — editorial horizontal variant.
- locusredtheme.png (assets/img/locusredtheme.png; assets/logo/locusredtheme.png) — identity/theme reference, grayscale filter in identity section.

No other logo file (Vertical_logo-06.png, Network_logo-05.png, AWS Student Builder icons, profile.png, stamp-09.png, final.png, cover_pic.png) is a verified LOCUS brand asset. They may appear ONLY if referenced by a verified document chunk — never as brand identity.

---

## 10. TERMINOLOGY CONFIRMATION (MANDATORY PHRASES)

The system is called LOCUS (institutional knowledge system). NEVER "LOCUS AI". The system retrieves verified records ABOUT LOCUS.

Mandatory phrases (verified from index.html, docs, and benchmark):
- "Retrieve institutional knowledge"
- "Search the LOCUS archive"
- "Query the archive"
- "Evidence verified" (only when verification passes — never fabricated)
- "Evidence insufficient — No fabrication" (honest abstain)
- "Institutional Intelligence System" (subtitle in footer, verified)

Search input placeholder (verified): "What requires verification?"
Button label (verified): "Retrieve"
Loader subtitle (verified): "Initializing institutional intelligence"
Hero meta (verified): "Evidence-first retrieval · Structured · Verifiable"

---

## SUMMARY FOR AGENTS

- 3D Engineer: build the gravitational constellation on top of existing 70-node scene; preserve real node geometry; add gravitational weights from chunk counts (not random); no synthetic particles.
- GSAP/Interaction: implement retrieval sequence (Section 6) with real timeline; scroll choreography (scrubCam) connected to camera; reduced-motion guard active; no fake CSS-only hover.
- UX Architect: enforce readability zone rule (Section 3) in every section; asymmetric editorial layouts; precise spacing; no centered cards.
- Frontend: use ONLY the 3 verified brand assets; typography from Section 4; real RAG fetch to localhost:8765; graceful empty states; verified data only (Section 8).
- QA: verify no fabrication in any section; test retrieval sequence timing (<3s loader); test reduced-motion; confirm no decorative gold shimmer / particle fountains; confirm every sponsor/event/people reference points to verified chunk evidence.

Files read (verified): docs/superpowers/specs/2026-09-14-locus-award-design.md, docs/ARCHITECTURE.md, docs/SCHEMAS.md, public/assets/img/A MAIN_LOGO.png, public/index.html, public/assets/logo/, data/eligible_sources.csv (head + counts), data/benchmark_50_results.md (verified categories + counts), https://locus.com.np/ (empty — no fabricated content). Data indexes confirm: sponsor 1999, event 1272 (2025), organizer 350, team leader 29, president 40, budget 371, prize 542.

No fabrication used. No decorative elements added. Only verified data referenced.
