// Three.js abstract LOCUS intelligence network
// Direct WebGL in canvas — no React framework needed (three installed at node_modules/three)
import * as THREE from 'three';
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x080820);
scene.fog = new THREE.FogExp2(0x080820, 0.015);

const camera = new THREE.PerspectiveCamera(60, window.innerWidth/window.innerHeight, 0.1, 100);
camera.position.set(0, 0.8, 4);

const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
document.getElementById('locus-3d-canvas').appendChild(renderer.domElement);

// Lighting — premium depth
const amb = new THREE.AmbientLight(0xffffff, 0.4);
scene.add(amb);
const dir = new THREE.DirectionalLight(0xa0c8ff, 2.0);
dir.position.set(3, 2, 5);
scene.add(dir);
const point = new THREE.PointLight(0xffaa77, 3, 20);
point.position.set(-2, 1, 2);
scene.add(point);

// Abstract geometric network nodes
const nodes = [];
const count = 60;
for (let i = 0; i < count; i++) {
  const geo = new THREE.SphereGeometry(0.05 + Math.random()*0.08, 8, 8);
  const mat = new THREE.MeshStandardMaterial({ color: 0x88ccff, emissive: 0x224488, roughness: 0.3, metalness: 0.7 });
  const mesh = new THREE.Mesh(geo, mat);
  mesh.position.set((Math.random()-0.5)*6, (Math.random()-0.5)*4, (Math.random()-0.5)*6);
  mesh.userData = { vx: (Math.random()-0.5)*0.01, vy: (Math.random()-0.5)*0.01, vz: (Math.random()-0.5)*0.01 };
  scene.add(mesh);
  nodes.push(mesh);
}

// Connections (lines between nearby nodes)
const lineMat = new THREE.LineBasicMaterial({ color: 0x5588ff, transparent: true, opacity: 0.25 });
const lines = [];
for (let i = 0; i < nodes.length; i++) {
  for (let j = i+1; j < nodes.length; j++) {
    const d = nodes[i].position.distanceTo(nodes[j].position);
    if (d < 1.4) {
      const geom = new THREE.BufferGeometry().setFromPoints([nodes[i].position, nodes[j].position]);
      const line = new THREE.Line(geom, lineMat);
      scene.add(line); lines.push({line, i, j});
    }
  }
}

let mouse = new THREE.Vector2(0, 0);
document.addEventListener('mousemove', e => { mouse.x = (e.clientX/window.innerWidth)*2-1; mouse.y = -(e.clientY/window.innerHeight)*2+1; }, { passive: true });

function animate() {
  requestAnimationFrame(animate);
  const t = Date.now()*0.001;
  nodes.forEach(n => {
    n.position.x += n.userData.vx; n.position.y += n.userData.vy; n.position.z += n.userData.vz;
    if (Math.abs(n.position.x)>3) n.userData.vx *= -1; if (Math.abs(n.position.y)>2) n.userData.vy *= -1; if (Math.abs(n.position.z)>3) n.userData.vz *= -1;
    n.rotation.y = t*0.5;
  });
  // Cursor-reactive camera tilt
  camera.rotation.y = mouse.x*0.08; camera.rotation.x = mouse.y*0.05;
  camera.position.x = Math.sin(t*0.2)*0.3; camera.position.y = 0.8 + Math.sin(t*0.3)*0.2;
  renderer.render(scene, camera);
}
animate();
window.addEventListener('resize', () => { camera.aspect = window.innerWidth/window.innerHeight; camera.updateProjectionMatrix(); renderer.setSize(window.innerWidth, window.innerHeight); });
