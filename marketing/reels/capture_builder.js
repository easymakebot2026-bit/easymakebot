// Records the real Visual Builder Mini App (webapp/dist) building a small
// flow, frame by frame, for reel 8. Telegram and the /api backend are mocked;
// everything on screen is the real React app.
//
//   (cd webapp && npm run build) && node marketing/reels/capture_builder.js
//
// Writes marketing/reels/assets/builder/NNNN.jpg plus timeline.json:
// { fps, frames: [{ pointer: {x, y, down} | null, seg }] } in screen pixels.
const { chromium } = require('playwright-core');
const fs = require('fs');
const path = require('path');

const DIST = path.join(__dirname, '../../webapp/dist');
const OUT = path.join(__dirname, 'assets/builder');
const FONT = path.join(__dirname, '../node_modules/vazirmatn/fonts/webfonts/Vazirmatn[wght].woff2');
const W = 408, H = 588, DPR = 2, FPS = 15;

(async () => {
  fs.rmSync(OUT, { recursive: true, force: true });
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({ executablePath: process.env.CHROME || '/opt/pw-browsers/chromium-1194/chrome-linux/chrome' });
  const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: DPR });
  await page.route('http://app.local/**', async (route) => {
    const u = new URL(route.request().url());
    if (u.pathname === '/__font.woff2') return route.fulfill({ body: fs.readFileSync(FONT), contentType: 'font/woff2' });
    if (u.pathname.startsWith('/api/flow')) {
      return route.fulfill({ json: route.request().method() === 'GET' ? { nodes: [], edges: [] } : { ok: true } });
    }
    if (u.pathname.startsWith('/api/')) return route.fulfill({ json: [] });
    let f = path.join(DIST, u.pathname === '/' ? 'index.html' : u.pathname);
    if (!fs.existsSync(f)) f = path.join(DIST, 'index.html');
    const ct = f.endsWith('.js') ? 'text/javascript' : f.endsWith('.css') ? 'text/css' : f.endsWith('.svg') ? 'image/svg+xml' : 'text/html';
    route.fulfill({ body: fs.readFileSync(f), contentType: ct });
  });
  await page.goto('http://app.local/?bot_id=demo');
  // Persian glyphs only (unicode-range), so the app's Latin UI is unchanged.
  await page.addStyleTag({ content: `@font-face{font-family:FA;src:url(/__font.woff2) format("woff2");unicode-range:U+0600-06FF,U+200C-200F,U+FB50-FDFF,U+FE70-FEFF}
    body,input,textarea,select,button{font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif,FA}` });
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(500);

  const frames = [];
  let seg = '';
  let pointer = null;
  const snap = async () => {
    const n = String(frames.length).padStart(4, '0');
    await page.screenshot({ path: path.join(OUT, `${n}.jpg`), type: 'jpeg', quality: 88 });
    frames.push({ pointer: pointer && { x: pointer.x * DPR, y: pointer.y * DPR, down: pointer.down }, seg });
  };
  const hold = async (sec) => { for (let i = 0; i < Math.round(sec * FPS); i++) await snap(); };
  const ease = (t) => (t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2);
  const moveTo = async (x, y, sec, down) => {
    const from = pointer || { x: W / 2, y: H / 2 };
    const n = Math.max(1, Math.round(sec * FPS));
    for (let i = 1; i <= n; i++) {
      const k = ease(i / n);
      const px = from.x + (x - from.x) * k, py = from.y + (y - from.y) * k;
      pointer = { x: px, y: py, down };
      await page.mouse.move(px, py);
      await snap();
    }
  };
  const center = async (selector) => {
    const box = await page.locator(selector).first().boundingBox();
    return { x: box.x + box.width / 2, y: box.y + box.height / 2 };
  };
  const tap = async (selector) => {
    const c = await center(selector);
    await moveTo(c.x, c.y, 0.5, false);
    pointer = { ...c, down: true }; await page.mouse.down(); await snap(); await snap();
    await page.mouse.up(); pointer = { ...c, down: false }; await snap();
  };
  const drag = async (fromSel, to, sec = 1.0) => {
    const c = await center(fromSel);
    await moveTo(c.x, c.y, 0.5, false);
    await page.mouse.move(c.x, c.y); await page.mouse.down();
    pointer = { ...c, down: true }; await snap();
    await moveTo(to.x, to.y, sec, true);
    await page.mouse.up(); pointer = { ...to, down: false }; await snap();
  };
  const paletteItem = (label) => `.palette-item:has-text("${label}")`;
  const scrollPaletteTo = async (label, sec = 0.6) => {
    const el = page.locator(paletteItem(label)).first();
    const target = await el.evaluate((e) => e.offsetLeft - 10);
    const start = await page.locator('.palette').evaluate((p) => p.scrollLeft);
    const n = Math.round(sec * FPS);
    for (let i = 1; i <= n; i++) {
      await page.locator('.palette').evaluate((p, v) => { p.scrollLeft = v; }, start + (target - start) * ease(i / n));
      await snap();
    }
  };
  const typeInto = async (selector, text, cps = 18) => {
    await tap(selector);
    const per = Math.max(1, Math.round(cps / FPS));
    const chars = [...text];
    for (let i = 0; i < chars.length; i += per) {
      await page.keyboard.insertText(chars.slice(i, i + per).join(''));
      await snap();
    }
  };
  const nodeSel = (title) => `.react-flow__node:has(.flow-node-title:has-text("${title}"))`;
  const handle = async (title, side) => center(`${nodeSel(title)} .react-flow__handle-${side}`);

  // 1. The empty canvas and the block strip.
  seg = 'blocks'; await hold(1.2);
  await scrollPaletteTo('Broadcast', 2.2); await hold(0.4);
  await scrollPaletteTo('Guide', 1.2); await hold(0.3);

  // 2. Trigger (/start).
  seg = 'trigger';
  await drag(paletteItem('Trigger'), { x: 14, y: 16 }); await hold(0.8);

  // 3. Force Join Gate, connected after the trigger.
  seg = 'gate';
  await scrollPaletteTo('Force Join', 0.6);
  await drag(paletteItem('Force Join'), { x: 214, y: 150 });
  await drag(`${nodeSel('Trigger')} .react-flow__handle-right`, await handle('Force Join', 'left'), 0.9);
  await hold(0.6);

  // 4. Send Message, written in the composer.
  seg = 'message';
  await scrollPaletteTo('Send Message', 0.5);
  await drag(paletteItem('Send Message'), { x: 14, y: 285 });
  await drag(`${nodeSel('Force Join')} .react-flow__handle-right`, await handle('Send Message', 'left'), 0.9);
  await hold(0.4);
  seg = 'composer';
  await tap(`${nodeSel('Send Message')} .flow-node-manage`); await hold(0.6);
  await typeInto('.cm-textarea', 'سلام 🌹 به فروشگاه گل رز خوش اومدی!\nدسته‌گل‌های امروز رو ببین 👇', 22);
  await hold(0.4);
  await tap('.cm-button:has-text("Add button")'); await hold(0.3);
  await typeInto('.cm-input[placeholder="Button text"]', '🌐 سایت ما', 15);
  await typeInto('.cm-input[placeholder="https://…"]', 'https://rose-shop.ir', 20);
  await tap('.cm-form .cm-button-primary:has-text("Add button")'); await hold(0.6);
  await tap('.cm-form-actions .cm-button-primary'); await hold(0.6);

  // 5. Shop, last in the chain.
  seg = 'shop';
  await scrollPaletteTo('Shop', 0.6);
  await drag(paletteItem('Shop'), { x: 214, y: 400 });
  await drag(`${nodeSel('Send Message')} .react-flow__handle-right`, await handle('Shop', 'left'), 0.9);
  await hold(0.5);

  // 6. Fit the whole flow on screen, then Save.
  seg = 'save';
  await tap('.react-flow__controls-fitview'); await hold(0.8);
  await tap('.save-button'); await hold(2.0);

  fs.writeFileSync(path.join(OUT, 'timeline.json'), JSON.stringify({ fps: FPS, width: W * DPR, height: H * DPR, frames }));
  console.log('frames', frames.length, 'seconds', (frames.length / FPS).toFixed(1));
  await browser.close();
})();
