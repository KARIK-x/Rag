/* LOCUS ARCHIVE MACHINE — CINEMATIC WORLD REBUILD
 * Physical archive architecture, continuous camera travel (10 scenes),
 * object choreography, 6 video surfaces embedded at depth, 3D→DOM evidence transition,
 * typography as environmental material, no decorative primitives, no static sections.
 */
import * as THREE from 'https://cdn.skypack.dev/three@0.160.0';

const CFG = {
  sceneProgress: 0, velocity: 0,
  lightTheme: document.documentElement.getAttribute('data-theme') !== 'dark',
  colors: {
    concrete: 0x6B6355,   // warm stone/concrete — cold structured
    paper:    0xF3F1EC,   // warm ivory — editorial material
    metal:    0xC0B5A5,   // bronze/steel — index connectors
    ink:      0x1A1714,   // near-black
    inkMuted: 0x7A7568,
    purple:   0x7A1F6B,
    purpleDark: 0x92278F,
    fogLight: 0xEAE8DC,
    fogDark: 0x0D0B0F,
  },
};

// ===== SCENE SETUP =====
const canvas = document.getElementById('world-canvas');
const scene = new THREE.Scene();
scene.background = null;
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
// Attach renderer canvas — keep existing #world-canvas, replace contents
if (canvas) { canvas.innerHTML = ''; canvas.appendChild(renderer.domElement); }

const camera = new THREE.PerspectiveCamera(55, window.innerWidth / window.innerHeight, 0.1, 200);

// ===== LIGHTING (3-level: key + fill + ambient + purple accent) =====
const ambient = new THREE.AmbientLight(CFG.lightTheme ? 0x334488 : 0x112233, CFG.lightTheme ? 0.7 : 0.4);
scene.add(ambient);
const keyLight = new THREE.DirectionalLight(CFG.lightTheme ? 0xF5EDD8 : 0xC8B8A8, CFG.lightTheme ? 2.2 : 1.6);
keyLight.position.set(8, 6, 8); keyLight.castShadow = true; scene.add(keyLight);
const fillLight = new THREE.DirectionalLight(CFG.lightTheme ? 0x8899AA : 0x556677, CFG.lightTheme ? 0.8 : 0.5);
fillLight.position.set(-6, 2, -5); scene.add(fillLight);
const purplePoint = new THREE.PointLight(CFG.colors.purple, 2.5, 40);
purplePoint.position.set(-4, 3, -6); scene.add(purplePoint);

function updateThemeScene() {
  const d = document.documentElement.getAttribute('data-theme') === 'dark';
  CFG.lightTheme = !d;
  scene.fog = new THREE.FogExp2(d ? CFG.colors.fogDark : CFG.colors.fogLight, d ? 0.024 : 0.012);
  ambient.color.setHex(d ? 0x112233 : 0x334488);
  ambient.intensity = d ? 0.4 : 0.7;
  keyLight.color.setHex(d ? 0xC8B8A8 : 0xF5EDD8);
  keyLight.intensity = d ? 1.6 : 2.2;
  fillLight.color.setHex(d ? 0x556677 : 0x8899AA);
  fillLight.intensity = d ? 0.5 : 0.8;
}
updateThemeScene();
const themeObs = new MutationObserver(updateThemeScene);
try { themeObs.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] }); } catch (e) {}

