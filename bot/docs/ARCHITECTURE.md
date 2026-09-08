# مستند فنی پلتفرم easymakebot

آخرین به‌روزرسانی: بعد از commit `e0aea55` («Shop v2»)، روی تگ rollback به‌نام `pre-shop-v2` (commit `cc5be47`).

این سند تمام کد، فایل‌ها، جدول‌های دیتابیس و ارتباط‌های بین بخش‌های مختلف پروژه‌ی easymakebot را مستند می‌کند — هم برای مرور خودت، هم برای جلسه‌ی فردا که سرورها رو با هم راه‌اندازی می‌کنیم.

---

## ۱. این پروژه چیست

easymakebot یک پلتفرم SaaS است: هرکسی می‌تونه بدون کدنویسی، با گرفتن یک توکن از BotFather، ربات تلگرام خودش رو بسازه — دستور تعریف کنه، عضویت اجباری بذاره، محتوا/فروشگاه/اشتراک راه بندازه، و بعد از یک دوره تست رایگان (Trial) یا خرید پلن، رباتش رو «Live» کنه تا واقعاً روی تلگرام جواب بده.

دو سرویس کاملاً جدا کنار هم کار می‌کنند:

1. **ربات (bot/ + webapp/ + deploy/)** — خودِ پلتفرم easymakebot؛ یک پروسه‌ی پایتونی که هم «ربات‌ساز» اصلی رو اجرا می‌کنه، هم به‌ازای هر ربات ساخته‌شده یک polling task جدا بالا می‌آره. قرار است روی سرور **آلمان** دیپلوی بشه.
2. **سایت (web/)** — یک وردپرس/ووکامرس که پلن‌های اشتراک رو به کاربرهای ایرانی می‌فروشه (چون درگاه ایرانی روی سرور خارج کار نمی‌کنه). روی سرور **ایران** هست. این دو فقط از طریق یک REST API کوچک (بخش ۱۱) با هم حرف می‌زنن — هیچ دیتابیس مشترکی ندارن.

---

## ۲. ساختار پوشه‌ها

```
easymakebot/
├── bot/                    # بک‌اند پایتونی (aiogram 3 + SQLAlchemy async + PostgreSQL)
│   ├── main.py             # نقطه‌ی ورود پروسه
│   ├── config.py           # خواندن تنظیمات از .env
│   ├── db/                 # مدل‌ها و init_db (base.py, models.py, encrypted_types.py)
│   ├── handlers/           # هندلرهای تلگرام (دستورها/دکمه‌ها)
│   │   └── tools/          # پنج ابزار «Build & Edit Tools»
│   ├── filters/            # فیلترهای aiogram (فعلاً فقط IsPlatformAdmin)
│   ├── runtime.py          # اجرای هر ربات ساخته‌شده + منطق /start قدیمی
│   ├── flow_engine.py      # مفسّر خروجی Visual Flow Builder
│   ├── shop.py / shop_import.py / inventory.py / pricing.py / premium_content.py
│   ├── live.py / platform_billing.py / website_client.py   # لایو‌شدن و پرداخت
│   ├── admin_panel.py      # داده‌ی پنل ادمین پلتفرم
│   ├── webapp_server.py / webapp_auth.py   # سرور HTTP برای Mini App
│   └── docs/               # همین مستندها
├── webapp/src/             # فرانت‌اند React — بوم Visual Flow Builder (Telegram Mini App)
├── web/                    # سایت وردپرس/ووکامرس (سمت ایران) — مستقل از bot/
│   ├── wordpress/wp-content/mu-plugins/emb-activation-codes.php   # پل بین سایت و ربات
│   └── docs/               # چک‌لیست و runbook دیپلوی سایت (از قبل نوشته شده)
├── deploy/                 # Docker Compose + Caddy برای دیپلوی خودِ ربات (سرور آلمان)
│   ├── docker-compose.bot.yml         # استک production (bot-db + bot + caddy)
│   ├── docker-compose.bot.local.yml   # override تست لوکال روی ویندوز
│   └── README.md           # runbook کامل دیپلوی (از قبل نوشته شده)
└── requirements.txt
```

---

## ۳. معماری زمان اجرا (Runtime)

