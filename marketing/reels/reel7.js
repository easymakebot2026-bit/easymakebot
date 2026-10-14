// Reel 7 — reels 5 + 6 in one: from adding a product, through cart,
// payment, owner approval and shipping, to the PDF invoice. Built from the
// bodies of reel5.js and reel6.js (see those for the bot code each text
// mirrors).
const OWNER = { name: "فروشگاه گل رز", st: "bot · از دید صاحب ربات", av: "🌹", color: "#ff7a90" };
const EMB = { name: "EasyMakeBot", st: "bot", av: "E", color: "#ffb43f" };
const ROSE = { name: "فروشگاه گل رز", st: "bot · از دید مشتری", av: "🌹", color: "#ff7a90" };
const TOOLS_KB = [["1️⃣ تعریف دستور", "2️⃣ عضویت اجباری"], ["3️⃣ پیام‌رسانی گروهی", "4️⃣ لیست محتوا"], ["5️⃣ فروشگاه"]];
const SHOP_KB = [["📦 محصولات", "➕ افزودن محصول"], ["💳 روش‌های پرداخت", "📋 سفارش‌های اخیر"], ["📥 وارد کردن محصولات", "📊 فروش و موجودی"], ["❌ لغو"]];
const NAME = "دسته‌گل عروس 💐";
const DESC = "رز سفید و ارکیده، ارسال همون روز 🚚";

INTRO_END = 3.4;
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


// ---- part 2 (reel 6) ----
card(`<div class="big" style="font-size:74px">یه بار تنظیم کن ⚙️</div><div class="codes">
<div class="row"><b>💳</b>روش پرداخت: کارت به کارت یا زرین‌پال</div>
<div class="row"><b>🧾</b>فاکتور: اسم، لوگو، آدرس و امضای فروشگاه</div></div>
<div class="mid" style="font-size:38px;margin-top:34px">از منوی «5️⃣ فروشگاه»</div>`, 3.6);

caption("قدم ۳", "مشتری پرداخت می‌کنه", "کارت به کارت یا درگاه");
wait(0.3); tapInline("💳 پرداخت / تسویه حساب");
wait(0.3); inc("💰 مجموع: 1,200,000 تومان\n\nروش پرداخت را انتخاب کنید:", { inline: ["💳 زرین‌پال", "🏦 کارت به کارت"] });
wait(1.1); tapInline("🏦 کارت به کارت");
wait(0.3); inc("💳 شماره کارت: 6037-9975-1234-5678\n👤 فروشگاه گل رز\n\n💰 مبلغ: 1,200,000 تومان\n\nبعد از پرداخت، شماره پیگیری تراکنش (یا هش) را ارسال کنید.");
wait(1.6); typed("748215", 0.6);
wait(0.4); inc("ممنون! پرداخت شما در انتظار بررسی مالک ربات است.");
wait(1.4);

scene(OWNER);
caption("قدم ۴", "تو فقط تأیید می‌کنی ✅", "یه دکمه، تمام");
wait(0.5); inc("🧾 New cart checkout #42\nTotal: 1,200,000 Toman\nPayment method: Card to Card\nBuyer: 482915736\nOrder date: 2026-10-14 18:30\nTransaction ref: 748215", { inline: ["✅ Confirm", "❌ Reject"] });
wait(1.6); tapInline("✅ Confirm");
note("✅ Approved", 1.4);
wait(1.6);

scene(ROSE);
caption("قدم ۵", "مشتری آدرس رو می‌ده", "روش ارسال رو هم خودش انتخاب می‌کنه");
wait(0.4); inc("✅ Payment confirmed. Please provide your shipping info for this order.", { inline: ["📦 Enter Shipping Info"] });
wait(1.0); tapInline("📦 Enter Shipping Info");
wait(0.3); inc("روش ارسال را انتخاب کنید:", { inline: ["📮 پست", "🚚 ماهکس", "📦 تیپاکس", "🛵 پیک اسنپ"] });
wait(1.0); tapInline("🛵 پیک اسنپ");
wait(0.3); inc("نام و نام خانوادگی گیرنده؟");
wait(0.3); typed("سارا محمدی", 0.6);
wait(0.3); inc("شماره تلفن؟");
wait(0.3); typed("09121234567", 0.6);
wait(0.3); inc("آدرس کامل ارسال؟");
wait(0.3); typed("تهران، سعادت‌آباد، خیابان سرو، پلاک ۸", 0.9);
wait(0.3); inc("کد پستی؟");
wait(0.3); typed("1998765432", 0.6);
wait(0.4); inc("ممنون! سفارش شما به‌زودی ارسال می‌شود.");
wait(0.6);
caption("قدم ۶", "فاکتور خودکار صادر می‌شه 🧾", "PDF، با اسم فروشگاه خودت");
inc("🧾 Invoice", { doc: "invoice-5A1E01-C000042.pdf" });
wait(1.8);

card(`<div class="big" style="font-size:66px">فاکتور رسمی، خودکار 🧾</div>
<img src="assets/invoice.png" style="width:1000px;margin-top:30px;border-radius:18px;box-shadow:0 20px 60px rgba(0,0,0,.5);background:#fff;height:980px;object-fit:cover;object-position:top">`, 4.4);


INTRO_HTML = `<div class="emoji">🛒 ⬅️ 🧾</div><div class="big" style="font-size:96px">یه سفارش<br>از صفر تا فاکتور</div><div class="mid">سبد خرید، پرداخت، ارسال، فاکتور رسمی<br>همه توی تلگرام… ببین چطوری 👀</div>`;
OUTRO_HTML = `<div class="big">فروشگاه کامل<br>توی ربات خودت</div><div class="handle">@easymakebot</div><div class="chips"><div>⏱ ۷۲ ساعت رایگان</div><div>🔗 لینک در بیو</div></div>`;
