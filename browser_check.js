const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
  
  // Use load event instead of networkidle to avoid long waits
  await page.goto('http://localhost:8000/', { waitUntil: 'load', timeout: 20000 });
  
  // Wait for boot to finish then check
  await page.waitForFunction(() => {
    const film = document.getElementById('film');
    return film && film.readyState !== '' && film.readyState !== 'uninitialized';
  }, {}, 8000);
  
  await new Promise(r => setTimeout(r, 1500));

  // 1. Verify video present and not autoplaying
  const video = await page.locator('#film').first();
  const videoProp = await video.evaluate(v => ({ paused: v.paused, currentTime: v.currentTime }));
  console.log('VIDEO STATE:', videoProp);

  // 2. Verify Three.js canvas visible
  const canvas = await page.locator('#world-canvas canvas').first();
  const canvasBox = await canvas.boundingBox();
  console.log('CANVAS VISIBLE:', canvasBox ? { w: canvasBox.width, h: canvasBox.height } : 'NOT FOUND');

  // 3. Scroll down and observe video.currentTime increases
  await page.evaluate(() => window.scrollBy(0, 300));
  await new Promise(r => setTimeout(r, 400));
  const afterScroll = await video.evaluate(v => ({ paused: v.paused, currentTime: v.currentTime, currentSrc: v.currentSrc }));
  console.log('AFTER SCROLL DOWN:', afterScroll);

  // 4. Scroll up and observe reversal
  await page.evaluate(() => window.scrollBy(0, -300));
  await new Promise(r => setTimeout(r, 400));
  const afterUp = await video.evaluate(v => ({ paused: v.paused, currentTime: v.currentTime }));
  console.log('AFTER SCROLL UP:', afterUp);

  // 5. Scroll some more for scene change
  await page.evaluate(() => window.scrollBy(0, 500));
  await new Promise(r => setTimeout(r, 500));
  const afterMore = await video.evaluate(v => ({ paused: v.paused, currentTime: v.currentTime }));
  console.log('AFTER MORE SCROLL:', afterMore);

  await browser.close();
})();