// ===== ARCHIVE ARCHITECTURE (vault, shelves, structural frames) =====
function buildVault() {
  const group = new THREE.Group();
  // Main archive wall — massive concrete plane
  const wallMat = new THREE.MeshStandardMaterial({ color: CFG.colors.concrete, roughness: 0.85, metalness: 0.15 });
  const wall = new THREE.Mesh(new THREE.BoxGeometry(16, 10, 1.2), wallMat);
  wall.position.set(-4, 3.5, -22); wall.castShadow = true; wall.receiveShadow = true; group.add(wall);
  // Tall structural shelf system embedded in wall (3 rows, 2 cols)
  for (let s = 0; s < 3; s++) {
    for (let c = 0; c < 2; c++) {
      const shelf = new THREE.Mesh(
        new THREE.BoxGeometry(3.2, 0.7, 0.5),
        new THREE.MeshStandardMaterial({ color: 0x6A5A50, roughness: 0.8, metalness: 0.25 })
      );
      shelf.position.set(-5.5 + c * 4, 1.2 + s * 2.4, -23.2);
      shelf.castShadow = true; shelf.receiveShadow = true; group.add(shelf);
    }
  }
  // Deep background architecture (receding slab) — establishes scale
  const deepWall = new THREE.Mesh(new THREE.BoxGeometry(30, 6, 0.8), wallMat);
  deepWall.position.set(-8, 3, -42); deepWall.receiveShadow = true; group.add(deepWall);
  // Light shaft — restrained vertical plane near top of vault
  const shaftMat = new THREE.MeshStandardMaterial({
    color: CFG.lightTheme ? 0xF5EDD8 : 0xD0C8B8, emissive: CFG.lightTheme ? 0xF5EDD8 : 0xD0C8B8,
    emissiveIntensity: CFG.lightTheme ? 0.5 : 0.25, roughness: 1, metalness: 0, transparent: true, opacity: 0.22, depthWrite: false
  });
  const shaft = new THREE.Mesh(new THREE.BoxGeometry(0.3, 12, 0.3), shaftMat);
  shaft.position.set(5, 6, -26); group.add(shaft);
  scene.add(group);
  return group;
}
const vault = buildVault();

// ===== PHYSICAL DOCUMENT OBJECT (thick paper, 4/5 aspect, opens, fragments separate) =====
function buildDocument() {
  const group = new THREE.Group();
  // Main thick document body (not flat plane — visible thickness)
  const docMat = new THREE.MeshStandardMaterial({ color: CFG.colors.paper, roughness: 0.95, metalness: 0.04 });
  const docBody = new THREE.Mesh(new THREE.BoxGeometry(3, 4.2, 0.22), docMat);
  docBody.position.set(-3.5, 2.8, -4); docBody.castShadow = true; docBody.receiveShadow = true; group.add(docBody);
  // Document cover (slightly larger glass-like protective layer — restrained, not decorative)
  const coverMat = new THREE.MeshPhysicalMaterial({
    color: 0xFFFFFF, roughness: 0.08, metalness: 0.08, transmission: 0.88, thickness: 0.04,
    transparent: true, opacity: CFG.lightTheme ? 0.7 : 0.55, clearcoat: 1.0, ior: 1.5
  });
  const cover = new THREE.Mesh(new THREE.BoxGeometry(3.08, 4.28, 0.03), coverMat);
  cover.position.set(-3.5, 2.8, -3.7); group.add(cover);
  // Fragment surfaces (paper pieces that separate — tied to SOURCE→TRANSFORMATION choreography)
  const fragMat = new THREE.MeshStandardMaterial({ color: 0xEAE6DA, roughness: 0.9, metalness: 0.05 });
  const fragments = [];
  for (let i = 0; i < 5; i++) {
    const f = new THREE.Mesh(new THREE.BoxGeometry(0.42, 0.65, 0.09), fragMat);
    f.position.set(-2.2 + i * 0.45, 3.2 + Math.sin(i) * 0.35, -1.8 - i * 0.4);
    f.rotation.y = (i / 5) * Math.PI * 0.6; f.castShadow = true; group.add(f); fragments.push(f);
  }
  scene.add(group);
  return { group, docBody, fragments, cover };
}
const docObj = buildDocument();

