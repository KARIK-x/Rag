# LOCUS Cinematic Scroll Experience Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the cinematic section as a pinned full-screen stage controlled by scroll position, with a real Three.js world, six chapter scenes, hidden video scrubbing, and real RAG handoff.

**Architecture:** Create a sticky full-screen cinematic stage (`<section class="cinematic-stage">`) that contains a Three.js canvas and a hidden video element. Use Lenis smooth scroll and GSAP ScrollTrigger to drive a master scroll progress (0.0–1.0) that controls scene transitions, video playback, and Three.js camera/lighting. The stage stays pinned while the user scrolls the rest of the page. After scene 6, automatically transition to the real search/RAG interface.

**Tech Stack:** 
- HTML5 semantic sections
- CSS position: fixed/sticky with height: 100vh
- Lenis for smooth scroll
- GSAP ScrollTrigger for pinning and progress control
- Three.js (existing 3d_world.js)
- HTML5 video element (hidden) for cinematic playback
- Lenis + ScrollTrigger for scroll → progress mapping
- Lenis scroll progress → video currentTime and Three.js camera/lighting updates

**Spec:** 
- Stage must be full-screen and pinned (top:0, height:100vh, position:fixed/sticky)
- Scroll position directly controls cinematic progress (0.0 → Scene 01, 1.0 → Scene 06)
- Scrolling down advances the cinematic; scrolling up reverses it
- Stop scrolling → cinematic freezes at exact position
- No autoplay independent of scroll
- Three.js world must be visible and responsive to scroll
- Six scenes must be reachable via scrolling
- Final scene transitions to real RAG answer interface

**Global Constraints:**
- Do not modify /Users/ashim/locus_drive
- Preserve existing public/index.html structure
- Use existing videos in public/videos/
- Reuse existing CSS classes where possible
- Minimal code changes; avoid new dependencies
- All changes must be testable via visual verification in a browser
- One runnable verification check at the end

---
### Task 1: Create cinematic stage container and basic layout

**Files:**
- Create: `public/index.html` (modify existing file)
- Modify: `public/css/film_scroll.css`

**Interfaces:**
- Consumes: existing `<header>`, `<main>` structure
- Produces: new `<section class="cinematic-stage">` element

**Steps:**
- [ ] Write failing test: Verify that a new `<section class="cinematic-stage">` exists in the DOM after modification
```html
<!-- test: verify cinematic stage container exists -->
<div class="cinematic-stage" id="cinematic-stage"></div>
```
Run: `grep -q '<section class="cinematic-stage"' public/index.html && echo "PASS" || echo "FAIL"`
- [ ] Run test to verify it fails (current page has no cinematic stage)
- [ ] Implement minimal HTML change: add `<section class="cinematic-stage" id="cinematic-stage" aria-label="Cinematic Archive"></section>` after `<header>` in `public/index.html`
- [ ] Add CSS rule in `public/css/film_scroll.css`: 
```css
.cinematic-stage {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100vh;
  z-index: 100;
  pointer-events: none;
  overflow: hidden;
}
```
Run test again; expect PASS
- [ ] Commit changes
```bash
git add public/index.html public/css/film_scroll.css
git commit -m "feat: create cinematic stage container"
```

### Task 2: Implement scroll progress tracking with Lenis and ScrollTrigger

**Files:**
- Create: `public/js/cinematic-scroll.js` (new)
- Modify: `public/js/film_scrubber.js` (if needed)

**Interfaces:**
- Consumes: Lenis scroll instance, ScrollTrigger
- Produces: global `cinematicProgress` variable (0.0–1.0) updated on scroll

**Steps:**
- [ ] Write failing test: Verify that `cinematicProgress` updates correctly based on scroll position
```js
// test: cinematicProgress reflects scroll position
import { cinematicProgress } from './cinematic-scroll.js';
import { lenis } from 'lenis';

let progress = 0;
const lenisScroll = lenis();
lenisScroll.scrollTo(0, { duration: 0 });
progress = cinematicProgress;
expect(progress).toBeCloseTo(0.0);
```
Run: `node -e "import './test/cinematic-scroll.test.js'; console.log('test result: ' + (require('./test/cinematic-scroll.test.js').pass ? 'PASS' : 'FAIL'))"` → expect FAIL

