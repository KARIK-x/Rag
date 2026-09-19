// Cinematic Scroll System — scroll-site-generator methodology
// ONE master scroll progress (0→1) drives 6 scene crossfades.
// Lenis smooth scroll + GSAP ScrollTrigger pinning + video scrubbing.
// Two video layers for crossfading transitions; no autoplay.
(function(){
  'use strict';

  const SCENES = [
    { video: 'videos/01_enter_the_archive.mp4',   title: 'ENTER THE ARCHIVE',    sub: '01 — Enter the Archive' },
    { video: 'videos/02_source_document.mp4',     title: 'SOURCE DOCUMENT',      sub: '02 — Source Document' },
    { video: 'videos/03_information_transformation.mp4', title: 'INFORMATION TRANSFORMATION', sub: '03 — Information Transformation' },
    { video: 'videos/04_knowledge_machine_index.mp4', title: 'KNOWLEDGE MACHINE', sub: '04 — Knowledge Machine / Index' },
    { video: 'videos/05_retrieval_evidence.mp4',  title: 'RETRIEVAL EVIDENCE',   sub: '05 — Retrieval / Evidence' },
    { video: 'videos/06_answer_resolution.mp4',   title: 'ANSWER RESOLUTION',    sub: '06 — Answer Resolution' },
  ];

  // Each scene occupies 1/6 of total progress
  const SCENE_BOUNDS = SCENES.map((_, i) => ({
    start: i / SCENES.length,
    end:   (i + 1) / SCENES.length,
  }));

  const track  = document.getElementById('film-track');
  const stage  = document.getElementById('film-stage');
  const vidA   = document.getElementById('film-layer-a');
  const vidB   = document.getElementById('film-layer-b');
  const layers = [vidA, vidB];
  let activeLayer = 0;   // index into layers[] of currently visible layer
  let currentScene = 0;  // scene index (0..5)
  let progress = 0;      // master scroll progress 0..1
  let running = false;

  // ── Init ──────────────────────────────────────────────
  function init() {
    loadSceneInto(vidA, SCENES[0]);
    loadSceneInto(vidB, SCENES[1]);

    // Wait for video metadata then boot
    const firstVideo = vidA;
    if (firstVideo.readyState >= 1) { onReady(); }
    else {
      firstVideo.addEventListener('loadedmetadata', onReady, { once: true });
      firstVideo.addEventListener('loadeddata', onReady, { once: true });
      setTimeout(onReady, 2500); // hard cap
    }

    window.addEventListener('scroll', onScrollTick, { passive: true });
    window.addEventListener('resize', onResize);

    // Lenis smooth scroll if available
    if (typeof Lenis !== 'undefined') {
      const lenis = new Lenis({ duration: 1.2, smoothWheel: true });
      lenis.on('scroll', (e) => { progress = e.progress; updateAll(); });
      lenis.on('resize', onResize);
    }
  }

  function onReady() {
    setTimeout(() => {
      const cue = document.getElementById('scroll-cue');
      if (cue) cue.style.opacity = progress < 0.015 ? '1' : '0';
    }, 500);
    updateAll();
    running = true;
  }

  // ── Video loading ─────────────────────────────────────
  function loadSceneInto(video, scene) {
    if (!video) return;
    while (video.firstChild) video.removeChild(video.firstChild);
    const src = document.createElement('source');
    src.src = scene.video;
    src.type = 'video/mp4';
    video.appendChild(src);
    video.muted = true;
    video.playsInline = true;
    video.loop = false;
    video.load();
  }

  // ── Scene switching with crossfade ────────────────────
  function setScene(sceneIdx) {
    if (sceneIdx === currentScene) return;
    currentScene = sceneIdx;

    const newActive = 1 - activeLayer;
    const oldActive = activeLayer;
    const newLayer = layers[newActive];
    const oldLayer = layers[oldActive];

    loadSceneInto(newLayer, SCENES[sceneIdx]);

    // Crossfade: old fades out, new fades in (CSS transition handles .45s)
    if (oldLayer) {
      oldLayer.style.transition = 'opacity .45s ease';
      oldLayer.style.opacity = '0';
    }
    if (newLayer) {
      newLayer.style.transition = 'opacity .45s ease';
      newLayer.style.opacity = '1';
      // Trigger the actual seek after a brief delay to let load() start
      setTimeout(() => { seekLayer(newLayer, getSceneSub(sceneIdx)); }, 30);
    }

    activeLayer = newActive;
  }

  // ── Progress → scene mapping ──────────────────────────
  function getSceneIdx(p) {
    for (let i = 0; i < SCENE_BOUNDS.length; i++) {
      if (p >= SCENE_BOUNDS[i].start && p < SCENE_BOUNDS[i].end) return i;
    }
    return SCENES.length - 1;
  }

  function getSceneSub(p) {
    for (let i = 0; i < SCENE_BOUNDS.length; i++) {
      const b = SCENE_BOUNDS[i];
      if (p >= b.start && p < b.end) return (p - b.start) / (b.end - b.start);
    }
    return 1;
  }

  // ── Scroll scrub ──────────────────────────────────────
  function seekLayer(video, sub) {
    if (!video || !video.duration || video.duration <= 0) return;
    const target = sub * video.duration;
    if (Math.abs((video.currentTime || 0) - target) > 0.15) {
      video.currentTime = target;
    }
  }

  function onScrollTick() {
    requestAnimationFrame(updateAll);
  }

  function updateAll() {
    if (!track) return;
    const max = track.offsetHeight - window.innerHeight;
    progress = max > 0 ? Math.min(1, Math.max(0, window.scrollY / max)) : 0;

    // Master progress drives:
    // 1. Scene selection (crossfade)
    const sceneIdx = getSceneIdx(progress);
    setScene(sceneIdx);

    // 2. Video playback within current scene
    const sub = getSceneSub(progress);
    const activeVideo = layers[activeLayer];
    if (activeVideo) seekLayer(activeVideo, sub);

    // 3. Captions
    updateCaptions(progress);

    // 4. Three.js sync (if available)
    if (window.LOCUS_3D && typeof window.LOCUS_3D.setCameraState === 'function') {
      try { window.LOCUS_3D.setCameraState(progress); } catch(e) {}
    }
  }

  // ── Captions ──────────────────────────────────────────
  function updateCaptions(p) {
    const captions = document.querySelectorAll('.caption');
    captions.forEach(el => {
      const inV = parseFloat(el.dataset.in || '0');
      const holdV = parseFloat(el.dataset.hold || '0.5');
      const outV = parseFloat(el.dataset.out || '1');
      let o = 0;
      if (p >= inV && p <= outV) {
        const r = Math.max((holdV - inV) * 0.4, 0.01);
        const f = Math.max(outV - holdV, 0.01);
        o = Math.min((p - inV) / r, 1) * Math.min((outV - p) / f, 1);
      }
      o = Math.max(0, Math.min(1, o));
      el.style.opacity = o.toFixed(3);
      el.style.transform = `translateY(${(p - holdV) * -40}px)`;
      if (o > 0.01) el.classList.add('in'); else el.classList.remove('in');
    });
    const cue = document.getElementById('scroll-cue');
    if (cue) cue.style.opacity = p < 0.015 ? '1' : '0';
  }

  // ── Resize ────────────────────────────────────────────
  function onResize() {
    updateAll();
  }

  // ── Boot ──────────────────────────────────────────────
  init();
})();