- **یک پروسه، N ربات.** `bot/main.py` هم دیسپچر ربات اصلی (ربات‌ساز) را اجرا می‌کند، هم با `runtime.start_all_built_bots()` برای هر `BuiltBot` که `live_until` معتبر و `suspended=False` دارد، یک polling task جدا (با `Bot(token=...)` مخصوص همون ربات) راه می‌اندازد. یعنی صدها ربات کاربر همه داخل همین یک پروسه پایتون polling می‌کنند.
- **ترتیب ثبت روتر در main.py مهم است:** اول `cancel_router` (تا `/cancel` همیشه هر جایی کار کند)، بعد روترهای state-محور (ابزارها) که باید روی متن آزاد وسط یک ویزارد — حتی اگر تصادفاً `/start` باشد — زودتر از `start_router` بگیرند.
- **میدل‌ور راهنما:** یک `outer_middleware` روی callback query، بعد از اجرای هندلر، اگر برای همان `callback_data` در `bot/help_text.py` راهنمایی ثبت شده باشد، به‌صورت پیام جدا (فارسی یا انگلیسی، بر اساس `guide.owner_prefers_persian`) می‌فرستد.
- **حلقه‌های پس‌زمینه:** `runtime.run_campaign_expiry_loop()` (پایان خودکار کمپین‌های تخفیف سررسیدشده) و `runtime.run_live_expiry_loop()` (توقف polling ربات‌هایی که پنجره‌ی Live‌شان تمام شده).
- **وب‌سرور Mini App:** `webapp_server.start_webapp_server()` یک سرور aiohttp جدا (پورت `WEBAPP_PORT`, پیش‌فرض ۸۰۸۰) برای Visual Flow Builder و کال‌بک‌های پرداخت بالا می‌آورد.

---

## ۴. پایگاه داده (PostgreSQL، از طریق SQLAlchemy async)

مهاجرت به‌صورت additive-only است — هیچ Alembic واقعی در زمان اجرا استفاده نمی‌شود؛ `bot/db/base.py: init_db()` هم `Base.metadata.create_all` را برای جدول‌های تازه صدا می‌زند، هم برای جدول‌های موجود یک سری `ALTER TABLE ... ADD COLUMN IF NOT EXISTS ...` دستی اجرا می‌کند. یعنی هر فیلد جدید همیشه باید nullable/optional باشد (هیچ‌وقت داده‌ی قدیمی را نمی‌شکند).

| جدول | توضیح خلاصه |
|---|---|
| `users` | کاربر پلتفرم (سازنده‌ی ربات). `phone_number` رمزنگاری‌شده؛ `region` = `iran`/`international` برای انتخاب روش پرداخت `/live`. |
| `built_bots` | یک ربات ساخته‌شده. `token` رمزنگاری‌شده. `flow_definition` (JSON رمزنگاری‌شده‌ی Visual Builder). `live_until`, `suspended` (کلید خاموشی دستی ادمین، مستقل از انقضا)، `commerce_mode` (`shop`/`subscription`، یک‌بار انتخاب و غیرقابل‌تغییر). |
| `commands` | دستورهای دلخواه هر ربات (`command_type`: `start`/`custom`/`broadcast`)؛ `payload` رمزنگاری‌شده (مثلاً فیلدهای ویزارد `/start`). |
| `join_channels` | کانال‌های عضویت اجباری هر ربات. |
| `content_items` | آیتم «لیست محتوا» — درخت خودارجاع (`parent_id`) برای دسته‌بندی تودرتو؛ می‌تواند به یک `Product` وصل باشد (`product_id`، فروش از دل محتوا) و/یا `is_premium` باشد (قفل اشتراک). `code` یکتا در سطح هر ربات، برای دسترسی میان‌بر با تایپ. |
| `content_unlocks` | ثبت اینکه یک مشترک با «سهمیه‌ی رایگان» کدام آیتم پولی را برای همیشه باز کرده — تفاوتش با اشتراک فعال این‌ست که هیچ‌وقت منقضی نمی‌شود. |
| `bot_subscribers` | هر کسی که یک بار `/start` ربات ساخته‌شده را زده. `access_level` (از خرید محصول نوع access) و `subscription_until` (زمان‌دار، همیشه زنده چک می‌شود). |
| `bot_posts` / `post_likes` / `post_comments` | پست‌های شبکه‌اجتماعی‌طور («Add Post») با لایک/کامنت. |
| `products` | محصول/پلن فروشگاه. `product_type`: `physical` / `digital` / `access` / `subscription` / `content_unlock` (مخفی، داخلی). فیلدهای **جدید Shop v2**: `stock_quantity`, `cost_price`, `import_code`. |
| `shop_settings` | یک ردیف به‌ازای هر ربات: درگاه‌های پرداخت (Zarinpal/کارت‌به‌کارت/Stripe/کریپتو/TON، همه رمزنگاری‌شده)، سهمیه‌ی پیش‌نمایش رایگان، قیمت پیش‌فرض تک‌خرید. فیلدهای **جدید Shop v2**: `invoice_business_name`, `invoice_logo_url`, `invoice_address`, `invoice_footer_note`. |
| `price_campaigns` | کمپین موقت تخفیف/افزایش روی همه‌ی قیمت‌های یک ربات؛ حداکثر یک کمپین `active` هم‌زمان (ایندکس یکتای جزئی). |
| `orders` | یک خرید. `status`: `pending` → `paid` → `fulfilled`، یا `rejected`. آدرس/روش ارسال فیزیکی، اطلاعات درگاه. |
| `cart_items` / `checkouts` | سبد خرید و پرداخت گروهی چند محصول با هم. |
| `live_payments` | پرداخت **به خودِ پلتفرم** برای لایو‌کردن ربات (جدا از `orders` که پول مشتریِ ربات است). |
| `broadcast_logs` | تاریخچه‌ی پیام‌های همگانیِ هر ربات به مشترکینش. |

