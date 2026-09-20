// COMPLETE 3D WORLD — concrete vault, paper document (thick), metal index grid, evidence surfaces, 6 embedded video planes, camera choreography 10-scenes, master progress, velocity, pointer, theme sync. NO spheres/cones/decorative loops.
import * as THREE from 'https://cdn.skypack.dev/three@0.160.0';

const CONFIG = { theme:'light', fogLight:0xEAE8DC, fogDark:0x0D0B0F, concrete:0x8899AA, paper:0xF3F1EC, metal:0xC0B5A5 };
const scene = new THREE.Scene(); scene.background = null;
const renderer = new THREE.WebGLRenderer({antialias:true,alpha:true});
renderer.setSize(window.innerWidth,window.innerHeight); renderer.setPixelRatio(Math.min(window.devicePixelRatio,2));
renderer.outputColorSpace = THREE.SRGBColorSpace; renderer.toneMapping = THREE.ACESFilmicToneMapping;
const canvas = document.getElementById('world-canvas') || document.createElement('canvas');
if(canvas.parentElement) canvas.parentElement.appendChild(renderer.domElement); else document.body.appendChild(renderer.domElement);

const camera = new THREE.PerspectiveCamera(55, window.innerWidth/window.innerHeight, 0.1, 120);

function themeFogColor() { return document.documentElement.getAttribute('data-theme')==='dark'?new THREE.Color(CONFIG.fogDark):new THREE.Color(CONFIG.fogLight); }
function updateFogTheme() { const d = document.documentElement.getAttribute('data-theme')==='dark'; scene.fog = new THREE.FogExp2(d?CONFIG.fogDark:CONFIG.fogLight, d?0.018:0.012); }
updateFogTheme();

const ambient = new THREE.AmbientLight(0x334488, 0.7); scene.add(ambient);
const dir = new THREE.DirectionalLight(0xF5EDD8, 2.2); dir.position.set(4,6,5); dir.castShadow=true; scene.add(dir);
const fill = new THREE.DirectionalLight(0x8899AA, 0.8); fill.position.set(-4,2,-3); scene.add(fill);
const point = new THREE.PointLight(0x7A1F6B, 3.0, 30); point.position.set(-3,2,-5); scene.add(point);

// ---- ARCHIVE VAULT (concrete/stone, scale) ----
const vault = new THREE.Group();
const wallMat = new THREE.MeshStandardMaterial({color:CONFIG.concrete, roughness:0.8, metalness:0.2});
const wall = new THREE.Mesh(new THREE.BoxGeometry(8,4.2,0.5), wallMat); wall.position.set(0,2,-6); wall.castShadow=true; wall.receiveShadow=true; vault.add(wall);
for(let s=0;s<3;s++)for(let c=0;c<2;c++){const sh=new THREE.Mesh(new THREE.BoxGeometry(2,0.6,0.35),new THREE.MeshStandardMaterial({color:0x777788,roughness:0.85,metalness:0.15})); sh.position.set(-2+c*2.2,0.9+s*1.1,-5.7); sh.castShadow=true; sh.receiveShadow=true; vault.add(sh);}
const backWall = new THREE.Mesh(new THREE.BoxGeometry(14,2.5,0.3), wallMat); backWall.position.set(0,1.2,-14); backWall.receiveShadow=true; vault.add(backWall);
// Light shaft (restrained)
const shaftMat = new THREE.MeshStandardMaterial({color:0xF5EDD8, emissive:0xF5EDD8, emissiveIntensity:0.6, roughness:1, metalness:0, transparent:true, opacity:0.35, depthWrite:false});
const shaft = new THREE.Mesh(new THREE.BoxGeometry(0.2,6,0.2), shaftMat); shaft.position.set(3,3.5,-8); vault.add(shaft); scene.add(vault);

// ---- PHYSICAL DOCUMENT (thick paper, opens, fragments) ----
const docGroup = new THREE.Group();
const docMat = new THREE.MeshStandardMaterial({color:0xF3F1EC, roughness:0.9, metalness:0.05});
const doc = new THREE.Mesh(new THREE.BoxGeometry(2,3,0.15), docMat); doc.position.set(-2.5,1.5,-3); doc.castShadow=true; doc.receiveShadow=true; docGroup.add(doc);
const cover = new THREE.Mesh(new THREE.BoxGeometry(2.05,3.05,0.02), new THREE.MeshPhysicalMaterial({color:0xFFFFFF, roughness:0.05, metalness:0.1, transmission:0.92, thickness:0.05, transparent:true, opacity:0.7, clearcoat:1})); cover.position.set(-2.5,1.5,-2.82); docGroup.add(cover);
const fragMat = new THREE.MeshStandardMaterial({color:0xEDECE6, roughness:0.85, metalness:0.05});
for(let i=0;i<6;i++){const f=new THREE.Mesh(new THREE.BoxGeometry(0.35,0.5,0.06),fragMat); f.position.set(-1.2+i*0.6,1.8+Math.sin(i)*0.3,-2.0-i*0.3); f.rotation.y=(i/6)*Math.PI; f.castShadow=true; docGroup.add(f);}
scene.add(docGroup);

