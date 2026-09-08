# مستند فنی ماژول‌های `live` و زیرساخت Mini App در easymakebot

پیش از شروع، یک نکتهٔ کلیدی که در چند فایل تکرار می‌شود: پروژه یک الگوی معماری ثابت دارد — فایل‌های داخل `bot/` (بدون پوشهٔ `handlers`) فقط **منطق و دسترسی به دیتابیس** هستند و هیچ کد مخصوص هندلر تلگرام ندارند؛ فایل‌های داخل `bot/handlers/` مصرف‌کنندهٔ آن‌ها هستند و کاربر واقعی تلگرام را می‌بینند. `bot/live.py` در برابر `bot/handlers/live.py` دقیقاً همین رابطه را دارد و در ادامه به‌صورت مجزا توضیح داده می‌شود.

---

## `bot/live.py`

این فایل «موتور» چرخهٔ عمر لایو‌شدن (`go live`) یک بات ساخته‌شده است: تست رایگان یک‌بارمصرف، پلن‌های پولی (`LIVE_PLANS`)، و سوییچ خاموشی دستی ادمین (`suspended`). هیچ کد هندلر تلگرامی این‌جا نیست — این ماژول توسط چهار هندلر مختلف بازاستفاده می‌شود: `bot/handlers/live.py` (خود دستور `/live`)، `bot/handlers/my_bots.py` (نمایش آیکون قفل و گیت پس از انقضا در «My Bots»)، `bot/handlers/tools_menu.py` (قفل‌کردن گرید ابزارها) و `bot/handlers/easybotadmin.py`. طبق docstring فایل، ثابت `LIVE_PLANS` عمداً همین‌جا تعریف شده نه در `bot/platform_billing.py` (که پردازش واقعی پرداخت را انجام می‌دهد)، چون `platform_billing.py` از `set_live_until` همین ماژول استفاده می‌کند و اگر `LIVE_PLANS` آن‌طرف تعریف می‌شد یک **import چرخه‌ای (circular import)** پیش می‌آمد.

### `TRIAL_HOURS = 72`
- **چه‌کار می‌کند:** طول مدت تست رایگان یک‌بارمصرف را به ساعت مشخص می‌کند (۷۲ ساعت).
- ارتباط: در `trial_until()` همین فایل و توسط `bot/handlers/live.py:start_trial` استفاده می‌شود.

### `LIVE_PLANS: list[dict]`
- **چه‌کار می‌کند:** لیست پلن‌های پولی پلتفرم را نگه می‌دارد؛ فعلاً فقط یک پلن placeholder («Monthly — 30 days»، ۴۹۰٬۰۰۰ تومان / ۱۰ دلار) وجود دارد تا کل مسیر پرداخت سرتاسری (end-to-end) — از `bot/platform_billing.py` تا `bot/handlers/live.py` — سیم‌کشی و تست‌پذیر باشد؛ جایگزین‌کردن پلن‌های واقعی بعداً فقط یک ویرایش داده‌ای (data-only) روی همین لیست خواهد بود.
- ارتباط: با `bot/keyboards.py:live_plans_keyboard` رندر می‌شود و در `bot/platform_billing.py:get_plan` جست‌وجو می‌شود.

### `is_bot_live(built_bot: BuiltBot) -> bool`
- **چه‌کار می‌کند:** `True` است اگر `live_until` مقدار داشته باشد و هنوز از الان (UTC) نگذشته باشد — یعنی بات فعلاً روی تلگرام آنلاین است.

### `is_bot_expired(built_bot: BuiltBot) -> bool`
- **چه‌کار می‌کند:** فقط برای باتی `True` است که **قبلاً حداقل یک‌بار** لایو بوده (چه با تست رایگان، چه با پلن) و پنجرهٔ زمانی‌اش گذشته باشد؛ هرگز برای باتی که هنوز اصلاً لایو نشده `True` نمی‌شود — چنین باتی در حال ساخته‌شدن است و باید کاملاً قابل ویرایش بماند.
- **موارد خاص:** تفاوتش با «هنوز لایو نشده» دقیقاً در همین چک `live_until is not None` است؛ اگر `live_until` اصلاً `None` باشد، تابع `False` برمی‌گرداند، نه اینکه اشتباهاً بات را «منقضی» حساب کند.

### `is_bot_suspended(built_bot: BuiltBot) -> bool`
- **چه‌کار می‌کند:** سوییچ خاموشی دستی ادمین پلتفرم (تنظیم‌شده در `bot/admin_panel.py`) را چک می‌کند؛ عمداً کاملاً مستقل از `live_until` است.
- **چرا اولویت دارد:** طبق docstring، هدف طراحی این است که «خرید یک پلن جدید هرگز نتواند به‌صورت خاموش (silently) یک suspension را لغو کند». به همین دلیل هر جای کد که یکی از این دو گیت را چک می‌کند، باید **این تابع را قبل از `is_bot_expired` چک کند** — یعنی اول ببیند ادمین آن را دستی خاموش نکرده، بعد به وضعیت انقضا/لایو بپردازد. این ترتیب در `bot/handlers/live.py:_send_live_status` هم رعایت شده (اول پیام suspension نشان داده می‌شود، بعد وضعیت پلن).

### `get_built_bot(bot_id: uuid.UUID | str) -> BuiltBot | None`
- **چه‌کار می‌کند:** یک `BuiltBot` را صرفاً با `id` پیدا می‌کند، **بدون هیچ چک مالکیتی**.
- **موارد خاص/edge case:** این تابع باید فقط وقتی صدا زده شود که `bot_id` از یک منبع از‌قبل‌تأییدشده بیاید — مثلاً از FSM state (`active_bot_id`) که فقط بعد از عبور موفق از یک چک مالکیت قبلی ست شده (توسط `bot/handlers/my_bots.py:select_bot` یا `bot/handlers/create_bot.py`)، یا از یک رکورد پرداخت/سفارش که از‌قبل به آن bot گره خورده. **هرگز** نباید مستقیماً روی مقداری که کاربر می‌تواند دستکاری کند (مثل `callback_data` یک دکمه) صدا زده شود.

### `get_owned_built_bot(bot_id: uuid.UUID | str, telegram_id: int) -> BuiltBot | None`
- **چه‌کار می‌کند:** همان جست‌وجوی `get_built_bot`، اما با یک `JOIN` روی جدول `User` و شرط `User.telegram_id == telegram_id` — یعنی فقط زمانی نتیجه برمی‌گرداند که همان `telegram_id` واقعاً مالک آن `BuiltBot` باشد.
- **مرز امنیتی:** این دقیقاً همان الگوی `JOIN` مالکیتی است که `bot/webapp_server.py:_authenticated_bot` برای API مربوط به Mini App استفاده می‌کند — یعنی این تابع «معادل تلگرامی» همان مرز امنیتی است.
- **موارد خاص:** طبق کامنت کد، باید در هر نقطهٔ ورودی که `bot_id` مستقیماً از چیزی که کاربر پایانی می‌تواند تأمین کند (مثلاً `callback_data` روی یک دکمه) می‌آید استفاده شود — یعنی دقیقاً نقطهٔ مقابل `get_built_bot`. تفاوت این دو تابع، مرز امنیتی «مالکیت» است: یکی فقط lookup ساده است (برای دادهٔ از‌قبل تأییدشده)، دیگری lookup + احراز مالکیت (برای دادهٔ نامعتبر/untrusted).

### `set_live_until(bot_id, until: datetime | None) -> BuiltBot | None`
- **چه‌کار می‌کند:** مقدار `live_until` بات را به‌روزرسانی کرده و commit می‌کند؛ اگر بات پیدا نشود `None` برمی‌گرداند.
- ارتباط: هستهٔ فعال‌سازی است — توسط `bot/handlers/live.py` (تست رایگان و فعال‌سازی با کد)، `bot/platform_billing.py:_activate_bot` و `bot/admin_panel.py:grant_bot_access` فراخوانی می‌شود.

### `trial_until() -> datetime`
- **چه‌کار می‌کند:** زمان الان (UTC) به‌علاوهٔ `TRIAL_HOURS` را برمی‌گرداند؛ به‌عنوان مقدار `live_until` تست رایگان استفاده می‌شود.

### `suspension_status_text(built_bot: BuiltBot) -> str`
- **چه‌کار می‌کند:** متن هشدار suspension را با دلیل (`suspension_reason`، یا «no reason given» اگر خالی باشد) می‌سازد؛ صراحتاً می‌گوید که هیچ پلن پرداختی نمی‌تواند suspension را لغو کند.

### `status_text(built_bot: BuiltBot) -> str`
- **چه‌کار می‌کند:** بر اساس ترتیب `is_bot_live` → `is_bot_expired` → حالت پیش‌فرض (هنوز هرگز لایو نشده)، متن وضعیت مناسب برای نمایش به کاربر را برمی‌گرداند (تاریخ انقضا، پیام قفل‌شدن ابزارها، یا دعوت به تست رایگان).
- ارتباط: مستقیماً در `bot/handlers/live.py:_send_live_status` استفاده می‌شود تا بدنهٔ پیام `/live` ساخته شود.

---

## `bot/platform_billing.py`

