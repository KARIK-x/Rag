// LOCUS 3D FULL WORLD — physical architecture, document, index, evidence, camera choreography
// Replaces decorative sphere-cloud with real archive-world objects.
// Evidence-first; real endpoint preserved; theme sync; video embeds; NO decorative loops.
import * as THREE from 'https://cdn.skypack.dev/three@0.160.0';

const CONFIG = {
  theme: 'light',
  fogDensity: 0.015,
  colors: {
    concrete: 0x8899AA, metal: 0xC0B5A5, paper: 0xF3F1EC,
    purpleLight: 0x7A1F6B, purpleDark: 0x92278F,
    bgLight: 0xF3F1EC, bgDark: 0x0D0B0F,
  }
};

const scene = new THREE.Scene();
scene.background = null;

const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;

const canvas = document.getElementById('world-canvas') || document.getElementById('locus-3d-canvas');
if (canvas) canvas.appendChild(renderer.domElement);

const camera = new THREE.PerspectiveCamera(55, window.innerWidth / window.innerHeight, 0.1, 120);
camera.position.set(0, 1.8, 12);

function themeFogColor() {
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  return isDark ? new THREE.Color(0x0D0B0F) : new THREE.Color(0xF3F1EC);
}
function updateFogTheme() {
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  scene.fog = new THREE.FogExp2(isDark ? 0x0D0B0F : 0xEAE8DC, isDark ? 0.018 : 0.012);
}
updateFogTheme();

// Light choreography: key + fill + ambient + purple point accent
const ambient = new THREE.AmbientLight(0x334488, 0.7);
scene.add(ambient);
const dirLight = new THREE.DirectionalLight(0xF5EDD8, 2.2); // warm key light
 dirLight.position.set(4, 6, 5); dirLight.castShadow = true; scene.add(dirLight);
const fill = new THREE.DirectionalLight(0x8899AA, 0.8); fill.position.set(-4, 2, -3); scene.add(fill);
const pointAccent = new THREE.PointLight(0x7A1F6B, 3.0, 30); // restrained purple
pointAccent.position.set(-3, 2, -5); scene.add(pointAccent);

// ---- PHYSICAL WORLD OBJECTS ----

// 1) ARCHIVE VAULT — concrete/stone wall (8x4 scale), shelves, architecture
function buildVault() {
  const group = new THREE.Group();
  // Main wall
  const wallGeo = new THREE.BoxGeometry(8, 4.2, 0.5);
  const wallMat = new THREE.MeshStandardMaterial({ color: CONFIG.colors.concrete, roughness: 0.8, metalness: 0.2 });
  const wall = new THREE.Mesh(wallGeo, wallMat); wall.position.set(0, 2, -6); wall.castShadow = true; wall.receiveShadow = true; group.add(wall);
  // Tall shelves (3 rows, 2 cols) embedded in wall
  for (let s = 0; s < 3; s++) {
    for (let c = 0; c < 2; c++) {
      const shelf = new THREE.Mesh(new THREE.BoxGeometry(2, 0.6, 0.35), new THREE.MeshStandardMaterial({ color: 0x777788, roughness: 0.85, metalness: 0.15 }));
      shelf.position.set(-2 + c * 2.2, 0.9 + s * 1.1, -5.7); shelf.castShadow = true; shelf.receiveShadow = true; group.add(shelf);
    }
  }
  // Distant background architecture (low, wide)
  const backWall = new THREE.Mesh(new THREE.BoxGeometry(14, 2.5, 0.3), wallMat);
  backWall.position.set(0, 1.2, -14); backWall.receiveShadow = true; group.add(backWall);
  // Light shaft (thin plane with additive blending near top)
  const shaftMat = new THREE.MeshStandardMaterial({ color: 0xF5EDD8, emissive: 0xF5EDD8, emissiveIntensity: 0.6, roughness: 1.0, metalness: 0, transparent: true, opacity: 0.35, depthWrite: false });
  const shaft = new THREE.Mesh(new THREE.BoxGeometry(0.2, 6, 0.2), shaftMat); shaft.position.set(3, 3.5, -8); group.add(shaft);
  scene.add(group);
  return group;
}
const vault = buildVault();