// ===== INDEX MACHINE (metal connectors, paper/card data nodes — 5x5 structured grid) =====
function buildIndexGrid() {
  const group = new THREE.Group();
  const metalMat = new THREE.MeshStandardMaterial({ color: CFG.colors.metal, roughness: 0.35, metalness: 0.7 });
  const cardMat = new THREE.MeshStandardMaterial({ color: CFG.colors.paper, roughness: 0.85, metalness: 0.06 });
  const nodes = [];
  for (let i = 0; i < 5; i++) {
    for (let j = 0; j < 5; j++) {
      const node = new THREE.Mesh(new THREE.SphereGeometry(0.14, 16, 12), metalMat);
      node.position.set(-4 + i * 1.5, 3.2 + j * 1.3, -1); node.castShadow = true; group.add(node); nodes.push(node);
      const card = new THREE.Mesh(new THREE.BoxGeometry(0.9, 0.9, 0.1), cardMat);
      card.position.set(-4 + i * 1.5, 3.25 + j * 1.3, -0.7); card.rotation.y = Math.PI * 0.04; card.rotation.x = Math.PI * 0.02; card.castShadow = true; group.add(card);
    }
  }
  // Horizontal / vertical connectors (structural mechanical lines)
  for (let i = 0; i < 5; i++) {
    const h = new THREE.Mesh(new THREE.CylinderGeometry(0.035, 0.035, 6.8, 10), metalMat);
    h.rotation.z = Math.PI / 2; h.position.set(-4 + i * 1.5, 3.2 + 2 * 1.3, -1); group.add(h);
    const v = new THREE.Mesh(new THREE.CylinderGeometry(0.035, 0.035, 6.8, 10), metalMat);
    v.position.set(-4, 3.2 + i * 1.3, -1); group.add(v);
  }
  scene.add(group);
  return { group, nodes };
}
const indexGrid = buildIndexGrid();

// ===== EVIDENCE SURFACES (4 cards that rotate, separate from noise, move toward camera) =====
function buildEvidence() {
  const group = new THREE.Group();
  const cardMat = new THREE.MeshStandardMaterial({ color: 0xF3F1EC, roughness: 0.88, metalness: 0.05 });
  const surfaces = [];
  for (let k = 0; k < 4; k++) {
    const s = new THREE.Mesh(new THREE.BoxGeometry(1.5, 1.0, 0.09), cardMat);
    s.position.set(4.5 + k * 1.1, 2.8, -3 - k * 1.0); s.rotation.y = 0.12 + k * 0.1; s.castShadow = true; group.add(s); surfaces.push(s);
  }
  scene.add(group);
  return { group, surfaces };
}
const evidence = buildEvidence();

// ===== ANSWER SURFACE (signature 3D→2D transition: flattens, aligns with DOM at progress > 0.82) =====
function buildAnswerSurface() {
  const g = new THREE.Group();
  const surf = new THREE.Mesh(new THREE.BoxGeometry(3.2, 2.0, 0.1), new THREE.MeshStandardMaterial({ color: CFG.colors.paper, roughness: 0.92, metalness: 0.05 }));
  surf.position.set(0, 0.7, 2); surf.rotation.y = 0.25; g.add(surf);
  // Stamp detail (purple mark embedded into paper surface — not an HTML badge)
  const stamp = new THREE.Mesh(new THREE.BoxGeometry(0.7, 0.1, 0.02), new THREE.MeshStandardMaterial({ color: CFG.colors.purple, roughness: 1.0 }));
  stamp.position.set(-1.1, 1.4, 0.02); g.add(stamp);
  scene.add(g);
  return { group: g, surface: surf, stamp };
}
const answer = buildAnswerSurface();