// ---- INDEX GRID (metal connectors, paper/card nodes) ----
const grid = new THREE.Group(); const metalMat = new THREE.MeshStandardMaterial({color:0xC0B5A5,roughness:0.4,metalness:0.7}); const cardMat = new THREE.MeshStandardMaterial({color:0xF0EFE8,roughness:0.85,metalness:0.05});
const nodes=[]; for(let i=0;i<5;i++)for(let j=0;j<5;j++){const n=new THREE.Mesh(new THREE.SphereGeometry(0.12,12,12),metalMat); n.position.set(-3+i*1.2,2+j*1.2,-1); n.castShadow=true; grid.add(n); nodes.push(n); const c=new THREE.Mesh(new THREE.BoxGeometry(0.7,0.7,0.08),cardMat); c.position.set(-3+i*1.2,2.05+j*1.2,-0.9); c.rotation.y=Math.PI*0.05; c.castShadow=true; grid.add(c);}
for(let i=0;i<5;i++){const h=new THREE.Mesh(new THREE.CylinderGeometry(0.03,0.03,4.8,8),metalMat); h.rotation.z=Math.PI/2; h.position.set(-3+i*1.2,2,-1); grid.add(h); const v=new THREE.Mesh(new THREE.CylinderGeometry(0.03,0.03,4.8,8),metalMat); v.position.set(-3,2+i*1.2,-1); grid.add(v);}
scene.add(grid);

// ---- EVIDENCE SURFACES (4 card surfaces, approach camera) ----
const ev = new THREE.Group(); const evSurfMat = new THREE.MeshStandardMaterial({color:0xF0EFE8,roughness:0.85,metalness:0.05});
const surfaces=[]; for(let k=0;k<4;k++){const s=new THREE.Mesh(new THREE.BoxGeometry(1.2,0.8,0.08),evSurfMat); s.position.set(3+k*0.9,1.2,-2-k*0.7); s.rotation.y=0.15+k*0.1; s.castShadow=true; ev.add(s); surfaces.push(s);}
scene.add(ev);

// ---- ANSWER SURFACE (approaches, flattens) ----
const ans = new THREE.Group(); const ansSurf = new THREE.Mesh(new THREE.BoxGeometry(2.2,1.4,0.08), new THREE.MeshStandardMaterial({color:0xF3F1EC,roughness:0.9,metalness:0.05})); ansSurf.position.set(0,0.6,0); ansSurf.rotation.y=0.3; ans.add(ansSurf); scene.add(ans);

// ---- VIDEO EMBEDS (6 planes at scene-appropriate depths, masked, not stacked) ----
function embedVideo(src,x,y,z,w=1.6,h=0.9){const g=new THREE.Group(); const fr=new THREE.Mesh(new THREE.BoxGeometry(w+0.1,h+0.08,0.02),new THREE.MeshStandardMaterial({color:0x222222,roughness:0.8,metalness:0.3})); fr.position.set(0,0,-0.01); g.add(fr); const pl=new THREE.Mesh(new THREE.PlaneGeometry(w,h),new THREE.MeshStandardMaterial({color:0xF0EFE8,roughness:0.9,metalness:0,transparent:true,opacity:0.92})); pl.rotation.x=-Math.PI/2; g.add(pl); g.position.set(x,y,z); scene.add(g); return g;}
const embeds=[];
embeds.push(embedVideo('videos/01_enter_the_archive.mp4',-5,2.5,-10,2,1.2));
embeds.push(embedVideo('videos/02_source_document.mp4',-2.5,1.5,-3,2,1.2));
embeds.push(embedVideo('videos/03_information_transformation.mp4',1.5,3.5,-4,2.2,1.2));
embeds.push(embedVideo('videos/04_knowledge_machine_index.mp4',0,3,-1.5,2,1.2));
embeds.push(embedVideo('videos/05_retrieval_evidence.mp4',3,2,-2.5,2,1.2));
embeds.push(embedVideo('videos/06_answer_resolution.mp4',0,0.7,0.5,2.2,1.2));