**رابطه‌ی کلیدی:** همه‌چیز به `built_bots.id` (UUID) قفل است؛ حذف یک `BuiltBot` با cascade همه‌ی داده‌های وابسته (دستورها، محصولات، سفارش‌ها، ...) را هم پاک می‌کند (`admin_panel.delete_bot`).

---

## ۵. ماژول‌های bot/ — فایل به فایل

### هسته و روتینگ
- **`main.py`** — نقطه‌ی ورود؛ می‌سازد Bot/Dispatcher، تمام روترها را با ترتیب مشخص ثبت می‌کند، `init_db`، `start_all_built_bots`، حلقه‌های انقضا، سرور Mini App، و `set_my_commands` (`/start`, `/mybots`, `/newbot`, `/live`, `/help`) را صدا می‌زند.
- **`config.py`** — `Config` dataclass از `.env`: `BOT_TOKEN`, `DATABASE_URL`, `PLATFORM_ADMIN_ID`, `WEBAPP_URL`, `WEBAPP_PORT`, `VIDEO_URL_FA/EN`, `PLATFORM_ZARINPAL_MERCHANT_ID`, `PLATFORM_STRIPE_SECRET_KEY`, `PLATFORM_TON_WALLET_ADDRESS`, `WEBSITE_URL`, `WEBSITE_ACTIVATION_KEY`, `WEBSITE_PLANS_URL`, `PLATFORM_ONBOT_ZARINPAL`.
- **`session.py`** — فکتوری یک‌خطی `AiohttpSession` مشترک برای instance‌های موقت `Bot`.
- **`runtime.py`** (بزرگ‌ترین فایل) — اجرای واقعی هر ربات ساخته‌شده: `/start` قدیمی (غیر بصری) در برابر Visual Flow، `sync_bot_commands` (به‌روزرسانی منوی «/» تلگرام هر ربات بعد از هر تغییر)، هندل خرید/پرداخت (`shop_buy`, `shop_pay`, کارت‌به‌کارت، Zarinpal/Stripe)، سبد خرید، ویزارد آدرس ارسال فیزیکی، لایک/کامنت پست‌ها، `start_built_bot`/`stop_built_bot`، حلقه‌های `run_campaign_expiry_loop`/`run_live_expiry_loop`.
- **`flow_engine.py`** — مفسّر گراف Visual Builder (`BuiltBot.flow_definition`). نسخه‌ی فعلی فقط **زنجیره‌ی خطی** را پشتیبانی می‌کند (بدون شاخه‌زدن)، ۷ نوع بلاک: `trigger`, `send_message`, `force_join_gate`, `guide_video`, `content_list`, `shop`, `broadcast`.
- **`filters/admin.py`** — `IsPlatformAdmin(BaseFilter)`؛ تنها مکانیزم کنترل‌دسترسی ادمین در کل پروژه.

### هویت، راهنما، پیام‌رسانی مشترک
- **`guide.py`** — تشخیص فارسی/انگلیسی (`owner_prefers_persian`) و ایران/بین‌الملل (`is_iran_phone`، پیش‌شماره‌ی `+98`)؛ متن کامل راهنمای پلتفرم و راهنمای هر ربات ساخته‌شده؛ کیبورد اشتراک‌گذاری شماره.
- **`help_text.py`** — دیکشنری نکته‌های راهنمای فارسی/انگلیسی (`tip_suffix`) که زیر پیام‌های ابزارها چسبانده می‌شود.
- **`list_render.py`** — رندر مشترک لیست آیتم‌ها (عکس‌دار → کارت جدا، بی‌عکس → دکمه‌ی ساده).
- **`force_join_gate.py`** — گیت عضویت اجباری مشترک بین `/start` قدیمی و Flow Engine؛ اگر تلگرام نتواند وضعیت یک کانال را چک کند، **fail-safe** (یعنی «هنوز عضو نشده» فرض می‌شود).
- **`content_nav.py`** — عملیات مشترک درخت «لیست محتوا» (شامل تشخیص چرخه‌ی `would_cycle` هنگام جابه‌جایی/ایمپورت).

