// Reel 6 — checkout -> card-to-card payment -> owner approval -> shipping
// info -> PDF invoice. Continues reel 5's cart. Texts mirror bot/runtime.py
// (handle_cart_checkout, _start_manual_checkout_payment,
// receive_checkout_transaction_ref, handle_cart_approve, the shipc_* shipping
// wizard) and bot/shop.py (fulfill_checkout, SHIPPING_METHODS). The invoice
// shown is a real one rendered by bot/shop.py:_render_invoice_pdf via
// assets/make_invoice.py. Several buyer/owner messages after payment are
// English-only in the bot, and are shown as-is.
const ROSE = { name: "فروشگاه گل رز", st: "bot · از دید مشتری", av: "🌹", color: "#ff7a90" };
const OWNER = { name: "فروشگاه گل رز", st: "bot · از دید صاحب ربات", av: "🌹", color: "#ff7a90" };
const NAME = "دسته‌گل عروس 💐";

INTRO_END = 2.8;
T = INTRO_END;

scene(ROSE);
card(`<div class="big" style="font-size:74px">یه بار تنظیم کن ⚙️</div><div class="codes">
<div class="row"><b>💳</b>روش پرداخت: کارت به کارت یا زرین‌پال</div>
<div class="row"><b>🧾</b>فاکتور: اسم، لوگو، آدرس و امضای فروشگاه</div></div>
<div class="mid" style="font-size:38px;margin-top:34px">از منوی «5️⃣ فروشگاه»</div>`, 3.6);

caption("قدم ۱", "مشتری پرداخت می‌کنه", "کارت به کارت یا درگاه");
wait(0.4); inc(`🧺 جمع سبد خرید:\n• ${NAME} × 1 — 1,200,000 Toman\n\n💰 مجموع: 1,200,000 Toman`, { inline: ["💳 پرداخت / تسویه حساب"] });
wait(1.0); tapInline("💳 پرداخت / تسویه حساب");
wait(0.3); inc("💰 مجموع: 1,200,000 تومان\n\nروش پرداخت را انتخاب کنید:", { inline: ["💳 زرین‌پال", "🏦 کارت به کارت"] });
wait(1.1); tapInline("🏦 کارت به کارت");
wait(0.3); inc("💳 شماره کارت: 6037-9975-1234-5678\n👤 فروشگاه گل رز\n\n💰 مبلغ: 1,200,000 تومان\n\nبعد از پرداخت، شماره پیگیری تراکنش (یا هش) را ارسال کنید.");
wait(1.6); typed("748215", 0.6);
wait(0.4); inc("ممنون! پرداخت شما در انتظار بررسی مالک ربات است.");
wait(1.4);

scene(OWNER);
caption("قدم ۲", "تو فقط تأیید می‌کنی ✅", "یه دکمه، تمام");
wait(0.5); inc("🧾 New cart checkout #42\nTotal: 1,200,000 Toman\nPayment method: Card to Card\nBuyer: 482915736\nOrder date: 2026-10-14 18:30\nTransaction ref: 748215", { inline: ["✅ Confirm", "❌ Reject"] });
wait(1.6); tapInline("✅ Confirm");
note("✅ Approved", 1.4);
wait(1.6);

scene(ROSE);
caption("قدم ۳", "مشتری آدرس رو می‌ده", "روش ارسال رو هم خودش انتخاب می‌کنه");
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
caption("قدم ۴", "فاکتور خودکار صادر می‌شه 🧾", "PDF، با اسم فروشگاه خودت");
inc("🧾 Invoice", { doc: "invoice-5A1E01-C000042.pdf" });
wait(1.8);

card(`<div class="big" style="font-size:66px">فاکتور رسمی، خودکار 🧾</div>
<img src="assets/invoice.png" style="width:1000px;margin-top:30px;border-radius:18px;box-shadow:0 20px 60px rgba(0,0,0,.5);background:#fff;height:980px;object-fit:cover;object-position:top">`, 4.4);

INTRO_HTML = `<div class="emoji">🧾</div><div class="big">از سبد خرید<br>تا فاکتور</div><div class="mid">پرداخت، تأیید، آدرس ارسال، فاکتور PDF<br>همه خودکار، توی تلگرام</div>`;
OUTRO_HTML = `<div class="big">فروش کامل<br>توی ربات خودت</div><div class="handle">@easymakebot</div><div class="chips"><div>⏱ ۷۲ ساعت رایگان</div><div>🔗 لینک در بیو</div></div>`;
