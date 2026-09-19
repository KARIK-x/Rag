// Regression test: cinematic scroll stage exists, video hidden, no autoplay, scroll-driven
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8');

const html = read('public/index.html');
const css = read('public/css/film_scroll.css');
const js = read('public/js/film_scrubber.js');

assert.match(html, /id="film-track"/);
assert.match(html, /id="film-stage"/);
assert.match(html, /<video[^>]*id="film-layer-/);
assert.doesNotMatch(html, /controls=/i);
assert.doesNotMatch(js, /\.play\s*\(\)/);
assert.match(js, /SCENES/);
assert.match(js, /getSceneIdx/);

console.log('PASS: cinematic scroll regression checks');