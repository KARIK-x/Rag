/* LOCUS RAG — Persistent Three.js world (no destroy/recreate)
   8 scenes: ARRIVAL / ENTER / SOURCE / TRANSFORMATION / INDEX / RETRIEVAL / EVIDENCE / ANSWER
   Camera choreography via setCameraState(progress 0-1) from ScrollTrigger.
   Geometric architecture only — lines, rings, boxes, translucent slabs, document planes.
   Dark charcoal #030406 + deep purple #92278f. No particle fields. <350 lines. */

(function(){
  'use strict';
  if(typeof THREE==='undefined'){ console.warn('world-core: Three.js not loaded'); return; }

  const BG = 0x030406, PURPLE = 0x92278f;
  const scenes = ['ARRIVAL','ENTER','SOURCE','TRANSFORMATION','INDEX','RETRIEVAL','EVIDENCE','ANSWER'];

  // Singleton persistent scene
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(BG);
  scene.fog = new THREE.FogExp2(BG, 0.012);

  const renderer = new THREE.WebGLRenderer({antialias:true, alpha:true, preserveDrawingBuffer:true});
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio,2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;

  const canvas = document.getElementById('world-canvas');
  if(canvas) canvas.appendChild(renderer.domElement);

  const camera = new THREE.PerspectiveCamera(55, window.innerWidth/window.innerHeight, 0.1, 120);
  camera.position.set(0,0.6,10);

  // Lights — restrained geometric atmosphere
  const amb = new THREE.AmbientLight(0x334488, 0.9);
  scene.add(amb);
  const dir = new THREE.DirectionalLight(0xa0c8ff, 1.6); dir.position.set(4,5,6); scene.add(dir);
  const pt = new THREE.PointLight(PURPLE, 3, 50); pt.position.set(-5,3,-4); scene.add(pt);

  // Geometry groups — static architecture rebuilt only once
  const groups = { rings: new THREE.Group(), slabs: new THREE.Group(), docs: new THREE.Group(), lines: new THREE.Group() };
  scene.add(groups.rings); scene.add(groups.slabs); scene.add(groups.docs); scene.add(groups.lines);

  // Rings (concentric, thin line) per scene position
  for(let i=0;i<6;i++){ const geo = new THREE.TorusGeometry(3+i*1.2, 0.02, 8, 64); const mat = new THREE.MeshStandardMaterial({color:PURPLE, emissive:PURPLE, emissiveIntensity:0.6, transparent:true, opacity:0.35, roughness:0.3, metalness:0.8}); const ring = new THREE.Mesh(geo, mat); ring.position.set(0,0,-4+i*3); ring.rotation.x=Math.PI/2; groups.rings.add(ring); }
  // Translucent slabs (document planes) at scene zones
  for(let i=0;i<8;i++){ const geo = new THREE.BoxGeometry(2.4,1.2,0.06); const mat = new THREE.MeshStandardMaterial({color:0x1a1022, emissive:PURPLE, emissiveIntensity:0.3, transparent:true, opacity:0.35, roughness:0.4, metalness:0.7}); const slab = new THREE.Mesh(geo, mat); slab.position.set((i%4-1.5)*3, 1.2, -3-i*2.5); groups.slabs.add(slab); }
  // Document planes (thin rectangles = source pages) floating near RETRIEVAL / EVIDENCE
  for(let i=0;i<4;i++){ const geo = new THREE.PlaneGeometry(1.8,2.2); const mat = new THREE.MeshStandardMaterial({color:0x2a1f30, emissive:0x92278f, emissiveIntensity:0.25, roughness:0.2, metalness:0.9, side:THREE.DoubleSide}); const plane = new THREE.Mesh(geo, mat); plane.position.set(-3+i*2, 0.5, 2); plane.rotation.y=-0.3-i*0.15; groups.docs.add(plane); }
  // Connection lines — geometric lattice (static, updated position only if needed)
  const lineMat = new THREE.LineBasicMaterial({color:0x6688cc, transparent:true, opacity:0.2, depthWrite:false});
  for(let i=0;i<5;i++){ const p1=new THREE.Vector3(-4+i*2,0.5,-10+i); const p2=new THREE.Vector3(4-i*2,0.5,-4+i); const g=new THREE.BufferGeometry().setFromPoints([p1,p2]); groups.lines.add(new THREE.Line(g,lineMat)); }

  // Fog adjustment on scene change
  const fogDens = [0.012,0.012,0.015,0.015,0.018,0.018,0.012,0.012];

  // Scene camera choreography: 8 keyframes (pos, target, fov, rot, scale) mapped 0-1
  const keyframes = [
    {pos:[0,1.5,12], tgt:[0,0,0], fov:55, rot:[0,0,0], s:1},      // ARRIVAL
    {pos:[-3,2,8],  tgt:[0,0,0], fov:50, rot:[0.1,0,0], s:1},     // ENTER
    {pos:[-4,3,7],  tgt:[2,0,0], fov:52, rot:[0,0.2,0], s:1},     // SOURCE
    {pos:[2,4,9],   tgt:[0,0,0], fov:48, rot:[-0.1,0,0], s:0.95}, // TRANSFORMATION
    {pos:[0,6,6],   tgt:[0,1,0], fov:45, rot:[0,0.15,0], s:1},    // INDEX/MACHINE
    {pos:[3,2,5],   tgt:[0,0,0], fov:55, rot:[0,0,0], s:1.1},     // RETRIEVAL
    {pos:[-2,2.5,8],tgt:[0,0,0], fov:54, rot:[0.05,0,0], s:1},    // EVIDENCE
    {pos:[0,1,12],  tgt:[0,0,0], fov:60, rot:[0,0,0], s:1},       // ANSWER
  ];


  // Procedural bird / knowledge carrier — simple curved path, responds to pointer subtly
  const birdGeo = new THREE.BufferGeometry();
  // Line-based bird: two crossing lines (suggestive wing/body) on a curved path
  const birdPts = [];
  for(let i=0;i<=30;i++){ const t=i/30; birdPts.push(new THREE.Vector3(Math.sin(t*Math.PI*2)*2.5, Math.sin(t*Math.PI)*0.8+1.5, -6+t*8)); }
  birdGeo.setFromPoints(birdPts);
  const birdMat = new THREE.LineBasicMaterial({ color: 0xF3F1EC, transparent:true, opacity:0.9 });
  const birdLine = new THREE.Line(birdGeo, birdMat);
  scene.add(birdLine);
  // Cross wing lines
  const wingGeo = new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(-0.6,0.3,0), new THREE.Vector3(0.6,-0.2,0)
  ]);
  const wingMat = new THREE.LineBasicMaterial({ color: 0x92278f, transparent:true, opacity:0.7 });
  const wing = new THREE.Line(wingGeo, wingMat);
  birdLine.add(wing);
  // Pointer response — subtle roll / tilt toward cursor
  document.addEventListener('pointermove', (e)=>{
    const nx = (e.clientX/window.innerWidth-0.5)*2;
    const ny = (e.clientY/window.innerHeight-0.5)*2;
    birdLine.rotation.z = 0.05*nx; birdLine.rotation.x = 0.03*ny;
  }, {passive:true});
  // Animate bird along path
  let birdT = 0;
  function animateBird(){ birdT+=0.003; if(birdT>1) birdT=0;
    const idx = Math.floor(birdT*30); const p = birdPts[idx];
    if(p){ birdLine.position.copy(p); }
    // Subtle pulse
    birdLine.scale.setScalar(1+Math.sin(Date.now()*0.003)*0.05);
  }
  // Wire into existing loop by adding call inside loop (we inject after loop definition, but easiest is to patch loop)

  let currentProgress = 0, animFrame = null, running = true;

  function lerp(a,b,t){ return a+(b-a)*t; }
  function vLerp(a,b,t){ return new THREE.Vector3(lerp(a.x,b.x,t), lerp(a.y,b.y,t), lerp(a.z,b.z,t)); }

  // Camera choreography — called by ScrollTrigger via setCameraState
  function setCameraState(progress){
    currentProgress = Math.max(0, Math.min(1, progress||0));
    const seg = currentProgress*7; // 0..7 across 8 scenes (boundaries continuous)
    const idx = Math.floor(seg); const t = seg - idx;
    const k0 = keyframes[idx]||keyframes[0];
    const k1 = keyframes[Math.min(idx+1, keyframes.length-1)]||keyframes[7];
    const pos = vLerp(new THREE.Vector3(...k0.pos), new THREE.Vector3(...k1.pos), t);
    const tgt = vLerp(new THREE.Vector3(...k0.tgt), new THREE.Vector3(...k1.tgt), t);
    camera.position.copy(pos);
    camera.fov = lerp(k0.fov, k1.fov, t);
    camera.updateProjectionMatrix();
    const rotY = lerp(k0.rot[1], k1.rot[1], t);
    camera.lookAt(tgt);
    // Rotate camera around Y slightly based on scene
    camera.rotation.y += rotY*0.02;
    // Fog transition by scene segment
    const fIdx = Math.round(currentProgress*7);
    scene.fog.density = fogDens[Math.min(fIdx, fogDens.length-1)];
    // Subtle object arrangement shift (slabs move slightly by scene)
    groups.slabs.children.forEach((s,i)=>{ s.position.z = -3 - (i*2.5) - (currentProgress*2); });
  }

  // Retrieval animation (triggered by search submit)
  function performRetrievalAnimation(query){
    // Intensify lighting + fog, highlight document planes near RETRIEVAL
    scene.fog.density = 0.025;
    pt.intensity = 6; pt.color.setHex(0xffaa66);
    groups.docs.children.forEach(p=>{ p.material.emissiveIntensity = 0.7; p.scale.setScalar(1.15); });
    // Camera push toward retrieval zone briefly
    const orig = camera.position.clone();
    const target = new THREE.Vector3(3,2,5);
    let step = 0;
    (function animateRetrieval(){ step++;
      const f = Math.min(1, step/45);
      camera.position.lerpVectors(orig, target, f*0.08); camera.lookAt(new THREE.Vector3(0,0,0));
      if(f<1 && running){ animFrame = requestAnimationFrame(animateRetrieval); } else { setTimeout(()=>{ scene.fog.density=0.015; pt.intensity=3; pt.color.setHex(PURPLE); groups.docs.children.forEach(p=>{p.material.emissiveIntensity=0.25; p.scale.setScalar(1);}); camera.position.copy(orig); camera.lookAt(new THREE.Vector3(0,0,0));}, 1200); }
    })();
  }

  // Resize
  window.addEventListener('resize',()=>{ camera.aspect=window.innerWidth/window.innerHeight; camera.updateProjectionMatrix(); renderer.setSize(window.innerWidth,window.innerHeight); },{passive:true});

  // Persistent render loop (scene never destroyed/recreated)
  const clock = new THREE.Clock();
  function loop(){ if(!running) return; animFrame = requestAnimationFrame(loop); const dt=clock.getDelta(); const t=clock.getElapsedTime();
    // Gentle ring rotation (geometric, not particle chaos)
    groups.rings.children.forEach((r,i)=>{ r.rotation.z = t*0.08*(i%2===0?1:-1); });
    // Document plane gentle sway
    groups.docs.children.forEach((p,i)=>{ p.rotation.y = Math.sin(t*0.6+i)*0.08; p.rotation.z = Math.sin(t*0.4+i*0.3)*0.05; });
    // Lines subtle pulsing opacity
    groups.lines.children.forEach((ln,i)=>{ ln.material.opacity = 0.15 + Math.sin(t*1.2+i)*0.08; });
    animateBird();
    renderer.render(scene, camera);
  }

  // Public API — exactly as specified
  window.LOCUS_3D = {
    init: function(){ scene.background = new THREE.Color(BG); loop(); },
    setCameraState: setCameraState,
    performRetrievalAnimation: performRetrievalAnimation,
    // Additional helpers (persistent, not replacing scene)
    getScene:()=>scene,
    getCamera:()=>camera,
    getRenderer:()=>renderer,
    scenes: scenes,
  };

  // Init after load (if Three already present; else can be called manually after load)
  if(document.readyState==='complete' || document.readyState==='interactive'){
    setTimeout(()=>{ if(window.LOCUS_3D && window.LOCUS_3D.init) window.LOCUS_3D.init(); }, 100);
  } else {
    window.addEventListener('load', ()=>{ if(window.LOCUS_3D && window.LOCUS_3D.init) window.LOCUS_3D.init(); }, {once:true});
  }
})();