- [ ] Implement minimal scroll progress tracking:
```js
// cinematic-scroll.js
import { lenis } from 'lenis';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

export const cinematicProgress = ref(0);

export function initCinematicScroll() {
  const lenisScroll = lenis();
  lenisScroll.addEventListener('scroll', () => {
    cinematicProgress.value = lenisScroll.progress;
  });
}
```
Run test; expect PASS (if test checks progress after init)

- [ ] Commit changes
```bash
git add public/js/cinematic-scroll.js
git commit -m "feat: implement scroll progress tracking"
```

### Task 3: Integrate Three.js world with scroll progress

**Files:**
- Modify: `public/js/3d_world.js` (add progress hook)
- Create: `public/js/three-cinematic.js` (new, optional)

**Interfaces:**
- Consumes: `cinematicProgress` from Task 2
- Produces: camera movement, lighting, fog adjustments based on progress

**Steps:**
- [ ] Write failing test: Verify that Three.js camera position changes with `cinematicProgress`
```js
// test: camera moves with cinematic progress
import { cinematicProgress } from './cinematic-scroll.js';
import { updateCamera } from './three-cinematic.js';

cinematicProgress.value = 0.5;
updateCamera();
expect(camera.position.z).toBeCloseTo(5.0); // example assertion
```
Run: expect FAIL

- [ ] Implement camera/lighting update in `public/js/three-cinematic.js`:
```js
// three-cinematic.js
import { cinematicProgress } from './cinematic-scroll.js';
import * as THREE from 'three';

export function updateCamera() {
  const progress = cinematicProgress.value;
  // Example: move camera forward as progress increases
  camera.position.z = 10 - progress * 8;
  // Update lighting/intensity based on progress
  const intensity = 0.5 + progress * 0.5;
  ambientLight.intensity = intensity;
}
```
- [ ] Hook `updateCamera()` into a ScrollTrigger or animation loop that runs on scroll progress changes
- [ ] Commit changes
```bash
git add public/js/three-cinematic.js public/js/3d_world.js
git commit -m "feat: integrate Three.js with scroll progress"
```

### Task 4: Add hidden video source with scroll-driven scrubbing

**Files:**
- Create: `public/videos/cinematic-composite.mp4` (optional, but better to use existing videos)
- Modify: `public/js/film_scrubber.js` (or create new `public/js/video-scrubber.js`)

**Interfaces:**
- Consumes: `cinematicProgress` and video duration
- Produces: video element scrubbable via scroll position

**Steps:**
- [ ] Write failing test: Verify video currentTime matches scroll progress
```js
// test: video scrubs with cinematic progress
import { cinematicProgress } from './cinematic-scroll.js';
import { videoScrubber } from './video-scrubber.js';
const video = document.createElement('video');
video.src = '/videos/01_enter_the_archive.mp4';
videoScrubber.setVideo(video);
cinematicProgress.value = 0.5;
expect(video.currentTime).toBeCloseTo(video.duration * 0.5);
```
Run: expect FAIL

- [ ] Implement video scrubbing:
```js
// video-scrubber.js
import { cinematicProgress } from './cinematic-scroll.js';

export function setVideo(videoEl) {
  videoEl.addEventListener('loadedmetadata', () => {
    videoEl.addEventListener('scroll', () => {
      const progress = cinematicProgress.value;
      videoEl.currentTime = progress * videoEl.duration;
    });
  });
}
```
- [ ] Hide video element via CSS (display:none) but keep it in DOM for scrubbing
- [ ] Commit changes
```bash
git add public/js/video-scrubber.js
git commit -m "feat: enable video scrubbing via scroll progress"
```

### Task 5: Implement six scene transitions

**Files:**
- Modify: `public/css/film_scroll.css` (add scene classes)
- Create: `public/js/scene-manager.js` (new)

**Interfaces:**
- Consumes: `cinematicProgress`, video element, Three.js scene
- Produces: scene visibility changes at defined progress thresholds (e.g., 0.0, 0.16, 0.32, 0.48, 0.65, 0.83, 1.0)