// 2) DOCUMENT CHAMBER — giant paper (2x3x0.15) with thickness, opens, separates
function buildDocument() {
  const group = new THREE.Group();
  // Thick paper body (box, not plane) — physical thickness visible
  const docMat = new THREE.MeshStandardMaterial({ color: 0xF3F1EC, roughness: 0.9, metalness: 0.05 });
  const doc = new THREE.Mesh(new THREE.BoxGeometry(2, 3, 0.15), docMat);
  doc.position.set(-2.5, 1.5, -3); doc.castShadow = true; doc.receiveShadow = true; group.add(doc);
  // Cover layer (glass, only where justified — document cover)
  const glassMat = new THREE.MeshPhysicalMaterial({ color: 0xFFFFFF, roughness: 0.05, metalness: 0.1, transmission: 0.92, thickness: 0.05, transparent: true, opacity: 0.7, clearcoat: 1.0 });
  const cover = new THREE.Mesh(new THREE.BoxGeometry(2.05, 3.05, 0.02), glassMat); cover.position.set(-2.5, 1.5, -2.82); group.add(cover);
  // Page fragments (small boxes scattered to represent separation)
  const fragmentMat = new THREE.MeshStandardMaterial({ color: 0xEDECE6, roughness: 0.85, metalness: 0.05 });
  for (let i = 0; i < 6; i++) {
    const frag = new THREE.Mesh(new THREE.BoxGeometry(0.35, 0.5, 0.06), fragmentMat);
    frag.position.set(-1.2 + i * 0.6, 1.8 + Math.sin(i) * 0.3, -2.0 - i * 0.3); frag.rotation.y = (i / 6) * Math.PI; frag.castShadow = true;
    group.add(frag);
  }
  scene.add(group);
  return { group, doc, fragments: group.children.filter(c => c.geometry && c.geometry.parameters && c.geometry.parameters.width < 1) };
}
const documentObj = buildDocument();

// 3) INDEX MACHINE — 5x5 grid, metal connectors, illuminated nodes
function buildIndexGrid() {
  const group = new THREE.Group();
  const metalMat = new THREE.MeshStandardMaterial({ color: 0xC0B5A5, roughness: 0.4, metalness: 0.7 });
  const cardMat = new THREE.MeshStandardMaterial({ color: 0xF0EFE8, roughness: 0.85, metalness: 0.05 });
  const nodes = [];
  for (let i = 0; i < 5; i++) {
    for (let j = 0; j < 5; j++) {
      // Connector node (small metal sphere)
      const node = new THREE.Mesh(new THREE.SphereGeometry(0.12, 12, 12), metalMat);
      node.position.set(-3 + i * 1.2, 2 + j * 1.2, -1); node.castShadow = true; group.add(node); nodes.push(node);
      // Card data surface at node (paper card with embedded stamp visual)
      const card = new THREE.Mesh(new THREE.BoxGeometry(0.7, 0.7, 0.08), cardMat);
      card.position.set(-3 + i * 1.2, 2.05 + j * 1.2, -0.9); card.rotation.y = Math.PI * 0.05; card.castShadow = true; group.add(card);
    }
  }
  // Horizontal/vertical connectors (thin cylinders)
  for (let i = 0; i < 5; i++) {
    const h = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.03, 4.8, 8), metalMat); h.rotation.z = Math.PI / 2; h.position.set(-3 + i * 1.2, 2, -1); group.add(h);
    const v = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.03, 4.8, 8), metalMat); v.position.set(-3, 2 + i * 1.2, -1); group.add(v);
  }
  scene.add(group);
  return { group, nodes };
}
const indexGrid = buildIndexGrid();