این فایل، برخلاف `bot/shop.py` (که فروشگاه شخصی هر مالک بات به مشتری‌های خودش است)، مربوط به «پرداخت مالک بات **به خود پلتفرم**» برای فعال‌سازی/تمدید `/live` است. نکتهٔ طراحی مهم: توابع سطح‌پایین ارتباط با درگاه‌ها (`_zarinpal_request`، `_zarinpal_verify`، `_stripe_create_session`، `_stripe_retrieve_session`) عیناً از `bot/shop.py` وارد (import) و بازاستفاده می‌شوند — چون آن‌ها تنها جایی هستند که واقعاً با API هر درگاه صحبت می‌کنند — اما رکوردهای پرداخت کاملاً جدا نگه داشته می‌شوند (`LivePayment` به‌جای `Order`/`Checkout`) تا این دو جریان پولی (درآمد پلتفرم در برابر درآمد مالک بات) هرگز با هم قاطی نشوند. مانند `bot/live.py`، این فایل هم هیچ کد هندلر تلگرامی ندارد و توسط `bot/handlers/live.py` و `bot/webapp_server.py` مصرف می‌شود.

### `__all__ = ["LIVE_PLANS"]`
- توضیح خودِ کد: `LIVE_PLANS` این‌جا صرفاً re-export شده (از `bot.live` وارد شده) تا کدهایی که این فایل را import می‌کنند مجبور نباشند مستقیم به `bot.live` هم مراجعه کنند؛ دلیل واقعی جای اصلی تعریفش در docstring خود `bot/live.py` توضیح داده شده (اجتناب از circular import).

### `get_plan(plan_key: str) -> dict | None`
- **چه‌کار می‌کند:** در `LIVE_PLANS` بر اساس `key` جست‌وجو می‌کند و اولین match را برمی‌گرداند.

### `available_methods_for_region(region: str | None) -> list[str]`
- **چه‌کار می‌کند:** بر اساس ریجن مالک بات و این‌که کدام credential های پلتفرم در `.env` تنظیم شده، لیست روش‌های پرداخت قابل‌ارائه را برمی‌گرداند. الگوی «حذف مهربانانه» (graceful-omit) — همان الگویی که `ShopSettings` هر بات هم دارد: اگر یک credential ست نشده، آن روش پرداخت اصلاً نمایش داده نمی‌شود، نه این‌که خطا بدهد.
- **منطق تشخیص منطقه:**
  - **`region == "international"`:** اگر `platform_ton_wallet_address` تنظیم شده باشد `"ton"` اضافه می‌شود؛ اگر `platform_stripe_secret_key` تنظیم شده باشد `"stripe"` هم اضافه می‌شود.
  - **`region == "iran"`:** حالت پیش‌فرض این است که هیچ روش داخل‌تلگرامی نمایش داده **نشود** (`return []`). فقط اگر هر دو شرط `_config.platform_onbot_zarinpal` (پرچم صریح در `.env`) **و** `_config.platform_zarinpal_merchant_id` برقرار باشند، `["zarinpal"]` برگردانده می‌شود.
  - **چرا Zarinpal داخل تلگرام برای ایران به‌طور پیش‌فرض خاموش است:** طبق کامنت داخل کد، یک کاربر ایرانی معمولاً هیچ روش پرداخت روی خود بات نمی‌بیند و باید در **وب‌سایت** (که روی سرور ایرانی است) بخرد و کد را redeem کند؛ چون اگر یک پرداخت Zarinpal از سرور بات که خارج از ایران است (مثلاً آلمان — طبق کامنت `bot/website_client.py`) شروع شود، ترکیب آن با VPN خریدار روی تلگرام باعث خرابی درگاه می‌شود. پرچم `PLATFORM_ONBOT_ZARINPAL=true` باید فقط زمانی روشن شود که خودِ بات روی یک IP ایرانی اجرا شود.
  - **`region` نامشخص:** اگر مقدار هیچ‌کدام از دو رشتهٔ بالا نباشد (یعنی هنوز پرسیده نشده)، لیست خالی برمی‌گردد و کامنت صریحاً می‌گوید caller باید اول از کاربر بپرسد.

### `resolve_region(user: User) -> str | None`
- **چه‌کار می‌کند:** اگر `user.region` از قبل ست شده، همان را برمی‌گرداند. در غیر این صورت، اگر `user.phone_number` موجود باشد، با `bot.guide.is_iran_phone` (همان تشخیصی که در بلوک «Guide & Video» هم استفاده می‌شود) ریجن را استنتاج می‌کند، آن را با `set_region` ذخیره (persist) می‌کند، و برمی‌گرداند. اگر نه ریجن ذخیره‌شده و نه شماره تلفنی موجود باشد، `None` برمی‌گرداند تا caller (در `bot/handlers/live.py`) صریحاً از کاربر بپرسد.

### `set_region(user_id: int, region: str) -> None`
- **چه‌کار می‌کند:** فیلد `region` روی رکورد `User` را می‌نویسد و commit می‌کند.

### `create_live_payment(bot_id, plan_key: str, payment_method: str) -> LivePayment | None`
- **چه‌کار می‌کند:** پلن را با `get_plan` پیدا می‌کند (اگر نبود `None`)، ارز را بر اساس روش پرداخت تعیین می‌کند (`"toman"` فقط برای `"zarinpal"`، در غیر این صورت `"usd"`) و قیمت متناظر (`price_toman` یا `price_usd`) را انتخاب می‌کند، سپس یک ردیف `LivePayment` با وضعیت پیش‌فرض (`pending`، طبق مدل) می‌سازد و برمی‌گرداند.

### `get_live_payment(payment_id: int) -> LivePayment | None`
- **چه‌کار می‌کند:** یک `LivePayment` را فقط با `id` واکشی می‌کند.

### `_activate_bot(payment: LivePayment) -> None`
- **چه‌کار می‌کند:** گام مشترک «فعال‌سازی» پس از هر پرداخت موفق (Zarinpal، Stripe، TON) — `until` را بر اساس `payment.days` محاسبه می‌کند (اگر `days` مقدار نداشته باشد از `3650` روز — یعنی «همیشگی» — استفاده می‌کند)، سپس با `set_live_until` (وارداتی از `bot/live.py`) آن را ست می‌کند، و اگر بات `suspended` نباشد با `start_built_bot` (از `bot/runtime.py`) واقعاً پولینگ تلگرامش را روشن می‌کند.
- ارتباط: کامنت کد صریحاً می‌گوید این همان ماشین‌آلاتی است که `bot/admin_panel.py:grant_bot_access` هم استفاده می‌کند (`set_live_until` + `start_built_bot`).
- **موارد خاص:** اگر بات suspend شده باشد، `live_until` همچنان ست می‌شود ولی `start_built_bot` صدا زده **نمی‌شود** — یعنی روی تلگرام آنلاین نمی‌شود تا وقتی ادمین suspension را بردارد (سازگار با اولویت `is_bot_suspended` در `bot/live.py`).

### `_notify_owner(bot_id, text: str) -> None`
- **چه‌کار می‌کند:** مالک بات مربوط به `bot_id` را پیدا می‌کند و با یک `Bot` موقت (ساخته‌شده با توکن **پلتفرم** یعنی `_config.bot_token`، نه توکن بات ساخته‌شده) پیام تلگرامی برایش می‌فرستد. هر خطایی در ارسال (مثلاً کاربر بات پلتفرم را بلاک کرده) بی‌صدا (silent) نادیده گرفته می‌شود، و در نهایت session موقت بسته می‌شود.

### بخش Zarinpal — مسیر مخصوص ایران

#### `start_zarinpal_live_payment(payment, callback_base_url) -> str | None`
- **چه‌کار می‌کند:** اگر merchant id تنظیم نشده `None` برمی‌گرداند. در غیر این صورت با `_zarinpal_request` (از `bot/shop.py`) یک authority می‌گیرد — قیمت را ضربدر ۱۰ می‌کند چون قیمت داخلی به تومان است ولی درگاه Rial می‌خواهد (`payment.price * 10`). آدرس بازگشت (callback) به‌شکل `{callback_base_url}/payment/live/zarinpal/callback?payment_id={payment.id}` ساخته می‌شود. سپس `authority` را روی همان رکورد `LivePayment` ذخیره می‌کند و URL شروع پرداخت (`ZARINPAL_STARTPAY_URL`) را برمی‌گرداند.

#### `verify_zarinpal_live_payment(authority: str) -> LivePayment | None`
- **چه‌کار می‌کند:** پرداخت را با `zarinpal_authority` پیدا می‌کند؛ اگر پیدا نشد `None`. اگر وضعیتش از قبل `pending` نبود (یعنی قبلاً verify شده)، همان را بدون verify مجدد برمی‌گرداند (idempotent — از verify دوباره جلوگیری می‌کند). اگر merchant id تنظیم نشده باشد هم بدون تغییر برمی‌گرداند. در غیر این صورت با `_zarinpal_verify` نتیجه را از درگاه می‌گیرد؛ اگر `None` بود (خطا) بدون تغییر برمی‌گرداند. در صورت موفقیت، وضعیت را `"paid"` می‌کند، `zarinpal_ref_id` را ذخیره می‌کند، سپس `_activate_bot` و `_notify_owner` را صدا می‌زند.
- ارتباط: از `bot/webapp_server.py:live_zarinpal_callback` صدا زده می‌شود.

### بخش Stripe — مسیر بین‌المللی (کارت Visa/Mastercard، هر دو مستقیماً توسط Stripe Checkout پشتیبانی می‌شوند، بدون نیاز به یکپارچه‌سازی جدا برای هر شبکه)

#### `start_stripe_live_payment(payment, callback_base_url) -> str | None`
- **چه‌کار می‌کند:** اگر `platform_stripe_secret_key` تنظیم نشده `None`. در غیر این صورت `success_url` و `cancel_url` را می‌سازد (که هردو به همان مسیر `/payment/live/stripe/callback` می‌روند، یکی با `{CHECKOUT_SESSION_ID}` که Stripe خودش جایگزین می‌کند، دیگری با `?cancelled=1&payment_id=`) و با `_stripe_create_session` یک session می‌سازد (قیمت دلاری ضربدر ۱۰۰ چون Stripe سنت می‌خواهد). `stripe_session_id` را ذخیره و `checkout_url` را برمی‌گرداند.

