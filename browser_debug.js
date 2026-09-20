const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
  const messages = [];
  page.on('console', m => messages.push(`[console:${m.type()}] ${m.text()}`));
  page.on('pageerror', e => messages.push(`[pageerror] ${e.stack || e.message}`));
  page.on('requestfailed', r => messages.push(`[requestfailed] ${r.url()} ${r.failure()?.errorText}`));
  await page.goto('http://localhost:8000/', { waitUntil: 'load', timeout: 20000 });
  await page.waitForTimeout(4000);
  const state = await page.evaluate(() => ({
    THREE: typeof window.THREE,
    worldChildren: document.querySelector('#world-canvas')?.children.length ?? null,
    film: document.querySelector('#film') ? { readyState: document.querySelector('#film').readyState, paused: document.querySelector('#film').paused, currentSrc: document.querySelector('#film').currentSrc } : null,
    filmTrack: document.querySelector('#film-track') ? { top: document.querySelector('#film-track').getBoundingClientRect().top, height: document.querySelector('#film-track').offsetHeight, scrollY: window.scrollY } : null,
    scriptErrors: window.LOCUS_3D ? 'api' : 'no-api'
  }));
  console.log(JSON.stringify({state,messages}, null, 2));
  await browser.close();
})();