### تجاری‌سازی
- **`commerce_mode.py`** — ذخیره‌ی انتخاب یک‌باره‌ی هر ربات بین `shop` و `subscription`.
- **`shop.py`** — قلب فروشگاه: محصولات، سفارش، سبد خرید، تأیید پرداخت (Zarinpal/Stripe/کارت‌به‌کارت/کریپتو)، `fulfill_order` (تحویل بر اساس نوع محصول)، **تولید فاکتور PDF فارسی** (`generate_invoice`، با reportlab + arabic_reshaper + bidi، حالا با برندینگ قابل‌تنظیم — بخش ۹)، و کمپین قیمت.
- **`shop_import.py`** *(جدید Shop v2)* — پارس اکسل/CSV محصولات (نام/قیمت/قیمت‌تمام‌شده/موجودی)، فقط فارسی+انگلیسی، upsert بر اساس ستون Code.
- **`inventory.py`** *(جدید Shop v2)* — آمار فروش/موجودی هر ربات به‌تنهایی (درآمد، سود، پرفروش‌ترین‌ها، کم‌موجودی‌ها) — نسخه‌ی مخصوص صاحب همان ربات، در برابر `admin_panel.py` که آمار کل پلتفرم است.
- **`pricing.py`** — محاسبه‌ی خالص تخفیف/افزایش قیمت و متن خط‌خورده، بدون هیچ وابستگی به دیتابیس/تلگرام.
- **`premium_content.py`** — منطق حالت اشتراک: سهمیه‌ی پیش‌نمایش رایگان، بعد نیاز به اشتراک فعال یا خرید تک‌آیتمی.

### لایو‌شدن و پرداخت پلتفرم
- **`live.py`** — چرخه‌ی عمر Live: تست رایگان ۷۲ساعته یک‌باره، `LIVE_PLANS` (فعلاً یک پلن ماهانه)، `is_bot_suspended` (کلید خاموشی ادمین، همیشه اولویت اول)، `is_bot_expired`، و `get_owned_built_bot` (تنها مرز امنیتی مالکیت ربات).
- **`platform_billing.py`** — منطق پرداخت **به خود پلتفرم** برای لایو‌کردن: تشخیص منطقه (ایران/بین‌الملل)، Zarinpal فقط برای ایران، Stripe/TON برای بین‌الملل، تأیید تراکنش‌های TON دستی توسط ادمین.
- **`website_client.py`** — کلاینت REST برای فراخوانی سایت وردپرس (بخش ۱۱).
- **`admin_panel.py`** — لایه‌ی داده‌ی پنل `/easybotadmin`: آمار کل پلتفرم، لیست/جزئیات کاربر و ربات، تعلیق/رفع‌تعلیق، اعطای دسترسی رایگان، تغییرنام، حذف کامل، خروجی اکسل. **خودش هیچ کنترل‌دسترسی‌ای ندارد** — مسئولیتش با هندلرهاست.

### Mini App (Visual Flow Builder)
- **`webapp_auth.py`** — اعتبارسنجی HMAC استاندارد تلگرام برای `initData` (اثبات اینکه درخواست واقعاً از همان Mini App/کاربر تلگرام آمده).
- **`webapp_server.py`** — سرور aiohttp: صفحه‌ی برگشت پرداخت‌های Zarinpal/Stripe (هم فروشگاه، هم لایو-پلتفرم — چهار route جدا)، API خواندن/ذخیره‌ی `flow_definition`، CRUD کامل «لیست محتوا» (`/api/content`)، سرو کردن فایل build شده‌ی React (`webapp/dist`).

### هندلرهای تلگرام (`handlers/`)
- **`start.py`** — `/start`, `/help`، ویزارد اشتراک‌گذاری شماره‌ی اولیه.
- **`my_bots.py`** — `/mybots`، انتخاب ربات (تنها نقطه‌ای که `bot_id` از callback ناامن به `active_bot_id` امن در state تبدیل می‌شود).
- **`create_bot.py`** — `/newbot`، اعتبارسنجی توکن BotFather.
- **`cancel.py`** — `/cancel` سراسری، همیشه برنده.
- **`tools_menu.py`** — نمایش گرید «Build & Edit Tools»، با چک تعلیق/انقضا.
- **`live.py`** — `/live`: نمایش وضعیت، تست رایگان، فعال‌سازی با کد سایت، پرداخت پلن (Zarinpal/Stripe/TON).
- **`easybotadmin.py`** — تمام پنل ادمین پلتفرم (فقط `PLATFORM_ADMIN_ID`).
- **`admin_broadcast.py`** — `/send_to_all` (ادمین پلتفرم → همه‌ی سازنده‌های ربات؛ فرق دارد با broadcast داخل هر ربات).
- **`tools/define_command.py`** — تعریف دستور دلخواه + ویزارد کامل `/start`.
- **`tools/force_join.py`** — مدیریت کانال‌های عضویت اجباری + روشن/خاموش.
- **`tools/message_to_all.py`** — ساخت دستور Broadcast مخصوص یک ربات (صاحب ربات → مشترکین همان ربات).
- **`tools/content_list.py`** — بزرگ‌ترین هندلر ابزارها: انتخاب حالت تجاری، افزودن/ویرایش/حذف/دسته‌بندی آیتم، «Add Post»، ایمپورت/اکسپورت اکسل (۱۰ زبان).
- **`tools/shop.py`** — همه‌ی «Shop» تولزمنو، شامل قابلیت‌های **جدید Shop v2** (بخش ۹).

