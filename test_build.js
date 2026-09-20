// Test script to verify cinematic scroll fixes
console.log('Testing cinematic scroll fixes...');

// Check if key functions exist
if (typeof Lenis !== 'undefined') {
  console.log('✓ Lenis available');
} else {
  console.log('✗ Lenis not loaded');
}

// Check DOM elements
const checkElement = (id) => {
  const el = document.getElementById(id);
  console.log(el ? `✓ ${id} found` : `✗ ${id} missing`);
  return el;
};

checkElement('film-track');
checkElement('film-stage');
checkElement('film-layer');
checkElement('scroll-cue');

// Verify video exists
checkElement('film-layer');

// Check scene bounds
console.log('Scene count:', window.SCENE_BOUNDS ? window.SCENE_BOUNDS.length : 'Not available');

console.log('Test complete!');
