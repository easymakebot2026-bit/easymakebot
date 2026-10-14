// Reel 5 — Shop: add a product, expose it with a /shop command, and the
// buyer's category -> product -> cart flow. Texts mirror
// bot/handlers/tools/shop.py (CORE_FIELDS, "محصول اضافه شد ✅"),
// bot/keyboards.py (shop menu labels), bot/flow_engine.py (shop entry and
// product list) and bot/runtime.py (_send_product_detail, cart_add, _send_cart).
// Assumes the bot's commerce mode is already "shop".
const EMB = { name: "EasyMakeBot", st: "bot", av: "E", color: "#ffb43f" };
const ROSE = { name: "فروشگاه گل رز", st: "bot · از دید مشتری", av: "🌹", color: "#ff7a90" };
const TOOLS_KB = [["1️⃣ تعریف دستور", "2️⃣ عضویت اجباری"], ["3️⃣ پیام‌رسانی گروهی", "4️⃣ لیست محتوا"], ["5️⃣ فروشگاه"]];
const SHOP_KB = [["📦 محصولات", "➕ افزودن محصول"], ["💳 روش‌های پرداخت", "📋 سفارش‌های اخیر"], ["📥 وارد کردن محصولات", "📊 فروش و موجودی"], ["❌ لغو"]];
const NAME = "دسته‌گل عروس 💐";
const DESC = "رز سفید و ارکیده، ارسال همون روز 🚚";

INTRO_END = 2.8;
T = INTRO_END;

scene(EMB);
caption("قدم ۱", "محصولت رو اضافه کن", "اسم، قیمت، عکس، دسته‌بندی");
kb(TOOLS_KB);
wait(0.6); tap("5️⃣ فروشگاه");
wait(0.3); inc("مدیریت فروشگاه این ربات.", { kb: SHOP_KB });
wait(0.7); tap("➕ افزودن محصول");
wait(0.3); inc("نام محصول رو وارد کن.", { kb: [["❌ لغو"]] });
wait(0.3); typed(NAME, 0.8);
wait(0.3); inc("قیمت رو به تومان وارد کن (فقط عدد).");
wait(0.3); typed("1200000", 0.7);
wait(0.3); inc("یه توضیح کوتاه وارد کن.");
wait(0.3); typed(DESC, 0.9);
wait(0.3); inc("آدرس تصویر رو وارد کن (اختیاری).", { kb: [["⏭ رد کردن", "❌ لغو"]] });
wait(0.3); typed("https://rose-shop.ir/img/bride.jpg", 0.8);
wait(0.3); inc("یه دسته‌بندی برای این محصول وارد کن (اختیاری) — خریدارها می‌تونن بر اساس اون فیلتر کنن.");
wait(0.5); typed("دسته‌گل", 0.6);
wait(0.3); inc("این محصول چه نوعیه؟", { kb: [["📦 فیزیکی", "💾 دیجیتال"], ["🎫 دسترسی / عضویت"], ["❌ لغو"]] });
wait(0.6); tap("📦 فیزیکی");
wait(0.3); inc("محصول اضافه شد ✅", { kb: SHOP_KB });
wait(1.0);

caption("قدم ۲", "دستور ‎/shop بساز", "تا مشتری فروشگاهت رو باز کنه");
kb(TOOLS_KB);
wait(0.4); tap("1️⃣ تعریف دستور");
wait(0.3); inc("اسم دستور جدید رو بنویس، با / شروع بشه.", { kb: [["📋 نمایش دستورها", "❌ لغو"]] });
wait(0.3); typed("/shop", 0.5);
wait(0.3); inc("دستور «/shop» — این دستور برای کی نمایش داده بشه؟", { kb: [["👥 همه (کاربرا هم ببینن)"], ["👤 فقط خودم (ادمین)"], ["❌ لغو"]] });
wait(0.5); tap("👥 همه (کاربرا هم ببینن)");
wait(0.3); inc("این دستور وقتی اجرا بشه چیکار کنه؟", { kb: [["💬 پیام متنی", "📚 لیست محتوا"], ["🛍 فروشگاه", "📦 وضعیت سفارش"], ["🔒 عضویت اجباری", "🎬 راهنما و ویدیو"], ["❌ لغو"]] });
wait(0.6); tap("🛍 فروشگاه");
wait(0.3); inc("دستور «/shop» ثبت شد ✅", { kb: TOOLS_KB });
wait(1.0);

scene(ROSE);
caption("نتیجه 👇", "مشتری فروشگاهت رو باز می‌کنه", "دسته‌بندی، محصول، قیمت");
kb(null);
wait(0.6); typed("/shop", 0.6);
wait(0.5); inc("🛍 یه دسته‌بندی رو انتخاب کن:", { inline: ["دسته‌گل", "گلدان", "📋 همه محصولات"] });
wait(1.2); tapInline("دسته‌گل");
wait(0.3); inc("🛍 دسته‌گل:", { inline: [`${NAME} — 1,200,000 تومان`, "دسته‌گل رز قرمز 🌹 — 450,000 تومان"] });
wait(1.4); tapInline(`${NAME} — 1,200,000 تومان`);
wait(0.3); inc(`📦 ${NAME}\n\n${DESC}\n\n💰 1,200,000 Toman`, { photo: "💐", inline: ["🛒 خرید", "➕ افزودن به سبد"] });
wait(2.2);
caption("🧺 سبد خرید", "یکی یا چند تا محصول", "تعداد رو هم خودش تغییر می‌ده");
tapInline("➕ افزودن به سبد");
wait(0.3); inc("🧺 سبد خرید شما:", { inline: ["🧺 مشاهده سبد خرید"] });
wait(1.2); tapInline("🧺 مشاهده سبد خرید");
wait(0.3); inc(`${NAME} — 1,200,000 Toman`, { inline: ["➖     1x     ➕", "❌ حذف"] });
wait(0.5); inc(`🧺 جمع سبد خرید:\n• ${NAME} × 1 — 1,200,000 Toman\n\n💰 مجموع: 1,200,000 Toman`, { inline: ["💳 پرداخت / تسویه حساب"] });
wait(0.6);
note("💳 زرین‌پال یا کارت به کارت، هر کدوم رو خودت فعال کنی", 3.4);
wait(3.6);

INTRO_HTML = `<div class="emoji">🛍</div><div class="big">فروشگاه کامل<br>توی تلگرام</div><div class="mid">دسته‌بندی، سبد خرید، پرداخت<br>بدون سایت، بدون کدنویسی</div>`;
OUTRO_HTML = `<div class="big">فروشگاه تلگرامی<br>خودت رو بساز</div><div class="handle">@easymakebot</div><div class="chips"><div>⏱ ۷۲ ساعت رایگان</div><div>🔗 لینک در بیو</div></div>`;