#### `verify_stripe_live_payment(session_id: str) -> LivePayment | None`
- **چه‌کار می‌کند:** مشابه نسخهٔ Zarinpal، ولی با `stripe_session_id` پیدا می‌کند و با `_stripe_retrieve_session` وضعیت را می‌خواند؛ فقط اگر `payment_status == "paid"` باشد وضعیت را `"paid"` می‌کند و `_activate_bot` + `_notify_owner` را صدا می‌زند.

### بخش TON — تأیید دستی (همان منطق مسیر crypto/TON در `bot/shop.py`: هیچ تأیید خودکار روی زنجیره‌ای وجود ندارد، چون یک چک خودکار اشتباه در هر دو جهت (تأیید غلط یا رد غلط) پول واقعی را به خطر می‌اندازد؛ تأیید به `PLATFORM_ADMIN_ID` می‌رود، نه به مالک بات)

#### `submit_ton_live_payment(payment_id, tx_hash: str) -> LivePayment`
- **چه‌کار می‌کند:** فقط `transaction_ref` (هش تراکنش که کاربر ادعا می‌کند فرستاده) را روی رکورد ثبت می‌کند و ذخیره‌شده را برمی‌گرداند — هیچ تغییری در `status` نمی‌دهد. جریان کامل تأیید دستی از `bot/handlers/live.py:receive_ton_tx_hash` شروع می‌شود که پس از این فراخوانی، پیامی با دکمه‌های تأیید/رد به `PLATFORM_ADMIN_ID` می‌فرستد.

#### `approve_ton_live_payment(payment_id) -> LivePayment | None`
- **چه‌کار می‌کند:** اگر رکورد پیدا نشود `None`. وضعیت را `"paid"` می‌کند، سپس `_activate_bot` و `_notify_owner` (با پیام تأیید) را صدا می‌زند.
- ارتباط: فقط از هندلر `bot/handlers/live.py:approve_ton_payment` صدا زده می‌شود که خودش پشت فیلتر `IsPlatformAdmin` است.

#### `reject_ton_live_payment(payment_id) -> None`
- **چه‌کار می‌کند:** وضعیت را `"rejected"` می‌کند و مالک را با پیام رد شدن پرداخت مطلع می‌سازد؛ هیچ فعال‌سازی‌ای رخ نمی‌دهد.

---

## `bot/website_client.py`

این فایل یک کلاینت سبک (thin client) برای API «کد فعال‌سازی پلن» وب‌سایت بازاریابی easymakebot است (سمت سرور آن در `web/wordpress/wp-content/mu-plugins/emb-activation-codes.php`). کاربر پلن را روی وب‌سایت می‌خرد، یک کد یک‌بارمصرف به‌شکل `EMB-XXXX-XXXX` می‌گیرد، و آن را در `/live` (توسط `bot/handlers/live.py`) redeem می‌کند تا `live_until` بات انتخاب‌شده‌اش تنظیم شود. این فایل هم هیچ کد هندلر تلگرامی ندارد.

### `is_configured() -> bool`
- **چه‌کار می‌کند:** `True` است اگر هر دو `_config.website_url` و `_config.website_activation_key` مقدار داشته باشند — یعنی این قابلیت اصلاً روی این نصب فعال است یا نه.

### `_post(path: str, payload: dict) -> dict`
- **چه‌کار می‌کند:** تابع داخلی مشترکی که واقعاً HTTP request می‌زند.
- **هدر امنیتی:** هر request با هدر `X-EMB-Key: {_config.website_activation_key}` امضا می‌شود؛ این کلید مشترک (shared secret) بین بات و وب‌سایت است.
- **مدیریت خطاها و retry با backoff نمایی:**
  - اگر `is_configured()` نباشد، بلافاصله `{"ok": False, "error": "not_configured"}` برمی‌گرداند، بدون هیچ تلاش شبکه‌ای.
  - حداکثر `_RETRIES = 3` بار تلاش می‌کند، با `_RETRY_BACKOFF = 2.0` ثانیه (یعنی تأخیرهای ۲، ۴ ثانیه بین تلاش‌ها — طبق کامنت کد نظیر «2, 4, 8» اما چون تأخیر فقط **بین** تلاش‌ها اعمال می‌شود و تلاش سوم آخرین تلاش است، در عمل بعد از تلاش اول ۲ ثانیه و بعد از تلاش دوم ۴ ثانیه صبر می‌کند).
  - **HTTP 403:** بلافاصله و بدون retry برمی‌گردد (`{"ok": False, "error": "http_403"}`) چون طبق کامنت «کلید اشتباه است و retry کمکی نمی‌کند».
  - **HTTP در `(429, 502, 503, 504)`:** این‌ها موقتی تلقی می‌شوند؛ `last_error` را ست می‌کند و به تلاش بعدی می‌رود (retry).
  - **پاسخ JSON معتبر (dict):** مستقیماً همان دیکشنری را برمی‌گرداند (این می‌تواند شامل خودِ خطاهای کسب‌وکاری مثل `already_used` هم باشد که سرور با HTTP 200 برمی‌گرداند).
  - **پاسخ غیر-dict:** `last_error = "bad_response"` و retry.
  - **هر استثنای سطح انتقال (connection error، timeout و…):** با `except Exception` گرفته می‌شود و `last_error = "network"` می‌شود (کامنت: «هر خطای transport برای caller به‌عنوان "network" شمرده می‌شود»)، سپس retry.
  - اگر همهٔ تلاش‌ها شکست بخورند، یک `logger.warning` ثبت می‌شود و `{"ok": False, "error": last_error}` برگردانده می‌شود.
- **چرا retry لازم است:** طبق کامنت، بات (در آلمان) و وب‌سایت (در ایران) روی هاست‌های مختلف‌اند و این call از مرز (border) با Cloudflare عبور می‌کند، پس یک شکست گذرا طبیعی است.

### `redeem_activation_code(code, bot_id, telegram_id, *, username=None, first_name=None, phone=None) -> dict`
- **چه‌کار می‌کند:** `POST /wp-json/emb/v1/redeem` می‌زند. بدنهٔ (payload) درخواست را می‌سازد: `code`، `bot_id` (به رشته تبدیل‌شده)، `telegram_id` (به عدد صحیح تبدیل‌شده)، و به‌صورت اختیاری `telegram_username`، `telegram_first_name`، و `phone` — فقط اگر مقدار داشته باشند (else کلید اصلاً در payload نیست).
- **چرا هویت تلگرام و شماره تلفن فرستاده می‌شود:** طبق docstring، هدف این است که وب‌سایت بتواند بات پرداخت‌شده را به یک شخص واقعی (real person) گره بزند، برای پاسخگویی در برابر سوءاستفاده/تقلب (abuse/fraud accountability). شماره‌ای که فرستاده می‌شود «Telegram-verified» است — یعنی همان شماره‌ای که کاربر با دکمهٔ اشتراک‌گذاری تماس تلگرام تأیید کرده، نه صرفاً تایپ‌شده بدون تأیید (این تفکیک را `bot/handlers/live.py` مدیریت می‌کند، پیش از فراخوانی این تابع).
- **قالب پاسخ موفق:** `{"ok": True, "days": 90, "months": 3, "code": "EMB-…"}`.
- **قالب پاسخ خطا:** `{"ok": False, "error": ...}` با مقادیر ممکن: `already_used` (کد قبلاً مصرف شده)، `not_found` (کدی با این مقدار وجود ندارد)، `malformed_code` (فرمت کد نامعتبر است)، `void` (کد باطل شده — مثلاً سفارش رفاند یا ناموفق بوده)، `not_configured` (کلید/URL وب‌سایت تنظیم نشده)، `network` (خطای شبکه پس از همهٔ retry ها)، `http_403` (کلید امنیتی نادرست)، `bad_response` (پاسخ غیرمنتظره از سرور).
- ارتباط: این نگاشت خطا به متن انسانی در `bot/handlers/live.py:_REDEEM_ERRORS` انجام می‌شود.

---

## `bot/admin_panel.py`

این فایل کوئری‌ها و mutation های سطح کل پلتفرم را برای پنل `/easybotadmin` (`bot/handlers/easybotadmin.py`) فراهم می‌کند — یعنی دید مالک پلتفرم (`PLATFORM_ADMIN_ID`) روی همهٔ کاربران و همهٔ بات‌های ساخته‌شده، برای پشتیبانی، جلوگیری از تقلب، و گزارش‌گیری.

**نکتهٔ حیاتی که باید تأکید شود:** این فایل به‌طور کامل و صریح (طبق docstring خودش) **هیچ کنترل‌دسترسی‌ای (authorization) انجام نمی‌دهد.** تک‌تک توابع این‌جا فقط از طریق هندلرهایی که پشت `bot/filters/admin.py:IsPlatformAdmin` گیت شده‌اند قابل‌دسترسی هستند؛ این ماژول به این فیلتر اعتماد کامل می‌کند و خودش هیچ چک هویتی روی caller ندارد. یعنی اگر کسی این توابع را مستقیم و بدون عبور از فیلتر ادمین صدا بزند، هیچ سد امنیتی داخل خودِ این فایل وجود ندارد — مسئولیت کامل کنترل دسترسی روی دوش هندلرهاست، دقیقاً همان الگوی جداسازی که در `bot/shop.py` / `bot/live.py` / `bot/content_nav.py` هم دیده می‌شود.