**Steps:**
- [ ] Write failing test: Verify that scene 1 is visible at progress 0.0 and scene 2 at 0.16
```js
// test: scene visibility changes at thresholds
import { cinematicProgress } from './cinematic-scroll.js';
import { sceneManager } from './scene-manager.js';

cinematicProgress.value = 0.0;
expect(sceneManager.currentScene).toBe('scene-01');

cinematicProgress.value = 0.16;
expect(sceneManager.currentScene).toBe('scene-02');
```
Run: expect FAIL

- [ ] Implement scene manager with thresholds:
```js
// scene-manager.js
import { cinematicProgress } from './cinematic-scroll.js';

const sceneThresholds = [
  { scene: 'scene-01', start: 0.0, end: 0.16 },
  { scene: 'scene-02', start: 0.16, end: 0.32 },
  { scene: 'scene-03', start: 0.32, end: 0.48 },
  { scene: 'scene-04', start: 0.48, end: 0.65 },
  { scene: 'scene-05', start: 0.65, end: 0.83 },
  { scene: 'scene-06', start: 0.83, end: 1.0 }
];

export const sceneManager = {
  currentScene: null,
  update() {
    const progress = cinematicProgress.value;
    for (const s of sceneThresholds) {
      if (progress >= s.start && progress < s.end) {
        this.currentScene = s.scene;
        return;
      }
    }
    this.currentScene = 'scene-06';
  }
};
```
- [ ] Add CSS classes for each scene (`.scene-01`, `.scene-02`, etc.) to control visibility and transitions
- [ ] Commit changes
```bash
git add public/js/scene-manager.js public/css/film_scroll.css
git commit -m "feat: implement six scene transitions"
```

### Task 6: Add RAG handoff after final scene

**Files:**
- Modify: `public/js/film_scrubber.js` (or create `public/js/rag-handoff.js`)
- Create: new UI component for real search interface (existing page already has search bar)

**Interfaces:**
- Consumes: sceneManager.currentScene, cinematicProgress
- Produces: transition to real RAG search interface after scene 6

**Steps:**
- [ ] Write failing test: Verify that after scene 6, the interface transitions to the real search form
```js
// test: after scene 6, real RAG interface appears
import { sceneManager } from './scene-manager.js';
import { showRealRag } from './rag-handoff.js';

sceneManager.currentScene = 'scene-06';
showRealRag();
expect(document.querySelector('#search-bar')).toBeInTheDocument();
```
Run: expect FAIL

- [ ] Implement handoff logic:
```js
// rag-handoff.js
import { sceneManager } from './scene-manager.js';
import { showRealRag } from './real-rag.js';

export function maybeHandoff() {
  if (sceneManager.currentScene === 'scene-06') {
    showRealRag();
  }
}
```
- [ ] Call `maybeHandoff()` in the scroll progress update loop
- [ ] Commit changes
```bash
git add public/js/rag-handoff.js
git commit -m "feat: add RAG handoff after scene 6"
```

### Task 7: Write regression tests and final verification

**Files:**
- Create: `tests/e2e/cinematic-scroll.test.js` (new)

**Steps:**
- [ ] Write comprehensive test that verifies:
  - Cinematic stage is pinned and full-screen
  - Scroll progress drives video scrubbing
  - Three.js camera moves with progress
  - Six scenes transition correctly
  - No autoplay independent of scroll
- [ ] Run all tests and ensure they pass
- [ ] Manual browser test: open http://localhost:8000, verify all 14 user requirements
- [ ] Commit final changes
```bash
git add tests/e2e/cinematic-scroll.test.js
git commit -m "feat: final verification and regression tests"
```

### Final Verification Checklist

- [ ] Cinematic stage is full-screen and pinned (top:0, height:100vh, position:fixed)
- [ ] Scrolling down advances scenes; scrolling up reverses
- [ ] Stop scrolling → cinematic freezes at exact position
- [ ] Video plays only when user scrolls (no autoplay)
- [ ] Three.js world is visible and camera moves with scroll
- [ ] Six scenes are reachable via scroll position
- [ ] Final scene transitions to real RAG search interface
- [ ] All regression tests pass
- [ ] Manual browser test confirms all 14 required behaviors

---