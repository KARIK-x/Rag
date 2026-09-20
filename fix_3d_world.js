const fs = require('fs');
let s = fs.readFileSync('public/js/3d_world.js', 'utf8');

// Fix 1: scene.background = null is transparent - renderer clears with alpha. 
// Set to actual background color so canvas renders even with alpha=true
s = s.replace(
  'scene.background = null;',
  'scene.background = new THREE.Color(CONFIG.colors.bgDark);'
);

// Fix 2: renderer alpha=true with transparent scene = canvas not painted.
// renderer should be opaque for the world to be visible behind film
s = s.replace(
  'const renderer = new rendererFn({antialias:true, alpha:true});',
  'const renderer = new rendererFn({antialias:true, alpha:false});'
);

// Fix 3: remove the problematic forceAttach loop that destroys/recreates
// renderer.domElement repeatedly. Keep a single attach after load.
// Replace the forceAttach calls with a single attach after DOMContentLoaded
const oldAttach = `const canvas = document.getElementById('world-canvas') || document.getElementById('locus-3d-canvas');
function forceAttach() {
  try {
    const c = document.getElementById('world-canvas');
    if (c && renderer && renderer.domElement) {
      if (!c.contains(renderer.domElement)) {
        c.innerHTML = '';
        c.appendChild(renderer.domElement);
      }
      return c.querySelector('canvas') !== null;
    }
  } catch (e) { console.error('[3d] force attach failed:', e); }
  return false;
}
// Force attach immediately and repeat
forceAttach();
setTimeout(forceAttach, 100);
setTimeout(forceAttach, 500);
// Also bind to window load
window.addEventListener('load', () => { setTimeout(forceAttach, 300); });
// Continuous check: if renderer.domElement exists but not in canvas, append
setInterval(() => {
  const c = document.getElementById('world-canvas');
  if (c && renderer && renderer.domElement && !c.contains(renderer.domElement)) {
    try { c.innerHTML = ''; c.appendChild(renderer.domElement); console.log('[3d] interval attached'); } catch(e){}
  }
}, 500);`;

const newAttach = `const canvas = document.getElementById('world-canvas') || document.getElementById('locus-3d-canvas');
if (canvas && renderer && renderer.domElement) {
  if (!canvas.contains(renderer.domElement)) {
    canvas.appendChild(renderer.domElement);
  }
}
window.addEventListener('load', () => {
  if (canvas && renderer && renderer.domElement && !canvas.contains(renderer.domElement)) {
    canvas.appendChild(renderer.domElement);
  }
});
window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});`;

s = s.replace(oldAttach, newAttach);

fs.writeFileSync('public/js/3d_world.js', s);
console.log('Fixed 3d_world.js:');
console.log('- scene.background set to bgDark color');
console.log('- renderer alpha=false for proper rendering');
console.log('- removed forceAttach loop');
