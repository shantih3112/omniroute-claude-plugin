const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch(); const p = await b.newPage();
  await p.goto('file://' + process.argv[2]);
  const c = await p.context().newCDPSession(p); await c.send('DOM.enable'); await c.send('CSS.enable');
  const doc = await c.send('DOM.getDocument');
  const n = await c.send('DOM.querySelector', {nodeId: doc.root.nodeId, selector: process.argv[3]});
  console.log(JSON.stringify(await c.send('CSS.getPlatformFontsForNode', {nodeId: n.nodeId})));
  await b.close();
})();
