// Cinematic Scroll System — ONE master progress (0→1) from ScrollTrigger drives everything
// No window.scrollY source. No manual inertia loops. Lenis handles smooth scroll; ScrollTrigger owns pin + progress.
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
  const SCENE_BOUNDS = SCENES.map((_, i) => ({
    start: i / SCENES.length,
    end:   (i + 1) / SCENES.length,
  }));

  const vid    = document.getElementById('film-layer');
  let currentScene = 0;
  let progress = 0;
  let running = false;

  // ── Load scene video ──────────────────────────────────
  function loadScene(scene) {
    if (!vid || !scene) return;
    while (vid.firstChild) vid.removeChild(vid.firstChild);
    const src = document.createElement('source');
    src.src = scene.video;
    src.type = 'video/mp4';
    vid.appendChild(src);
    vid.muted = true;
    vid.playsInline = true;
    vid.loop = false;
    vid.load();
  }

  // ── Scene + sub-progress mapping ──────────────────────
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

  // ── Seek within current scene video ───────────────────
  function seekLayer(video, sub) {
    if (!video || !video.duration || video.duration <= 0) return;
    const target = sub * video.duration;
    if (Math.abs((video.currentTime || 0) - target) > 0.15) {
      video.currentTime = target;
    }
  }

  // ── Captions choreography (scroll-linked opacity/translate) ──
  function updateCaptions(p) {
    document.querySelectorAll('.caption').forEach(el => {
      const inV  = parseFloat(el.dataset.in || '0');
      const holdV= parseFloat(el.dataset.hold || '0.5');
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

  // ── Scene-state choreography mapped to master progress ──
  window.CINEMATIC_UPDATE = function(self) {
    progress = Math.max(0, Math.min(1, self ? self.progress : progress));

    // Scene selection by master progress (6 scenes, 0→1)
    const idx = getSceneIdx(progress);
    if (idx !== currentScene) {
      currentScene = idx;
      loadScene(SCENES[idx]);
      setTimeout(() => seekLayer(vid, getSceneSub(progress)), 80);
    } else {
      seekLayer(vid, getSceneSub(progress));
    }

    // Typography choreography: enter/exit transformed per state
    updateCaptions(progress);

    // State choreography drives 3D + lighting via progress
    updateSceneState(progress);
  };

  // ── Six-state archive choreography (one master progress drives all) ──
  function updateSceneState(p) {
    // 01 ENTER (0.00–0.17): archive wakes, cinematic dominates, large editorial title
    // 02 SOURCE (0.17–0.33): fragments emerge, connections to network begin
    // 03 TRANSFORM (0.33–0.50): fragments reorganize, RAW→STRUCTURED, topology changes
    // 04 MACHINE (0.50–0.67): network dominant, camera travels, video atmospheric
    // 05 RETRIEVAL (0.67–0.83): paths illuminate, nodes converge, RETRIEVAL→EVIDENCE
    // 06 RESOLUTION (0.83–1.00): settles, evidence resolves, atmospheric
    if (p < 0.17) {
      if (window.LOCUS_3D && window.LOCUS_3D.setPhase) window.LOCUS_3D.setPhase('wide');
    } else if (p < 0.33) {
      if (window.LOCUS_3D && window.LOCUS_3D.setPhase) window.LOCUS_3D.setPhase('orbit');
    } else if (p < 0.50) {
      if (window.LOCUS_3D && window.LOCUS_3D.setPhase) window.LOCUS_3D.setPhase('close');
    } else if (p < 0.67) {
      if (window.LOCUS_3D && window.LOCUS_3D.setPhase) window.LOCUS_3D.setPhase('orbit');
    } else if (p < 0.83) {
      if (window.LOCUS_3D && window.LOCUS_3D.setPhase) window.LOCUS_3D.setPhase('close');
    } else {
      if (window.LOCUS_3D && window.LOCUS_3D.setPhase) window.LOCUS_3D.setPhase('answer');
    }
    // Pointer/parallax interaction: subtle mouse influence preserved by 3D animate loop
  }

  // ── Init ───────────────────────────────────────────────
  function init() {
    loadScene(SCENES[0]);
    if (vid) {
      const ready = () => {
        running = true;
        seekLayer(vid, 0);
        updateCaptions(0);
      };
      if (vid.readyState >= 1) { setTimeout(ready, 100); }
      else {
        vid.addEventListener('loadedmetadata', () => setTimeout(ready, 50), { once: true });
        vid.addEventListener('loadeddata', () => setTimeout(ready, 50), { once: true });
        setTimeout(ready, 2500); // hard cap
      }
    }
    window.addEventListener('resize', () => updateCaptions(progress));
  }
  init();
})();