### فرانت‌اند Mini App (`webapp/src/`)
React + `@xyflow/react`. `App.jsx` بوم اصلی؛ `nodes.jsx` تعریف ۷ نوع بلاک (باید همیشه با `flow_engine.py` هم‌خوان بماند)؛ `Palette.jsx` نوار بلاک‌های قابل‌درگ (با Pointer Events خام، چون Drag-and-Drop نیتیو HTML5 داخل webview موبایل تلگرام کار نمی‌کند)؛ `ContentManager.jsx` مودال مدیریت «لیست محتوا» از دل خودِ Mini App؛ `telegram.js` پل بین Telegram WebApp SDK و API بک‌اند (هدر `X-Telegram-Init-Data`).

---

## ۶. سطوح دسترسی و امنیت — خلاصه

| نقش | مکانیزم |
|---|---|
| **ادمین پلتفرم (خودت)** | `PLATFORM_ADMIN_ID` در `.env`؛ فیلتر `IsPlatformAdmin` روی تک‌تک هندلرهای `/easybotadmin` و `/send_to_all`. `admin_panel.py` خودش چک نمی‌کند — مسئولیت با هندلر است. |
| **صاحب ربات** | مالکیت یک‌بار در `my_bots.py:select_bot` با `live.get_owned_built_bot(bot_id, telegram_id)` چک می‌شود؛ بعد از آن `active_bot_id` در FSM state «قابل‌اعتماد» فرض می‌شود و همه‌ی ابزارها به آن تکیه می‌کنند. |
| **کاربر نهایی/مشترک ربات ساخته‌شده** | بدون سطح خاص — فقط گیت‌های عضویت اجباری/اشتراک/موجودی روی او اعمال می‌شود. |
| **کلید خاموشی تعلیق ادمین** (`suspended`) | همیشه اولویت اول، حتی روی پرداخت موفق؛ فقط با رفع‌تعلیق دستی ادمین برمی‌گردد. |
| **Mini App** | HMAC استاندارد تلگرام (`webapp_auth.py`) + join مالکیت در `webapp_server.py:_authenticated_bot`. Route های کال‌بک پرداخت عمداً بدون این چک‌اند (چون خودِ درگاه صداشان می‌زند)، امنیتشان از توکن/session_id غیرقابل‌حدس تراکنش می‌آید. |
| **داده‌های حساس** | توکن ربات، شماره تلفن، کلیدهای درگاه پرداخت، متن broadcast — همه با `EncryptedString`/`EncryptedJSON` (`db/encrypted_types.py`, کلید از `ENCRYPTION_KEY`) رمزنگاری می‌شوند. |

---

## ۷. سیستم Live / تعلیق / صورتحساب پلتفرم

- هر ربات تازه‌ساخته‌شده فقط قابل **ویرایش** است، polling تلگرامش خاموش است تا «Live» شود.
- **تست رایگان:** یک‌بار، ۷۲ ساعته (`live.TRIAL_HOURS`)، از دکمه‌ی «live:trial».
- **پلن پولی:** `live.LIVE_PLANS` (فعلاً یک پلن ماهانه، ۴۹۰٬۰۰۰ تومان / ۱۰ دلار). روش پرداخت بر اساس منطقه‌ی کاربر (`platform_billing.resolve_region`) فیلتر می‌شود:
  - **ایران:** اگر `PLATFORM_ONBOT_ZARINPAL=false` باشد (حالت پیش‌فرض وقتی سایت ایران و ربات آلمان است)، پرداخت مستقیم تلگرامی برای ایران اصلاً پیشنهاد نمی‌شود؛ به‌جایش پیام «خرید پلن روی وب‌سایت» + دکمه‌ی «فعال‌سازی با کد» نشان داده می‌شود (بخش ۱۱).
  - **بین‌الملل:** Stripe یا TON، مستقیم از داخل تلگرام (`live:pay:<plan>:<method>`).
- تأیید TON دستی است: کاربر هش تراکنش را می‌فرستد، به ادمین پیام می‌رود، ادمین با دکمه `live:ton_approve:<id>` تأیید می‌کند.
- **تعلیق ادمین** (`suspended`) کاملاً مستقل از `live_until` است و همیشه اول چک می‌شود — حتی اگر ربات پلن معتبر داشته باشد، تعلیق آن را آفلاین نگه می‌دارد.

---

## ۸. فروشگاه/اشتراک — شامل قابلیت‌های جدید Shop v2

هر ربات یک بار بین دو حالت انتخاب می‌کند (`commerce_mode.py`، غیرقابل‌تغییر):

- **Shop:** فروش تک‌محصولی، سبد خرید، پرداخت.
- **Subscription:** آرشیو محتوای قفل‌شده پشت اشتراک، با سهمیه‌ی پیش‌نمایش رایگان.

