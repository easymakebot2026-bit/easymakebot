// Reel 4 — Content List item with a shortcut code ("send 101 to our bot").
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
const TITLE = "راهنمای نگهداری گل 🌿";
const BODY = "۵ نکته که دسته‌گلت یه هفته تازه بمونه:\n۱. ساقه‌ها رو اریب ببُر ✂️\n۲. آب گلدون رو یه روز در میون عوض کن 💧";

INTRO_END = 2.8;
T = INTRO_END;

scene(EMB);
caption("قدم ۱", "یه محتوا اضافه کن", "آموزش، فایل، کاتالوگ… هر چی");
kb(TOOLS_KB);
wait(0.6); tap("4️⃣ لیست محتوا");
wait(0.3); inc("مدیریت آیتم‌های محتوای این ربات — استفاده‌شده توسط بلوک «لیست محتوا» تو سازنده‌ی بصری.", { kb: MENU_KB });
wait(0.8); tap("➕ افزودن");
wait(0.3); inc("عنوان آیتم رو وارد کن.", { kb: [["❌ لغو"]] });
wait(0.4); typed(TITLE, 0.9);
wait(0.3); inc("متن اصلی آیتم رو وارد کن.");
wait(0.4); typed("۵ نکته که دسته‌گلت یه هفته تازه بمونه…", 1.1);
wait(0.3); inc("آدرس تصویر رو وارد کن (اختیاری).", { kb: SKIP_KB });
wait(0.4); typed("https://rose-shop.ir/care.jpg", 0.9);
wait(0.3); inc("آدرس لینک رو وارد کن (اختیاری).");
wait(0.5); tap("⏭ رد کردن");
wait(0.5);

caption("قدم ۲", "کد میان‌بر بذار 🔑", "مثلاً 101");
wait(0.2); inc("یه کد میان‌بر برای این آیتم تنظیم کن، مثلاً 101 یا buy (اختیاری). هر کسی این کد رو به رباتت بفرسته مستقیم به این آیتم می‌ره — برای پستی مثل «کد رو به ربات ما بفرست» تو اینستاگرام مفیده.");
wait(1.6); typed("101", 0.6);
wait(0.3); inc("این آیتم برای فروشه؟ (خریدارها روش قیمت و دکمه‌ی خرید می‌بینن.)", { kb: [["💰 بله، برای فروشه", "➖ نه"], ["❌ لغو"]] });
wait(0.6); tap("➖ نه");
wait(0.3); inc("این زیر کدوم دسته باشه؟ (تودرتو کردن اختیاریه.)", { inline: ["📁 سطح بالا (بدون دسته)", "❌ لغو"], kb: null });
wait(0.8); tapInline("📁 سطح بالا (بدون دسته)");
wait(0.2); inc("آیتم اضافه شد ✅", { kb: MENU_KB });
wait(1.4);

scene(ROSE);
caption("نتیجه 👇", "مشتری فقط می‌نویسه 101", "و مستقیم می‌رسه به همون محتوا");
kb(null);
note("📱 توی پستت بنویس: «کد 101 رو به ربات بفرست»", 2.2);
wait(0.8); typed("101", 0.6);
wait(0.5); inc(`📌 ${TITLE}\n\n${BODY}`, { photo: "🌷", inline: ["🔙 بازگشت به لیست"] });
wait(4.0);

INTRO_HTML = `<div class="emoji">🔑</div><div class="big">«کد ۱۰۱ رو<br>به ربات بفرست»</div><div class="mid">اینستاگرامت رو به ربات تلگرامت وصل کن<br>بدون برنامه‌نویسی</div>`;
OUTRO_HTML = `<div class="big">کد میان‌بر<br>توی ربات خودت</div><div class="handle">@easymakebot</div><div class="chips"><div>⏱ ۷۲ ساعت رایگان</div><div>🔗 لینک در بیو</div></div>`;
