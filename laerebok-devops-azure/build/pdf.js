const { chromium } = require('playwright');
(async () => {
  const [,, input, output] = process.argv;
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto('file://' + input, { waitUntil: 'load' });
  await page.pdf({
    path: output, format: 'A4', printBackground: true, preferCSSPageSize: true,
    displayHeaderFooter: true,
    headerTemplate: '<div style="font-size:7pt;width:100%;text-align:right;padding-right:18mm;color:#8a94a3;font-family:sans-serif">DevOps, Cloud &amp; Microsoft Azure</div>',
    footerTemplate: '<div style="font-size:8pt;width:100%;text-align:center;color:#5b6675;font-family:sans-serif"><span class="pageNumber"></span> / <span class="totalPages"></span></div>',
  });
  await browser.close();
})();
