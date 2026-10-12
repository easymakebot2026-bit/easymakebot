// Reel 3 — broadcast: register a /sendall command, then message every user.
// Texts mirror bot/handlers/tools/message_to_all.py and the built bot's
// owner-side broadcast flow in bot/runtime.py (handle_owner_command /
// handle_broadcast_message), which is English-only on the built bot.
const EMB = { name: "EasyMakeBot", st: "bot", av: "E", color: "#ffb43f" };
const ROSE = { name: "فروشگاه گل رز", st: "bot", av: "🌹", color: "#ff7a90" };
const TOOLS_KB = [["1️⃣ تعریف دستور", "2️⃣ عضویت اجباری"], ["3️⃣ پیام‌رسانی گروهی", "4️⃣ لیست محتوا"], ["5️⃣ فروشگاه"]];
const OFFER = "🎉 جشنواره‌ی پاییزه!\n۳۰٪ تخفیف همه‌ی دسته‌گل‌ها، فقط تا جمعه 🌹";
function outPhoto(photo, text) { cur.events.push({ t: T, type: "msg", side: "out", text: text || "", photo }); }

INTRO_END = 2.8;
T = INTRO_END;

scene(EMB);
caption("قدم ۱", "دستور پیام همگانی بساز", "یه بار برای همیشه");
kb(TOOLS_KB);
wait(0.6); tap("3️⃣ پیام‌رسانی گروهی");
wait(0.3); inc("نام دستوری که پیام‌رسانی گروهی رو فعال می‌کنه بنویس، با / شروع کن.\nبعد از ذخیره، هر پیامی که با این دستور روی رباتت بفرستی، به تمام کاربرهای اون ربات ارسال می‌شه.", { kb: [["📋 نمایش دستورها", "❌ لغو"]] });
wait(1.2); typed("/sendall", 0.8);
wait(0.4); inc("دستور «/sendall» برای پیام‌رسانی گروهی ثبت شد 📢✅\nاز این به بعد، هر وقت این دستور رو روی رباتت همراه یه پیام بفرستی، به تمام کاربرهای اون ربات ارسال می‌شه.", { kb: [["🛠 ابزارهای ساخت‌وساز"]] });
wait(2.2);

scene(ROSE);
caption("قدم ۲", "توی ربات خودت بفرستش", "عکس، متن، ویدیو… هر چی خواستی");
kb(null);
wait(0.5); typed("/sendall", 0.7);
wait(0.4); inc("Send the message you want to deliver to all users of this bot.\n\nOr send /cancel to abort.");
wait(0.9); outPhoto("💐", OFFER);
wait(0.9);
caption("📢 ارسال شد!", "به همه‌ی کاربرات رسید", "بدون حتی یه پیام دستی");
inc("✅ Delivered to 1284 user(s)");
note("💡 کاربر هر وقت نخواد، با ‎/stop لغوش می‌کنه", 2.8);
wait(2.8);

scene({ name: "فروشگاه گل رز", st: "bot · از دید مشتری", av: "🌹", color: "#ff7a90" });
caption("نتیجه 👇", "از دید مشتری", "همون لحظه نوتیفیکیشن می‌گیره 🔔");
wait(0.5); inc(OFFER, { photo: "💐" });
wait(3.6);

INTRO_HTML = `<div class="emoji">📢</div><div class="big">با یه پیام<br>به همه‌ی مشتری‌هات برس</div><div class="mid">تخفیف، محصول جدید، خبر مهم<br>بدون کپی‌پیست تک‌تکی</div>`;
OUTRO_HTML = `<div class="big">پیام همگانی<br>توی ربات خودت</div><div class="handle">@easymakebot</div><div class="chips"><div>⏱ ۷۲ ساعت رایگان</div><div>🔗 لینک در بیو</div></div>`;
