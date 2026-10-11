const BF = { name: "BotFather", st: "bot", av: "🤖", color: "#5a9bd5" };
const EMB = { name: "EasyMakeBot", st: "bot", av: "E", color: "#ffb43f" };
const ROSE = { name: "فروشگاه گل رز", st: "bot", av: "🌹", color: "#ff7a90" };

INTRO_END = 2.8;
T = INTRO_END;

// 1. BotFather
scene(BF);
caption("قدم ۱", "توکن بگیر از ‎@BotFather", "سی ثانیه‌ای تمومه");
wait(0.4); typed("/newbot", 0.6);
wait(0.4); inc("Alright, a new bot. How are we going to call it? Please choose a name for your bot.");
wait(0.6); typed("فروشگاه گل رز", 0.9);
wait(0.4); inc("Good. Now let's choose a username for your bot. It must end in `bot`.");
wait(0.6); typed("rose_shop_bot", 0.9);
wait(0.4); inc("Done! Congratulations on your new bot.\n\nUse this token to access the HTTP API:\n7XXXXXXXXX:AAH-xxxxxxxxxxxxxxxxxxxxxxxxxxxx");
wait(1.6);

// 2. register
scene(EMB);
caption("قدم ۲", "توکن رو بده به ایزی‌میک‌بات", "ربات ساخته شد ✅");
kb([["🤖 ربات‌های من", "➕ ساخت ربات جدید"], ["💳 اشتراک من"]]);
wait(0.7); tap("➕ ساخت ربات جدید");
wait(0.3); inc("توکنی که از @BotFather گرفتی رو برام بفرست.", { kb: [["❌ لغو"]] });
wait(0.5); typed("7XXXXXXXXX:AAH-xxxxxxxxxxxxxxxxxxxx", 1.0, { blur: true });
wait(0.4); inc("ربات «فروشگاه گل رز» با موفقیت ثبت شد ✅\n\nوارد محیط ساخت‌وساز ربات «فروشگاه گل رز» شدی.", { kb: [["🛠 ابزارهای ساخت‌وساز"]] });
wait(1.8);

// 3. /start
caption("قدم ۳", "دکمه‌ی استارت رو تعریف کن", "پیام خوش‌آمد + راه تماس");
wait(0.3); tap("🛠 ابزارهای ساخت‌وساز");
wait(0.2); kb([["1️⃣ تعریف دستور", "2️⃣ عضویت اجباری"], ["3️⃣ پیام‌رسانی گروهی", "4️⃣ لیست محتوا"], ["5️⃣ فروشگاه"]]);
wait(0.8); tap("1️⃣ تعریف دستور");
wait(0.3); inc("چون این اولین دستوریه که برای این ربات تعریف می‌کنی، پیشنهاد ما /start ئه.\n\nاسم دستور رو با / شروع کن و بنویس.", { kb: [["📋 نمایش دستورها", "❌ لغو"]] });
wait(0.6); typed("/start", 0.6);
wait(0.3); inc("یه پیام خوش‌آمدگویی کوتاه بنویس که توضیح بده رباتت چیکار می‌کنه.", { kb: [["❌ لغو"]] });
wait(0.5); typed("سلام 🌹 به فروشگاه گل رز خوش اومدی!", 1.2);
wait(0.3); inc("یوزرنیم تلگرام برای تماس مستقیم با ادمین رو وارد کن.");
wait(0.4); typed("@rose_admin", 0.8);
wait(0.3); inc("شماره و شبکه‌های اجتماعی هم اختیاریه…", { kb: [["⏭ رد کردن", "❌ لغو"]] });
wait(0.5); tap("⏭ رد کردن");
wait(0.3); inc("همه چی آماده‌ست. این مقادیر برای دستور /start ذخیره بشن؟", { kb: [["✅ ذخیره‌ی دستور /start"], ["❌ لغو"]] });
wait(0.6); tap("✅ ذخیره‌ی دستور /start");
wait(0.4); inc("ذخیره شد ✅", { kb: [["1️⃣ تعریف دستور", "2️⃣ عضویت اجباری"], ["3️⃣ پیام‌رسانی گروهی", "4️⃣ لیست محتوا"], ["5️⃣ فروشگاه"]] });
wait(1.2);