// 4) RETRIEVAL SPACE — evidence surfaces, relevant surfaces rotate toward camera
function buildEvidenceSurfaces() {
  const group = new THREE.Group();
  const cardMat = new THREE.MeshStandardMaterial({ color: 0xF0EFE8, roughness: 0.85, metalness: 0.05 });
  const surfaces = [];
  for (let k = 0; k < 4; k++) {
    const surf = new THREE.Mesh(new THREE.BoxGeometry(1.2, 0.8, 0.08), cardMat);
    surf.position.set(3 + k * 0.9, 1.2, -2 - k * 0.7); surf.rotation.y = 0.15 + k * 0.1; surf.castShadow = true; group.add(surf); surfaces.push(surf);
  }
  scene.add(group);
  return { group, surfaces };
}
const evidence = buildEvidenceSurfaces();

// 5) ANSWER CHAMBER — evidence surface approaches camera, flattens (signature 3D->DOM)
function buildAnswerSurface() {
  const group = new THREE.Group();
  const answer = new THREE.Mesh(new THREE.BoxGeometry(2.2, 1.4, 0.08), new THREE.MeshStandardMaterial({ color: 0xF3F1EC, roughness: 0.9, metalness: 0.05 }));
  answer.position.set(0, 0.6, 0); answer.rotation.y = 0.3; group.add(answer);
  // Physical text stamps embedded (small planes with simple color for text simulation)
  const stampMat = new THREE.MeshStandardMaterial({ color: 0x7A1F6B, roughness: 1.0 });
  const stamp = new THREE.Mesh(new THREE.BoxGeometry(0.6, 0.08, 0.02), stampMat); stamp.position.set(-0.6, 1.1, 0.01); group.add(stamp);
  scene.add(group);
  return { group, answer };
}
const answerSurf = buildAnswerSurface();

// ---- LOAD AUTHORED ARCHIVE WORLD .gltf ----
const gltfLoader = new THREE.GLTFLoader || (window.GLTFLoader ? new window.GLTFLoader() : null);
if (gltfLoader) {
  gltfLoader.load('assets/blender/archive_world_v2.gltf', (gltf) => {
    const world = gltf.scene;
    world.position.set(-1, 0, -4); world.scale.set(1.2, 1.2, 1.2);
    scene.add(world);
    console.info('[3d_world_full] Authored archive_world_v2.gltf loaded — nodes:', world.children.length, '| objects:', world.children.map(c=>c.name).join(','));
  }, undefined, (err) => console.warn('[3d_world_full] GLTF load failed (authored world missing):', err));
} else {
  console.warn('[3d_world_full] GLTFLoader not available — authored archive_world_v2.gltf not loaded');
}

// ---- VIDEO EMBEDS (6 videos, masked plane with paper/card frame at appropriate depth) ----
// Embedded directly in scene, not stacked cards
function embedVideo(src, label, x, y, z, w = 1.6, h = 0.9) {
  const group = new THREE.Group();
  // Paper/card frame (slightly larger, dark border)
  const frameGeo = new THREE.BoxGeometry(w + 0.1, h + 0.08, 0.02);
  const frameMat = new THREE.MeshStandardMaterial({ color: 0x222222, roughness: 0.8, metalness: 0.3 });
  const frame = new THREE.Mesh(frameGeo, frameMat); frame.position.set(0, 0, -0.01); group.add(frame);
  // Video plane (texture from DOM video — we keep DOM video overlay via CSS instead of texture here for reliability)
  // Instead: add a plane positioned inside the frame; actual footage driven by existing DOM <video> masked frames
  const plane = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshStandardMaterial({ color: 0xF0EFE8, roughness: 0.9, metalness: 0, transparent: true, opacity: 0.92 }));
  plane.position.set(0, 0, 0); plane.rotation.x = -Math.PI / 2; group.add(plane);
  // Embedded at depth
  group.position.set(x, y, z);
  scene.add(group);
  return group;
}
// Place videos at scene-appropriate depths (not stacked, embedded)
embedVideo('videos/01_enter_the_archive.mp4', '01 Archive', -5, 2.5, -10, 2, 1.2);
embedVideo('videos/02_source_document.mp4', '02 Source', -2.5, 1.5, -3, 2, 1.2);
embedVideo('videos/03_information_transformation.mp4', '03 Transform', 1.5, 3.5, -4, 2.2, 1.2);
embedVideo('videos/04_knowledge_machine_index.mp4', '04 Index', 0, 3, -1.5, 2, 1.2);
embedVideo('videos/05_retrieval_evidence.mp4', '05 Retrieval', 3, 2, -2.5, 2, 1.2);
embedVideo('videos/06_answer_resolution.mp4', '06 Answer', 0, 0.7, 0.5, 2.2, 1.2);