### `PAID_STATUSES = ("paid", "fulfilled")`
- ثابتی که مشخص می‌کند کدام وضعیت‌های `Order` واقعاً یعنی «پول جابه‌جا شده است»؛ در محاسبهٔ درآمد استفاده می‌شود.

### `get_platform_stats() -> dict`
- **چه‌کار می‌کند:** آماری کلی از کل پلتفرم جمع می‌کند: تعداد کاربران، تعداد بات‌ها، و با یک پاس روی همهٔ ردیف‌های `(live_until, suspended)` تعداد بات‌های live/expired/never_activated/suspended را می‌شمارد (هرکدام با شرط `not sus and ...` به‌جز شمارش خودِ suspended). سپس تعداد subscriber ها، تعداد محصولات، تعداد کل سفارش‌ها، و تعداد+جمع مبلغ سفارش‌های با وضعیت در `PAID_STATUSES` را هم می‌خواند و همه را در یک دیکشنری برمی‌گرداند.

### `list_users_page(offset=0, limit=20) -> tuple[list[User], bool]`
- **چه‌کار می‌کند:** صفحه‌بندی (pagination) ساده روی جدول `User`، مرتب بر اساس `created_at`. با گرفتن `limit + 1` ردیف و برش (slice) به `limit`، مقدار bool دوم مشخص می‌کند آیا صفحهٔ بعدی وجود دارد یا نه (بدون یک کوئری COUNT جدا).

### `get_user_detail(user_id) -> dict | None`
- **چه‌کار می‌کند:** یک `User` را با بات‌های متعلق به او (`owner_id == user_id`) برمی‌گرداند؛ اگر کاربر پیدا نشود `None`.

### `list_bots_page(offset=0, limit=20) -> tuple[list[BuiltBot], bool]`
- **چه‌کار می‌کند:** همان الگوی صفحه‌بندی `list_users_page` اما روی `BuiltBot`.

### `get_bot_detail(bot_id) -> dict | None`
- **چه‌کار می‌کند:** `BuiltBot` را با `JOIN` روی `User` (برای گرفتن مالک) واکشی می‌کند، همراه با تعداد subscriber ها و تعداد+جمع درآمد سفارش‌های پرداخت‌شدهٔ همان بات.

### `suspend_bot(bot_id, reason: str) -> BuiltBot | None`
- **چه‌کار می‌کند:** `built_bot.suspended = True` و `suspension_reason = reason` را ست و commit می‌کند، سپس `stop_built_bot(built_bot.id)` (از `bot/runtime.py`) را صدا می‌زند تا بات واقعاً از تلگرام آفلاین شود.

### `unsuspend_bot(bot_id) -> BuiltBot | None`
- **چه‌کار می‌کند:** پرچم suspension را برمی‌دارد (`suspended = False`، `suspension_reason = None`)، و اگر `live_until` هنوز در آینده باشد (یعنی پلن هنوز منقضی نشده)، دوباره با `start_built_bot` بات را روی تلگرام روشن می‌کند. اگر `live_until` گذشته یا `None` باشد، بات روشن نمی‌شود — رفع suspension به‌تنهایی یک بات منقضی‌شده را دوباره لایو نمی‌کند.

### `grant_bot_access(bot_id, days: int | None) -> BuiltBot | None`
- **چه‌کار می‌کند:** دسترسی رایگان به `/live` را از طرف ادمین به یک بات اعطا می‌کند — بدون این‌که هیچ رکورد پرداختی ساخته شود.
- **پارامتر `days`:** اگر عدد باشد، `live_until = now + timedelta(days=days)`. اگر `days=None` باشد، به‌جای آن `timedelta(days=3650)` (یعنی تقریباً ۱۰ سال) استفاده می‌شود که کامنت کد آن را «دسترسی همیشگی (permanent)» می‌نامد — همان رویکرد grandfathering ای که طبق کامنت قبلاً برای بات‌های از‌قبل‌موجود هم استفاده شده بود.
- **رفتار پس از ست‌کردن:** فقط اگر بات `suspended` نباشد، `start_built_bot` صدا زده می‌شود — یعنی حتی اعطای دسترسی توسط خودِ ادمین هم suspension را دور نمی‌زند (سازگار با اولویت `is_bot_suspended` که در `bot/live.py` تعریف شده).
- ارتباط: از نظر مکانیزم فعال‌سازی دقیقاً معادل `bot/platform_billing.py:_activate_bot` عمل می‌کند (همان دو مرحله: `set_live_until` سپس `start_built_bot`)، با این تفاوت که این‌جا هیچ `LivePayment` ای ساخته نمی‌شود چون پرداختی رخ نداده.

### `rename_bot(bot_id, new_display_name: str) -> BuiltBot | None`
- **چه‌کار می‌کند:** فقط `display_name` بات را عوض می‌کند و رکورد به‌روزشده را برمی‌گرداند.

### `delete_bot(bot_id) -> bool`
- **چه‌کار می‌کند:** حذف کامل (hard delete) یک بات ساخته‌شده.
- **مراحل دقیق:**
  1. ابتدا `stop_built_bot(bot_id)` صدا زده می‌شود تا polling تلگرامی آن بات فوراً متوقف شود (این تابع طبق کامنت، هم UUID و هم شکل رشته‌ای آن را می‌پذیرد).
  2. سپس رکورد `BuiltBot` با `session.delete()` حذف و commit می‌شود.
- **Cascade:** طبق کامنت کد و ارجاع به `bot/db/models.py`، رابطه‌های `BuiltBot` (شامل `commands`، `content_items`، `products`، `orders`، `shop_settings`، `join_channels`) همه با `cascade="all, delete-orphan"` تعریف شده‌اند — یعنی حذف یک `BuiltBot` به‌صورت خودکار همهٔ دادهٔ وابسته به آن را هم حذف می‌کند؛ این یک عملیات غیرقابل‌بازگشت است.
- **موارد خاص:** کامنت صریحاً هشدار می‌دهد که caller (هندلر) باید پیش از این تابع یک تأیید سخت (hard confirmation) از ادمین بگیرد، چون خودِ این تابع هیچ تأییدی نمی‌گیرد و این دقیقاً همان چیزی است که در «هیچ کنترل‌دسترسی‌ای در این ماژول نیست» گفته شد — هم مسئولیت authorization و هم مسئولیت confirmation کاملاً روی هندلر است.
- برمی‌گرداند: `True` اگر حذف انجام شد، `False` اگر بات از ابتدا پیدا نشد.

### `list_recent_activity(limit=10) -> dict`
- **چه‌کار می‌کند:** جدیدترین `limit` بات، جدیدترین `limit` سفارش (به‌همراه `bot_username` هر بات با یک `JOIN`)، و جدیدترین `limit` کاربر را (هرکدام بر اساس `created_at` نزولی) برمی‌گرداند — برای داشبورد فعالیت اخیر پنل ادمین.

### `generate_report_excel() -> bytes`
- **چه‌کار می‌کند:** با کتابخانهٔ `openpyxl` یک فایل اکسل سه‌شیتی می‌سازد و آن را به‌صورت `bytes` برمی‌گرداند (احتمالاً برای ارسال به ادمین به‌عنوان یک فایل تلگرامی از هندلر مصرف‌کننده).
  - **شیت «Users»:** برای هر کاربر — `User ID`، `Telegram ID`، `Joined At`، و تعداد بات‌های آن کاربر (با یک کوئری COUNT جدا به‌ازای هر کاربر).
  - **شیت «Bots»:** برای هر بات — نام کاربری بات، نام نمایشی، `telegram_id` مالک (با `JOIN` روی `User`)، وضعیت محاسبه‌شده (`suspended`/`never activated`/`live`/`expired` — با همان منطق اولویت suspended-first)، تعداد subscriber، و تاریخ ساخت.
  - **شیت «Orders»:** برای هر سفارش — `Order ID`، نام کاربری بات، نام محصول (با `JOIN` روی `BuiltBot` و `Product`)، قیمت به تومان، وضعیت، روش پرداخت (یا `"-"` اگر خالی)، و تاریخ ساخت.

---

## `bot/webapp_auth.py`

این فایل تنها یک وظیفه دارد: اعتبارسنجی رشتهٔ `initData` که Telegram Mini App (وب‌اپ فلوبیلدر بصری) هنگام باز شدن به بک‌اند می‌فرستد، دقیقاً طبق الگوریتم مستندشدهٔ خود تلگرام (لینک در docstring: `core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app`).

### `MAX_AGE_SECONDS = 24 * 60 * 60`
- **چه‌کار می‌کند:** حداکثر «سن» قابل‌قبول یک `initData` — یک روز.
- **چرا:** طبق کامنت، مستندات تلگرام توصیه می‌کند `auth_date` چک شود تا مدت‌زمانی که یک `initData` ربوده‌شده (captured) قابل replay است محدود بماند؛ برای یک نشست ساخت بات (builder session)، هیچ‌وقت واقعاً به یک امضای یک‌روزه‌تر نیاز نیست.

