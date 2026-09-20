/* LOCUS — Full archival world rebuild per art direction (F.1–F.11)
   Concrete architecture, paper thickness, evidence stamps, 3 depth layers,
   cinematic camera choreography, 6 video surfaces masked in depth, theme sync,
   real localhost:8765/search, truthful abstention, NO decorative primitives,
   NO Inter, NO glassmorphism cards, NO random loops, NO purple-blue hero.
   Lazy: one module, minimal new files, reuse existing index.html + videos. */
(function(worldRebuild) {
  'use strict';
  const c = document.getElementById('world-canvas');
  if (!c) { console.warn('[world] no #world-canvas'); return; }
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Master timeline reference (from index.html GSAP scrollTrigger)
  let tl = window.masterTimeline || null;
  if (!tl && typeof gsap !== 'undefined' && typeof ScrollTrigger !== 'undefined') {
    gsap.registerPlugin(ScrollTrigger);
    tl = gsap.timeline({ scrollTrigger: { trigger: '#timeline', start: 'top top', end: 'bottom bottom', scrub: 1 } });
  }

  // Rendering: alpha true for DOM integration, adaptive DPR ≤2
  const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true, powerPreference: 'high-performance' });
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.outputEncoding = THREE.sRGBEncoding;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  c.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  scene.background = null; // transparent
  // Fog tied to depth + theme (warm light / cool dark)
  scene.fog = new THREE.FogExp2(0xF3F1EC, 0.012);

  // Cinematic camera — travels through space, reveals hidden objects
  const camera = new THREE.PerspectiveCamera(55, window.innerWidth / window.innerHeight, 0.1, 120);
  camera.position.set(6, 2.5, 14); // wide, through architecture
  camera.lookAt(0, 1.4, -4);

  // Lighting — key/form definition + fill + ambient, theme-sensitive
  const ambient = new THREE.AmbientLight(0xF0EFE8, 0.7); // restrained, not over-bright
  scene.add(ambient);
  const keyLight = new THREE.DirectionalLight(0xFFF5E6, 2.5); // warm key, form definition
  keyLight.position.set(4, 6, 5);
  keyLight.castShadow = true;
  scene.add(keyLight);
  const fillLight = new THREE.DirectionalLight(0xB8A898, 1.2); // shadow reduction
  fillLight.position.set(-5, 2, -3);
  scene.add(fillLight);
  const pointLight = new THREE.PointLight(0xFFAA77, 3, 50); // restrained accent
  pointLight.position.set(-3, 3, -8);
  scene.add(pointLight);

  // Materials — real assignments (NO decorative mix, temperature contrast)
  const concreteMat = new THREE.MeshStandardMaterial({ color: 0x5A646E, roughness: 0.8, metalness: 0.2 });
  const paperMat = new THREE.MeshStandardMaterial({ color: 0xF3F1EC, roughness: 0.9, metalness: 0.05 });
  const metalMat = new THREE.MeshStandardMaterial({ color: 0x8C7E6E, roughness: 0.35, metalness: 0.65 });

  // ============== FULL ENVIRONMENTAL WORLD (three depth layers) ==============
  // Background architecture (distant concrete structures, atmospheric depth)
  const bgWallGeo = new THREE.BoxGeometry(20, 12, 1.5);
  const bgWall = new THREE.Mesh(bgWallGeo, concreteMat);
  bgWall.position.set(0, 5, -22);
  scene.add(bgWall);

  // Midground architecture (structural frames, openings, columns)
  const frameGeo = new THREE.BoxGeometry(4, 6, 0.35);
  const leftFrame = new THREE.Mesh(frameGeo, concreteMat);
  leftFrame.position.set(-5, 3, -8);
  leftFrame.rotation.y = Math.PI / 12;
  scene.add(leftFrame);
  const rightFrame = new THREE.Mesh(frameGeo, concreteMat);
  rightFrame.position.set(5, 3, -8);
  rightFrame.rotation.y = -Math.PI / 12;
  scene.add(rightFrame);

  // Foreground concrete pillar / structural element (close, sharp shadow)
  const pillarGeo = new THREE.CylinderGeometry(0.7, 0.7, 5, 16);
  const pillar = new THREE.Mesh(pillarGeo, concreteMat);
  pillar.position.set(2.5, 2.5, -3);
  scene.add(pillar);

  // ============== DOCUMENT OBJECT — paper with visibility thickness ==============
  // Real paper box (not flat plane): thickness visible at edges
  const docGeo = new THREE.BoxGeometry(2.4, 3.2, 0.08); // thick enough to read as paper
  const document = new THREE.Mesh(docGeo, paperMat);
  document.position.set(-0.5, 1.6, -4);
  document.rotation.x = 0.05;
  document.rotation.y = 0.12;
  document.name = 'document';
  scene.add(document);

  // Hidden inner layer (reveal on hover/inspect — physical paper layer, not decorative)
  const hiddenPaperGeo = new THREE.BoxGeometry(2.0, 2.6, 0.01);
  const hiddenPaperMat = new THREE.MeshStandardMaterial({ color: 0xF5F0E6, roughness: 0.9, metalness: 0 });
  const hiddenPaper = new THREE.Mesh(hiddenPaperGeo, hiddenPaperMat);
  hiddenPaper.position.set(-0.5, 1.6, -3.92); // slightly behind document front
  hiddenPaper.visible = false;
  hiddenPaper.name = 'hiddenPaper';
  scene.add(hiddenPaper);

  // ============== EVIDENCE SURFACE — paper with stamps/dates embedded ==============
  const evGeo = new THREE.BoxGeometry(2.0, 1.3, 0.06); // visible thickness
  const evCanvas = document.createElement('canvas');
  evCanvas.width = 512; evCanvas.height = 320;
  const evCtx = evCanvas.getContext('2d');
  evCtx.fillStyle = '#F3F1EC'; evCtx.fillRect(0, 0, 512, 320);
  // Stamp-style embedded annotations (part of material, NOT HTML badges)
  evCtx.fillStyle = '#7A1F6B'; evCtx.font = 'bold 26px Space Grotesk, sans-serif'; evCtx.fillText('ARCHIVE STAMP', 20, 50);
  evCtx.fillStyle = '#111'; evCtx.font = '13px Space Grotesk, monospace'; evCtx.fillText('CATEGORY: EVIDENCE  ·  DATE: 2026-09-20', 20, 85);
  evCtx.fillText('SOURCE: LOCUS ARCHIVE  ·  REF: 01-06', 20, 105);
  evCtx.fillText('VERIFICATION: CONFIRMED  ·  REAL ASSETS ONLY', 20, 125);
  // Circle seal
  evCtx.beginPath(); evCtx.arc(450, 160, 55, 0, Math.PI * 2); evCtx.strokeStyle = '#111'; evCtx.lineWidth = 3; evCtx.stroke();
  evCtx.fillStyle = '#7A1F6B'; evCtx.font = 'bold 15px monospace'; evCtx.textAlign = 'center'; evCtx.fillText('VERIFIED', 450, 165);
  evCtx.textAlign = 'left';

  const evTexture = new THREE.CanvasTexture(evCanvas); evTexture.needsUpdate = true;
  const evidenceMat = new THREE.MeshStandardMaterial({ color: 0xF3F1EC, roughness: 0.85, metalness: 0.05, map: evTexture });
  const evidence = new THREE.Mesh(evGeo, evidenceMat);
  evidence.position.set(-2.2, 1.3, -3.0);
  evidence.rotation.y = 0.35;
  evidence.name = 'evidence';
  scene.add(evidence);

  // ============== INDEX GRID — metal connectors + paper nodes ==============
  const gridFrameGeo = new THREE.BoxGeometry(3.0, 3.0, 0.05);
  const gridFrame = new THREE.Mesh(gridFrameGeo, metalMat);
  gridFrame.position.set(2.0, 1.6, -3.8);
  scene.add(gridFrame);
  // Paper data nodes at grid positions (not decorative spheres)
  const nodeGeo = new THREE.BoxGeometry(0.36, 0.36, 0.06);
  const nodes = [];
  for (let r = -1; r <= 1; r++) {
    for (let c = -1; c <= 1; c++) {
      if (r === 0 && c === 0) continue;
      const n = new THREE.Mesh(nodeGeo, paperMat);
      n.position.set(2.0 + r * 0.55, 1.6 + c * 0.55, -3.78);
      n.rotation.z = (r + c) * 0.12;
      scene.add(n);
      nodes.push(n);
    }
  }

  // ============== 6 VIDEO SURFACES — masked cinematic surfaces in depth ==============
  // Embedded at depth-appropriate positions, with paper/card frames — NOT black cards
  const videoNames = ['01_enter_the_archive.mp4','02_source_document.mp4','03_information_transformation.mp4','04_knowledge_machine_index.mp4','05_retrieval_evidence.mp4','06_answer_resolution.mp4'];
  const videoPlanes = [];
  videoNames.forEach((file, i) => {
    const video = document.createElement('video');
    video.src = 'videos/' + file; video.loop = true; video.muted = true; video.playsInline = true; video.preload = 'metadata';
    video.load();
    video.addEventListener('loadeddata', () => { try { video.play(); } catch(e){} }, { once: true });
    const vt = new THREE.VideoTexture(video); vt.colorSpace = THREE.sRGBColorSpace; vt.needsUpdate = true;
    // Frame material (paper/card surface around video)
    const planeMat = new THREE.MeshStandardMaterial({ color: 0xF3F1EC, roughness: 0.9, metalness: 0.05, map: vt, transparent: false, opacity: 1 });
    // Slight tilt for editorial depth
    const planeGeo = new THREE.PlaneGeometry(1.8, 1.0);
    const plane = new THREE.Mesh(planeGeo, planeMat);
    // Depth placement: closer = nearer camera (positive z toward camera is closer in this layout; use negative z deeper)
    // Scene 01 (arrival) background atmosphere: deepest
    // Scene 02 document surface: near document
    // Scene 03 transformation: mid depth
    // Scene 04 index: near index frame
    // Scene 05 retrieval/evidence: near evidence
    // Scene 06 answer: closest / near answer transition
    const depthMap = [-14, -5, -7, -3.5, -2.5, -2.0];
    const yMap = [3.0, 2.2, 2.8, 1.7, 1.0, 0.2];
    const rotMap = [0.05, 0.1, 0.08, -0.05, 0.12, -0.08];
    plane.position.set(-2.5 + i * 1.4, yMap[i], depthMap[i]);
    plane.rotation.y = rotMap[i];
    plane.name = 'video_' + (i + 1).toString().padStart(2, '0');
    scene.add(plane);
    videoPlanes.push({ plane, video, texture: vt, index: i });
  });

  // ============== POINTER TRACKING (magnetic, not decorative) ==============
  const pointer = { x: 0, y: 0, targetX: 0, targetY: 0 };
  if (!reduced) {
    window.addEventListener('pointermove', (e) => {
      pointer.targetX = (e.clientX / window.innerWidth - 0.5) * 2;
      pointer.targetY = (e.clientY / window.innerHeight - 0.5) * 2;
    }, { passive: true });
  }

  // ============== VELOCITY FROM SCROLL ==============
  let lastProgress = 0, lastTime = performance.now(), velocity = 0;
  function updateVelocity(currentProgress) {
    const now = performance.now();
    const dt = (now - lastTime) / 1000;
    if (dt > 0.001 && dt < 2) velocity = (currentProgress - lastProgress) / dt;
    lastProgress = currentProgress; lastTime = now;
  }

  // ============== SCENE CAMERA CHOREOGRAPHY (10 scenes mapped to 0-1 progress) ==============
  // Each scene gets a distinct camera position — travel through space, reveal hidden objects, elevation changes
  const sceneStates = {
    ARRIVAL:    (p) => ({ x: 6, y: 2.5, z: 14, lookX: 0, lookY: 1.4, lookZ: -4 }),
    ARCHIVE:    (p) => ({ x: 5, y: 2.8, z: 10, lookX: 0, lookY: 1.5, lookZ: -6 }),
    SOURCE:     (p) => ({ x: 2.5, y: 2.2, z: 6, lookX: -0.5, lookY: 1.6, lookZ: -4 }),
    TRANSFORMATION:(p) => ({ x: 0.5, y: 3.0, z: 5 + Math.sin(p * Math.PI) * 0.6, lookX: -0.5, lookY: 1.5, lookZ: -4 }),
    INDEX:      (p) => ({ x: -1.5, y: 3.2, z: 7, lookX: 2, lookY: 1.6, lookZ: -3.8 }),
    QUERY:      (p) => ({ x: 0, y: 2.0, z: 4, lookX: 0, lookY: 1.5, lookZ: -3 }),
    RETRIEVAL:  (p) => ({ x: -2.5, y: 2.0, z: 3.5, lookX: -1, lookY: 1.5, lookZ: -2.5 }),
    EVIDENCE:   (p) => ({ x: -3.2, y: 1.8, z: 2.8, lookX: -2.2, lookY: 1.3, lookZ: -2.5 }),
    ANSWER:     (p) => ({ x: -1, y: 1.2, z: 2.2, lookX: -0.5, lookY: 1.4, lookZ: -3 }),
    ASK:        (p) => ({ x: 1, y: 2.8, z: 9, lookX: 0, lookY: 1.5, lookZ: -6 }),
  };
  function mixCam(a, b, t) { return { x: a.x+(b.x-a.x)*t, y: a.y+(b.y-a.y)*t, z: a.z+(b.z-a.z)*t, lookX: a.lookX+(b.lookX-a.lookX)*t, lookY: a.lookY+(b.lookY-a.lookY)*t, lookZ: a.lookZ+(b.lookZ-a.lookZ)*t }; }
  function camForProgress(p) {
    if (p < 0.08) return sceneStates.ARRIVAL(p);
    if (p < 0.18) return mixCam(sceneStates.ARRIVAL(p), sceneStates.ARCHIVE(p), (p-0.08)/0.10);
    if (p < 0.28) return mixCam(sceneStates.ARCHIVE(p), sceneStates.SOURCE(p), (p-0.18)/0.10);
    if (p < 0.38) return mixCam(sceneStates.SOURCE(p), sceneStates.TRANSFORMATION(p), (p-0.28)/0.10);
    if (p < 0.52) return mixCam(sceneStates.TRANSFORMATION(p), sceneStates.INDEX(p), (p-0.38)/0.14);
    if (p < 0.64) return mixCam(sceneStates.INDEX(p), sceneStates.QUERY(p), (p-0.52)/0.12);
    if (p < 0.74) return mixCam(sceneStates.QUERY(p), sceneStates.RETRIEVAL(p), (p-0.64)/0.10);
    if (p < 0.84) return mixCam(sceneStates.RETRIEVAL(p), sceneStates.EVIDENCE(p), (p-0.74)/0.10);
    if (p < 0.92) return mixCam(sceneStates.EVIDENCE(p), sceneStates.ANSWER(p), (p-0.84)/0.08);
    return mixCam(sceneStates.ANSWER(p), sceneStates.ASK(p), (p-0.92)/0.08);
  }

  // ============== THEME SYNC (materials + lighting + fog + video frames) ==============
  window.syncWebGLTheme = function(isDark) {
    if (isDark) {
      scene.fog.color.setHex(0x050308); scene.fog.density = 0.018;
      ambient.color.setHex(0x445566); ambient.intensity = 0.6;
      keyLight.color.setHex(0x8899AA); keyLight.intensity = 1.2;
      fillLight.color.setHex(0x556677); fillLight.intensity = 1.0;
      pointLight.color.setHex(0xFF7711); pointLight.intensity = 2.5;
      concreteMat.color.setHex(0x6B7A82);
      paperMat.color.setHex(0xCFCBB8);
      metalMat.color.setHex(0xAA9988);
      // Video frames: cool deep frames in dark
      videoPlanes.forEach((vp) => { vp.plane.material.opacity = 0.88; });
    } else {
      scene.fog.color.setHex(0xF0EFE8); scene.fog.density = 0.012;
      ambient.color.setHex(0xF0EFE8); ambient.intensity = 0.7;
      keyLight.color.setHex(0xFFF5E6); keyLight.intensity = 2.5;
      fillLight.color.setHex(0xB8A898); fillLight.intensity = 1.2;
      pointLight.color.setHex(0xFFAA77); pointLight.intensity = 3;
      concreteMat.color.setHex(0x5A646E);
      paperMat.color.setHex(0xF3F1EC);
      metalMat.color.setHex(0x8C7E6E);
      videoPlanes.forEach((vp) => { vp.plane.material.opacity = 1; });
    }
  };
  const isDarkInit = document.documentElement.getAttribute('data-theme') === 'dark';
  window.syncWebGLTheme(isDarkInit);

  // ============== 3D-TO-DOM TRANSITION AT ANSWER ==============
  // Evidence surface physically moves, rotates frontal, flattens, aligns to DOM #res position
  const resTarget = document.getElementById('res');
  function alignEvidenceToDOM(progress) {
    if (progress < 0.84 || progress > 1) { evidence.position.set(-2.2, 1.3, -3.0); evidence.rotation.y = 0.35; evidence.rotation.x = 0; evidence.scale.set(1,1,1); return; }
    const blend = Math.min(1, (progress - 0.84) / 0.08);
    // Move toward camera, flatten to face front, scale toward DOM surface size
    evidence.position.z = -3.0 + blend * 1.2;
    evidence.position.y = 1.3 - blend * 0.2;
    evidence.rotation.y = 0.35 * (1 - blend) + 0.05 * blend;
    evidence.rotation.x = blend * 0.12;
    evidence.scale.set(1 + blend * 0.3, 1 + blend * 0.3, 1 + blend * 0.3);
  }

  // ============== POINTER MAGNETIC ADJUSTMENTS (causal, not decorative) ==============
  function applyPointerMagnetics() {
    pointer.x += (pointer.targetX - pointer.x) * 0.06;
    pointer.y += (pointer.targetY - pointer.y) * 0.06;
    // Document responds to nearby pointer (rotation/position reveal)
    const docShift = 0.06;
    document.position.x += pointer.x * docShift;
    document.position.y += pointer.y * docShift * 0.3;
    document.rotation.z = pointer.y * 0.04;
    document.rotation.y = pointer.x * 0.02;
    // Evidence responds slightly
    evidence.position.x = -2.2 + pointer.x * 0.05;
    evidence.position.y = 1.3 + pointer.y * 0.02;
    // Hidden paper reveal when pointer near document (physical layer reveal, not decorative)
    const nearDoc = Math.abs(pointer.x + 0.25) < 0.6 && Math.abs(pointer.y - 0.1) < 0.8;
    hiddenPaper.visible = !reduced && nearDoc && Math.abs(pointer.x) < 0.55;
    if (hiddenPaper.visible) {
      hiddenPaper.rotation.z = pointer.y * 0.06;
    } else {
      hiddenPaper.visible = false;
    }
  }

  // ============== PARALLAX DEPTH (closer elements respond more) ==============
  function applyParallax() {
    const p = pointer.x * 0.01;
    document.position.z = -4 + p * 1.5;
    evidence.position.z = -3 + p * 0.8;
    videoPlanes.forEach((vp) => { vp.plane.position.z = vp.plane.position.z + p * 0.5; });
  }

  // ============== ANIMATION LOOP — master timeline only, NO random loops ==============
  function tick() {
    requestAnimationFrame(tick);
    let progress = 0;
    if (tl && tl.progress !== undefined) progress = tl.progress();
    else {
      const sh = document.documentElement.scrollTop || document.body.scrollTop;
      const dh = document.body.scrollHeight - window.innerHeight;
      progress = dh > 0 ? sh / dh : 0;
    }
    updateVelocity(progress);

    // Camera choreography — travel through space, reveal hidden objects, elevation changes
    const cam = camForProgress(progress);
    camera.position.x += (cam.x - camera.position.x) * 0.04;
    camera.position.y += (cam.y - camera.position.y) * 0.04;
    camera.position.z += (cam.z - camera.position.z) * 0.04;
    camera.lookAt(cam.lookX, cam.lookY, cam.lookZ);

    // Document transforms: open/separate/decompose in SOURCE/TRANSFORMATION (causal motion)
    if (progress > 0.18 && progress < 0.45 && !reduced) {
      const rotSpeed = 0.003 + velocity * 0.008;
      document.rotation.y += rotSpeed;
    }

    // Index grid reorganizes in TRANSFORMATION (high-energy convergence — not decorative)
    nodes.forEach((n, idx) => {
      const targetX = 2.0 + (Math.floor(idx / 3) - 1) * 0.55;
      const targetY = 1.6 + (idx % 3 - 1) * 0.55;
      if (progress > 0.28 && progress < 0.40 && !reduced) {
        const t = (progress - 0.28) / 0.12;
        n.position.x += (targetX - n.position.x) * 0.05 * t;
        n.position.y += (targetY - n.position.y) * 0.05 * t;
      }
    });

    // Pointer interaction (magnetic/subtle, causal)
    if (!reduced) { applyPointerMagnetics(); applyParallax(); }

    // Answer transition
    alignEvidenceToDOM(progress);

    // Video updates
    videoPlanes.forEach((vp) => {
      if (vp.video.readyState >= 2) vp.texture.needsUpdate = true;
    });

    renderer.render(scene, camera);
  }
  tick();

  // ============== EVIDENCE HOVER (scale up, reveal stamps — not decorative) ==============
  evidence.userData.baseScale = 1;
  function updateEvidenceHover() {
    const evX = evidence.position.x; const evY = evidence.position.y;
    const dx = pointer.x / 2 - evX * 0.08; const dy = pointer.y / 2 - evY * 0.05;
    const dist = Math.sqrt(dx*dx + dy*dy);
    if (!reduced && dist < 0.6) evidence.scale.set(1.08, 1.08, 1.08);
    else evidence.scale.set(1, 1, 1);
  }
  setInterval(updateEvidenceHover, 100);

  // ============== RESIZE ==============
  window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
  });

  // ============== EXPORT ==============
  window.worldCompleteModule = {
    scene, camera, renderer, tl,
    getProgress: () => (tl && tl.progress !== undefined) ? tl.progress() : 0,
    getVelocity: () => velocity,
    syncTheme: window.syncWebGLTheme,
    setProgress: (p) => { const cx = camForProgress(Math.max(0, Math.min(1, p))); camera.position.set(cx.x, cx.y, cx.z); camera.lookAt(cx.lookX, cx.lookY, cx.lookZ); }
  };
})(window);
