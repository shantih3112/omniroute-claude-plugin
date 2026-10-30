const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch(); const p = await b.newPage({viewport:{width:900,height:900}});
  await p.goto('file://' + process.argv[2]);
  const el = (await p.$$('pre'))[process.argv[3]|0];
  await el.screenshot({path: process.argv[4]});
  await b.close();
})();