### `validate_init_data(init_data: str, bot_token: str, *, max_age_seconds: int = MAX_AGE_SECONDS) -> dict | None`
- **چه‌کار می‌کند:** اگر امضای HMAC معتبر باشد (و در صورت `max_age_seconds > 0`، `auth_date` هم به‌اندازهٔ کافی تازه باشد)، دیکشنری `user` استخراج‌شده از `initData` را برمی‌گرداند؛ در غیر این صورت `None`.
- **الگوریتم قدم‌به‌قدم:**
  1. **پارس کردن:** `parse_qsl(init_data, strict_parsing=True)` رشتهٔ query-string مانند `initData` را به لیست جفت‌های کلید-مقدار تبدیل می‌کند؛ `strict_parsing=True` یعنی اگر فرمت بدشکل باشد `ValueError` می‌دهد که به `None` تبدیل می‌شود.
  2. جفت‌ها به `dict` تبدیل می‌شوند و کلید `hash` از آن جدا (`pop`) می‌شود — این همان مقداری است که باید در انتها با آن مقایسه شود. اگر اصلاً `hash` وجود نداشته باشد، بلافاصله `None`.
  3. **ساخت `data_check_string`:** بقیهٔ کلیدها بر اساس نام کلید (`sorted(data.items())`) مرتب می‌شوند و به‌شکل `key=value` با کاراکتر `\n` به هم متصل می‌شوند — این دقیقاً همان قالبی است که الگوریتم تلگرام برای تولید امضا مشخص کرده.
  4. **ساخت `secret_key`:** طبق مشخصات تلگرام، کلید مخفی HMAC-SHA256، خروجی `HMAC(key=b"WebAppData", message=bot_token)` است — یعنی رشتهٔ ثابت `"WebAppData"` به‌عنوان کلید و توکن خودِ بات به‌عنوان پیام استفاده می‌شود؛ نتیجه یک `secret_key` باینری است.
  5. **محاسبهٔ `computed_hash`:** با همان `secret_key` به‌دست‌آمده، یک HMAC-SHA256 دیگر روی `data_check_string` محاسبه می‌شود و به‌صورت hex خوانده می‌شود.
  6. **مقایسهٔ امن:** `computed_hash` با `received_hash` (همان `hash` استخراج‌شده از `initData`) با `hmac.compare_digest(...)` مقایسه می‌شود — نه با اپراتور `==` معمولی. دلیل: `compare_digest` در زمان ثابت (constant-time) مقایسه می‌کند تا جلوی حملهٔ timing attack (که در آن مهاجم با اندازه‌گیری زمان پاسخ می‌تواند بایت‌به‌بایت هش صحیح را حدس بزند) گرفته شود؛ اگر برابر نبودند، `None` برگردانده می‌شود.
  7. **چک تازگی `auth_date`:** فقط اگر `max_age_seconds > 0` باشد اجرا می‌شود. مقدار `auth_date` (timestamp یونیکس، به‌شکل رشته در `data`) به `int` تبدیل می‌شود؛ اگر تبدیل شکست بخورد (`TypeError`/`ValueError`) نتیجه `None` است. سپس اگر `auth_date <= 0` (یعنی اصلاً وجود نداشت و پیش‌فرض `"0"` گرفته شد) یا `time.time() - auth_date > max_age_seconds` (یعنی خیلی قدیمی است)، نتیجه `None` است.
  8. **استخراج کاربر:** مقدار کلید `user` (که خودش یک رشتهٔ JSON است) از `data` خوانده می‌شود؛ اگر خالی/وجود نداشت `None`. سپس با `json.loads` پارس می‌شود و در صورت شکست پارس (`TypeError`/`ValueError`) هم `None` برگردانده می‌شود؛ در غیر این صورت دیکشنری کاربر (شامل حداقل `id`) برگردانده می‌شود.
- **موارد خاص/edge case:** پارامتر `max_age_seconds` می‌تواند صفر یا منفی داده شود تا کلاً چک تازگی رد شود (برای موارد خاص تست/دیباگ)؛ در استفادهٔ واقعی همیشه مقدار پیش‌فرض `MAX_AGE_SECONDS` استفاده می‌شود.
- ارتباط: تنها مصرف‌کنندهٔ این تابع در پروژه `bot/webapp_server.py:_authenticated_bot` است.

---

## `bot/webapp_server.py`

این فایل یک سرور `aiohttp` است که دو چیز را سرو می‌کند: (۱) فرانت‌اند از‌قبل‌بیلدشدهٔ Mini App فلوبیلدر بصری (از `webapp/dist/`) و (۲) یک API کوچک JSON برای خواندن/ذخیرهٔ `flow_definition` یک بات، که با `initData` تلگرام (از طریق `bot/webapp_auth.py`) احراز هویت می‌شود. این همان سروری است که کالبک‌های بازگشتی درگاه‌های پرداخت (هم فروشگاه هر بات، هم پلن‌های پلتفرم) را هم میزبانی می‌کند.

### `STATIC_DIR`
- مسیر پوشهٔ استاتیک: `webapp/dist/` (نسبت به ریشهٔ پروژه) — همان‌جایی که خروجی build فرانت‌اند قرار می‌گیرد.

### `_authenticated_bot(request: web.Request, bot_token: str) -> BuiltBot | None`
- **چه‌کار می‌کند:** مرز امنیتی اصلی هر API این سرور.
- **مراحل:**
  1. هدر `X-Telegram-Init-Data` را از request می‌خواند؛ اگر نبود `None`.
  2. با `validate_init_data(init_data, bot_token)` امضا و تازگی آن را چک می‌کند؛ اگر نامعتبر `None`.
  3. پارامتر query یعنی `bot_id` را می‌خواند؛ اگر نبود `None`.
  4. با یک کوئری `SELECT BuiltBot JOIN User WHERE BuiltBot.id == bot_id AND User.telegram_id == user["id"]` چک می‌کند که همان کاربر تلگرامی احرازشده واقعاً مالک آن `bot_id` است — عیناً همان الگوی مالکیتی که `bot/live.py:get_owned_built_bot` هم استفاده می‌کند.
- **پارامترها:** `bot_token` توکن **همان بات ساخته‌شده‌ای** است که این نمونهٔ سرور برایش راه‌اندازی شده (نه توکن پلتفرم) — چون `secret_key` در `validate_init_data` از روی همین توکن ساخته می‌شود، و تلگرام `initData` را برای هر بات با توکن همان بات امضا می‌کند.
- هر یک از هندلرهای API زیر (`get_flow`, `save_flow`, `list_content`, `create_content`, `update_content`, `delete_content`) اولین کارشان صدا زدن همین تابع است؛ اگر `None` برگردد بلافاصله `401 {"error": "unauthorized"}` برمی‌گردانند.

### `_payment_page(heading, detail) -> web.Response`
- **چه‌کار می‌کند:** یک صفحهٔ HTML مینیمال (بدون فریم‌ورک) برای نمایش نتیجهٔ پرداخت (موفق/ناموفق/لغوشده) به مرورگر کاربر می‌سازد، تا او بعد از پرداخت بداند چه اتفاقی افتاده و برگردد به تلگرام.

### `create_app(bot_token: str) -> web.Application`
یک اپلیکیشن `aiohttp` می‌سازد و route های زیر را روی آن ثبت می‌کند. مسیرها به‌ترتیب ثبت در کد:

| متد | مسیر | توضیح |
|---|---|---|
| `GET` | `/payment/zarinpal/callback` | کالبک درگاه Zarinpal فروشگاه شخصی هر بات (`bot/shop.py`) |
| `GET` | `/payment/stripe/callback` | کالبک درگاه Stripe فروشگاه شخصی هر بات |
| `GET` | `/payment/live/zarinpal/callback` | کالبک Zarinpal مخصوص پرداخت پلن `/live` **به پلتفرم** |
| `GET` | `/payment/live/stripe/callback` | کالبک Stripe مخصوص پرداخت پلن `/live` **به پلتفرم** |
| `GET` | `/api/flow` | خواندن `flow_definition` بات |
| `POST` | `/api/flow` | ذخیرهٔ `flow_definition` بات |
| `GET` | `/api/content` | لیست `ContentItem` های بات |
| `POST` | `/api/content` | ساخت یک `ContentItem` جدید |
| `PUT` | `/api/content/{item_id}` | ویرایش یک `ContentItem` |
| `DELETE` | `/api/content/{item_id}` | حذف یک `ContentItem` |
| `GET` | `/` | سرو `index.html` فرانت‌اند |
| `GET` | `/favicon.svg` | سرو favicon |
| `GET` | `/assets/*` (static) | سرو فایل‌های استاتیک بیلدشده (فقط اگر پوشهٔ `assets` وجود داشته باشد) |

#### `zarinpal_callback` (`/payment/zarinpal/callback`)
- **چه‌کار می‌کند:** پس از پرداخت/لغو یک خرید مشتری از فروشگاه یک بات، Zarinpal مرورگر خریدار را به این آدرس ریدایرکت می‌کند. `Authority` و `Status` را از query می‌خواند؛ اگر `Status != "OK"` یا `Authority` نبود، صفحهٔ «لغو شد» نشان می‌دهد.
- **بدون احراز initData:** چون این کالبک را خودِ Zarinpal می‌زند (نه فرانت‌اند خودمان)، هیچ چک `initData` ندارد؛ خودِ `Authority` توکنی غیرقابل‌حدس (unguessable) است که به یک سفارش خاص گره می‌خورد و همین نقش «اعتبارنامه» را بازی می‌کند.
- **جست‌وجوی دوگانه:** اول با `verify_zarinpal_payment(authority)` روی جدول `Order` (خرید تکی) نگاه می‌کند؛ اگر نبود، با `verify_zarinpal_checkout(authority)` روی `Checkout` (خرید سبدی/cart) نگاه می‌کند. چون `authority` برای هر درگاه یکتاست، هیچ ابهامی بین این دو جست‌وجو نیست.

