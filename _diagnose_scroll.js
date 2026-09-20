const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: false, slowMo: 50 });
  const page = await browser.newPage();
  page.on('console', msg => console.log('BROWSER:', msg.text()));
  await page.goto('http://localhost:8000');
  await page.waitForTimeout(2000);

  const getState = async () => {
    return await page.evaluate(() => {
      return {
        scrollY: window.scrollY,
        docHeight: document.body.scrollHeight,
        winHeight: window.innerHeight,
        lenis: typeof window.__lenis !== 'undefined' ? window.__lenis : null,
        hasLenisLib: typeof Lenis !== 'undefined',
      };
    });
  };

  let initial = await getState();
  console.log('Initial:', JSON.stringify(initial));

  // Try native wheel first
  await page.mouse.wheel({ deltaY: 300 });
  await page.waitForTimeout(200);
  let after1 = await getState();
  console.log('After wheel 1:', JSON.stringify(after1));

  // Try with Lenis.raf
  await page.evaluate(() => {
    if (window.__lenis) window.__lenis.raf();
  });
  await page.waitForTimeout(50);
  let after2 = await getState();
  console.log('After raf:', JSON.stringify(after2));

  await browser.close();
})();
