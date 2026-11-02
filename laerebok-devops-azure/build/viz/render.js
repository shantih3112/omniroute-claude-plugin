// Rendrer figur-HTML-filer til PNG med Chromium. Argument: jobs.json med [[html, png], ...]
const { chromium } = require('playwright');
const fs = require('fs');

(async () => {
  const jobs = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1060, height: 800 }, deviceScaleFactor: 1.3 });
  let failed = 0;
  for (const [html, png] of jobs) {
    await page.goto('file://' + html);
    await page.waitForFunction(() => document.body.dataset.done === '1', null, { timeout: 20000 });
    const err = await page.evaluate(() => document.body.dataset.err);
    if (err) { console.error('FEIL i', html, err); failed++; continue; }
    const el = await page.$('#fig');
    await el.screenshot({ path: png });
  }
  await browser.close();
  if (failed) process.exit(1);
})();