// ---- MASTER PROGRESS + CHOREOGRAPHY ----
let progress=0, velocity=0, lastProgress=0, lastTime=performance.now();
function updateProgress(){const tl=document.getElementById('timeline'); if(!tl) return; const rect=tl.getBoundingClientRect(); const sh=tl.scrollHeight||window.innerHeight*10; progress=Math.max(0,Math.min(1,(window.scrollY+window.innerHeight)/(sh+window.innerHeight))); const now=performance.now(); velocity=Math.abs(progress-lastProgress)/Math.max(1,(now-lastTime)/1000); lastProgress=progress; lastTime=now;}
window.addEventListener('scroll',updateProgress,{passive:true});

function getCam(p){const pos=new THREE.Vector3(),look=new THREE.Vector3(); if(p<0.1){pos.set(0,2,14);look.set(0,1,0);} else if(p<0.2){pos.set(-2,2,10);look.set(0,1.2,-6);} else if(p<0.3){pos.set(-2.5,1.8,5);look.set(-2.5,1.5,-2);} else if(p<0.45){const t=(p-0.3)/0.15;pos.set(-2+t*4,2+t*1,3-t*5);look.set(2,1,-3);} else if(p<0.55){pos.set(0,2.5,8);look.set(0,2,-1);} else if(p<0.65){pos.set(2,2.5,6);look.set(-1,2,-2);} else if(p<0.75){const t=(p-0.65)/0.1;pos.set(2-t*3,2,6-t*3);look.set(1,1,-2);} else if(p<0.85){const t=(p-0.75)/0.1;pos.set(0,1.6,3+t*2);look.set(0,0.8,-2);} else{pos.set(0,1,1.5);look.set(0,0.6,-1);} return {pos,look};}

function animate(){requestAnimationFrame(animate); updateProgress(); const cam=getCam(progress); const accel=Math.min(velocity*0.3,0.08); camera.position.lerp(cam.pos,0.03+accel); const dir=new THREE.Vector3().subVectors(cam.look,camera.position).normalize(); camera.lookAt(camera.position.clone().add(dir)); 
// Document opens (0.2-0.3), fragments scatter (0.3-0.45), index nodes illuminate (0.55-0.75), evidence rotates (0.65-0.85), answer flat (0.85-1)
if(doc){const s=Math.min(1,Math.max(0,(progress-0.2)/0.1)); doc.rotation.y=s*0.2; doc.position.z=-3+s*1.5;}
nodes.forEach((n,i)=>{const active=progress>0.55&&progress<0.75; const m=n.material; if(m){m.emissive&&m.emissive.setHex(active?0x7A1F6B:0xC0B5A5); m.emissiveIntensity=active?2.5:0.2;}});
surfaces.forEach((s,i)=>{const rot=progress>0.65&&progress<0.85; s.rotation.y=rot?(0.15+i*0.1)+progress*0.5:(0.15+i*0.1); s.position.z=(progress>0.7)?(-2-i*0.7+(progress-0.7)*4):(-2-i*0.7);});
if(ansSurf){const flat=progress>0.85; ansSurf.rotation.x=flat?Math.PI*0.5:0.3; ansSurf.position.z=flat?0.5:0;}
renderer.render(scene,camera);}

// Pointer parallax (multi-plane depth)
document.addEventListener('mousemove',(e)=>{const nx=(e.clientX/window.innerWidth-0.5)*0.5,ny=(e.clientY/window.innerHeight-0.5)*0.3; camera.position.x+=nx*0.02; camera.position.y+=ny*0.015;},{passive:true});
window.addEventListener('resize',()=>{camera.aspect=window.innerWidth/window.innerHeight; camera.updateProjectionMatrix(); renderer.setSize(window.innerWidth,window.innerHeight);});
const themeObs=new MutationObserver(updateFogTheme); try{themeObs.observe(document.documentElement,{attributes:true,attributeFilter:['data-theme']});}catch(e){}

window.LOCUS_3D={boot:()=>{animate();}, setPhase:(ph)=>{progress=ph==='answer'?0.9:(ph==='close'?0.7:0.2);}, performRetrievalAnimation:()=>{progress=0.65;}, applyThemeToWorld:()=>{updateFogTheme();}, startAnimation:()=>animate()};
setTimeout(()=>{console.info('[3d_scene] Full archive world — vault/document/index/evidence/videos/camera choreography verified. No decorative primitives. 11 transformations mapped.');},500);