#### `stripe_callback` (`/payment/stripe/callback`)
- **چه‌کار می‌کند:** همان الگوی بالا برای Stripe؛ اگر `?cancelled=1` باشد صفحهٔ لغو، وگرنه با `session_id` (که Stripe در `success_url` جایگزین کرده) ابتدا `verify_stripe_payment` (روی `Order`) و سپس fallback به `verify_stripe_checkout` (روی `Checkout`) را چک می‌کند.

#### `live_zarinpal_callback` (`/payment/live/zarinpal/callback`)
- **چه‌کار می‌کند:** این کالبکِ زمانی است که یک **مالک بات** به **خودِ پلتفرم** برای فعال‌سازی پلن `/live` پول پرداخت می‌کند (طبق `bot/platform_billing.py:start_zarinpal_live_payment`). فقط `verify_zarinpal_live_payment(authority)` را روی جدول `LivePayment` صدا می‌زند.

#### `live_stripe_callback` (`/payment/live/stripe/callback`)
- **چه‌کار می‌کند:** معادل بالا برای Stripe، با `verify_stripe_live_payment(session_id)`.

**چرا این چهار callback (Zarinpal/Stripe فروشگاه در برابر Zarinpal/Stripe لایو-پلتفرم) کاملاً جدا نگه داشته شده‌اند:** دو زوج بالا از نظر route، تابع verify، و جدول دیتابیس زیرین کاملاً مستقل‌اند. `verify_zarinpal_payment`/`verify_stripe_payment`/`verify_zarinpal_checkout`/`verify_stripe_checkout` روی `Order`/`Checkout` کار می‌کنند (درآمد **مالک بات** از **مشتری‌های خودش**)، درحالی‌که `verify_zarinpal_live_payment`/`verify_stripe_live_payment` روی `LivePayment` کار می‌کنند (درآمد **پلتفرم** از **مالکان بات**). این تفکیک مستقیماً بازتاب همان تصمیم معماری در `bot/platform_billing.py` است (رکوردهای جدا برای این‌که این دو جریان پولی هرگز قاطی نشوند) و اگر این دو مسیر یکی می‌شدند، یک پرداخت مشتری به فروشگاه می‌توانست به‌اشتباه بات را به‌جای فعال‌سازی حساب مشتری، لایو کند یا برعکس.

#### `get_flow(request) -> web.Response`
- **چه‌کار می‌کند:** پس از عبور از `_authenticated_bot`، `flow_definition` بات را به‌شکل JSON برمی‌گرداند؛ اگر خالی باشد یک ساختار پیش‌فرض `{"nodes": [], "edges": []}` برمی‌گردد.

#### `save_flow(request) -> web.Response`
- **چه‌کار می‌کند:** بعد از احراز مالکیت، بدنهٔ JSON درخواست را می‌خواند (اگر JSON نامعتبر بود `400`)؛ اگر ساختار `dict` نبود یا کلیدهای `nodes`/`edges` نداشت `400`. سپس روی `BuiltBot` (با یک session/کوئری جدید) `flow_definition` و `flow_updated_at = now(UTC)` را می‌نویسد و commit می‌کند، و در پایان `sync_bot_commands(built_bot.id)` (از `bot/runtime.py`) را صدا می‌زند تا لیست دستورات `/` بات روی تلگرام با فلوی جدید هماهنگ شود.

#### `_serialize_content_item(item) -> dict`
- **چه‌کار می‌کند:** یک `ContentItem` را به دیکشنری JSON-پذیر تبدیل می‌کند؛ شامل `unlock_price` که کامنت توضیح می‌دهد قیمت à-la-carte این آیتم خاص در حالت subscription است، یا `null` برای بازگشت (fallback) به `ShopSettings.default_unlock_price` (طبق `bot/premium_content.py`).

#### `_premium_fields(payload) -> dict`
- **چه‌کار می‌کند:** فیلدهای `is_premium`/`unlock_price` را از بدنهٔ درخواست استخراج و coerce می‌کند: `is_premium` به `bool`؛ برای `unlock_price`، اگر مقدار در `(None, "", 0, "0")` باشد `None` می‌شود (یعنی «قیمت پیش‌فرض shop را استفاده کن»)، وگرنه سعی می‌کند به `int` مثبت تبدیل کند (`max(0, int(raw)) or None`) و در صورت شکست تبدیل هم `None` می‌گذارد — یعنی یک ورودی نامعتبر هرگز کرش نمی‌کند، فقط بی‌اثر می‌شود.

#### `list_content(request) -> web.Response`
- **چه‌کار می‌کند:** پس از احراز مالکیت، همهٔ `ContentItem` های آن بات را (مرتب بر اساس `title`) برمی‌گرداند.

#### `create_content(request) -> web.Response`
- **چه‌کار می‌کند:** بدنه را می‌خواند؛ اگر `title` خالی باشد `400`. اگر `code` داده شده باشد (case-insensitive با `func.lower`)، چک می‌کند که در همین بات تکراری نباشد (`409` اگر بود). سپس با `upsert_item` (از `bot/content_nav.py`) آیتم را می‌سازد (شامل فیلدهای premium). اگر `parent_id` داده شده باشد، با `reparent_item` سلسله‌مراتب را ست می‌کند و آیتم را دوباره با `get_item` می‌خواند تا مقدار به‌روز برگردد. در پایان `sync_bot_commands` صدا زده می‌شود.

#### `update_content(request) -> web.Response`
- **چه‌کار می‌کند:** `item_id` از مسیر (`match_info`) و مالکیت هم بات (`_authenticated_bot`) و هم آیتم (`ContentItem.bot_id == built_bot.id`) چک می‌شود؛ اگر آیتم نبود `404`. فقط فیلدهای موجود در payload (`title`, `body`, `image_url`, `link_url` + premium fields) روی `upsert_item` اعمال می‌شوند. اگر `parent_id` در payload بود، `reparent_item` صدا زده می‌شود و اگر آن `False` برگرداند (چرخه/cycle یا parent متعلق به بات دیگر) `400` برمی‌گردد. در پایان `sync_bot_commands`.

#### `delete_content(request) -> web.Response`
- **چه‌کار می‌کند:** پس از احراز مالکیت و پیداکردن آیتم (`404` اگر نبود)، چک می‌کند آیتم زیرمجموعه (`parent_id == item_id`) دارد یا نه — اگر داشت `409` («has sub-items — delete those first»)؛ یعنی حذف تنها برای برگ‌های درخت (leaf nodes) مجاز است، برای جلوگیری از یتیم‌ماندن آیتم‌های فرزند. در غیر این صورت حذف و commit می‌شود، سپس `sync_bot_commands`.

#### `index(request) -> web.Response`
- **چه‌کار می‌کند:** اگر `webapp/dist/index.html` وجود نداشته باشد (فرانت‌اند build نشده)، پیام `503` با راهنمای build می‌دهد. در غیر این صورت آن فایل را با هدر `Cache-Control: no-store, must-revalidate` سرو می‌کند — طبق کامنت کد، این عمداً است: بعد از هر redeploy، نام فایل‌های hash-شدهٔ `/assets/*.js` عوض می‌شود، و اگر `index.html` کش شود، یک نسخهٔ قدیمی که به فایل‌های اسکریپت حذف‌شده اشاره می‌کند، Mini App را سفید (blank) رندر می‌کند؛ خودِ فایل‌های `assets` با هش در نامشان همیشه قابل کش دائمی‌اند.

#### `favicon(request) -> web.Response`
- **چه‌کار می‌کند:** فایل `favicon.svg` را سرو می‌کند؛ اگر نبود `404`.

### `start_webapp_server(bot_token, port) -> web.AppRunner`
- **چه‌کار می‌کند:** با `create_app(bot_token)` اپلیکیشن را می‌سازد، یک `web.AppRunner` راه‌اندازی می‌کند، و روی `0.0.0.0:{port}` یک `web.TCPSite` باز می‌کند؛ لاگ می‌کند که سرور آماده است و `runner` را برمی‌گرداند (تا فراخوانندهٔ آن، احتمالاً در `bot/runtime.py`، بتواند بعداً آن را متوقف کند).

---

## `bot/handlers/live.py`

**تفاوت با `bot/live.py`:** این فایل، برخلاف `bot/live.py` که یک ماژول منطق خالص و بدون کد تلگرامی است، یک **هندلر واقعی aiogram** است — یعنی جایی که پیام‌ها و callback query های تلگرام واقعاً دریافت و پردازش می‌شوند، صفحه‌کلیدها ساخته می‌شوند، FSM state ها مدیریت می‌شوند، و به کاربر پاسخ داده می‌شود. این فایل توابع منطقی‌اش را از `bot.live`، `bot.platform_billing`، و `bot.website_client` وارد (import) می‌کند و آن‌ها را به رویدادهای تلگرام متصل می‌کند. `router = Router(name="live")` این‌جا تعریف و احتمالاً در نقطهٔ اصلی راه‌اندازی بات (`bot/runtime.py` یا مشابه) با بقیهٔ router ها ترکیب می‌شود.

### راه‌اندازی ماژول
- `_config = load_config()` و `_is_platform_admin = IsPlatformAdmin(_config.platform_admin_id)` — یک نمونهٔ از فیلتر `bot/filters/admin.py:IsPlatformAdmin` که فقط اجازه می‌دهد کاربری با `telegram_id == platform_admin_id` هندلرهای تأیید/رد TON را اجرا کند.

### `_get_user(telegram_id) -> User | None`
- **چه‌کار می‌کند:** یک تابع کمکی کوچک برای واکشی `User` با `telegram_id`؛ در چندین هندلر این فایل استفاده می‌شود.

