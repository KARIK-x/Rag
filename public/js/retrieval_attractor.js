/* LOCUS RAG — Retrieval Attractor Prototype
   Integrates into existing world-core.js Three.js scene (no second renderer).
   Information-field convergence: fragments pulled toward relevance point.
   Obeys master GSAP progress; no independent scroll listener. */
(function(){
  'use strict';
  if(typeof THREE==='undefined') return;

  // Config
  const FRAGMENT_COUNT = 180;
  const ATTRACTOR_STRENGTH = 0.08;
  const DAMPING = 0.92;
  const MAX_FORCE = 0.25;

  // Theme-aware colors (light / dark mapped to world-core palette)
  const LIGHT_CANDIDATE = 0x2a2a2e;   // graphite dark
  const LIGHT_ATTRACTOR = 0x92278f;    // LOCUS purple
  const LIGHT_EVIDENCE = 0xf2f0e8;     // warm ivory
  const DARK_CANDIDATE = 0xd6d4ce;     // warm white
  const DARK_ATTRACTOR = 0xa020c0;     // purple accent
  const DARK_EVIDENCE = 0xf8f6ec;      // near-ivory

  // Internal state
  let scene = null, renderer = null, camera = null;
  let fragments = [];
  let attractorPos = new THREE.Vector3(0, 0.5, 2.5);
  let progress = 0, velocity = 0, pointerX = 0, pointerY = 0;
  let reducedMotion = false;
  let active = false;
  let mesh = null; // InstancedMesh

  // Initialize using existing world scene (lazy lookup)
  function resolveWorld(){
    if(window.LOCUS_3D){
      scene = window.LOCUS_3D.getScene();
      camera = window.LOCUS_3D.getCamera();
      renderer = window.LOCUS_3D.getRenderer();
    }
  }

  // Build fragment geometry: small rectangular shards
  function buildFragments(){
    const count = Math.max(10, FRAGMENT_COUNT);
    // Geometry: thin rectangular shard
    const geo = new THREE.BoxGeometry(0.18, 0.08, 0.05);
    // Candidate material
    const isDark = document.body.classList.contains('dark') || document.documentElement.getAttribute('data-theme') === 'dark';
    const mat = new THREE.MeshStandardMaterial({
      color: isDark ? DARK_CANDIDATE : LIGHT_CANDIDATE,
      roughness: 0.9,
      metalness: 0.05,
      transparent: true,
      opacity: 0.85,
      depthWrite: false,
    });
    mesh = new THREE.InstancedMesh(geo, mat, count);
    mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    // Initial spread in a volume around retrieval zone (near document planes)
    const dummy = new THREE.Object3D();
    fragments = [];
    for(let i=0;i<count;i++){
      const angle = Math.random()*Math.PI*2;
      const r = 2.5 + Math.random()*3.5;
      const y = -1 + Math.random()*2.5;
      const x = Math.cos(angle)*r;
      const z = Math.sin(angle)*r + 1;
      dummy.position.set(x, y, z);
      dummy.rotation.set(Math.random()*0.2, Math.random()*Math.PI, Math.random()*0.2);
      dummy.scale.setScalar(0.7 + Math.random()*0.9);
      dummy.updateMatrix();
      mesh.setMatrixAt(i, dummy.matrix);
      fragments.push({
        pos: new THREE.Vector3(x, y, z),
        vel: new THREE.Vector3((Math.random()-0.5)*0.02, (Math.random()-0.5)*0.02, (Math.random()-0.5)*0.02),
        selected: false,
        selectedProgress: 0,
        index: i,
      });
    }
    mesh.instanceMatrix.needsUpdate = true;
    if(scene) scene.add(mesh);
  }

  // Attractor point visual (small purple sphere)
  let attractorMesh = null;
  function buildAttractor(){
    const geo = new THREE.SphereGeometry(0.35, 16, 16);
    const isDark = document.body.classList.contains('dark') || document.documentElement.getAttribute('data-theme') === 'dark';
    const mat = new THREE.MeshStandardMaterial({
      color: isDark ? DARK_ATTRACTOR : LIGHT_ATTRACTOR,
      emissive: isDark ? DARK_ATTRACTOR : LIGHT_ATTRACTOR,
      emissiveIntensity: 0.6,
      roughness: 0.3,
      metalness: 0.7,
      transparent: true,
      opacity: 0.9,
    });
    attractorMesh = new THREE.Mesh(geo, mat);
    attractorMesh.position.copy(attractorPos);
    if(scene) scene.add(attractorMesh);
  }

  // Master update — called by world-core loop or by master scroll (not own loop)
  function update(dt){
    if(!mesh || !scene || reducedMotion || !active) return;
    const progressNow = Math.max(0, Math.min(1, progress || 0));
    // Activation window: retrieval ~0.55 to evidence ~0.78
    if(progressNow < 0.48 || progressNow > 0.85) {
      // Dormant: make fragments calm, attractor minimal
      if(attractorMesh) { attractorMesh.scale.setScalar(0.1); attractorMesh.visible = false; }
      return;
    }
    if(attractorMesh) { attractorMesh.visible = true; attractorMesh.scale.setScalar(1); }

    // Attractor strength scales with progress in window
    const strength = ATTRACTOR_STRENGTH * Math.min(1, (progressNow - 0.48) / 0.25);

    // Subtle pointer influence on attractor
    const ptrInfluence = 0.3;
    attractorPos.set(
      attractorPos.x + (pointerX*ptrInfluence - attractorPos.x*0.05),
      attractorPos.y + (pointerY*ptrInfluence - attractorPos.y*0.05),
      2.5 + Math.sin(progressNow*Math.PI)*0.5
    );
    if(attractorMesh) attractorMesh.position.copy(attractorPos);

    const dummy = new THREE.Object3D();
    for(let i=0;i<fragments.length;i++){
      const f = fragments[i];
      // Distance to attractor
      const dx = attractorPos.x - f.pos.x;
      const dy = attractorPos.y - f.pos.y;
      const dz = attractorPos.z - f.pos.z;
      const distSq = dx*dx + dy*dy + dz*dz;
      const dist = Math.sqrt(distSq) || 1e-3;

      // Attractor force increases as progress increases
      const force = Math.min(MAX_FORCE, strength / (dist + 0.1));
      f.vel.x += (dx/dist)*force;
      f.vel.y += (dy/dist)*force;
      f.vel.z += (dz/dist)*force;

      // Damping
      f.vel.multiplyScalar(DAMPING);

      // Subtle tangential orbit (only near center) — physical feel
      const orbit = 0.02 * Math.sin(progressNow*Math.PI*2 + i*0.05);
      f.vel.x += orbit*(dz/dist);
      f.vel.z -= orbit*(dx/dist);

      // Velocity smoothing response
      const velMag = f.vel.length();
      if(velMag > 0.15) f.vel.multiplyScalar(0.95); // cap excessive speed

      // Position update
      f.pos.add(f.vel);

      // Evidence transition: near center fragments become selected (light/ivory)
      if(dist < 0.9){
        f.selectedProgress = Math.min(1, f.selectedProgress + 0.03);
      } else {
        f.selectedProgress = Math.max(0, f.selectedProgress - 0.02);
      }

      // Scaling / material change via instance coloring handled below (simplified: use matrix for position/rot/scale; material change per instance requires setColorAt — skip for performance, rely on position convergence as visual cue)
      dummy.position.copy(f.pos);
      dummy.rotation.set(0, Math.sin(progressNow*2+i)*0.1, 0);
      const s = 0.7 + f.selectedProgress*0.5; // slightly larger when selected
      dummy.scale.setScalar(s);
      dummy.updateMatrix();
      mesh.setMatrixAt(i, dummy.matrix);
    }
    mesh.instanceMatrix.needsUpdate = true;
  }

  // Theme update (called when theme changes)
  function setTheme(isDark){
    if(!mesh) return;
    mesh.material.color.setHex(isDark ? DARK_CANDIDATE : LIGHT_CANDIDATE);
    if(attractorMesh) {
      const m = attractorMesh.material;
      m.color.setHex(isDark ? DARK_ATTRACTOR : LIGHT_ATTRACTOR);
      m.emissive.setHex(isDark ? DARK_ATTRACTOR : LIGHT_ATTRACTOR);
    }
  }

  // Reduced motion
  function setReducedMotion(enabled){
    reducedMotion = !!enabled;
    if(mesh) mesh.visible = !reducedMotion;
    if(attractorMesh) attractorMesh.visible = !reducedMotion;
  }

  // Public API
  window.RetrievalAttractor = {
    init: function(){
      resolveWorld();
      if(!scene || !mesh){ buildFragments(); buildAttractor(); }
      active = true;
    },
    setProgress: function(p){ progress = p; },
    setVelocity: function(v){ velocity = v; }, // subtle velocity: increase pull slightly with high velocity
    setPointer: function(x,y){ pointerX = x; pointerY = y; },
    setTheme: function(dark){ setTheme(!!dark); },
    setReducedMotion: function(e){ setReducedMotion(!!e); },
    update: function(dt){ update(dt||0.016); },
    dispose: function(){
      if(mesh && scene) scene.remove(mesh); if(attractorMesh && scene) scene.remove(attractorMesh);
      mesh = null; attractorMesh = null; active = false;
    },
  };

  // Auto-init after world ready (if world already loaded)
  if(document.readyState==='complete' || document.readyState==='interactive'){
    setTimeout(()=>{ if(window.RetrievalAttractor && window.RetrievalAttractor.init) window.RetrievalAttractor.init(); }, 300);
  } else {
    window.addEventListener('load', ()=>{ if(window.RetrievalAttractor && window.RetrievalAttractor.init) window.RetrievalAttractor.init(); }, {once:true});
  }
})();