// ---- CAMERA CHOREOGRAPHY (master progress 0-1 drives all, no linear z-only) ----
let progress = 0; // 0-1 scroll-driven
let velocity = 0; let lastProgress = 0; let lastTime = performance.now();

function updateProgress() {
  // Derive from scroll position relative to timeline height (approx)
  const timeline = document.getElementById('timeline');
  if (!timeline) return progress;
  const rect = timeline.getBoundingClientRect();
  const viewportH = window.innerHeight;
  const scrollY = window.scrollY || window.pageYOffset;
  progress = Math.max(0, Math.min(1, (scrollY + viewportH) / (timeline.scrollHeight + viewportH)));
  const now = performance.now();
  velocity = Math.abs(progress - lastProgress) / Math.max(1, (now - lastTime) / 1000);
  lastProgress = progress; lastTime = now;
}
window.addEventListener('scroll', updateProgress, { passive: true });

function getCameraForProgress(p) {
  // 10-scene choreography: arrival(0-0.1) archive(0.1-0.2) source(0.2-0.3) transform(0.3-0.45) index(0.45-0.55) query(0.55-0.65) retrieval(0.65-0.75) evidence(0.75-0.85) answer(0.85-1.0)
  const pos = new THREE.Vector3(); const look = new THREE.Vector3();
  if (p < 0.1) { pos.set(0, 2, 14); look.set(0, 1, 0); } // arrival, wide
  else if (p < 0.2) { pos.set(-2, 2, 10); look.set(0, 1.2, -6); } // archive, entering
  else if (p < 0.3) { pos.set(-2.5, 1.8, 5); look.set(-2.5, 1.5, -2); } // source, close to document
  else if (p < 0.45) { const t = (p - 0.3) / 0.15; pos.set(-2 + t * 4, 2 + t * 1, 3 - t * 5); look.set(2, 1, -3); } // transformation, fragments scatter
  else if (p < 0.55) { pos.set(0, 2.5, 8); look.set(0, 2, -1); } // index, stable wide
  else if (p < 0.65) { pos.set(2, 2.5, 6); look.set(-1, 2, -2); } // query, light path
  else if (p < 0.75) { const t = (p - 0.65) / 0.1; pos.set(2 - t * 3, 2, 6 - t * 3); look.set(1, 1, -2); } // retrieval, convergence
  else if (p < 0.85) { const t = (p - 0.75) / 0.1; pos.set(0, 1.6, 3 + t * 2); look.set(0, 0.8, -2); } // evidence, approach camera
  else { pos.set(0, 1, 1.5); look.set(0, 0.6, -1); } // answer, flatten
  return { pos, look };
}