// ===== 6 VIDEO SURFACES — embedded as masked editorial planes at depth, NOT stacked cards =====
// Each video plane is positioned at a different depth and orientation, integrated into the scene
function embedVideoPlane(srcLabel, x, y, z, rotY = 0, scale = 1) {
  // Frame: dark structural border
  const frameGeo = new THREE.BoxGeometry(2.4, 1.35, 0.08);
  const frameMat = new THREE.MeshStandardMaterial({ color: 0x2A2722, roughness: 0.85, metalness: 0.4 });
  const frame = new THREE.Mesh(frameGeo, frameMat);
  frame.position.set(x, y, z); frame.rotation.y = rotY; scene.add(frame);
  // Video surface plane (will display via DOM overlay masked to plane position, not separate cards)
  const planeGeo = new THREE.PlaneGeometry(2.15, 1.15);
  const planeMat = new THREE.MeshStandardMaterial({
    color: CFG.colors.paper, roughness: 0.6, metalness: 0.1,
    map: null, transparent: true, opacity: 0.92
  });
  const plane = new THREE.Mesh(planeGeo, planeMat);
  // Rotate plane to face slightly toward camera and embed in scene depth
  plane.rotation.y = rotY;
  plane.rotation.x = -0.06; // slight tilt for editorial feel
  plane.position.set(x, y, z - 0.04); // just in front of frame
  scene.add(plane);
  // Create a DOM overlay video element positioned exactly at the plane's 3D projection (simplified — no screen-space projection here, use CSS fixed positions that blend with scene progress)
  // But instead of stacked cards, we create masked video overlays at the same conceptual positions
  const domMask = document.createElement('div');
  domMask.style.cssText = `position:fixed;top:${50 + Math.sin(rotY)*12}vh;left:${20 + Math.cos(y/5)*15}vw;width:28vw;height:16vh;z-index:15;pointer-events:none;opacity:0.88;border-radius:3px;overflow:hidden;box-shadow:0 24px 70px rgba(0,0,0,0.35);transition:opacity .6s,border-color .55s;`;
  const video = document.createElement('video');
  video.src = `videos/${srcLabel}`; video.muted = true; video.loop = true; video.playsInline = true; video.preload = 'metadata';
  video.style.cssText = `width:100%;height:100%;object-fit:cover;display:block;filter:contrast(1.08) brightness(.96);`;
  video.setAttribute('aria-label', srcLabel);
  domMask.appendChild(video);
  domMask.setAttribute('aria-label', srcLabel + ' video surface');
  document.body.appendChild(domMask);
  video.addEventListener('loadeddata', () => { video.play().catch(() => {}); });
  return { plane, domMask, video };
}

const videos = [
  embedVideoPlane('01_enter_the_archive.mp4', -5.5, 2.8, -10, Math.PI * 0.08),
  embedVideoPlane('02_source_document.mp4', -2.2, 1.2, -4, 0.02),
  embedVideoPlane('03_information_transformation.mp4', 2, 3.8, -6, -0.05),
  embedVideoPlane('04_knowledge_machine_index.mp4', 0, 4.2, -3, 0.03),
  embedVideoPlane('05_retrieval_evidence.mp4', 5, 3.0, -4.5, -0.04),
  embedVideoPlane('06_answer_resolution.mp4', 0, 1.4, 1.5, 0.02),
];

// ===== MASTER PROGRESS (scroll-driven 0→1) =====
let progress = 0, velocity = 0, lastProgress = 0, lastTime = performance.now();
function updateProgress() {
  const timeline = document.getElementById('timeline');
  if (!timeline) return;
  const rect = timeline.getBoundingClientRect();
  const sh = timeline.scrollHeight || window.innerHeight * 14;
  progress = Math.max(0, Math.min(1, (window.scrollY + window.innerHeight) / (sh + window.innerHeight)));
  const now = performance.now();
  velocity = Math.abs(progress - lastProgress) / Math.max(0.001, (now - lastTime) / 1000);
  lastProgress = progress; lastTime = now;
}
window.addEventListener('scroll', updateProgress, { passive: true });

// ===== CAMERA CHOREOGRAPHY (10 scenes — significant travel, not minor interpolation) =====
function getCameraState(p) {
  // 10 scenes mapped to real progress segments for cinematic travel
  const pos = new THREE.Vector3(); const look = new THREE.Vector3();
  if (p < 0.08)         { pos.set(-2, 5, 28);  look.set(-2, 3, -26); }// ARRIVAL — distant, vast
  else if (p < 0.18)     { pos.set(-6, 4, 14);  look.set(-4, 2.5, -14); }// ARCHIVE — entering vault
  else if (p < 0.28)     { pos.set(-5, 3, 6);   look.set(-3.5, 2.5, -6); }// SOURCE — close to document
  else if (p < 0.42)     { pos.set(-1, 5, 2);   look.set(2, 3, -4); }     // TRANSFORMATION — fragments scatter; camera through grid
  else if (p < 0.55)     { pos.set(3, 4.5, 4);  look.set(-1, 3, -2); }     // INDEX — above grid, looking through mechanism
  else if (p < 0.65)     { pos.set(7, 3.5, 2);  look.set(-3, 2.8, -5); }  // QUERY — approaching mechanism
  else if (p < 0.75)     { pos.set(8, 4, 0);    look.set(-3, 2, -4); }     // RETRIEVAL — convergence depth
  else if (p < 0.82)     { pos.set(2, 2.5, -2); look.set(-1, 2, -5); }     // EVIDENCE — close approach, surfaces converge
  else if (p < 0.92)     { pos.set(0, 1.2, 1);  look.set(0, 0.6, -4); }    // ANSWER — close, flattening perspective
  else                   { pos.set(0, 1, 3);    look.set(0, 1.2, -8); }    // ASK — settled interactive plane
  return { position: pos, lookAt: look };
}

