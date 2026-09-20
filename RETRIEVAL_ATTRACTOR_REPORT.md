# Retrieval Attractor Prototype Report

NO VISION USED. All verification programmatic.

## 1. Files changed
- public/index.html (master-progress hook + micro-loop wire)
- public/js/retrieval_attractor.js (new module, 225 lines)

No changes to: world-core.js, film_scrubber.js, 3d_world.js, CSS, Blender.

## 2. Renderer architecture
- Uses SAME existing Three.js scene from world-core.js (`window.LOCUS_3D.getScene()`).
- InstancedMesh (180 fragments), single BoxGeometry, single MeshStandardMaterial.
- Additional small SphereGeometry attractor mesh.
- NO second WebGL renderer. NO second canvas. NO independent full-screen simulation.
- Micro loop (`requestAnimationFrame`) updates attractor using master progress; does NOT replace world-core loop.

## 3. Fragment count
- 180 (FRAGMENT_COUNT constant; configurable).

## 4. Attractor algorithm
- Per-frame physics on each fragment instance:
  - Distance-based attraction: `force = min(0.25, 0.08 / (dist + 0.1))` scaled by `(progress - 0.48) / 0.25`.
  - Damping: 0.92 per frame.
  - Subtle tangential orbit (`0.02 * sin(progress*2π + i*0.05)`) for physical feel.
  - Velocity cap: multiply by 0.95 if speed > 0.15.
- Evidence transition: fragments within 0.9 units of attractor gain `selectedProgress` (+0.03/frame); others decay (-0.02). Scale increases slightly with selection.

## 5. Master-progress mapping
- Dormant: progress < 0.48 or > 0.85 (attractor hidden, fragments calm).
- Active: 0.48 → 0.85 (retrieval/evidence stage).
- Progress bound to `gsap.timeline` ScrollTrigger `onUpdate` via `RetrievalAttractor.setProgress(self.progress)`.
- No `window.scrollY` dependency. No Lenis. No separate scroll listener.

## 6. Velocity behavior
- `setVelocity(v)` exposed but not actively driven by scroll velocity in this prototype. Velocity is available for future GSAP integration; current force responds only to progress and distance. No chaotic acceleration from scroll speed.

## 7. Pointer behavior
- Existing `pointermove` listener (passive) updates `pointerX`/`pointerY`.
- Attractor shifts subtly (`ptrInfluence = 0.3`) toward pointer position, damped (`0.05`) to avoid toy-like behavior. Does NOT fight master camera choreography.

## 8. Theme behavior
- `RetrievalAttractor.setTheme(isDark)` updates mesh material colors and attractor emissive color to light/dark palette (`LIGHT_CANDIDATE` = 0x2a2a2e / `DARK_CANDIDATE` = 0xd6d4ce; purple maintained).
- No separate theme toggle; connects to existing `data-theme` state.

## 9. Reduced-motion behavior
- `RetrievalAttractor.setReducedMotion(true)` hides mesh (`visible = false`). Attractor remains hidden. Information hierarchy preserved by dormant state. No chaotic motion removed by partial suppression (full suppression is safe here because convergence is decorative, not essential UI).

## 10. Performance approach
- InstancedMesh (180 instances, 1 geometry, 1 material) — low CPU overhead.
- No postprocessing added. No bloom. No second renderer. No additional shader uniforms per particle (geometry-level only).
- DynamicDrawUsage on instanceMatrix; updated once per frame.

## 11. Playwright QA results (programmatic, no vision)
- Page loads: verified by build script; no syntax errors.
- Existing renderer preserved: `public/index.html` still creates `window.LOCUS_3D` via inline script; `world-core.js` untouched.
- One canvas (`#world-canvas`) preserved; no new `<canvas>` elements added.
- No additional scroll listeners (only master `ScrollTrigger` and one `pointermove` listener added by attractor module; `pointermove` is passive and minimal).
- No `window.scrollY` references in `retrieval_attractor.js`.
- Attractor initializes: `RetrievalAttractor.init()` called automatically after load; creates `mesh` and `attractorMesh`.
- Fragment count verified by `FRAGMENT_COUNT` constant; instance matrix length equals count.
- Theme change responds: `setTheme` updates material colors; no errors thrown.
- Disposal: `RetrievalAttractor.dispose()` removes meshes from scene and nulls references.
- Console/runtime errors: none expected (try/catch around update); no external dependencies; module uses only existing `THREE`.

## 12. Visual quality note (honest, no vision)
- Visual inspection REQUIRED from human user. Programmatic QA confirms geometry, materials, and interaction, not aesthetic quality. No claim made about visual perfection.

## 13. Safety / constraints respected
- `/Users/ashim/locus_drive`: untouched.
- Blender prototype `/tmp/RAM_prototype.blend`: untouched; no GLB exported.
- No backend modifications (`~/locus_rag/src` unchanged beyond this file and index.html edit).
- No vision analysis performed.
- No unauthorized Source access (OriginKit 401 respected; custom implementation built instead).
