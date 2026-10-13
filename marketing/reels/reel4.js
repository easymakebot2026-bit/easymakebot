// Reel 4 — price lookup by code: 101-105 are flowers for sale; sending a code shows price + buy buttons.
// Texts mirror bot/handlers/tools/content_list.py (ADD_ITEM_FIELDS, the
// for-sale / category steps) and the built bot's code jump in bot/runtime.py
// (handle_possible_content_code -> _send_content_post: "📌 title\n\nbody").
// Assumes the bot's commerce mode was already chosen, so that one-time
// question is skipped.
const EMB = { name: "EasyMakeBot", st: "bot", av: "E", color: "#ffb43f" };
const ROSE = { name: "فروشگاه گل رز", st: "bot · از دید مشتری", av: "🌹", color: "#ff7a90" };
const TOOLS_KB = [["1️⃣ تعریف دستور", "2️⃣ عضویت اجباری"], ["3️⃣ پیام‌رسانی گروهی", "4️⃣ لیست محتوا"], ["5️⃣ فروشگاه"]];
const MENU_KB = [["📋 نمایش", "➕ افزودن"], ["✏️ ویرایش", "🗑 حذف"], ["📢 افزودن پست"], ["🔀 دسته‌بندی (زیرمجموعه/والد)"], ["❌ لغو"]];
const SKIP_KB = [["⏭ رد کردن", "❌ لغو"]];
const FLOWERS = [
  ["101", "گل رز قرمز 🌹", "450,000", "۴۵۰ هزار"],
  ["102", "گل مریم 🤍", "280,000", "۲۸۰ هزار"],
  ["103", "لیلیوم صورتی 🌸", "390,000", "۳۹۰ هزار"],
  ["104", "ارکیده‌ی بنفش 🪻", "850,000", "۸۵۰ هزار"],
  ["105", "آفتابگردان 🌻", "320,000", "۳۲۰ هزار"],
];
// Customer-side post: "📌 title\n\nbody\n\n💰 price" + Open link, Buy / Add to
// cart, the i/n sibling carousel and Back (bot/runtime.py _content_post_markup).
function post(i, body, emoji) {
  const f = FLOWERS[i];
  inc(`📌 ${f[1]}\n\n${body}\n\n💰 ${f[2]} Toman`, { photo: emoji,
    inline: ["🔗 باز کردن", "🛒 خرید  |  ➕ افزودن به سبد", (i > 0 ? "◀️  " : "") + `${i + 1} / 5` + (i < 4 ? "  ▶️" : ""), "🔙 بازگشت به لیست"] });
}

INTRO_END = 2.8;
T = INTRO_END;

scene(EMB);
caption("قدم ۱", "محصولت رو اضافه کن", "عکس، توضیح و لینک خرید");
kb(TOOLS_KB);
wait(0.6); tap("4️⃣ لیست محتوا");
wait(0.3); inc("مدیریت آیتم‌های محتوای این ربات — استفاده‌شده توسط بلوک «لیست محتوا» تو سازنده‌ی بصری.", { kb: MENU_KB });
wait(0.7); tap("➕ افزودن");
wait(0.3); inc("عنوان آیتم رو وارد کن.", { kb: [["❌ لغو"]] });
wait(0.3); typed("گل رز قرمز 🌹", 0.8);
wait(0.3); inc("متن اصلی آیتم رو وارد کن.");
wait(0.3); typed("دسته‌ی ۱۰ شاخه رز هلندی، تازه‌ی امروز", 1.0);
wait(0.3); inc("آدرس تصویر رو وارد کن (اختیاری).", { kb: SKIP_KB });
wait(0.3); typed("https://rose-shop.ir/img/rose.jpg", 0.8);
wait(0.3); inc("آدرس لینک رو وارد کن (اختیاری).");
wait(0.3); typed("https://rose-shop.ir/rose", 0.8);
wait(0.4);

caption("قدم ۲", "کد و قیمت بذار 🔑💰", "کد 101 = گل رز");
wait(0.2); inc("یه کد میان‌بر برای این آیتم تنظیم کن، مثلاً 101 یا buy (اختیاری). هر کسی این کد رو به رباتت بفرسته مستقیم به این آیتم می‌ره — برای پستی مثل «کد رو به ربات ما بفرست» تو اینستاگرام مفیده.");
wait(1.3); typed("101", 0.5);
wait(0.3); inc("این آیتم برای فروشه؟ (خریدارها روش قیمت و دکمه‌ی خرید می‌بینن.)", { kb: [["💰 بله، برای فروشه", "➖ نه"], ["❌ لغو"]] });
wait(0.6); tap("💰 بله، برای فروشه");
wait(0.3); inc("قیمت رو به تومان وارد کن (فقط عدد).", { kb: [["❌ لغو"]] });
wait(0.3); typed("450000", 0.7);
wait(0.3); inc("این محصول چه نوعیه؟", { kb: [["📦 فیزیکی", "💾 دیجیتال"], ["🎫 دسترسی / عضویت"], ["❌ لغو"]] });
wait(0.6); tap("📦 فیزیکی");
wait(0.3); inc("این زیر کدوم دسته باشه؟ (تودرتو کردن اختیاریه.)", { inline: ["📁 سطح بالا (بدون دسته)", "❌ لغو"], kb: null });
wait(0.7); tapInline("📁 سطح بالا (بدون دسته)");
wait(0.2); inc("آیتم اضافه شد ✅", { kb: MENU_KB });
wait(1.2);

card(`<div class="big" style="font-size:74px">هر گل، یه کد 🔑</div><div class="codes">
${FLOWERS.map(f => `<div class="row"><b>${f[0]}</b><span style="flex:1">${f[1]}</span><span style="font-size:36px;opacity:.85">${f[3]} تومان</span></div>`).join("\n")}</div>
<div class="mid" style="font-size:38px;margin-top:34px">بقیه رو هم همین‌طوری اضافه کن</div>`, 4.6);

scene(ROSE);
caption("نتیجه 👇", "مشتری می‌نویسه 101", "قیمت + لینک خرید، همون لحظه");
kb(null);
note("📱 زیر پست گل رز بنویس: «کد 101 رو به ربات بفرست»", 2.4);
wait(0.7); typed("101", 0.5);
wait(0.5); post(0, "دسته‌ی ۱۰ شاخه رز هلندی، تازه‌ی امروز", "🌹");
wait(2.6);
caption("یه کد دیگه 👇", "104 = ارکیده", "هر گل، قیمت و خرید خودش");
wait(0.3); typed("104", 0.5);
wait(0.5); post(3, "ارکیده‌ی دوشاخه در گلدان سرامیکی", "🪻");
wait(3.4);

INTRO_HTML = `<div class="emoji">🌹</div><div class="big">«قیمت؟»<br>کد ۱۰۱ رو بفرست!</div><div class="mid">مشتری کد رو می‌فرسته، قیمت و لینک خرید رو می‌گیره<br>بدون اینکه تو جواب بدی</div>`;
OUTRO_HTML = `<div class="big">استعلام قیمت خودکار<br>توی ربات خودت</div><div class="handle">@easymakebot</div><div class="chips"><div>⏱ ۷۲ ساعت رایگان</div><div>🔗 لینک در بیو</div></div>`;
