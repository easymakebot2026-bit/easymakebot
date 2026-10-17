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
caption("قدم ۱", "از کجا بازش کنم؟ 🤔", "از «ربات‌های من» رباتت رو انتخاب کن");
kb(MAIN_KB);
wait(0.6); tap("🤖 ربات‌های من");
wait(0.3); inc("ربات‌های تو:", { inline: ["🤖 فروشگاه گل رز", "➕ ساخت ربات جدید"] });
wait(1.0); tapInline("🤖 فروشگاه گل رز");
wait(0.3); inc("وارد محیط ساخت‌وساز ربات «فروشگاه گل رز» شدی.\nاز ابزار زیر برای توسعه‌ی رباتت استفاده کن.", { kb: [["🛠 ابزارهای ساخت‌وساز"]] });
wait(0.5); inc("دوست داری از بوم بصری استفاده کنی؟ سازنده‌ی درگ‌اند‌دراپ رو باز کن:", { inline: ["🎨 سازنده‌ی بصری"] });
wait(1.4);
caption("👆 اینجا", "دکمه‌ی «🎨 سازنده‌ی بصری»", "داخل خود تلگرام باز می‌شه، بدون نصب برنامه");
wait(1.6); tapInline("🎨 سازنده‌ی بصری");

// --- the real Mini App -------------------------------------------------
const segStart = {};
TL.frames.forEach((f, i) => { if (!(f.seg in segStart)) segStart[f.seg] = i / TL.fps; });
const SEG_CAPTIONS = {
  blocks: ["🧩 بلوک‌ها", "۹ بلوک آماده", "پیام، فروشگاه، جوین اجباری، محتوا و…"],
  trigger: ["قدم ۲", "▶️ Trigger = دستور", "مثلاً /start: مسیر ربات از اینجا شروع می‌شه"],
  gate: ["قدم ۳", "🔒 جوین اجباری", "بکش، بنداز، با یه خط به قبلی وصلش کن"],
  message: ["قدم ۴", "💬 پیام خوش‌آمد", "یه بلوک پیام، بعد از جوین اجباری"],
  composer: ["قدم ۴", "✏️ متن و دکمه‌ی لینک", "عکس، ویدیو، فایل و چند پیام پشت سر هم هم می‌شه"],
  shop: ["قدم ۵", "🛍 فروشگاه، آخر مسیر", "محصولاتی که توی ربات تعریف کردی"],
  save: ["قدم ۶", "💾 Save و تمام!", "رباتت همین الان به‌روز شد ✅"],
};
const SHOW_START = T + 0.4;
const SHOW_DUR = TL.frames.length / TL.fps;
for (const [seg, c] of Object.entries(SEG_CAPTIONS)) {
  const keep = T; T = SHOW_START + (segStart[seg] || 0); caption(...c); T = keep;
}
wait(0.4);
screen("assets/builder", TL, SHOW_DUR + 0.6);

card(`<div class="big" style="font-size:70px">۹ بلوک، هر کاری 🧩</div><div class="codes">
<div class="row"><b>▶️</b>Trigger: دستور شروع (/start، /menu…)</div>
<div class="row"><b>💬</b>Send Message: متن، عکس، دکمه</div>
<div class="row"><b>🔒</b>Force Join: اول عضویت کانال</div>
<div class="row"><b>📚</b>Content List: آموزش‌ها و فایل‌ها</div>
<div class="row"><b>🛍</b>Shop: فروشگاه و سبد خرید</div>
<div class="row"><b>📦</b>Order Status: پیگیری سفارش</div>
<div class="row"><b>🪪</b>Verify: احراز هویت مشتری</div>
<div class="row"><b>📖</b>Guide & Video: راهنمای ویدیویی</div>
<div class="row"><b>📢</b>Broadcast: پیام همگانی</div></div>`, 6.5);

// --- result for a customer ---------------------------------------------
scene(ROSE);
caption("نتیجه 👇", "مشتری /start می‌زنه", "دقیقاً همون مسیری که چیدی");
kb(null);
wait(0.6); typed("/start", 0.6);
wait(0.5); inc("Please join the channel(s) below to use this bot, then tap \"I've Joined\".", { inline: ["📢 @rose_flowers", "✅ I've Joined"] });
wait(2.2); tapInline("✅ I've Joined");
wait(0.4); inc(WELCOME, { inline: ["🌐 سایت ما"] });
wait(1.8); inc("🛍 یه دسته‌بندی رو انتخاب کن:", { inline: ["دسته‌گل", "گلدان", "📋 همه محصولات"] });
note("🔒 جوین ← 💬 خوش‌آمد ← 🛍 فروشگاه", 4.4);
wait(5.0);

INTRO_HTML = `<div class="emoji">🎨</div><div class="big">رباتت رو<br>مثل پازل بچین</div><div class="mid">سازنده‌ی بصری ایزی‌میک‌بات<br>بکش، بنداز، وصل کن… تمام 👀</div>`;
OUTRO_HTML = `<div class="big">سازنده‌ی بصری<br>توی ربات خودت</div><div class="handle">@easymakebot</div><div class="chips"><div>⏱ ۷۲ ساعت رایگان</div><div>🔗 لینک در بیو</div></div>`;