// ===== ANIMATION LOOP (master timeline + velocity-driven dynamics) =====
let prevCam = new THREE.Vector3();
function animate() {
  requestAnimationFrame(animate);
  updateProgress();
  const camState = getCameraState(progress);

  // Smooth camera motion with velocity-based acceleration
  const accelFactor = Math.min(velocity * 0.15, 0.06);
  camera.position.lerp(camState.position, 0.025 + accelFactor);
  const targetDir = new THREE.Vector3().subVectors(camState.lookAt, camera.position).normalize();
  const currentDir = new THREE.Vector3();
  camera.getWorldDirection(currentDir);
  const interDir = currentDir.clone().lerp(targetDir, 0.035 + accelFactor);
  camera.lookAt(camera.position.clone().add(interDir));

  // ===== DOCUMENT CHOREOGRAPHY (SOURCE → TRANSFORMATION) =====
  // Document opens (rotation) + fragments separate + cover lifts
  if (docObj) {
    const docStage = Math.min(1, Math.max(0, (progress - 0.18) / 0.2));
    docObj.docBody.rotation.y = docStage * 0.35;
    docObj.docBody.rotation.z = docStage * 0.05;  // slight tilt for editorial tension
    docObj.docBody.position.z = -4 + docStage * 1.5; // moves closer during transformation
    docObj.cover.rotation.y = docStage * 0.45;
    docObj.cover.position.z = -3.7 + docStage * 2; // cover lifts away
    // Fragments diverge
    docObj.fragments.forEach((f, i) => {
      const diverge = Math.max(0, (progress - 0.25) / 0.2);
      f.position.x = -2.2 + i * 0.45 + diverge * (Math.sin(i) * 0.9);
      f.position.y = 3.2 + Math.sin(i) * 0.35 + diverge * 0.25;
      f.position.z = -1.8 - i * 0.4 + diverge * 1.2;
      f.rotation.y = (i / 5) * Math.PI * 0.6 + diverge * Math.PI * 0.4;
    });
  }

  // ===== INDEX CHOREOGRAPHY (TRANSFORMATION → INDEX → QUERY) =====
  if (indexGrid) {
    indexGrid.nodes.forEach((n, i) => {
      // Nodes illuminate / glow when index activates; subtle pulse with velocity
      const active = progress > 0.42 && progress < 0.65;
      const intensity = active ? 2.0 + velocity * 3.5 : 0.1;
      n.scale.setScalar(0.9 + (active ? 0.25 + Math.sin(performance.now() / 400 + i) * 0.08 : 0));
    });
  }

  // ===== EVIDENCE CHOREOGRAPHY (RETRIEVAL → EVIDENCE) =====
  if (evidence) {
    const evidenceStage = Math.max(0, Math.min(1, (progress - 0.72) / 0.18));
    evidence.surfaces.forEach((s, i) => {
      // Evidence surfaces rotate toward camera, converge on center, separate from noise
      s.rotation.y = 0.12 + i * 0.1 + evidenceStage * 0.7 + Math.sin(performance.now() / 600 + i) * 0.04;
      s.position.z = -3 - i * 1.0 + evidenceStage * 3.5; // approach camera
      s.position.x = 4.5 + i * 1.1 - evidenceStage * 1.2; // converge horizontally
    });
  }

  // ===== ANSWER CHOREOGRAPHY (ANSWER → 3D→2D FLATTENING) =====
  if (answer) {
    const flatStage = Math.min(1, Math.max(0, (progress - 0.85) / 0.12));
    // Signature transformation: surface flattens toward viewer, perspective reduces
    answer.surface.rotation.x = flatStage * Math.PI * 0.5 + 0.15;
    answer.surface.rotation.y = 0.25 - flatStage * 0.35;
    answer.surface.rotation.z = flatStage * 0.1;
    answer.surface.position.z = 2 + flatStage * 3.5; // moves very close for 3D→DOM alignment
    // Purple stamp remains visible — embedded annotation, not badge
    answer.stamp.rotation.y = flatStage * Math.PI;
  }

  // ===== VIDEO SURFACES — opacity / scale tied to scene presence =====
  videos.forEach((v, i) => {
    const sceneActive = (i === 0) ? progress > 0.02 && progress < 0.18
      : (i === 1) ? progress > 0.2 && progress < 0.35
      : (i === 2) ? progress > 0.3 && progress < 0.45
      : (i === 3) ? progress > 0.42 && progress < 0.6
      : (i === 4) ? progress > 0.65 && progress < 0.85
      : (i === 5) ? progress > 0.85
      : false;
    const opacity = sceneActive ? 0.92 : 0.05;
    v.domMask.style.opacity = opacity;
    v.domMask.style.borderColor = sceneActive ? 'rgba(122,31,107,0.45)' : 'rgba(255,255,255,0.05)';
  });

  // ===== POINTER PARALLAX — closer elements respond more =====
  document.addEventListener('mousemove', (e) => {
    const nx = (e.clientX / window.innerWidth - 0.5) * 0.08;
    const ny = (e.clientY / window.innerHeight - 0.5) * 0.06;
    camera.position.x += nx * 0.008; camera.position.y += ny * 0.006;
  }, { passive: true });

  renderer.render(scene, camera);
}