### قابلیت‌های تازه اضافه‌شده (روی commit `e0aea55`، بعد از تگ `pre-shop-v2`)

1. **برندسازی فاکتور (Invoice Branding)** — منوی «🧾 Invoice Branding» در ابزار Shop: نام کسب‌وکار، لوگو (URL عکس)، آدرس، یادداشت پایین فاکتور. همه‌ی این‌ها روی `ShopSettings` ذخیره و در `shop.generate_invoice()` روی فاکتور PDF چاپ می‌شوند؛ نبودشان یعنی برگشت به فاکتور ساده‌ی پیش‌فرض (بدون شکستن چیزی).
2. **ایمپورت محصول با قیمت/موجودی (`shop_import.py`)** — منوی «📥 Import Products»: دانلود نمونه‌ی اکسل (فارسی/انگلیسی)، آپلود فایل خودِ صاحب ربات (ستون‌های نام/توضیح/قیمت/قیمت‌تمام‌شده/موجودی/عکس/کد/عملیات)، upsert بر اساس ستون Code (آپلود دوباره با همان کد = به‌روزرسانی، نه تکرار)؛ ردیف با Action=Delete یعنی حذف.
3. **موجودی و جلوگیری از فروش بیش از موجودی** — `Product.stock_quantity`؛ `create_order`/`create_checkout` آیتم ناموجود را رد می‌کنند (بدون خطا، فقط پنهانش می‌کنند)، `fulfill_order` یک کاهش اتمی (`UPDATE ... WHERE stock_quantity > 0`) انجام می‌دهد تا زیر صفر نرود، حتی زیر بار همزمان. Flow Engine هم آیتم ناموجود را از لیست خریدار مخفی می‌کند.
4. **آمار فروش و موجودی («📊 Sales & Stock»)** — `bot/inventory.py`: تعداد محصول، تعداد سفارش، درآمد، سود (فقط اگر قیمت‌تمام‌شده برای حداقل یک محصول ثبت شده باشد)، ۵ پرفروش‌ترین، لیست کم‌موجودی (≤۵ عدد). مخصوص همان یک ربات — نسخه‌ی همه‌ی پلتفرم فقط برای ادمین است (`admin_panel.py`).

### نقطه‌ی rollback

نسخه‌ی قبل از این چهار قابلیت، دقیقاً روی تگ گیت `pre-shop-v2` نگه داشته شده (بخش ۱۳).

---

## ۹. Visual Flow Builder (Mini App)

- از «My Bots» → انتخاب ربات → دکمه‌ی «🎨 Visual Builder» (فقط اگر `WEBAPP_URL` تنظیم شده باشد) یک Telegram Mini App باز می‌شود.
- بوم درگ‌ودراپ (`webapp/src/App.jsx`) با ۷ نوع بلاک: Trigger، Send Message، Force Join Gate، Guide & Video، Content List، Shop، Broadcast (مارکر، ارسال واقعی همچنان از ابزار چت انجام می‌شود).
- ذخیره با دکمه‌ی Save → `POST /api/flow` → `BuiltBot.flow_definition` (JSON رمزنگاری‌شده).
- **محدودیت فعلی نسخه‌ی ۱:** فقط زنجیره‌ی خطی، بدون شاخه‌زدن (branching)، بدون متغیر، بدون نمایش داده‌ی پویا/محاسبه‌شده (مثل «فروش امروز» زنده). این را در بخش «سؤال‌های قبلی» (پایین همین سند نیست، در تاریخچه‌ی گفتگو ثبت شده) قبلاً بررسی کردیم — قابل توسعه است ولی هنوز پیاده نشده.
- برای `/start` مشخصاً: هرکدام از Flow جدید و دستور قدیمی `Command(name="/start")` که آخر ویرایش شده باشد، برنده است (`runtime.py:_should_use_flow_for_start`). دستورهای دیگر همیشه از Flow پیروی می‌کنند اگر تریگر داشته باشند.

---

## ۱۰. ارتباط سایت (ایران) ↔ ربات (آلمان) — پل فعال‌سازی

این دقیقاً همان چیزی است که فردا باید روی سرورهای واقعی وصل شود.

```
کاربر ایرانی                 سایت وردپرس (ایران)              ربات (آلمان)
     │  خرید پلن با درگاه ایرانی │                                  │
     ├──────────────────────────►│                                  │
     │                            │ woocommerce_order_status_        │
     │                            │  processing/completed →          │
     │                            │  emb-activation-codes.php        │
     │                            │  یک کد یک‌بارمصرف می‌سازد          │
     │                            │  EMB-XXXX-XXXX                   │
     │◄──────────────────────────┤                                  │
     │  کد را در ربات، از /live → «فعال‌سازی با کد» وارد می‌کند       │
     ├─────────────────────────────────────────────────────────────►│
     │                            │       POST /wp-json/emb/v1/redeem │
     │                            │◄───────────────────────────────┤
     │                            │  هدر X-EMB-Key چک می‌شود،         │
     │                            │  کد atomically claim می‌شود      │
     │                            ├─────────────────────────────────►│
     │                            │  {ok, months, days}               │
     │  ربات live_until را ست     │                                  │
     │  می‌کند و polling را        │                                  │
     │  استارت می‌کند              │                                  │
```