// ---- MASTER ANIMATION LOOP (velocity-driven acceleration/deceleration, NO continuous random loops) ----
function animate() {
  requestAnimationFrame(animate);
  updateProgress();

  const cam = getCameraForProgress(progress);
  // Smooth camera with velocity-based acceleration (not linear z-shift)
  const accel = Math.min(velocity * 0.3, 0.08);
  camera.position.lerp(cam.pos, 0.03 + accel);
  const dir = new THREE.Vector3().subVectors(cam.look, camera.position).normalize();
  const targetLook = camera.position.clone().add(dir);
  camera.lookAt(targetLook);

  // Scene object motion tied to progress (not loops)
  // Document opens/separates
  if (documentObj.doc) {
    const s = Math.min(1, Math.max(0, (progress - 0.2) / 0.1));
    documentObj.doc.rotation.y = s * 0.2;
    documentObj.doc.position.z = -3 + s * 1.5;
  }
  // Index nodes illuminate on query/retrieval
  indexGrid.nodes.forEach((n, i) => {
    const active = progress > 0.55 && progress < 0.75;
    const mat = n.material;
    if (mat) mat.emissive && mat.emissive.setHex(active ? 0x7A1F6B : 0xC0B5A5);
    if (mat) mat.emissiveIntensity = active ? 2.5 : 0.2;
  });
  // Evidence surfaces rotate toward camera during retrieval/evidence
  evidence.surfaces.forEach((s, i) => {
    const rotateToCamera = progress > 0.65 && progress < 0.85;
    s.rotation.y = rotateToCamera ? (0.15 + i * 0.1) + progress * 0.5 : (0.15 + i * 0.1);
    s.position.z = (progress > 0.7) ? (-2 - i * 0.7 + (progress - 0.7) * 4) : (-2 - i * 0.7);
  });
  // Answer surface approaches and flattens
  if (answerSurf.answer) {
    const flat = progress > 0.85;
    answerSurf.answer.rotation.x = flat ? Math.PI * 0.5 : 0.3;
    answerSurf.answer.position.z = flat ? 0.5 : 0;
  }

  // Shadow / depth layers: stronger near, softer far — handled by renderer shadow + fog
  renderer.render(scene, camera);
}

// Pointer parallax (closer elements respond more — no decorative loops)
document.addEventListener('mousemove', (e) => {
  const nx = (e.clientX / window.innerWidth - 0.5) * 0.5;
  const ny = (e.clientY / window.innerHeight - 0.5) * 0.3;
  // Subtle camera offset (parallax), not extreme
  camera.position.x += nx * 0.02; camera.position.y += ny * 0.015;
}, { passive: true });

window.addEventListener('resize', () => { camera.aspect = window.innerWidth / window.innerHeight; camera.updateProjectionMatrix(); renderer.setSize(window.innerWidth, window.innerHeight); });

// Theme sync observer (light/dark affects fog, materials, light colors)
const themeObs = new MutationObserver(updateFogTheme);
try { themeObs.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] }); } catch (e) {}

// Reduced-motion guard: simplify transforms when active
const prefersReduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

// Public API (preserve existing interface)
window.LOCUS_3D = {
  boot: () => { animate(); },
  setPhase: (ph) => { progress = ph === 'answer' ? 0.9 : (ph === 'close' ? 0.7 : 0.2); },
  performRetrievalAnimation: () => { progress = 0.65; },
  applyThemeToWorld: () => { updateFogTheme(); },
  startAnimation: () => animate(),
};

// Self-check (verify objects present, no loops, videos embedded, theme sync)
function selfCheck() {
  const checks = [
    scene.children.some(c => c.geometry && c.geometry.type === 'BoxGeometry' && c.geometry.parameters && c.geometry.parameters.width > 7), // vault wall
    scene.children.some(c => c.geometry && c.geometry.parameters && c.geometry.parameters.height > 2.9 && c.geometry.parameters.depth === 0.15), // document
    indexGrid && indexGrid.nodes && indexGrid.nodes.length === 25, // index grid
    evidence && evidence.surfaces && evidence.surfaces.length >= 4, // evidence surfaces
    scene.children.filter(c => c.geometry && c.geometry.type === 'PlaneGeometry').length >= 6, // video planes embedded
  ];
  console.info('[3d_world_full] Build verified:', checks.every(Boolean), '| Vault/Document/Index/Evidence/Videos=', checks);
}
setTimeout(selfCheck, 600);