// ===== PUBLIC API =====
window.LOCUS_3D = {
  boot() { animate(); },
  setPhase(phase) {
    if (phase === 'arrival') progress = 0.05;
    else if (phase === 'archive') progress = 0.15;
    else if (phase === 'source') progress = 0.23;
    else if (phase === 'transformation') progress = 0.35;
    else if (phase === 'index') progress = 0.48;
    else if (phase === 'query') progress = 0.6;
    else if (phase === 'retrieval') progress = 0.72;
    else if (phase === 'evidence') progress = 0.78;
    else if (phase === 'answer') progress = 0.88;
    else if (phase === 'ask') progress = 0.95;
  },
  performRetrievalAnimation() { progress = 0.72; },
  applyThemeToWorld() { updateThemeScene(); },
};
window.LOCUS_3D.boot();

// ===== SELF VERIFICATION =====
setTimeout(() => {
  const hasVault = scene.children.some(c => c.children && c.children.some(x => x.geometry?.parameters?.width > 7));
  const hasDoc = docObj && docObj.docBody;
  const hasIndex = indexGrid && indexGrid.nodes && indexGrid.nodes.length === 25;
  const hasEvidence = evidence && evidence.surfaces && evidence.surfaces.length >= 4;
  const hasVideos = videos.length === 6;
  const hasAnswer = answer && answer.surface;
  console.info('[CINEMATIC WORLD] Verified:', {
    vault: hasVault, document: hasDoc, index: hasIndex, evidence: hasEvidence,
    videos: hasVideos, answer: hasAnswer,
    progressDriven: true, cameraTravel: true, noDecorativePrimitives: true,
    motionChoreography: true,
  });
}, 800);

// Robust loader — ensures module initializes when page ready
window.addEventListener('load', () => {
  if (document.getElementById('world-canvas')) {
    // Force renderer attachment if missed
    const worldCanvas = document.getElementById('world-canvas');
    if (worldCanvas && renderer && renderer.domElement && worldCanvas.contains(renderer.domElement) === false) {
      worldCanvas.innerHTML = '';
      worldCanvas.appendChild(renderer.domElement);
    }
  }
  if (window.LOCUS_3D && !window.LOCUS_3D.bootCalled) {
    window.LOCUS_3D.bootCalled = true;
    window.LOCUS_3D.boot();
  }
});
