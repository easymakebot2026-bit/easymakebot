// Renders Instagram stories (1080x1920) and post slides (1080x1350) from a
// JSON spec: a background image plus Persian text blocks.
//
//   node tools/compose.js specs/day0.json
//
// Spec: { "items": [ { "src": "images/1.jpg", "out": "out/day0/story1.png",
//   "size": "story" | "post", "blocks": [ { "y": 0.18, "kicker": "...",
//   "title": "...", "body": "..." } ], "qmark": { "x": 0.5, "y": 0.45 } } ] }
// `y` is the block's vertical centre as a fraction of the height. Lines in
// kicker/title/body are split on "\n". `qmark` draws a big "?" (e.g. on the
// blank card of the evidence board). `card: true` renders a plain brand card
// (no image) — used for call-to-action slides.
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright-core');

const ROOT = path.join(__dirname, '..');
const FONT = 'file://' + path.join(ROOT, 'node_modules/vazirmatn/fonts/webfonts/Vazirmatn[wght].woff2');
const SIZES = { story: [1080, 1920], post: [1080, 1350] };

const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
  .replace(/(@[A-Za-z_][A-Za-z0-9_]*|\/[a-z_]+|t\.me\/\S+)/g, '<bdi dir="ltr">$1</bdi>')
  .replace(/\n/g, '<br>');

function page(item) {
  const [w, h] = SIZES[item.size || 'story'];
  const bg = item.card
    ? `background:radial-gradient(900px 900px at 50% 30%,#2f6fe0,#0b1220 70%)`
    : `background:#000 url('file://${path.join(ROOT, item.src)}') center/cover no-repeat`;
  const blocks = (item.blocks || []).map(b => `
    <div class="blk" style="top:${b.y * 100}%">
      ${b.kicker ? `<div class="k">${esc(b.kicker)}</div>` : ''}
      ${b.title ? `<div class="t">${esc(b.title)}</div>` : ''}
      ${b.body ? `<div class="b">${esc(b.body)}</div>` : ''}
    </div>`).join('');
  const q = item.qmark ? `<div class="q" style="left:${item.qmark.x * 100}%;top:${item.qmark.y * 100}%">؟</div>` : '';
  const logo = item.card ? `<img class="logo" src="file://${path.join(ROOT, 'images/logo.png')}">` : '';
  return `<!doctype html><html><head><meta charset="utf-8"><style>
@font-face{font-family:V;src:url('${FONT}') format('woff2');font-weight:100 900}
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:${w}px;height:${h}px;overflow:hidden}
body{${bg};font-family:V,'Noto Color Emoji',sans-serif;direction:rtl;position:relative}
.blk{position:absolute;left:70px;right:70px;transform:translateY(-50%);text-align:center;
  background:rgba(10,14,22,.72);border:1px solid rgba(255,210,63,.35);border-radius:34px;padding:34px 40px;
  box-shadow:0 18px 50px rgba(0,0,0,.45);backdrop-filter:blur(6px)}
.k{display:inline-block;background:#ffd23f;color:#141414;font-weight:900;font-size:38px;padding:6px 26px;border-radius:30px;margin-bottom:16px}
.t{color:#fff;font-weight:900;font-size:58px;line-height:1.45}
.b{color:#e9e4d8;font-weight:500;font-size:38px;line-height:1.65;margin-top:14px}
.q{position:absolute;transform:translate(-50%,-50%) rotate(-6deg);font-weight:900;font-size:230px;color:#b3262b;
  text-shadow:0 6px 18px rgba(0,0,0,.35);opacity:.92}
.logo{position:absolute;left:50%;top:${item.logoY || 0.2}*100%;transform:translateX(-50%);width:260px;border-radius:50%}
</style></head><body>${logo}${blocks}${q}</body></html>`.replace(`${item.logoY || 0.2}*100%`, `${(item.logoY || 0.2) * 100}%`);
}

(async () => {
  const spec = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const browser = await chromium.launch({ executablePath: process.env.CHROME || '/opt/pw-browsers/chromium-1194/chrome-linux/chrome' });
  for (const item of spec.items) {
    const [w, h] = SIZES[item.size || 'story'];
    const p = await browser.newPage({ viewport: { width: w, height: h } });
    const tmp = path.join(ROOT, 'out', '.tmp.html');
    fs.mkdirSync(path.dirname(tmp), { recursive: true });
    fs.writeFileSync(tmp, page(item));
    await p.goto('file://' + tmp, { waitUntil: 'load' });
    await p.evaluate(() => document.fonts.ready);
    const out = path.join(ROOT, item.out);
    fs.mkdirSync(path.dirname(out), { recursive: true });
    await p.screenshot({ path: out, type: out.endsWith('.jpg') ? 'jpeg' : 'png', quality: out.endsWith('.jpg') ? 92 : undefined });
    await p.close();
    console.log('wrote', item.out);
  }
  fs.rmSync(path.join(ROOT, 'out', '.tmp.html'), { force: true });
  await browser.close();
})();