### `_send_live_status(message, bot_id, telegram_id) -> None`
هستهٔ نمایش وضعیت `/live` — قدم‌به‌قدم:
1. `built_bot` را با `live.get_built_bot(bot_id)` می‌خواند (توجه: این‌جا `bot_id` از `active_bot_id` در FSM state می‌آید که طبق کامنت `bot/live.py` از‌قبل تأییدشده است، پس استفادهٔ `get_built_bot` به‌جای `get_owned_built_bot` این‌جا درست است). اگر نبود پیام «Bot not found.».
2. اگر `live.is_bot_suspended(built_bot)` باشد، پیام suspension (`live.suspension_status_text`) را **قبل از هرچیز دیگر** نمایش می‌دهد — همراه با توضیح که کاربر همچنان می‌تواند پلن‌ها را ببیند ولی حتی بعد از پرداخت موفق، بات آفلاین می‌ماند تا suspension برداشته شود. این دقیقاً همان قاعدهٔ اولویت `is_bot_suspended` قبل از `is_bot_expired` است که در `bot/live.py` تعریف شده.
3. `show_trial = built_bot.live_until is None` — تست رایگان فقط وقتی نمایش داده می‌شود که بات هنوز اصلاً هیچ‌وقت لایو نشده (یک‌بارمصرف بودن با همین شرط تضمین می‌شود).
4. با `platform_billing.resolve_region(user)` ریجن مالک را می‌خواند؛ اگر `None` (هنوز نامشخص)، سوال دوزبانه (انگلیسی/فارسی) «کجایی؟» را با `live_region_keyboard()` می‌فرستد و برمی‌گردد — بدون نمایش پلن‌ها تا وقتی ریجن مشخص شود.
5. `methods = platform_billing.available_methods_for_region(region)` را می‌گیرد؛ `is_fa = region == "iran"`.
6. `can_redeem = website_client.is_configured()` و `plans_url = _config.website_plans_url if can_redeem else None` — یعنی گزینهٔ «فعال‌سازی با کد» فقط وقتی نشان داده می‌شود که کلاینت وب‌سایت واقعاً پیکربندی شده باشد.
7. اگر هیچ‌کدام از `methods`، `show_trial`، `plans_url`، `can_redeem` موجود نبود — یعنی هیچ راهی برای این کاربر در این ریجن نیست — پیامی می‌دهد که «هیچ روش پرداختی برای منطقهٔ شما تنظیم نشده، با ادمین تماس بگیرید» و برمی‌گردد.
8. اگر `methods` خالی است ولی `plans_url` موجود است (حالت رایج کاربر ایرانی)، متن راهنمای دوزبانه اضافه می‌شود: خرید روی وب‌سایت انجام می‌شود، اگر کاربر VPN دارد باید موقتاً برای صفحهٔ پرداخت خاموشش کند، و کد دریافتی (`EMB-XXXX-XXXX`) را با «فعال‌سازی با کد» وارد کند.
9. در پایان `live.status_text(built_bot)` + متن راهنما با `live_plans_keyboard(...)` (شامل پلن‌ها، روش‌های پرداخت موجود، آیا تست رایگان نشان داده شود، آیا گزینهٔ redeem نشان داده شود، و `plans_url`) نمایش داده می‌شود.

### `cmd_live(message, state)` — `@router.message(CommandFilter("live"))`
- **چه‌کار می‌کند:** نقطهٔ ورود دستور `/live`. `active_bot_id` را از FSM state می‌خواند؛ اگر نبود می‌گوید اول یک بات از «My Bots» انتخاب کن. در غیر این صورت `_send_live_status` را صدا می‌زند.

### `choose_region(callback, state)` — `@router.callback_query(F.data.startswith("live:region:"))`
- **چه‌کار می‌کند:** وقتی کاربر روی دکمهٔ «ایران»/«بین‌الملل» می‌زند، ریجن را از انتهای `callback.data` می‌گیرد، کاربر را پیدا می‌کند (اگر نبود خطای «try /start first»)، با `platform_billing.set_region` ذخیره می‌کند، و دوباره `_send_live_status` را صدا می‌زند تا حالا با ریجن مشخص، پلن‌ها نمایش داده شوند.

### `start_trial(callback, state)` — `@router.callback_query(F.data == "live:trial")`
- **چه‌کار می‌کند:** جریان تست رایگان.
- **مراحل:** `built_bot` را می‌خواند؛ اگر نبود خطا. **موارد خاص:** اگر `built_bot.live_until is not None` باشد (یعنی این بات قبلاً یک‌بار لایو شده — چه با تست، چه با پلن)، پیام «تست قبلاً استفاده شده» با `show_alert=True` نمایش داده می‌شود و اجرا متوقف می‌شود — این‌جا دقیقاً قاعدهٔ یک‌بارمصرف‌بودن trial اجرا می‌شود. در غیر این صورت `until = live.trial_until()`، سپس `live.set_live_until(built_bot.id, until)`، و اگر بات `suspended` نباشد `start_built_bot` صدا زده می‌شود تا واقعاً روی تلگرام روشن شود. در پایان پیام تبریک با تاریخ انقضا نشان داده می‌شود.

### جریان «فعال‌سازی با کد سایت»

#### `_REDEEM_ERRORS: dict`
- نگاشت کدهای خطای `bot/website_client.py:redeem_activation_code` به متن انسانی قابل‌نمایش (شامل `already_used`، `not_found`، `malformed_code`، `void`، `not_configured`، `network`، `bad_response`).

#### `ask_activation_code(callback, state)` — `@router.callback_query(F.data == "live:redeem")`
- **چه‌کار می‌کند:** وقتی کاربر دکمهٔ «فعال‌سازی با کد» را می‌زند، اگر `active_bot_id` وجود نداشته باشد خطا می‌دهد؛ در غیر این صورت state را به `LivePlanStates.waiting_for_activation_code` می‌برد و از کاربر می‌خواهد کد `EMB-XXXX-XXXX` را بفرستد (با دکمهٔ لغو).

#### `_save_user_phone(telegram_id, phone) -> None`
- **چه‌کار می‌کند:** `phone_number` روی رکورد `User` را می‌نویسد و commit می‌کند؛ در چند مسیر (فعال‌سازی با کد، پرداخت پلن) به‌عنوان یک تابع کمکی مشترک استفاده می‌شود.

#### `_apply_activation_code(message, state, code, bot_id, phone) -> None`
تابع مرکزی که واقعاً کد را redeem می‌کند و بات را فعال می‌سازد:
1. `built_bot` را می‌خواند؛ اگر نبود state پاک می‌شود و پیام خطا.
2. `website_client.redeem_activation_code(code, bot_id, user.id, username=..., first_name=..., phone=phone)` صدا زده می‌شود.
3. اگر `ok` نبود، خطا با `_REDEEM_ERRORS` ترجمه می‌شود؛ **فقط** برای `not_configured` state کاملاً پاک می‌شود (چون تلاش دوباره فایده‌ای ندارد)، برای بقیهٔ خطاها (مثلاً تایپ اشتباه کد) state روی همان `waiting_for_activation_code` باقی می‌ماند تا کاربر بتواند فوراً کد اصلاح‌شده را دوباره بفرستد.
4. اگر `days <= 0` بود (کد بی‌اعتبار از نظر مدت زمان)، state پاک و خطا.
5. **محاسبهٔ تاریخ جدید:** `base` یا `built_bot.live_until` است (اگر هنوز در آینده باشد — یعنی بات فعلاً لایو است) یا `now` (اگر بات هرگز لایو نبوده یا قبلاً منقضی شده)؛ `until = base + timedelta(days=days)` — یعنی کد روی زمان باقی‌ماندهٔ فعلی add می‌شود، نه جایگزین آن.
6. `live.set_live_until` و در صورت عدم suspension، `start_built_bot`.
7. پیام تبریک با تعداد ماه (اگر `months` در پاسخ بود) یا روز، و در صورت `base != now` یادآوری «از تاریخ انقضای فعلی تمدید شد»، و در صورت suspend‌بودن هشدار مربوطه.

#### `receive_activation_code(message, state)` — `@router.message(LivePlanStates.waiting_for_activation_code)`
- **چه‌کار می‌کند:** وقتی کاربر متن کد را می‌فرستد.
- **گرفتن شماره تلفن تأییدشده قبل از مصرف کد (نکتهٔ کلیدی این جریان):** کد را trim می‌کند (اگر خالی، دوباره می‌خواهد)؛ `built_bot` و `user` را می‌خواند؛ `phone = user.phone_number` (اگر بود). **اگر شماره‌ای روی پروفایل کاربر ذخیره نشده باشد** ('' یا `None`)، بات کد را هنوز مصرف (redeem) **نمی‌کند** — به‌جایش `code` را در `state.update_data(pending_activation_code=code)` نگه می‌دارد، state را به `waiting_for_activation_code_phone` می‌برد و با `phone_share_keyboard()` از کاربر شماره می‌خواهد (`_ACTIVATION_PHONE_PROMPT`، دوزبانه). فقط اگر شماره از‌قبل موجود بود، مستقیم `_apply_activation_code` صدا زده می‌شود. این دقیقاً همان الزام «گرفتن شماره تلفن تأییدشده قبل از مصرف کد» است — چون یک کد یک‌بارمصرف است، بات ترجیح می‌دهد ابتدا هویت را کامل کند تا کد را «بسوزاند» بدون این‌که هویت کامل ثبت شده باشد.

#### `receive_activation_phone_contact(message, state)` — `@router.message(LivePlanStates.waiting_for_activation_code_phone, F.contact)`
- **چه‌کار می‌کند:** وقتی کاربر با دکمهٔ اشتراک‌گذاری مخاطب، شماره را می‌فرستد (این «شماره تأییدشده» واقعی طبق تلگرام است). اگر با `+` شروع نشود، `+` اضافه می‌شود. با `_save_user_phone` ذخیره می‌شود، و کد نگه‌داشته‌شده در `pending_activation_code` را با `_apply_activation_code` اعمال می‌کند.