- **سمت ربات:** `bot/website_client.py: redeem_activation_code()` با هدر `X-EMB-Key: {WEBSITE_ACTIVATION_KEY}` به `{WEBSITE_URL}/wp-json/emb/v1/redeem` می‌زند (۳ تلاش، backoff ۲/۴/۸ ثانیه). `bot/handlers/live.py` این جریان را با گرفتن شماره تلفن معتبر (یک‌بار) و اعمال روزهای اضافه‌شده به `live_until` تمام می‌کند.
- **سمت سایت:** `web/wordpress/wp-content/mu-plugins/emb-activation-codes.php` روی ثبت سفارش ووکامرس (متادیتای `_emb_plan_months` روی محصول پلن) کد می‌سازد؛ `hash_equals()` برای چک کلید، claim اتمیک کد (جلوگیری از استفاده‌ی دوباره).
- **تنظیمات باید دقیقاً هم‌خوان باشند:** `WEBSITE_URL`, `WEBSITE_ACTIVATION_KEY` (سمت ربات) باید دقیقاً با `EMB_ACTIVATION_KEY` (سمت سایت) یکی باشد؛ `WEBSITE_PLANS_URL` جایی است که کاربر ایرانی برای خرید فرستاده می‌شود.
- چون سرور ربات در آلمان است، **پرداخت مستقیم Zarinpal داخل تلگرام برای ایران خاموش می‌ماند** (`PLATFORM_ONBOT_ZARINPAL=false`) — این دقیقاً منطقی است که خودت خواستی: «خرید اشتراک باید از روی سایت انجام بشه».
- برای فردا چک‌لیست باز: دسترسی به هر دو سرور، دامنه/DNS هرکدام (Cloudflare)، محصول پلن در ووکامرس با `_emb_plan_months` درست، و یکی‌بودن کلید فعال‌سازی بین دو طرف. Runbook کامل هرکدام از قبل نوشته شده: `deploy/README.md` (سمت آلمان/ربات) و `web/docs/00-provisioning-checklist.md` + `web/docs/10-deploy-runbook.md` (سمت ایران/سایت).

---

## ۱۱. دیپلوی و زیرساخت

### سمت ربات (آلمان) — `deploy/`
- **Production:** `docker-compose.bot.yml` — سه سرویس: `bot-db` (Postgres)، `bot` (بیلد از `deploy/Dockerfile`، context کل ریپو)، `caddy` (TLS خودکار برای `APP_DOMAIN`، پروکسی به سرور aiohttp ربات — همان دامنه‌ای که Mini App و کال‌بک‌های پرداخت روی آن سرو می‌شوند).
- **تست لوکال ویندوز:** `docker-compose.bot.local.yml` (override) — بدون `bot-db`/`caddy` جدا؛ به دیتابیس موجود روی هاست وصل می‌شود (`host.docker.internal`)، پوشه‌ی `bot/` را **read-only bind-mount** می‌کند (یعنی تغییر کد فقط با **ریستارت ساده‌ی کانتینر** اعمال می‌شود، نه rebuild)، و به‌جای Caddy از تونل موقت `cloudflared tunnel --url http://localhost:8081` استفاده می‌کند — چون این تونل‌ها منقضی می‌شوند، هر بار که خطای Cloudflare 1016 دیدی یعنی باید یک تونل تازه بسازی و `WEBAPP_URL` را در `.env.bot` آپدیت کنی و کانتینر را recreate کنی (`up -d --no-deps bot`، نه فقط restart، چون env فقط موقع recreate خوانده می‌شود).
- کامند کامل: `docker compose --env-file .env.bot -f docker-compose.bot.yml -f docker-compose.bot.local.yml up -d --build --no-deps bot` (اولین بار یا بعد از نصب پکیج جدید؛ برای فقط تغییر کد پایتون کافی‌ست restart ساده چون bind-mount است).

### سمت سایت (ایران) — `web/`
راهنمای کامل provisioning و دیپلوی از قبل در `web/docs/00-provisioning-checklist.md` و `web/docs/10-deploy-runbook.md` نوشته شده (دامنه، هاستینگ، Cloudflare، درگاه پرداخت، SMTP، بکاپ، مانیتورینگ).

---

## ۱۲. Git Checkpoint و Rollback

طبق درخواستت، قبل از شروع Shop v2 یک چک‌پوینت گیت گرفته شد — **هم روی کپی کاری من، هم روی خودِ ماشین واقعی `C:\easymakebot`**:

```
tag: pre-shop-v2   →  commit cc5be47   (نسخه‌ی قبل از Shop v2 — پایدار و تست‌شده)
                        │
                        ▼
   commit e0aea55   →  «Shop v2: custom invoice branding, product import
                         with price/stock, per-bot sales & inventory stats»
```

اگر بعد از تست، نسخه‌ی جدید مشکلی داشت، برگشت کامل به نسخه‌ی سالم قبلی:

```powershell
cd C:\easymakebot
git checkout pre-shop-v2 -- bot/
docker restart easymakebot-bot
```

(یا برای برگشت کامل‌تر و همیشگی: `git reset --hard pre-shop-v2` — این کار history بعدی را هم پاک می‌کند، فقط اگر مطمئنی دیگر به Shop v2 نیازی نیست.)

`.gitignore` طوری تنظیم شده که `venv/`, `webapp/node_modules/`, `webapp/dist/`, `.env`, `.env.bot`, `deploy/.env.bot`, `web/.env`, `*.log` هیچ‌وقت داخل ریپو کامیت نشوند.

---

## ۱۳. جدول مرجع سریع همه‌ی فایل‌های `bot/`

| فایل | یک‌خطی |
|---|---|
| `main.py` | نقطه‌ی ورود پروسه، ثبت روترها |
| `config.py` | تنظیمات `.env` |
| `session.py` | فکتوری session مشترک aiohttp |
| `runtime.py` | اجرای واقعی هر ربات ساخته‌شده |
| `flow_engine.py` | مفسّر Visual Flow Builder |
| `commerce_mode.py` | انتخاب یک‌باره‌ی Shop/Subscription |
| `shop.py` | فروشگاه، سفارش، فاکتور PDF |
| `shop_import.py` | ایمپورت اکسل محصولات (جدید) |
| `inventory.py` | آمار فروش/موجودی هر ربات (جدید) |
| `pricing.py` | محاسبه‌ی خالص تخفیف/افزایش قیمت |
| `premium_content.py` | گیت اشتراک/پیش‌نمایش رایگان |
| `content_import.py` | ایمپورت اکسل لیست محتوا (۱۰ زبان) |
| `content_nav.py` | عملیات درخت لیست محتوا |
| `list_render.py` | رندر مشترک لیست‌ها |
| `force_join_gate.py` | گیت عضویت اجباری |
| `guide.py` | راهنما + تشخیص زبان/منطقه |
| `help_text.py` | نکته‌های راهنمای فارسی/انگلیسی |
| `live.py` | چرخه‌ی Live/Trial/Suspension |
| `platform_billing.py` | پرداخت لایو‌شدن به پلتفرم |
| `website_client.py` | کلاینت REST سایت وردپرس |
| `admin_panel.py` | داده‌ی پنل ادمین پلتفرم |
| `webapp_auth.py` | اعتبارسنجی initData تلگرام |
| `webapp_server.py` | سرور HTTP برای Mini App + پرداخت |
| `states.py` | همه‌ی FSM States |
| `keyboards.py` | همه‌ی کیبوردها |
| `filters/admin.py` | فیلتر ادمین پلتفرم |
| `db/base.py` | اتصال دیتابیس + `init_db` (مهاجرت additive) |
| `db/models.py` | همه‌ی مدل‌های SQLAlchemy |
| `db/encrypted_types.py` | تایپ‌های رمزنگاری‌شده |
| `handlers/start.py` | `/start`, `/help` |
| `handlers/my_bots.py` | `/mybots`, انتخاب ربات |
| `handlers/create_bot.py` | `/newbot` |
| `handlers/cancel.py` | `/cancel` سراسری |
| `handlers/tools_menu.py` | منوی «Build & Edit Tools» |
| `handlers/live.py` | `/live` کامل |
| `handlers/easybotadmin.py` | `/easybotadmin` (پنل ادمین) |
| `handlers/admin_broadcast.py` | `/send_to_all` |
| `handlers/tools/define_command.py` | ابزار «Define Command» |
| `handlers/tools/force_join.py` | ابزار «Force Join» |
| `handlers/tools/message_to_all.py` | ابزار «Broadcast» |
| `handlers/tools/content_list.py` | ابزار «Content List» (بزرگ‌ترین) |
| `handlers/tools/shop.py` | ابزار «Shop» (شامل Shop v2) |
| `webapp/src/App.jsx` | بوم اصلی Visual Builder |
| `webapp/src/nodes.jsx` | تعریف ۷ نوع بلاک |
| `webapp/src/Palette.jsx` | نوار بلاک‌های قابل‌درگ |
| `webapp/src/FlowContext.js` | context اکشن‌های نود |
| `webapp/src/ContentManager.jsx` | مدیریت لیست محتوا از دل Mini App |
| `webapp/src/telegram.js` | پل Telegram SDK ↔ API بک‌اند |