// 4. force join
caption("قدم ۴", "جوین اجباری 🔒", "اول عضو کانالت بشن، بعد وارد ربات");
wait(0.3); tap("2️⃣ عضویت اجباری");
wait(0.3); inc("کانال‌هایی که کاربرها باید عضوشون بشن رو تعریف کن.\nعضویت اجباری 🔓 در حال حاضر خاموشه.", { kb: [["📋 لیست کانال‌ها", "➕ تعریف کانال جدید"], ["🔒 فعال کردن عضویت اجباری"], ["❌ لغو"]] });
wait(0.7); tap("➕ تعریف کانال جدید");
wait(0.3); inc("یوزرنیم کانال رو با @ در ابتدا بفرست (مثلاً @mychannel).", { kb: [["🔙 بازگشت به منوی عضویت اجباری"]] });
wait(0.4); typed("@rose_flowers", 0.8);
wait(0.3); inc("«@rose_flowers» به لیست اضافه بشه؟", { kb: [["✅ تأیید", "🔙 بازگشت به منوی عضویت اجباری"]] });
wait(0.5); tap("✅ تأیید");
wait(0.3); inc("با موفقیت ذخیره شد ✅", { kb: [["📋 لیست کانال‌ها", "➕ تعریف کانال جدید"], ["🔒 فعال کردن عضویت اجباری"], ["❌ لغو"]] });
wait(0.6); tap("🔒 فعال کردن عضویت اجباری");
wait(0.3); inc("عضویت اجباری فعال شد ✅", { kb: [["📋 لیست کانال‌ها", "➕ تعریف کانال جدید"], ["🔓 غیرفعال کردن عضویت اجباری"], ["❌ لغو"]] });
note("⚠️ یادت نره: رباتت رو ادمین کانال کن", 3.0);
wait(3.0);

// 5. live
caption("قدم ۵", "روشنش کن: ۷۲ ساعت رایگان", "با دستور ‎/live");
kb(null);
wait(0.3); typed("/live", 0.6);
wait(0.4); inc("⚠️ فعال‌سازی آزمایشی رباتت رو 72 ساعت روی تلگرام فعال می‌کنه، تا خودت تستش کنی و نتیجه رو نشون بدی.");
wait(0.5); inc("✅ این ربات تا ۷۲ ساعت دیگه روی تلگرام فعاله.");
wait(1.8);

// 6. user view
scene(ROSE);
caption("نتیجه 👇", "از دید کاربر", "اول عضویت، بعد خوش‌آمد");
kb(null);
wait(0.5); typed("/start", 0.6);
wait(0.5); inc("Please join the channel(s) below to use this bot, then tap \"I've Joined\".", { inline: ["📢 @rose_flowers", "✅ I've Joined"] });
wait(1.0); tapInline("📢 @rose_flowers");
wait(0.6); tapInline("✅ I've Joined");
wait(0.4); inc("سلام 🌹 به فروشگاه گل رز خوش اومدی!\nContact: @rose_admin");
wait(2.4);


INTRO_HTML = `<div class="emoji">🤖</div><div class="big">بدون یک خط کد<br>ربات تلگرام بساز</div><div class="mid">دکمه‌ی استارت + جوین اجباری<br>در کمتر از یک دقیقه</div>`;
OUTRO_HTML = `<div class="big">رباتت رو همین الان بساز</div><div class="handle">@easymakebot</div><div class="chips"><div>⏱ ۷۲ ساعت رایگان</div><div>🔗 لینک در بیو</div></div>`;