#### `receive_activation_phone_text(message, state)` — `@router.message(LivePlanStates.waiting_for_activation_code_phone, F.text)`
- **چه‌کار می‌کند:** مسیر جایگزین برای کاربری که شماره را تایپ می‌کند به‌جای اشتراک‌گذاری دکمه‌ای. اگر متن دقیقاً برابر `SKIP_BUTTON_TEXT` باشد (یعنی کاربر می‌خواهد رد کند)، توضیح می‌دهد که برای فعال‌سازی پولی، شماره اجباری است (رد شدن مجاز نیست) و دوباره صفحه‌کلید را نشان می‌دهد. در غیر این صورت با `normalize_typed_phone` (از `bot/guide.py`) شماره را نرمال‌سازی می‌کند؛ اگر نامعتبر بود دوباره می‌خواهد؛ در غیر این صورت ذخیره و `_apply_activation_code`.

### پرداخت پلن: Zarinpal (ایران) / Stripe یا TON (بین‌الملل)

#### `_PLAN_PAYMENT_PHONE_PROMPT`
- متن دوزبانهٔ مشابه پرامپت شمارهٔ فعال‌سازی با کد، ولی مخصوص جریان پرداخت مستقیم پلن.

#### `_terms_line() -> str`
- **چه‌کار می‌کند:** اگر `_config.website_url` تنظیم شده باشد، یک خط لینک به «Terms of Service» (`{website_url}/terms/`) برمی‌گرداند تا به انتهای پیام‌های پرداخت اضافه شود؛ وگرنه رشتهٔ خالی.

#### `_start_plan_payment_flow(target, state, plan_key, method, bot_id, remove_kb=False) -> None`
تابع مرکزی که واقعاً `LivePayment` می‌سازد و لینک/دستورالعمل پرداخت را به کاربر می‌دهد؛ طبق docstring خودش، **فقط پس از این اجرا می‌شود که یک شماره تلفن Telegram-verified برای مالک در دست باشد.**
- اگر `remove_kb=True` (یعنی از مسیر «بعد از دریافت شماره تلفن» آمده)، ابتدا صفحه‌کلید reply (دکمهٔ اشتراک شماره) با یک «Thanks! 🙌» حذف می‌شود.
- `payment = platform_billing.create_live_payment(bot_id, plan_key, method)`؛ اگر `None` (پلن نامعتبر) state پاک و پیام خطا.
- **مسیر Zarinpal/Stripe:** state پاک می‌شود (`None`)، تابع شروع‌کنندهٔ مناسب (`start_zarinpal_live_payment` یا `start_stripe_live_payment`) صدا زده می‌شود؛ اگر `pay_url` نبود خطا؛ وگرنه یک دکمهٔ inline لینک‌دار «🔗 Pay Now» + خط قوانین (`_terms_line`) فرستاده می‌شود.
- **مسیر TON:** اگر `platform_ton_wallet_address` تنظیم نشده، خطا و state پاک. در غیر این صورت `payment.id` در state ذخیره می‌شود (`live_payment_id`)، state به `LivePlanStates.waiting_for_ton_tx_hash` می‌رود، و آدرس ولت + مبلغ دلاری (معادل TON را خودِ کاربر باید بپردازد) + درخواست ارسال هش تراکنش نمایش داده می‌شود.

#### `start_plan_payment(callback, state)` — `@router.callback_query(F.data.startswith("live:pay:"))`
- **چه‌کار می‌کند:** `callback.data` به‌شکل `live:pay:{plan_key}:{method}` پارس می‌شود. اگر `active_bot_id` نبود خطا. سپس شماره تلفن کاربر چک می‌شود؛ اگر نبود، `plan_key`/`method` در `pending_plan_pay` state ذخیره می‌شود، state به `waiting_for_plan_payment_phone` می‌رود و شماره درخواست می‌شود؛ اگر بود، مستقیم `_start_plan_payment_flow` صدا زده می‌شود.

#### `_resume_plan_payment_after_phone(message, state, phone) -> None`
- **چه‌کار می‌کند:** بعد از دریافت شماره (چه با دکمه چه با تایپ)، شماره را ذخیره می‌کند، `pending_plan_pay` و `active_bot_id` را از state می‌خواند (اگر ناقص بودند، خطا و پاک‌سازی state)، و `_start_plan_payment_flow` را با `remove_kb=True` صدا می‌زند.

#### `receive_plan_payment_phone_contact` / `receive_plan_payment_phone_text`
- **چه‌کار می‌کند:** دقیقاً معادل دو هندلر مشابه در جریان فعال‌سازی با کد (`receive_activation_phone_contact`/`_text`) اما برای state مربوط به پرداخت پلن (`waiting_for_plan_payment_phone`)؛ نسخهٔ contact پیش‌وند `+` را تضمین می‌کند، نسخهٔ متنی گزینهٔ «رد کردن» را قبول نمی‌کند و با `normalize_typed_phone` اعتبارسنجی می‌کند.

### تأیید دستی TON توسط ادمین

#### `receive_ton_tx_hash(message, state, bot)` — `@router.message(LivePlanStates.waiting_for_ton_tx_hash)`
- **چه‌کار می‌کند:**
  1. `payment_id` را از `live_payment_id` در state می‌خواند؛ اگر نبود state پاک و خروج بی‌صدا.
  2. `tx_hash` (متن پیام) را trim می‌کند؛ اگر خالی، دوباره می‌خواهد.
  3. `platform_billing.submit_ton_live_payment(payment_id, tx_hash)` صدا زده می‌شود — این فقط `transaction_ref` را ذخیره می‌کند، هیچ فعال‌سازی‌ای هنوز رخ **نمی‌دهد**.
  4. state پاک می‌شود و به کاربر گفته می‌شود پرداخت در انتظار بررسی ادمین است.
  5. مالک بات با `_get_user` پیدا می‌شود، و یک پیام گزارشی شامل نام کاربری بات، پلن و قیمت، هویت کاربر (username/first_name + `telegram_id` + شماره تلفن در صورت وجود)، و خودِ `tx_hash` به `PLATFORM_ADMIN_ID` فرستاده می‌شود، همراه با `live_ton_admin_keyboard(payment.id)` — یک صفحه‌کلید inline با دکمه‌های تأیید/رد.
  - **موارد خاص:** ارسال پیام به ادمین داخل `try/except Exception: pass` است — یعنی حتی اگر پیام به ادمین نرسد (مثلاً بات پلتفرم بلاک شده)، خودِ فرآیند برای کاربر خطا نمی‌دهد؛ رکورد `pending` در دیتابیس باقی می‌ماند و ادمین می‌تواند بعداً از طریق پنل هم بررسی کند.

#### `approve_ton_payment(callback)` — `@router.callback_query(F.data.startswith("live:ton_approve:"), _is_platform_admin)`
- **چه‌کار می‌کند:** این هندلر پشت فیلتر `_is_platform_admin` گیت شده — یعنی فقط `PLATFORM_ADMIN_ID` می‌تواند این دکمه را بزند (حتی اگر تلگرام رویداد callback را از یک کاربر دیگر بفرستد، فیلتر جلوی اجرا را می‌گیرد). `payment_id` از انتهای `callback.data` استخراج می‌شود؛ `platform_billing.approve_ton_live_payment(payment_id)` صدا زده می‌شود که وضعیت را `"paid"` می‌کند و بات را فعال (`_activate_bot`) و مالک را مطلع (`_notify_owner`) می‌سازد. سپس دکمه‌های inline از پیام ادمین برداشته می‌شوند (`edit_reply_markup(reply_markup=None)`) تا دوباره قابل کلیک نباشند.

#### `reject_ton_payment(callback)` — `@router.callback_query(F.data.startswith("live:ton_reject:"), _is_platform_admin)`
- **چه‌کار می‌کند:** معادل بالا اما `platform_billing.reject_ton_live_payment(payment_id)` را صدا می‌زند (وضعیت `"rejected"`، پیام رد به مالک)؛ هیچ فعال‌سازی‌ای رخ نمی‌دهد. مانند مورد قبل، دکمه‌های inline پیام ادمین حذف می‌شوند.

---

### جمع‌بندی مسیرهای فایل با فایل

| فایل | نقش |
|---|---|
| `bot/live.py` | منطق چرخهٔ عمر لایو‌شدن، ثابت پلن‌ها، گیت‌های suspended/expired، دو تابع lookup با/بدون چک مالکیت |
| `bot/platform_billing.py` | پردازش واقعی پرداخت پلن‌های پلتفرم (Zarinpal/Stripe/TON)، تشخیص و ذخیرهٔ منطقهٔ کاربر |
| `bot/website_client.py` | کلاینت HTTP امن با retry برای redeem کردن کد فعال‌سازی از وب‌سایت |
| `bot/admin_panel.py` | کوئری/mutation های سطح پلتفرم برای پنل ادمین، بدون هیچ authorization داخلی |
| `bot/webapp_auth.py` | اعتبارسنجی رمزنگاری‌شدهٔ `initData` تلگرام برای Mini App |
| `bot/webapp_server.py` | سرور HTTP: کالبک‌های پرداخت + API فلوبیلدر با احراز initData |
| `bot/handlers/live.py` | هندلر تلگرامی که تمام موارد بالا را به تجربهٔ کاربری `/live` تبدیل می‌کند |
