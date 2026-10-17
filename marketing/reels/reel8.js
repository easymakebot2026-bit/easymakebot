// Reel 8 — the Visual Builder: how to open it from the bot, a tour of the
// real Mini App building /start -> Force Join -> Send Message -> Shop, and
// the result for a customer. The builder footage is the real webapp
// (webapp/dist) recorded by capture_builder.js; chat texts mirror
// bot/handlers/my_bots.py + keyboards.py:webapp_keyboard and
// bot/flow_engine.py (force_join_gate / send_message / shop nodes).
const EMB = { name: "EasyMakeBot", st: "bot", av: "E", color: "#ffb43f" };
const ROSE = { name: "فروشگاه گل رز", st: "bot · از دید مشتری", av: "🌹", color: "#ff7a90" };
const MAIN_KB = [["🤖 ربات‌های من", "➕ ساخت ربات جدید"], ["💳 اشتراک من"]];
const TL = window.BUILDER_TL;
const WELCOME = "سلام 🌹 به فروشگاه گل رز خوش اومدی!\nدسته‌گل‌های امروز رو ببین 👇";

INTRO_END = 3.2;
T = INTRO_END;

scene(EMB);
card(`<div class="big" style="font-size:76px">سازنده‌ی بصری چیه؟ 🤔</div><div class="codes">
<div class="row"><b>🧩</b>بلوک = یه کار (پیام، فروشگاه، جوین…)</div>
<div class="row"><b>🔗</b>خط بین بلوک‌ها = ترتیب اجرا</div>
<div class="row"><b>💾</b>Save = همون لحظه روی رباتت اعمال می‌شه</div></div>
<div class="mid" style="font-size:40px;margin-top:34px">مسیر رباتت رو می‌چینی، بدون کد ✨</div>`, 5.0);
caption("اول", "از کجا بازش کنم؟ 🤔", "«🤖 ربات‌های من» ← رباتت رو انتخاب کن");
kb(MAIN_KB);
wait(0.6); tap("🤖 ربات‌های من");
wait(0.3); inc("ربات‌های تو:", { inline: ["🤖 فروشگاه گل رز", "➕ ساخت ربات جدید"] });
wait(1.0); tapInline("🤖 فروشگاه گل رز");
wait(0.3); inc("وارد محیط ساخت‌وساز ربات «فروشگاه گل رز» شدی.\nاز ابزار زیر برای توسعه‌ی رباتت استفاده کن.", { kb: [["🛠 ابزارهای ساخت‌وساز"]] });
wait(0.5); inc("دوست داری از بوم بصری استفاده کنی؟ سازنده‌ی درگ‌اند‌دراپ رو باز کن:", { inline: ["🎨 سازنده‌ی بصری"] });
wait(1.4);
caption("👆 اینجا", "دکمه‌ی «🎨 سازنده‌ی بصری»", "داخل خود تلگرام باز می‌شه، بدون نصب برنامه");
wait(1.3); tapInline("🎨 سازنده‌ی بصری");

// --- the real Mini App -------------------------------------------------
const segStart = {};
TL.frames.forEach((f, i) => { if (!(f.seg in segStart)) segStart[f.seg] = i / TL.fps; });
const SEG_CAPTIONS = {
  canvas: ["🎨 صفحه‌ی سازنده", "اینجا بوم رباتته", "پایین: بلوک‌ها  |  بالا: دکمه‌ی Save"],
  blocks: ["🧩 بلوک‌ها", "هر بلوک = یه کار", "پیام، فروشگاه، جوین اجباری، محتوا و… بکش تا همه رو ببینی"],
  trigger: ["قدم ۱", "▶️ Trigger رو بکش روی بوم", "یعنی دستور ‎/start: مسیر ربات از اینجا شروع می‌شه"],
  gate: ["قدم ۲", "🔒 بلوک جوین اجباری", "کاربر اول باید عضو کانالت بشه"],
  connect: ["🔗 مهم‌ترین نکته", "نقطه‌ی آبی رو بکش روی بلوک بعدی", "این خط یعنی: «بعد از این، اون اجرا بشه»"],
  message: ["قدم ۳", "💬 بلوک پیام رو اضافه و وصل کن", "بعد از عضویت، این پیام برای کاربر میاد"],
  composer: ["قدم ۴", "✏️ روی Edit Message بزن", "متن خوش‌آمدت رو بنویس، فارسی هم کاملاً اوکیه"],
  button: ["قدم ۵", "🔗 یه دکمه‌ی لینک بذار", "متن دکمه + آدرس سایت، بعد Save"],
  shop: ["قدم ۶", "🛍 فروشگاه، آخر مسیر", "محصولاتت بعد از پیام خوش‌آمد نشون داده می‌شن"],
  fit: ["👀 کل مسیر", "دکمه‌ی ⛶ همه‌چی رو یه‌جا نشون می‌ده", "‎/start ← جوین ← پیام ← فروشگاه"],
  save: ["قدم ۷", "💾 Save رو بزن", "همین! رباتت همون لحظه به‌روز شد ✅"],
};
const SHOW_START = T + 0.4;
const SHOW_DUR = TL.frames.length / TL.fps;
for (const [seg, c] of Object.entries(SEG_CAPTIONS)) {
  const keep = T; T = SHOW_START + (segStart[seg] || 0); caption(...c); T = keep;
}
wait(0.4);
screen("assets/builder", TL, SHOW_DUR + 0.2);

card(`<div class="big" style="font-size:68px">مسیری که ساختیم 👇</div><div class="codes">
<div class="row"><b>▶️</b>کاربر ‎/start رو می‌زنه</div>
<div class="row" style="justify-content:center;background:none;border:none;padding:0">⬇️</div>
<div class="row"><b>🔒</b>اول باید عضو کانالت بشه</div>
<div class="row" style="justify-content:center;background:none;border:none;padding:0">⬇️</div>
<div class="row"><b>💬</b>پیام خوش‌آمد + دکمه‌ی سایت</div>
<div class="row" style="justify-content:center;background:none;border:none;padding:0">⬇️</div>
<div class="row"><b>🛍</b>فروشگاه و محصولات</div></div>`, 4.6);

// --- result for a customer ---------------------------------------------
scene(ROSE);
caption("نتیجه 👇", "از دید مشتری", "دقیقاً همون مسیری که چیدی، بدون حتی یه خط کد");
kb(null);
wait(0.6); typed("/start", 0.6);
wait(0.5); inc("Please join the channel(s) below to use this bot, then tap \"I've Joined\".", { inline: ["📢 @rose_flowers", "✅ I've Joined"] });
wait(2.2); tapInline("✅ I've Joined");
wait(0.4); inc(WELCOME, { inline: ["🌐 سایت ما"] });
wait(1.8); inc("🛍 یه دسته‌بندی رو انتخاب کن:", { inline: ["دسته‌گل", "گلدان", "📋 همه محصولات"] });
note("🔒 جوین ← 💬 خوش‌آمد ← 🛍 فروشگاه", 3.6);
wait(4.0);

INTRO_HTML = `<div class="emoji">🎨</div><div class="big">رباتت رو<br>مثل پازل بچین</div><div class="mid">سازنده‌ی بصری ایزی‌میک‌بات<br>بکش، بنداز، وصل کن… تمام 👀</div>`;
OUTRO_HTML = `<div class="big">سازنده‌ی بصری<br>توی ربات خودت</div><div class="handle">@easymakebot</div><div class="chips"><div>⏱ ۷۲ ساعت رایگان</div><div>🔗 لینک در بیو</div></div>`;
