# مستند فنی پروژه easymakebot — بخش لایه دیتابیس و فروشگاه

---

## `bot/db/base.py`

این فایل نقطه‌ی راه‌اندازی (bootstrap) اتصال به دیتابیس است: موتور async SQLAlchemy را می‌سازد، `session_maker` را برای بقیه‌ی پروژه فراهم می‌کند، کلاس پایه‌ی `Base` را تعریف می‌کند، و مهم‌تر از همه تابع `init_db()` را دارد که چون این پروژه ابزار مهاجرت واقعی (مثل Alembic) ندارد، نقش «مهاجرت دستی اسکیمای دیتابیس» را هم بازی می‌کند.

خطوط ۱ تا ۲۰: `engine` با `create_async_engine(_config.database_url, echo=False)` ساخته می‌شود (تنظیمات از `bot/config.py` خوانده می‌شود). `async_session_maker` یک `async_sessionmaker` است با `expire_on_commit=False` — یعنی بعد از `commit()` شدن یک session، آبجکت‌های SQLAlchemy همچنان قابل خواندن می‌مانند بدون این‌که مجبور شوید دوباره از دیتابیس بخوانید (این الگو در تقریباً همه‌ی فایل‌های پروژه، از جمله `bot/shop.py`، استفاده می‌شود). کلاس `Base(DeclarativeBase)` پایه‌ی همه‌ی مدل‌های ORM در `bot/db/models.py` است.

### `async def init_db() -> None`
- **چه‌کار می‌کند:** این تابع در زمان راه‌اندازی برنامه صدا زده می‌شود و دو کار انجام می‌دهد:
  1. با `from bot.db import models` مطمئن می‌شود همه‌ی کلاس‌های مدل import شده‌اند تا روی `Base.metadata` ثبت شوند (وگرنه `create_all` چیزی درباره‌شان نمی‌داند).
  2. داخل یک تراکنش (`engine.begin()`) ابتدا `Base.metadata.create_all` را اجرا می‌کند که **فقط جدول‌هایی که اصلاً وجود ندارند** را می‌سازد؛ سپس یک سری دستور خام SQL به شکل `ALTER TABLE ... ADD COLUMN IF NOT EXISTS ...` اجرا می‌کند تا ستون‌هایی که بعداً (در نسخه‌های جدیدتر کد) به مدل‌ها اضافه شده‌اند، روی یک دیتابیس قدیمی که از قبل آن جدول را داشته هم اعمال شوند.
- **چرا این‌طوری طراحی شده:** کامنت کد صریحاً می‌گوید چون Alembic هنوز وصل نشده، این روش «فعلاً خوب است» (`fine for now`). `create_all` توانایی تغییر جدول موجود را ندارد، پس تنها راه اضافه کردن ستون جدید به جدولی که از قبل در دیتابیس production/dev وجود دارد همین `ALTER TABLE ... IF NOT EXISTS` دستی است. استفاده از `IF NOT EXISTS` هم idempotent بودن را تضمین می‌کند — هر بار برنامه بالا می‌آید `init_db()` دوباره اجرا می‌شود و اجرای مجدد یک `ALTER TABLE` روی ستونی که از قبل وجود دارد، خطا نمی‌دهد.
- **موارد خاص/edge case:** چون همه‌ی این دستورها داخل یک `engine.begin()` هستند، اگر یکی از آن‌ها خطا بدهد، کل تراکنش rollback می‌شود و برنامه بالا نمی‌آید — این عمداً است تا دیتابیس هرگز در وضعیت نیمه‌مهاجرت‌یافته نماند. ترتیب دستورها هم مهم است: مثلاً ستون `content_items.product_id` باید بعد از ساخته‌شدن جدول `products` اضافه شود (چون `REFERENCES products(id)` دارد) و این با `create_all` که همه‌ی جدول‌ها را اول می‌سازد تضمین می‌شود.

فهرست دستورهای `ALTER TABLE` و ایندکس‌ها، به‌ترتیب، به همراه دلیل هرکدام:

| دستور | قابلیتی که برایش اضافه شده |
|---|---|
| `commands.command_type VARCHAR(32) DEFAULT 'custom'` | تفکیک نوع دستور (`start`/`custom`/`broadcast`) برای رفتار متفاوت در `bot/runtime.py` |
| `built_bots.force_join_enabled BOOLEAN DEFAULT false` | قابلیت «عضویت اجباری در کانال» قبل از پاسخ به `/start` |
| `built_bots.flow_definition BYTEA` | ذخیره‌ی خروجی رمزنگاری‌شده‌ی flow builder بصری (Mini App) |
| `users.phone_number BYTEA` | ذخیره‌ی رمزنگاری‌شده‌ی شماره تلفن کاربر پلتفرم برای بومی‌سازی راهنما |
| `bot_subscribers.phone_number BYTEA` | همان قابلیت، برای مشترکین یک ربات ساخته‌شده |
| `built_bots.flow_updated_at TIMESTAMPTZ` | تشخیص این‌که flow جدیدتر است یا `Command(name="/start")` قدیمی (منطق در `bot/runtime.py:_should_use_flow_for_start`) |
| `content_items.parent_id INTEGER REFERENCES content_items(id)` | ساختار درختی (پوشه/زیرآیتم) برای لیست محتوا |
| `bot_subscribers.access_level VARCHAR(100)` | سطح دسترسی اعطاشده توسط محصول نوع `access` |
| `content_items.product_id INTEGER REFERENCES products(id) ON DELETE SET NULL` | اتصال آیتم محتوا به یک محصول قابل‌فروش |
| `shop_settings.stripe_secret_key BYTEA` | افزودن درگاه Stripe |
| `orders.stripe_session_id VARCHAR(200)` | ردیابی سفارش‌های پرداخت‌شده با Stripe |
| `shop_settings.crypto_wallet_address BYTEA` | پرداخت با کریپتو (کیف پول) |
| `shop_settings.crypto_network_label VARCHAR(100)` | برچسب شبکه کریپتو (مثل `USDT (TRC20)`) |
| `shop_settings.ton_wallet_address BYTEA` | پرداخت با TON |
| `built_bots.live_until TIMESTAMPTZ` | مکانیزم «Go live» / انقضای پلن ربات |
| `content_items.code VARCHAR(50)` + `CREATE UNIQUE INDEX uq_content_item_bot_code ON content_items (bot_id, code)` | کد میان‌بر برای دسترسی مستقیم به یک آیتم؛ ایندکس یکتا **per-bot** (نه سراسری) |
| `orders.checkout_id INTEGER REFERENCES checkouts(id)` | اتصال سفارش به یک Checkout سبدخرید (جدول `checkouts` خودش با `create_all` ساخته می‌شود) |
| `built_bots.suspended BOOLEAN DEFAULT false` + `built_bots.suspension_reason VARCHAR(300)` | کلید خاموش‌کردن ربات توسط ادمین پلتفرم |
| `users.region VARCHAR(20)` | تفکیک روش‌های پرداخت «ایران» / «بین‌المللی» |
| `products.subscription_days INTEGER` | مدت زمان اعطاشده توسط محصول نوع `subscription` |
| `bot_subscribers.subscription_until TIMESTAMPTZ` | تاریخ انقضای اشتراک مشترک |
| `content_items.is_premium BOOLEAN DEFAULT false` | علامت‌گذاری محتوای premium (نیازمند اشتراک یا خرید تکی) |
| `shop_settings.free_preview_limit INTEGER DEFAULT 1` | تعداد پیش‌نمایش رایگان مجاز قبل از الزام اشتراک |
| `built_bots.commerce_mode VARCHAR(20)` | تعیین مدل کسب‌وکار ربات: `shop` یا `subscription` |
| `content_items.unlock_price` و `content_items.original_unlock_price INTEGER` | قیمت باز کردن تکی آیتم premium + مقدار پیش از کمپین |
| `content_unlocks.source VARCHAR(20) DEFAULT 'quota'` | تفکیک این‌که باز شدن آیتم از سهمیه رایگان بوده یا خرید |
| `products.original_price INTEGER` | قیمت پیش از کمپین قیمتی، برای بازگردانی |
| `shop_settings.default_unlock_price` و `original_default_unlock_price INTEGER` | قیمت پیش‌فرض باز کردن آیتم premium در سطح ربات + مقدار پیش از کمپین |
| `CREATE UNIQUE INDEX uq_price_campaign_active ON price_campaigns (bot_id) WHERE status = 'active'` | ایندکس یکتای شرطی (partial index) که تضمین می‌کند هر ربات حداکثر یک کمپین قیمتی `active` هم‌زمان داشته باشد |
| `products.stock_quantity INTEGER` | مدیریت موجودی انبار |
| `products.cost_price INTEGER` | قیمت تمام‌شده (برای محاسبه سود، هرگز به خریدار نشان داده نمی‌شود) |
| `products.import_code VARCHAR(50)` | کلید upsert برای ایمپورت گروهی محصول از اکسل |
| `shop_settings.invoice_business_name/logo_url/address/footer_note` (چهار ستون) | برندسازی فاکتور PDF |
| `CREATE UNIQUE INDEX uq_product_bot_import_code ON products (bot_id, import_code) WHERE import_code IS NOT NULL` | یکتایی `import_code` فقط در محدوده‌ی هر ربات (نه سراسری)، مشابه منطق `uq_content_item_bot_code` |

---

## `bot/db/encrypted_types.py`

این فایل دو نوع ستون سفارشی SQLAlchemy (`TypeDecorator`) تعریف می‌کند که داده‌های حساس (توکن ربات، شماره کارت، شماره تلفن، متن broadcast و…) را قبل از ذخیره در دیتابیس با الگوریتم Fernet رمزنگاری می‌کنند و هنگام خواندن به‌طور شفاف رمزگشایی می‌کنند — به‌طوری‌که بقیه‌ی کد اصلاً نمی‌داند رمزنگاری در کار است، فقط رشته/دیکشنری معمولی می‌بیند.

### `_load_key() -> bytes`
- **چه‌کار می‌کند:** متغیر محیطی `ENCRYPTION_KEY` را می‌خواند و به بایت تبدیل می‌کند.
- **موارد خاص:** اگر این متغیر ست نشده باشد، `ValueError` با یک پیام راهنما پرتاب می‌کند که دقیقاً دستور تولید کلید جدید (`Fernet.generate_key()`) را نشان می‌دهد — یعنی این خطا برنامه را در همان لحظه import شدن ماژول متوقف می‌کند (fail-fast)، نه بعداً هنگام اولین نوشتن در دیتابیس.
- در خط ۲۰، `_fernet = Fernet(_load_key())` یک نمونه‌ی سراسری (module-level singleton) از Fernet ساخته می‌شود که هر دو کلاس زیر از آن استفاده می‌کنند.

### `class EncryptedJSON(TypeDecorator)`
- **چه‌کار می‌کند:** یک ستون که مقدار پایتونی آن (لیست/دیکشنری، مثل `flow_definition` یا `payload` در `Command`) ابتدا با `json.dumps` سریالایز می‌شود، سپس با Fernet (که طبق docstring، AES-۱۲۸ در حالت CBC به‌همراه HMAC است) رمزنگاری و به‌صورت `LargeBinary` (یعنی ستون `BYTEA` در PostgreSQL) ذخیره می‌شود.
- `process_bind_param(self, value, dialect)`: هنگام **نوشتن** در دیتابیس صدا زده می‌شود. اگر `value` برابر `None` باشد همان `None` را برمی‌گرداند (یعنی مقدار خالی رمزنگاری نمی‌شود). در غیر این صورت با `ensure_ascii=False` سریالایز می‌کند (تا کاراکترهای فارسی/یونیکد به‌صورت escape شده ذخیره نشوند) و نتیجه را رمزنگاری می‌کند.
- `process_result_value(self, value, dialect)`: هنگام **خواندن** از دیتابیس صدا زده می‌شود؛ عکس عملیات بالا — رمزگشایی سپس `json.loads`.
- **موارد خاص/edge case:** اگر کلید `ENCRYPTION_KEY` عوض شود، هر رکورد رمزنگاری‌شده با کلید قدیمی دیگر قابل رمزگشایی نیست (`fernet.decrypt` استثنا پرتاب می‌کند) — این کلید باید در طول عمر دیتابیس ثابت بماند.

### `class EncryptedString(TypeDecorator)`
- **چه‌کار می‌کند:** دقیقاً همان منطق `EncryptedJSON` اما بدون مرحله‌ی JSON — مستقیماً رشته را encode/رمزنگاری یا رمزگشایی/decode می‌کند. برای مقادیر متنی ساده مثل `BuiltBot.token`، `ShopSettings.card_number`، `User.phone_number` و `BroadcastLog.text` استفاده می‌شود.
- **ارتباط با بقیه‌ی پروژه:** این دو کلاس در `bot/db/models.py` روی ستون‌های حساس اعمال می‌شوند (فهرست کامل در بخش مدل‌ها آمده). چون رمزگشایی/رمزنگاری در سطح ستون و به‌صورت خودکار توسط SQLAlchemy انجام می‌شود، توابع `bot/shop.py` و بقیه‌ی ماژول‌ها می‌توانند مستقیماً مثلاً `settings.zarinpal_merchant_id` را به‌عنوان یک رشته‌ی ساده بخوانند بدون این‌که نگران رمزگشایی دستی باشند.

---

## `bot/db/models.py`

این فایل تمام مدل‌های SQLAlchemy (جدول‌های دیتابیس) پروژه را با استفاده از سبک `Mapped`/`mapped_column` (سبک SQLAlchemy 2.x) تعریف می‌کند. هر کلاس معادل یک جدول PostgreSQL است. الگوی مشترک در همه‌ی مدل‌ها: کلید خارجی به `built_bots.id` (چون تقریباً همه‌چیز در این پلتفرم «به یک ربات ساخته‌شده متعلق است»)، فیلد `created_at` با `server_default=func.now()`، و «graceful omit» — یعنی فیلدهای اختیاری `None`/`NULL` هستند و نبودشان یعنی آن قابلیت غیرفعال است، نه خطا.

### `class User`
جدول `users` — نماینده‌ی کاربر **پلتفرم easymakebot** (کسی که وارد ربات سازنده می‌شود تا ربات تلگرامی خودش را بسازد؛ با `BotSubscriber` که مشترک یک ربات ساخته‌شده است اشتباه نشود).
- `id`: کلید اصلی.
- `telegram_id` (`BigInteger`, `unique`, `index`): شناسه‌ی تلگرام کاربر؛ `BigInteger` چون شناسه‌های تلگرام از محدوده‌ی `int32` فراتر می‌روند.
- `phone_number` (`EncryptedString`, nullable): شماره‌ی تلفنی که هنگام `/start` برای بومی‌سازی راهنما به اشتراک گذاشته می‌شود (کد کشور برای حدس زدن کشور استفاده می‌شود — `bot/guide.py`).
- `region` (`String(20)`, nullable): مقدار `"iran"` یا `"international"` که تعیین می‌کند کاربر کدام روش‌های پرداخت `/live` را ببیند (`bot/platform_billing.py`)؛ عمدتاً از روی `phone_number` استنتاج می‌شود، وگرنه یک‌بار پرسیده و ذخیره می‌شود.
- `created_at`: تاریخ ثبت‌نام.
- رابطه: `bots` → لیست `BuiltBot`های متعلق به این کاربر، با `cascade="all, delete-orphan"` یعنی حذف یک `User` همه‌ی ربات‌هایش را هم حذف می‌کند.

### `class BuiltBot`
جدول `built_bots` — قلب مدل داده، هر رکورد یک ربات تلگرامی است که کاربری با easymakebot ساخته.
- `id` (`UUID`, primary key, `default=uuid.uuid4`): از UUID به‌جای عدد ترتیبی استفاده شده — احتمالاً برای غیرقابل‌حدس بودن شناسه‌ی ربات در URLها/callbackها.
- `owner_id`: کلید خارجی به `users.id`.
- `token` (`EncryptedString`): توکن ربات تلگرامی که مالک وارد کرده؛ حساس‌ترین داده در کل سیستم، رمزنگاری‌شده.
- `bot_username`, `display_name`: نام کاربری و نام نمایشی ربات.
- `force_join_enabled` (`Boolean`, default `False`): وقتی فعال باشد، کاربران نهایی باید عضو همه‌ی `JoinChannel`های تعریف‌شده باشند تا ربات به `/start` پاسخ دهد (منطق در `bot/runtime.py`).
- `flow_definition` (`EncryptedJSON`, nullable): خروجی flow builder بصری Mini App، به شکل `{"nodes": [...], "edges": [...]}`. برای `/start` به‌طور خاص، هرکدام از این و رکورد قدیمی `Command(name="/start")` که دیرتر ویرایش شده باشد، اولویت دارد (`bot/runtime.py:_should_use_flow_for_start`). دستورهای غیر `/start` معادل قدیمی ندارند، پس همیشه flow آن‌ها را کنترل می‌کند (`bot/runtime.py:_has_flow_trigger`).
- `flow_updated_at` (nullable): زمان آخرین ویرایش flow، برای همان مقایسه.
- `live_until` (`DateTime`, nullable): گیت «Go live» (`bot/live.py`). `NULL` = هرگز فعال نشده (اما همچنان قابل ویرایش است، فقط polling روی تلگرام ندارد). زمان آینده = درحال‌حاضر live (دوره‌ی آزمایشی یا پلن پولی). زمان گذشته = پنجره‌ی live منقضی شده، `bot/runtime.py` polling را متوقف می‌کند و ابزارهای ویرایش سمت مالک قفل می‌شوند تا خرید پلن جدید.
- `suspended`/`suspension_reason`: کلید خاموش‌کردن ادمین پلتفرم (`bot/admin_panel.py`)؛ عمداً **مستقل** از `live_until` است — رباتی که suspend شده باید حتی با پلن معتبر هم غیرفعال بماند، و خرید پلن جدید نباید به‌طور خاموش این وضعیت را دور بزند؛ فقط رفع تعلیق صریح ادمین این کار را می‌کند. این چک همیشه پیش از چک live/expired انجام می‌شود.
- `commerce_mode` (`String(20)`, nullable): `"shop"` یا `"subscription"` یا `None` (هنوز انتخاب نشده) — `bot/commerce_mode.py`. یک ربات فقط یکی از این دو مدل کسب‌وکار را می‌تواند داشته باشد (فروش تک‌محصولی یا آرشیو محتوای اشتراکی)، نه هر دو. اولین بار که مالک ابزار Shop یا Content List را باز می‌کند پرسیده و سپس به‌خاطر سپرده می‌شود.
- `created_at`, `updated_at`.
- روابط: `owner` (به `User`)، و لیست‌های `commands`, `join_channels`, `content_items`, `posts`, `products`, `orders` همگی با `cascade="all, delete-orphan"` (حذف ربات، همه‌ی داده‌های وابسته را پاک می‌کند)، و `shop_settings` به‌صورت `uselist=False` (رابطه‌ی یک‌به‌یک).

### `class Command`
جدول `commands` — یک دستور (مثل `/start`) تعریف‌شده برای یک ربات ساخته‌شده.
- `bot_id`: کلید خارجی به `built_bots.id`.
- `name`: نام دستور (مثل `/start`).
- `command_type` (`String(32)`, default `"custom"`): `"start"` | `"custom"` | `"broadcast"` — رفتار runtime در `bot/runtime.py` را تعیین می‌کند.
- `payload` (`EncryptedJSON`, nullable): محتوای ساختاریافته‌ی جمع‌آوری‌شده برای دستور (مثلاً پاسخ‌های ویزارد `/start`).
- رابطه: `bot` (به `BuiltBot`).

### `class JoinChannel`
جدول `join_channels` — کانالی که کاربران باید قبل از پاسخ‌گیری `/start` عضو آن باشند.
- `bot_id`, `username` (نام کاربری کانال).
- رابطه: `bot`.

### `class ContentItem`
جدول `content_items` — واحد عمومی «محتوا» در ابزار Content List (خبر، محصول، درس، سؤال متداول و…)، از طریق چت/آپلود اکسل/(در آینده) فید زنده پر می‌شود. **رمزنگاری نشده** چون این محتوا قرار است به کاربر نهایی نمایش داده شود.
- `UniqueConstraint("bot_id", "code", name="uq_content_item_bot_code")`.
- `title`, `body`, `image_url`, `link_url`, `position` (ترتیب نمایش).
- `parent_id` (self-referencing FK به `content_items.id`): درخت تودرتو برای گروه‌بندی؛ آیتمی با فرزند به‌صورت پوشه نمایش داده می‌شود (لمس آن فرزندان را می‌آورد)، آیتم بدون فرزند برگ است (جزئیات خودش را نشان می‌دهد) — نیازی به فلگ جدای «is category» نیست، از وجود/نبود فرزند استنتاج می‌شود.
- `product_id` (FK به `products.id`, `ondelete="SET NULL"`): وقتی این آیتم از ویزارد Content List به‌عنوان «برای فروش» ساخته شده باشد، این آیتم همچنان به‌عنوان محتوای معمولی مرور/نمایش می‌شود اما دکمه‌ی قیمت + خرید هم دارد که به همان مسیر سفارش/پرداخت `bot/shop.py` وصل است. `SET NULL` هنگام حذف تا حذف `Product` مانع حذف/نگه‌داری این آیتم محتوا نشود.
- `code` (`String(50)`, nullable): میان‌بر اختیاری انتخابی مالک (مثلاً `"101"` یا `"buy"`) که یک مشترک می‌تواند مستقیم تایپ کند (بدون پیمایش منو) تا مستقیم به این آیتم برود — برای حالت رایج «به اینستاگرام بنویسید CODE را برای ربات ما بفرستید». یکتا فقط در محدوده‌ی `(bot_id, code)`، **نه سراسری** — یعنی دو ربات از دو مالک مختلف می‌توانند آزادانه یک کد را دوباره استفاده کنند، چون هر جستجویی از قبل با `bot_id` محدود شده.
- `is_premium` (`Boolean`, default `False`): برای دیدن آن نیاز به اشتراک فعال (`BotSubscriber.subscription_until`) یا مصرف یک سهمیه‌ی پیش‌نمایش رایگان (`ContentUnlock`) است (`bot/premium_content.py`). مستقل از `product_id` — یک آیتم می‌تواند قابل‌خرید تکی، محدود به اشتراک، هر دو، یا هیچ‌کدام باشد.
- `unlock_price` (nullable): در حالت اشتراک، قیمت تکی (تومان) برای باز کردن دائمی همین یک آیتم برای مشترکی که پیش‌نمایش رایگانش تمام شده. `None` یعنی برو سراغ `ShopSettings.default_unlock_price`؛ اگر آن هم `None` باشد، خرید تکی اصلاً پیشنهاد نمی‌شود. پشت‌صحنه با یک `Product` مخفی (`product_type="content_unlock"`) که هنگام نیاز ساخته می‌شود پیاده‌سازی شده (`bot/shop.py`).
- `original_unlock_price`: فقط وقتی یک کمپین قیمتی فعال است ست می‌شود — قیمت پیش از کمپین، که هنگام پایان کمپین دقیقاً بازگردانده می‌شود.
- رابطه: `bot`.

### `class ContentUnlock`
جدول `content_unlocks` — یک رکورد یعنی این مشترک این آیتم premium خاص را با سهمیه‌ی رایگانش برای همیشه باز کرده (`bot/premium_content.py`). دسترسی از طریق اشتراک فعال اینجا ردیابی **نمی‌شود** — همیشه زنده در برابر `BotSubscriber.subscription_until` چک می‌شود (چون می‌تواند منقضی شود)، اما باز کردن با سهمیه‌ی رایگان هرگز منقضی نمی‌شود (باز کردن دوباره‌ی آیتمی که قبلاً باز شده نباید دوباره سهمیه مصرف کند).
- `UniqueConstraint("bot_id", "subscriber_telegram_id", "content_item_id", name="uq_content_unlock")`.
- `subscriber_telegram_id`: شناسه‌ی تلگرام مشترک (نه FK به `BotSubscriber`، مقدار خام).
- `content_item_id`: FK به `content_items.id`.
- `source` (`String(20)`, default `"quota"`): `"quota"` (یک سهمیه‌ی پیش‌نمایش رایگان مصرف شده) یا `"purchase"` (قیمت خرید تکی پرداخت شده). فقط ردیف‌های `"quota"` علیه `ShopSettings.free_preview_limit` شمرده می‌شوند؛ هر دو دسترسی دائمی می‌دهند.
- `unlocked_at`.

### `class BotSubscriber`
جدول `bot_subscribers` — یک کاربر تلگرامی که یک ربات ساخته‌شده‌ی خاص را استارت زده (به‌عنوان مخاطب broadcastها استفاده می‌شود).
- `UniqueConstraint("bot_id", "telegram_id", name="uq_bot_subscriber")`.
- `phone_number` (`EncryptedString`, nullable): در بلوک flow «راهنما و ویدیو» به‌درخواست به اشتراک گذاشته می‌شود، برای بومی‌سازی همان راهنما.
- `access_level` (`String(100)`, nullable): با خرید محصول نوع `"access"` ست می‌شود (مثل `"VIP"`)؛ فعلاً چیز دیگری در کدبیس روی این چک نمی‌کند اما بلوک‌های flow آینده می‌توانند رویش شاخه بزنند.
- `subscription_until` (`DateTime`, nullable): با خرید محصول نوع `"subscription"` ست/تمدید می‌شود — برخلاف `access_level`، **زمان‌دار** است و همیشه زنده چک می‌شود (`bot/premium_content.py:has_active_subscription`) نه یک اعطای دائمی. `None` = هرگز مشترک نشده یا اشتراک منقضی شده.
- رابطه‌ی صریحی به `BotPost`/`Order` تعریف نشده (کوئری‌ها با `bot_id`/`telegram_id` مستقیم انجام می‌شوند).

### `class BotPost`
جدول `bot_posts` — پست شبکه‌اجتماعی‌گونه (عکس/ویدیو + کپشن) که از گزینه‌ی «Add Post» ابزار Content List اضافه می‌شود، برای مالکانی که ترجیح می‌دهند از طریق ربات به‌جای یک کانال جدا اطلاع‌رسانی کنند. هنگام ساخته‌شدن به تمام `BotSubscriber`های فعلی ارسال می‌شود (`bot/handlers/tools/content_list.py`)؛ در runtime لایک/کامنت می‌شود (`bot/runtime.py`). رمزنگاری‌نشده.
- `media_type` (`String(10)`): `"photo"` یا `"video"`.
- `media_file_id` (`String(300)`): **نکته‌ی مهم** — این `file_id` برای توکن **همین ربات ساخته‌شده** معتبر است، نه ربات سازنده (builder bot). از اولین ارسالی که *از طریق* ربات مالک انجام می‌شود گرفته می‌شود (یک نمونه‌ی موقت `Bot(token=built_bot.token)`)، نه از `file_id` که آپلود مالک در چت builder با آن رسیده — چون `file_id`های تلگرام بین ربات‌های مختلف قابل استفاده نیستند.
- `like_count`, `comment_count` (denormalized، پیش‌فرض ۰): تا رندر دکمه‌های لایک/کامنت هرگز نیازی به کوئری `COUNT` نداشته باشد؛ در همان تراکنش insert/delete هر `PostLike`/`PostComment` به‌روز نگه داشته می‌شود.
- روابط: `bot`, `likes` (به `PostLike`), `comments` (به `PostComment`) — هر دو `cascade="all, delete-orphan"`.

### `class PostLike`
جدول `post_likes` — یک رکورد یعنی این کاربر تلگرامی این پست را لایک کرده. یکتا به‌ازای `(post_id, liker_telegram_id)` تا لمس دوباره‌ی 👍 به‌جای شمارش دوباره، لایک را toggle کند (خاموش).
- رابطه: `post`.

### `class PostComment`
جدول `post_comments` — یک کامنت متنی روی پست. هیچ محدودیت یکتایی ندارد (چند کامنت از یک کاربر مجاز است). مالک ربات هنگام رسیدن کامنت جدید به‌صورت زنده اطلاع داده می‌شود (`bot/runtime.py`).
- رابطه: `post`.

### `class Product`
جدول `products` — چیزی که مالک یک ربات ساخته‌شده از طریق ابزار/بلوک flow «Shop» می‌فروشد.
- `name`, `description`, `price` (`Integer`, تومان).
- `original_price` (nullable): فقط هنگام اجرای کمپین قیمتی ست می‌شود — قیمت پیش از کمپین؛ در نمایش خریدار، خط‌خورده کنار قیمت تخفیف‌دار نشان داده می‌شود (`bot/pricing.py`).
- `image_url` (nullable).
- `product_type` (`String(20)`, default `"digital"`): پنج مقدار ممکن:
  - `"physical"` — کالای فیزیکی؛ بعد از پرداخت اطلاعات ارسال جمع می‌شود.
  - `"digital"` — پس از پرداخت `delivery_text`/`delivery_file_url` ارسال می‌شود.
  - `"access"` — `BotSubscriber.access_level` را به `access_level_name` تنظیم می‌کند.
  - `"subscription"` — `BotSubscriber.subscription_until` را به‌اندازه‌ی `subscription_days` تمدید می‌کند.
  - `"content_unlock"` — مخفی؛ دسترسی دائمی به یک `ContentItem` premium می‌دهد؛ `delivery_file_url` آیینه‌ی `link_url` همان آیتم است؛ هرگز در لیست محصولات مالک نشان داده نمی‌شود (ببینید `bot/shop.py:fulfill_order` / `ensure_unlock_product`).
- `delivery_text`, `delivery_file_url` (nullable).
- `access_level_name` (nullable), `subscription_days` (nullable، فقط برای نوع `"subscription"` لازم است).
- `stock_quantity` (nullable): مدیریت موجودی (`bot/inventory.py`). `None` = ردیابی نمی‌شود (نامحدود — بیشتر برای انواع دیجیتال/دسترسی/اشتراک معنا ندارد). فقط عملاً برای `"physical"` معنادار است اما در سطح دیتابیس اجباری نیست (مالک می‌تواند روی هر نوعی موجودی ردیابی کند). در هر سفارش پرداخت‌شده به‌صورت اتمیک کم می‌شود؛ ردیف با مقدار ۰ در لیست خریدار حذف می‌شود («ناموجود»).
- `cost_price` (nullable): قیمت تمام‌شده‌ی هر واحد (تومان) فقط برای گزارش سود (`bot/inventory.py`) — هرگز به خریدار نشان داده نمی‌شود. `None` = نامعلوم، در این صورت سود برای این محصول محاسبه نمی‌شود.
- `import_code` (`String(50)`, nullable): وقتی این ردیف توسط ابزار «Import as Products» گروهی از یک ستون Code در اکسل upsert شده باشد ست می‌شود (`bot/shop_import.py`) — آپلود دوباره‌ی همان فایل این ردیف‌ها را جای‌گزین می‌کند نه تکراری می‌سازد. `None` برای محصولاتی که دستی یا با ایمپورتر قدیمی Content List ساخته شده‌اند.
- رابطه: `bot`.

### `class ShopSettings`
جدول `shop_settings` — یک ردیف به‌ازای هر ربات: خریداران چگونه می‌توانند پرداخت کنند. هرکدام می‌تواند تنظیم‌نشده باشد که یعنی آن روش پرداخت اصلاً پیشنهاد نمی‌شود.
- `bot_id` (کلید اصلی و FK هم‌زمان — رابطه‌ی یک‌به‌یک با `built_bots`).
- `zarinpal_merchant_id`, `card_number` (هر دو `EncryptedString`), `card_holder_name` (رمزنگاری‌نشده).
- `stripe_secret_key` (`EncryptedString`): معادل بین‌المللی زرین‌پال — Stripe Checkout، به دلار قیمت‌گذاری می‌شود (در این مسیر `Product.price` به‌عنوان دلار کامل تلقی می‌شود، برخلاف مسیر زرین‌پال که تومان است).
- `crypto_wallet_address` (`EncryptedString`), `crypto_network_label` (مثل `"USDT (TRC20)"`), `ton_wallet_address` (`EncryptedString`): جریان دستی «خریدار می‌فرستد، رفرنس تراکنش را ارسال می‌کند، مالک تأیید می‌کند» (`bot/shop.py:submit_manual_payment`) — عمداً بدون تأیید روی زنجیره، چون یک چک خودکار اشتباه هرجور که باشد ریسک پول واقعی دارد (چه تأیید نادرست، چه بلوکه کردن نادرست).
- `free_preview_limit` (`Integer`, default `1`): تعداد آیتم premium که یک مشترک می‌تواند پیش از الزام اشتراک، رایگان باز کند.
- `default_unlock_price` (nullable): قیمت پیش‌فرض تکی (تومان) وقتی `ContentItem.unlock_price` تنظیم نشده باشد. `None` هم اینجا یعنی خرید تکی هیچ‌جا پیشنهاد نمی‌شود.
- `original_default_unlock_price`: مقدار پیش از کمپین.
- `invoice_business_name`, `invoice_logo_url`, `invoice_address`, `invoice_footer_note`: برندسازی فاکتور (`bot/shop.py:generate_invoice`)، همه اختیاری با fallback به پیش‌فرض ساده‌ی «easymakebot»؛ رمزنگاری‌نشده چون قرار است روی سندی که به خریدار داده می‌شود چاپ شود.
- رابطه: `bot`.

### `class PriceCampaign`
جدول `price_campaigns` — یک تغییر قیمتی زمان‌دار و بربنیاد کل ربات (حراج، یا افزایش موقت). وقتی یک کمپین `active` است، هر `Product.price`/`ContentItem.unlock_price`/`ShopSettings.default_unlock_price` مربوط به آن ربات با مقدار تعدیل‌شده جای‌گزین می‌شود، و مقدار پیش از کمپین در ستون `original_*` متناظر ذخیره می‌شود. وقتی `ends_at` بگذرد (چک‌شده توسط `bot/runtime.py:run_campaign_expiry_loop`) — یا مالک زودتر آن را پایان بدهد — هر `original_*` عیناً بازگردانده می‌شود و `status` به `ended` می‌رود. حداکثر یک ردیف `active` به‌ازای هر ربات (اجرا در کد `bot/shop.py:start_price_campaign` + ایندکس یکتای partial اضافه‌شده در `bot/db/base.py`).
- `direction` (`String(10)`): `"discount"` یا `"markup"`.
- `percent` (`Integer`): بین ۱ تا ۹۰ برای تخفیف، ۱ تا ۵۰۰ برای افزایش.
- `status` (`String(10)`, default `"active"`): `"active"` یا `"ended"`.
- `starts_at`, `ends_at`, `ended_at` (nullable).

### `class Order`
جدول `orders` — یک تلاش خرید؛ در وضعیت `pending` تا پرداخت تأیید شود (verify زرین‌پال، یا تأیید مالک روی ارسال کارت‌به‌کارت)، سپس بر اساس `Product.product_type` تحویل داده می‌شود (`bot/shop.py:fulfill_order`).
- `product_id`, `buyer_telegram_id`.
- `price` (`Integer`): اسنپ‌شات `Product.price` در لحظه‌ی خرید (تا تغییر بعدی قیمت محصول، سفارش‌های قبلی را تحت‌تأثیر قرار ندهد).
- `payment_method` (`String(20)`, nullable): `"zarinpal"` | `"card_to_card"` | `"stripe"` (و در عمل `"crypto"`/`"ton"` هم از طریق مسیر manual).
- `status` (`String(20)`, default `"pending"`): `"pending"` → `"paid"` → `"fulfilled"`، یا `"rejected"` (فقط برای کارت‌به‌کارت).
- `zarinpal_authority`, `zarinpal_ref_id`, `transaction_ref`, `stripe_session_id` (همه nullable، برای ردیابی هر درگاه).
- `shipping_method`, `shipping_name`, `shipping_phone`, `shipping_address` (nullable، فقط برای محصولات فیزیکی پر می‌شوند).
- `invoice_number` (nullable).
- `checkout_id` (FK به `checkouts.id`, nullable): فقط برای سفارشی که از مرحله‌ی «Checkout» سبد خرید ساخته شده ست می‌شود — `None` برای هر خرید مستقیم «🛒 Buy». چند سفارش که یک `checkout_id` مشترک دارند با هم در یک پرداخت پرداخت شده‌اند، اما هرکدام مستقل بر اساس `product_type` خودش تحویل داده می‌شود.
- روابط: `bot`, `product`.

### `class CartItem`
جدول `cart_items` — یک محصول که خریدار قبل از تسویه‌حساب به سبد خرید (به‌ازای هر ربات) اضافه کرده.
- `UniqueConstraint("bot_id", "buyer_telegram_id", "product_id", name="uq_cart_item")` — هر محصول فقط یک‌بار می‌تواند در سبد یک خریدار باشد.
- `bot_id`, `buyer_telegram_id`, `product_id`.

### `class Checkout`
جدول `checkouts` — یک پرداخت که چند `Order` را یک‌جا پوشش می‌دهد (مرحله‌ی «پرداخت همه» در سبد خرید) — همان فیلدهای ردیابی پرداخت `Order` را تکرار می‌کند. هیچ وضعیت `"fulfilled"` جداگانه‌ای اینجا نیست — بعد از پرداخت، هر `Order` وابسته مستقل و دقیقاً مثل یک خرید مستقیم بر اساس `product_type` خودش تحویل می‌شود.
- `total_price` (`Integer`): مجموع قیمت‌های اسنپ‌شات‌شده‌ی `Order`ها.
- `payment_method`, `status` (default `"pending"`), `zarinpal_authority`, `zarinpal_ref_id`, `stripe_session_id`, `transaction_ref`.

### `class LivePayment`
جدول `live_payments` — مالک یک ربات به **خود پلتفرم** برای فعال‌سازی/تمدید پنجره‌ی live ربات پرداخت می‌کند (`bot/platform_billing.py`) — عمداً از `Order`/`Checkout` بالا جداست، که آن‌ها جریان پول «مشتری‌های خود ربات که از فروشگاهش خرید می‌کنند» را ردیابی می‌کنند. همان شکل ردیابی پرداخت، اما یک جریان پولی کاملاً متفاوت.
- `plan_key` (`String(50)`), `days` (nullable — `None` یعنی دائمی), `price` (اسنپ‌شات در لحظه‌ی خرید), `currency` (`"toman"` | `"usd"`).
- `payment_method` (`String(20)`): `"zarinpal"` | `"stripe"` | `"ton"`.
- `status` (default `"pending"`), و فیلدهای ردیابی مشابه `zarinpal_authority`/`zarinpal_ref_id`/`stripe_session_id`/`transaction_ref`.

### `class BroadcastLog`
جدول `broadcast_logs` — رکوردی از یک پیام گروهی ارسال‌شده از مالک ربات ساخته‌شده به مشترکین آن ربات.
- `command_name` (`String(64)`).
- `text` (`EncryptedString`): متن broadcast رمزنگاری‌شده.
- `recipient_count` (`Integer`, default `0`): تعداد گیرندگان.
- `sent_at`.

---

## `bot/shop.py`

این فایل قلب منطق فروشگاهی پلتفرم است — تمام کد مرتبط با محصول، سفارش، سبد خرید، درگاه‌های پرداخت (Zarinpal، Stripe، کارت‌به‌کارت/کریپتو/TON دستی)، تحویل سفارش (`fulfill_order`)، کمپین‌های قیمتی، ایمپورت گروهی محصول، و تولید فاکتور PDF فارسی است. طبق docstring بالای فایل، **هیچ کد مربوط به handler تلگرام اینجا نیست** — این ماژول توسط `bot/runtime.py` (تعامل چت با خریدار/مالک) و `bot/webapp_server.py` (کال‌بک HTTP زرین‌پال) به‌عنوان یک لایه‌ی منطق تجاری مشترک استفاده می‌شود — دقیقاً همان تفکیکی که در `bot/content_nav.py` / `bot/flow_engine.py` هم رعایت شده.

در ابتدای فایل، ثابت‌های مهم:
- `ZARINPAL_REQUEST_URL`/`VERIFY_URL`/`STARTPAY_URL`: نقاط پایانی REST API نسخه‌ی v4 زرین‌پال. کامنت هشدار می‌دهد مبالغ ارسالی باید ریال باشند (`Product.price` تومان است، پس همیشه ضربدر ۱۰ می‌شود) و این مسیر هنوز با یک حساب واقعی merchant تست نشده — پیش از تکیه به آن با یک خرید واقعی تأیید شود.
- `STRIPE_CHECKOUT_URL`/`SESSION_URL`: تماس مستقیم با REST API استرایپ با `aiohttp` (بدون SDK رسمی استرایپ)، مشابه رویکرد زرین‌پال. برخلاف مسیر زرین‌پال (تومان)، در مسیر استرایپ `Product.price` به‌عنوان **دلار کامل** تلقی می‌شود — یک ساده‌سازی عمدی نسخه‌ی اول (بدون تنظیم ارز جداگانه به‌ازای هر ربات) برای فروشندگان خارج از ایران که به‌جای زرین‌پال/کارت‌به‌کارت، Stripe تنظیم می‌کنند.
- `TYPE_FIELDS`: دیکشنری فیلدهای اضافی مورد نیاز هنگام افزودن محصول، کلید بر اساس `product_type` — بین ویزارد محصول مستقل (`bot/handlers/tools/shop.py`) و شاخه‌ی «این آیتم محتوا را برای فروش علامت بزن» ویزارد Content List (`bot/handlers/tools/content_list.py`) مشترک است.
- `SHIPPING_METHODS`: لیست روش‌های ارسال (پست، ماهکس، پیک).
- `_FONT_NAME`/`_FONT_PATH`: در بارگذاری ماژول، فونت `Vazirmatn-Regular.ttf` (فونت فارسی) از `bot/assets/` با `pdfmetrics.registerFont` ثبت می‌شود تا reportlab بتواند فارسی درست رندر کند.

### `_fa(text: str) -> str`
- **چه‌کار می‌کند:** متن فارسی را `reshape` (اتصال درست حروف فارسی/عربی) و سپس با `get_display` (الگوریتم bidi) بازچینی می‌کند تا از راست‌به‌چپ درست نمایش داده شود.
- **چرا لازم است:** reportlab رشته‌ها را به‌صورت خام و چپ‌به‌راست، بدون آگاهی از اسکریپت رسم می‌کند، پس متن فارسی/عربی باید پیش از رسم دستی reshape/bidi شود. این تابع در همه‌ی توابع رسم فاکتور استفاده می‌شود.

### `async def get_products(bot_id) -> list[Product]`
- **چه‌کار می‌کند:** همه‌ی محصولات واقعی یک ربات را برمی‌گرداند (مرتب‌شده بر اساس `id`)، با فیلتر `Product.product_type != CONTENT_UNLOCK_TYPE` — یعنی محصولات مخفی «باز کردن تکی آیتم» هرگز جایی که مالک یا سبد خرید می‌بیند نمایان نمی‌شوند.

### `async def get_products_page(bot_id, offset=0, limit=30) -> tuple[list[Product], bool]`
- **چه‌کار می‌کند:** یک صفحه‌ی محدودشده از محصولات برمی‌گرداند به‌همراه `has_more`. با گرفتن `limit + 1` رکورد و بررسی این‌که آیا بیش از `limit` برگشته، `has_more` را بدون کوئری `COUNT` جدا محاسبه می‌کند.
- **چرا لازم است:** برای لیست «📦 Products» ابزار Shop که یک کیبورد اینلاین می‌سازد، و تلگرام کیبوردی با بیش از چند ده دکمه را رد می‌کند (`bot/keyboards.py:shop_products_keyboard`). `get_products` بدون محدودیت باقی می‌ماند برای مصرف‌کننده‌هایی که فقط لیست کامل (مثل شمارش/بررسی وجود) یا مجموعه‌ی از قبل کوچک می‌خواهند.

### `async def get_standalone_products(bot_id) -> list[Product]`
- **چه‌کار می‌کند:** محصولاتی که به هیچ `ContentItem` وصل نیستند را برمی‌گرداند — با یک subquery روی `ContentItem.product_id` که `NOT NULL` است، و فیلتر `Product.id.not_in(linked_ids)`.
- **چرا لازم است:** تا بلوک/دستور flow «shop» آیتم‌هایی که از قبل از طریق بلوک «content_list» با دکمه‌ی Buy قابل مرور هستند را تکرار نکند. محصولات متصل به محتوا همچنان به‌طور کامل از لیست Products ابزار چت Shop قابل مدیریت هستند.

### `async def upsert_products_from_import(bot_id, items: list[dict]) -> dict`
- **چه‌کار می‌کند:** ردیف‌های تجزیه‌شده از یک فایل اکسل (توسط `bot/shop_import.py:parse_products_workbook`) را روی جدول `products` اعمال می‌کند:
  1. ابتدا همه‌ی محصولات موجود این ربات که `import_code` غیر `None` دارند را می‌خواند و یک دیکشنری `code_to_product` می‌سازد.
  2. برای هر `item` در `items`: اگر `action == "delete"` باشد، محصول متناظر با آن کد حذف می‌شود (اگر وجود داشته باشد) و `deleted` افزایش می‌یابد.
  3. وگرنه اگر `item["code"]` با یک `import_code` موجود مطابقت داشته باشد، آن ردیف به‌جا (in place) با فیلدهای جدید به‌روزرسانی می‌شود (`updated`+۱).
  4. وگرنه یک `Product` جدید با `product_type="physical"` و `import_code=item["code"]` ساخته می‌شود (`created`+۱)، و بلافاصله در `code_to_product` هم اضافه می‌شود تا اگر همان فایل دو ردیف با کد یکسان داشته باشد، ردیف دوم به‌جای ساخت تکراری، همین ردیف تازه‌ساخته را به‌روز کند.
- **چرا `product_type="physical"` پیش‌فرض است:** ایمپورتر هیچ فیلدی برای انتخاب مکانیزم تحویل ندارد؛ مالکی که محصول دیجیتال/دسترسی/اشتراک با تحویل تکی می‌خواهد باید همچنان از ویزارد دستی «Add Product» استفاده کند.
- **الگو:** این منطق دقیقاً آینه‌ی قانون add-vs-edit در `bot/content_nav.py:upsert_item` است، فقط به‌جای `item_id` حل‌شده، بر اساس `import_code` کار می‌کند.
- **موارد خاص:** خروجی `{"created": n, "updated": n, "deleted": n, "skipped": n}` را برمی‌گرداند اما در بدنه‌ی تابع کلید `"skipped"` هرگز مقداردهی نمی‌شود (dict برگشتی فاقد این کلید خواهد بود مگر این‌که در جای دیگری اضافه شود) — این احتمالاً یک ناهم‌خوانی جزئی بین docstring و پیاده‌سازی است. همه‌ی تغییرات در یک `session` و یک `commit()` نهایی اتمی انجام می‌شود.

### `async def get_product(product_id) -> Product | None`
یک محصول را با `id` برمی‌گرداند، یا `None`.

### `async def get_order(order_id) -> Order | None`
یک سفارش را با `id` برمی‌گرداند، یا `None`.

### `async def list_recent_orders(bot_id, limit=20) -> list[Order]`
آخرین سفارش‌های یک ربات را نزولی بر اساس `created_at` برمی‌گرداند.

### `async def get_shop_settings(bot_id) -> ShopSettings | None`
تنظیمات فروشگاه یک ربات را برمی‌گرداند (یا `None` اگر هنوز ساخته نشده).

### `async def _get_or_create_settings(session, bot_id) -> ShopSettings`
- **چه‌کار می‌کند:** اگر `ShopSettings` برای این ربات وجود نداشته باشد، یک ردیف خالی می‌سازد، `session.add` و `flush` می‌کند (تا بدون commit کامل هم بتوان بلافاصله از آبجکت استفاده کرد) و برمی‌گرداند. یک تابع کمکی داخلی است که یک `session` از بیرون می‌گیرد (بر خلاف بقیه‌ی توابع که خودشان `session` باز می‌کنند) — چون فراخوان‌ها می‌خواهند در همان تراکنش تغییرات دیگری هم اعمال کنند.

### `async def get_default_unlock_price(bot_id) -> int | None`
مقدار `ShopSettings.default_unlock_price` را برمی‌گرداند، یا `None` اگر تنظیمات اصلاً وجود نداشته باشد.

### `async def set_default_unlock_price(bot_id, price: int | None) -> None`
- **چه‌کار می‌کند:** قیمت پیش‌فرض بازکردن تکی سطح-ربات را ست می‌کند. اگر یک `PriceCampaign` فعال در حال اجرا باشد **و** `settings.original_default_unlock_price` از قبل مقداری داشته باشد (یعنی این کمپین از قبل روی این تنظیم اثر گذاشته)، به‌جای نوشتن مستقیم روی `default_unlock_price`، مقدار جدید را در `original_default_unlock_price` (خط پایه‌ی پیش از کمپین) ذخیره می‌کند و مقدار «زنده» را با اعمال تعدیل کمپین (`pricing.adjusted_price`) محاسبه می‌کند. در غیر این صورت (کمپینی در جریان نیست) مستقیماً `default_unlock_price` را می‌نویسد.
- **چرا این‌طور است:** اگر مالک وسط یک کمپین فعال قیمت پایه را عوض کند، باید همچنان تخفیف/افزایش کمپین روی مقدار جدید اعمال شود و مقدار «اصلی» که در پایان کمپین بازگردانده می‌شود هم درست همین مقدار جدید باشد، نه مقدار قدیمی‌تر.

### `async def ensure_unlock_product(bot_id, item: ContentItem, price: int) -> Product`
- **چه‌کار می‌کند:** محصول مخفی پشت دکمه‌ی «باز کردن تکی» یک `ContentItem` را get-or-create می‌کند:
  1. به‌جای اعتماد به `item.product_id` که ممکن است در حافظه قدیمی باشد، مستقیماً از دیتابیس `ContentItem.product_id` را می‌خواند تا فراخوانی‌های تکراری دقیقاً همان محصول مخفی را دوباره استفاده کنند، نه این‌که هربار یکی تازه بسازند.
  2. اگر محصولی با آن id و `product_type == CONTENT_UNLOCK_TYPE` پیدا شد، آن را می‌گیرد؛ وگرنه `product = None`.
  3. کمپین فعال ربات را چک می‌کند؛ اگر فعال باشد، `live_price = pricing.adjusted_price(price, ...)` و `original_price = price` محاسبه می‌شود (پارامتر `price` ورودی همیشه قیمت **پیش از کمپین** است).
  4. اگر محصول وجود نداشت، یک `Product` جدید با `product_type=CONTENT_UNLOCK_TYPE` ساخته و به `item.product_id` وصل می‌شود (با یک خواندن دوباره‌ی `db_item` از دیتابیس، نه استفاده از `item` ورودی، تا از حالت `detached`/stale جلوگیری شود).
  5. اگر از قبل وجود داشت، `name`/`description`/`delivery_file_url` به‌روزرسانی می‌شوند؛ اما قیمت **فقط** اگر خط پایه واقعاً تغییر کرده باشد بازنویسی می‌شود (`baseline = product.original_price if ... else product.price`؛ `if baseline != price:`) — تا یک تعدیل کمپین از قبل اعمال‌شده خراب نشود.
- **موارد خاص:** توجه شود که این تابع خودش `session.commit()` می‌کند و در انتها `session.refresh(product)` می‌کند تا آبجکت برگشتی از حالت stale خارج شود.

### بخش کمپین قیمتی (Time-boxed price campaigns)

#### `async def get_active_campaign(bot_id) -> PriceCampaign | None`
کمپین فعال (`status == "active"`) یک ربات را برمی‌گرداند، یا `None`.

#### `async def start_price_campaign(bot_id, direction, percent, days) -> PriceCampaign | None`
- **چه‌کار می‌کند:**
  1. اگر از قبل یک کمپین `active` برای این ربات وجود داشته باشد، فوراً `None` برمی‌گرداند (باید اول پایان یابد).
  2. یک تابع محلی `adj(base)` تعریف می‌کند که `pricing.adjusted_price` را با `direction`/`percent` صدا می‌زند.
  3. همه‌ی `Product`های ربات را می‌خواند؛ برای هرکدام `p.original_price = p.price` (اسنپ‌شات) سپس `p.price = adj(p.price)`.
  4. همه‌ی `ContentItem`های ربات که `unlock_price is not None` دارند را همین‌طور اسنپ‌شات و تعدیل می‌کند.
  5. اگر `ShopSettings.default_unlock_price` مقدار دارد، آن را هم اسنپ‌شات و تعدیل می‌کند.
  6. یک ردیف `PriceCampaign(status="active", starts_at=now, ends_at=now+timedelta(days=days))` می‌سازد، ذخیره و برمی‌گرداند.
- **موارد خاص:** همه‌ی این کارها در یک `session`/`commit` واحد انجام می‌شود — یعنی اتمیک است؛ اگر خطایی وسط رخ دهد، هیچ قیمتی نصفه‌نیمه تغییر نمی‌کند.

#### `async def _revert_campaign(session, campaign: PriceCampaign) -> None`
- **چه‌کار می‌کند:** با سه دستور `UPDATE` گروهی (نه select-then-loop) هر سه جدول را یک‌جا بازمی‌گرداند:
  - `products`: هر ردیفی که `original_price` غیر `NULL` دارد و متعلق به `campaign.bot_id` است، `price = original_price` و `original_price = NULL` می‌شود.
  - همین کار برای `content_items.unlock_price`/`original_unlock_price`.
  - همین کار برای `shop_settings.default_unlock_price`/`original_default_unlock_price`.
  - سپس `campaign.status = "ended"` و `campaign.ended_at = now()` ست می‌شود (این یک تابع داخلی است، `commit` نمی‌کند — فراخوان مسئول commit است).
- **چرا با `UPDATE` مستقیم به‌جای select+loop:** کارآمدتر است و در سطح دیتابیس یک‌باره اعمال می‌شود؛ ستون‌های `Product.original_price`/`ContentItem.original_unlock_price` به‌عنوان مقدار سمت راست `.values()` مستقیماً به SQL منتقل می‌شوند (SQLAlchemy Core-level expression update).

#### `async def end_price_campaign(bot_id) -> bool`
کمپین فعال ربات را (اگر باشد) با `_revert_campaign` بازمی‌گرداند و `True` برمی‌گرداند؛ اگر کمپینی فعال نبود `False`.

#### `async def expire_due_campaigns() -> list[uuid.UUID]`
- **چه‌کار می‌کند:** همه‌ی کمپین‌های `active` که `ends_at <= now()` دارند را پیدا می‌کند، هرکدام را با `_revert_campaign` برمی‌گرداند، و لیست `bot_id`های تحت‌تأثیر را برمی‌گرداند (برای لاگ کردن). فقط اگر حداقل یک کمپین منقضی پیدا شود `commit()` می‌کند.
- **ارتباط با بقیه‌ی پروژه:** طبق کامنت، این تابع به‌صورت دوره‌ای (timer) از `bot/runtime.py` صدا زده می‌شود.

### `async def create_order(bot_id, product_id, buyer_telegram_id) -> Order | None`
- **چه‌کار می‌کند:** یک `Order` جدید در وضعیت `"pending"` می‌سازد با `price=product.price` (اسنپ‌شات لحظه‌ای).
- **موارد خاص/edge case:**
  - اگر محصول وجود نداشته باشد یا `product.bot_id != bot_id` باشد، `None` برمی‌گرداند (محافظت در برابر دستکاری/عدم تطابق ربات).
  - اگر `stock_quantity is not None and stock_quantity <= 0`، سفارش ساخته **نمی‌شود** و `None` برمی‌گردد (کامنت صریح می‌گوید: موجودی فقط در لحظه‌ی fulfillment کم می‌شود، اما هرگز زیر صفر فروخته نمی‌شود — یعنی این چک در `create_order` صرفاً یک محافظ ورودی سریع است، محافظ واقعی در برابر race condition در `_decrement_stock` با شرط `WHERE stock_quantity > 0` است).
  - **race condition بالقوه:** این چک اولیه‌ی `stock_quantity <= 0` خودش atomically محافظت نمی‌کند — دو خریدار می‌توانند هم‌زمان این چک را با موفقیت رد کنند وقتی فقط ۱ عدد باقی مانده، و هر دو یک `Order` بسازند؛ اما چون کاهش واقعی موجودی در `_decrement_stock` با یک `UPDATE ... WHERE stock_quantity > 0` اتمیک انجام می‌شود، فقط یکی از آن دو سفارش واقعاً موجودی را کم می‌کند (دیگری موجودی صفر پیدا می‌کند و `UPDATE` او هیچ ردیفی را تغییر نمی‌دهد) — یعنی موجودی هرگز منفی نمی‌شود، اما ممکن است دو سفارش پرداخت‌شده برای یک عدد آخر کالای فیزیکی وجود داشته باشد که باید دستی توسط مالک حل شود (این پروژه چنین حالتی را صراحتاً مدیریت نمی‌کند).

### بخش سبد خرید (Cart)

#### `async def get_cart_items(bot_id, buyer_telegram_id) -> list[tuple[CartItem, Product]]`
یک `JOIN` بین `CartItem` و `Product` انجام می‌دهد و لیست جفت‌ها را مرتب بر اساس `CartItem.id` برمی‌گرداند.

#### `async def add_to_cart(bot_id, buyer_telegram_id, product_id) -> bool`
- **چه‌کار می‌کند:** اگر محصول به این ربات تعلق نداشته باشد یا از قبل در سبد باشد، `False` (no-op) برمی‌گرداند؛ وگرنه یک `CartItem` جدید می‌سازد و `True` برمی‌گرداند.

#### `async def remove_from_cart(cart_item_id, bot_id, buyer_telegram_id) -> None`
یک آیتم سبد را حذف می‌کند، فقط اگر `id` + `bot_id` + `buyer_telegram_id` هرسه مطابقت داشته باشند (محافظت در برابر حذف سبد کاربر دیگر).

#### `async def get_checkout(checkout_id) -> Checkout | None`
یک `Checkout` را با `id` برمی‌گرداند.

#### `async def create_checkout(bot_id, buyer_telegram_id) -> Checkout | None`
- **چه‌کار می‌کند:**
  1. آیتم‌های سبد خریدار را می‌خواند و آن‌هایی که هنوز موجودند (`stock_quantity is None or > 0`) را جدا می‌کند (`available`).
  2. اگر `available` خالی باشد (سبد خالی یا همه چیز ناموجود)، `None` برمی‌گرداند.
  3. `total_price` را از جمع `product.price`های موجود محاسبه می‌کند.
  4. یک `Checkout` می‌سازد، `flush` می‌کند تا `checkout.id` تخصیص یابد (قبل از این‌که `Order`های وابسته آن را رفرنس بدهند).
  5. برای هر آیتم موجود، یک `Order` با `checkout_id=checkout.id` و `price=product.price` (اسنپ‌شات) می‌سازد و `CartItem` متناظر را حذف می‌کند.
  6. آیتم‌های سبد که ناموجود بودند را هم (که در `available` نبودند) در یک حلقه‌ی جدا حذف می‌کند — تا در سبد خرید باقی نمانند و باعث سردرگمی در تلاش بعدی checkout نشوند.
  7. `commit` می‌کند و `Checkout` را برمی‌گرداند.
- **الگوی طراحی:** «graceful-omit» — آیتم ناموجود مانع پرداخت آیتم‌های موجود نمی‌شود، فقط بی‌صدا حذف می‌شود، مطابق فلسفه‌ی کل ماژول.

### توابع کمکی زرین‌پال

#### `async def _zarinpal_request(merchant_id, amount_rial, description, callback_url) -> str | None`
- **چه‌کار می‌کند:** با `aiohttp` یک `POST` به `payment/request.json` می‌زند با `timeout=15s`. اگر استثنایی رخ دهد (شبکه، JSON نامعتبر و…) لاگ می‌کند (`logger.exception`) و `None` برمی‌گرداند. اگر پاسخ `authority` نداشته باشد، هشدار می‌دهد و `None` برمی‌گرداند. تنها نقطه‌ای در کل فایل است که واقعاً با این endpoint صحبت می‌کند؛ هم مسیر تک-Order و هم مسیر Checkout از آن استفاده می‌کنند.

#### `async def _zarinpal_verify(merchant_id, amount_rial, authority) -> dict | None`
مشابه بالا، به `verify.json` پست می‌کند. کد `100` (تأیید تازه) یا `101` (از قبل تأیید شده) موفق تلقی می‌شود؛ هرچیز دیگری یا خطای شبکه، `None` برمی‌گرداند.

#### `async def start_zarinpal_payment(order, callback_base_url) -> str | None`
- **چه‌کار می‌کند:** تنظیمات فروشگاه را می‌خواند؛ اگر `zarinpal_merchant_id` تنظیم نشده باشد `None`. محصول را می‌خواند (برای نام در توضیحات پرداخت). `_zarinpal_request` را با `order.price * 10` (تبدیل تومان به ریال) و `callback_url` شامل `order_id` صدا می‌زند. در صورت موفقیت، `order.payment_method = "zarinpal"` و `order.zarinpal_authority` را در یک `session` جدا ذخیره می‌کند و URL شروع پرداخت (`ZARINPAL_STARTPAY_URL`) را برمی‌گرداند.

#### `async def verify_zarinpal_payment(authority) -> Order | None`
- **چه‌کار می‌کند و چرا idempotent است:**
  1. سفارش را با `zarinpal_authority` پیدا می‌کند؛ اگر نبود `None`.
  2. **اگر `order.status != "pending"` است، بلافاصله همان `order` را برمی‌گرداند بدون هیچ کار دیگری** — این خط کلید idempotency است، چون کامنت صریح می‌گوید «Zarinpal can hit the callback more than once» (زرین‌پال ممکن است کال‌بک را بیش از یک‌بار بزند). چون اولین بار وضعیت به `"paid"` تغییر می‌کند، فراخوانی‌های بعدی بلافاصله همین‌جا متوقف می‌شوند و دیگر `_zarinpal_verify` یا `fulfill_order` دوباره اجرا نمی‌شود.
  3. تنظیمات فروشگاه را چک می‌کند؛ اگر merchant تنظیم نشده، همان `order` (بدون تغییر) برمی‌گردد.
  4. `_zarinpal_verify` را صدا می‌زند؛ اگر `None` بود (رد یا خطا)، `order` بدون تغییر برمی‌گردد (باقی می‌ماند `pending`، امکان تلاش بعدی هست).
  5. در صورت موفقیت، `order.status = "paid"` و `zarinpal_ref_id` را در یک `session` جدا ذخیره می‌کند و رکورد را رفرش می‌کند.
  6. `BuiltBot` مربوطه را می‌خواند تا `token`ش را بگیرد، یک نمونه‌ی موقت `Bot(token=built_bot.token, session=make_session())` می‌سازد (`bot/session.py:make_session` یک `AiohttpSession` تازه برمی‌گرداند)، `fulfill_order` را با آن صدا می‌زند، و در `finally` حتماً `session.close()` می‌کند تا کانکشن HTTP نشتی نکند.
  7. چون `fulfill_order` وضعیت/شماره‌فاکتور را روی `session` خودش تغییر می‌دهد، آبجکت `order` محلی دیگر تازه نیست («stale»، هنوز `"paid"` نشان می‌دهد نه `"fulfilled"`)، پس در انتها `get_order(order.id)` دوباره از دیتابیس خوانده می‌شود تا خروجی درست باشد.
- **موارد خاص/race condition:** اگر دو کال‌بک همزمان (نه پشت‌سرهم) برسند، هردو ممکن است هم‌زمان `order.status` را `"pending"` ببینند (چون خواندن اول در یک `session` جدا از نوشتن است) و هر دو سعی کنند verify/fulfill کنند — این کد **محافظت سطح دیتابیس (مثل قفل ردیف یا شرط `WHERE status='pending'` در UPDATE)** ندارد؛ محافظت صرفاً منطقی و «به‌احتمال زیاد کافی» است چون در عمل کال‌بک‌های زرین‌پال به‌ندرت واقعاً هم‌زمان می‌رسند، ولی از نظر تئوری یک پنجره‌ی کوچک race وجود دارد که می‌تواند منجر به دو بار اجرای `fulfill_order` شود (به همین دلیل idempotency خود `fulfill_order` هم مهم است — پایین‌تر توضیح داده می‌شود).

### توابع کمکی Stripe

#### `async def _stripe_create_session(secret_key, amount_cents, description, success_url, cancel_url) -> tuple[str, str] | None`
یک `Checkout Session` با `mode="payment"` می‌سازد (پارامترهای فرم‌مانند به سبک Stripe REST API، بدون SDK)، `(session_id, checkout_url)` برمی‌گرداند یا `None` روی خطا/نبود این دو کلید در پاسخ.

#### `async def _stripe_retrieve_session(secret_key, session_id) -> dict | None`
یک `GET` به session endpoint می‌زند و JSON خام را برمی‌گرداند (یا `None` روی خطا).

#### `async def start_stripe_payment(order, callback_base_url) -> str | None`
مشابه `start_zarinpal_payment` اما با Stripe: `order.price * 100` (دلار به سنت)، `success_url` شامل placeholder تلگرام-استایل `{CHECKOUT_SESSION_ID}` که Stripe خودش پر می‌کند، `cancel_url` شامل `order_id`. در موفقیت `payment_method="stripe"` و `stripe_session_id` را ذخیره می‌کند.

#### `async def verify_stripe_payment(session_id) -> Order | None`
دقیقاً همان الگوی `verify_zarinpal_payment` (شامل همان چک `status != "pending"` برای idempotency، همان الگوی `Bot` موقت + `fulfill_order` + بازخوانی نهایی)، فقط شرط موفقیت `data.get("payment_status") != "paid"` است به‌جای کد ۱۰۰/۱۰۱ زرین‌پال.

### مسیرهای Checkout (سبد خرید) — «آینه»‌ی مسیرهای بالا

کامنت بالای این بخش صراحتاً می‌گوید این‌ها «همان کمک‌کننده‌های درگاه (`_zarinpal_request`/`_verify`, `_stripe_create_session`/`_retrieve_session`)، همان شکل، اما پرداخت هم‌زمان همه‌ی `Order`های یک `Checkout`» هستند.

#### `async def start_zarinpal_checkout(checkout, callback_base_url) -> str | None`
مثل `start_zarinpal_payment` اما با `checkout.total_price * 10` و توضیح ثابت `"Cart checkout"`؛ `callback_url` شامل `checkout_id` (نه `order_id`).

#### `async def verify_zarinpal_checkout(authority) -> Checkout | None`
همان الگوی `verify_zarinpal_payment` (شامل چک idempotency `status != "pending"`)، اما در پایان `fulfill_checkout` را صدا می‌زند نه `fulfill_order`.

#### `async def start_stripe_checkout(checkout, callback_base_url) -> str | None`
مثل `start_stripe_payment` با `checkout.total_price * 100` و `"Cart checkout"`.

#### `async def verify_stripe_checkout(session_id) -> Checkout | None`
همان الگوی `verify_stripe_payment` اما روی `Checkout` و صدا زدن `fulfill_checkout`.

### پرداخت دستی (کارت‌به‌کارت / کریپتو / TON)

#### `async def submit_manual_payment(order_id, payment_method, transaction_ref) -> Order`
- **چه‌کار می‌کند:** `order.payment_method` و `order.transaction_ref` را ذخیره می‌کند (بدون تغییر `status`). طبق docstring، `payment_method` یکی از `"card_to_card" | "crypto" | "ton"` است — هر سه از همین جریان یکسان استفاده می‌کنند: خریدار بیرون از پلتفرم پول می‌فرستد، یک مرجع تراکنش ثبت می‌کند، و مالک تأیید/رد می‌کند.

#### `async def approve_manual_payment(bot, order_id) -> Order`
- **چه‌کار می‌کند:** `order.status = "paid"` می‌کند و commit می‌کند، سپس `fulfill_order(bot, order_snapshot)` را صدا می‌زند و در پایان `get_order(order_id)` تازه را برمی‌گرداند (چون `fulfill_order` وضعیت را روی `session` خودش عوض می‌کند).
- **تفاوت با مسیرهای verify بالا:** اینجا `bot` از بیرون پاس داده می‌شود (چون فراخوان — یک هندلر تلگرام مالک — از قبل یک `Bot` معتبر در اختیار دارد)، نه ساختن یک `Bot` موقت جدید.

#### `async def reject_manual_payment(order_id) -> None`
`order.status = "rejected"` می‌کند (اگر سفارش وجود داشته باشد).

#### `async def submit_manual_checkout_payment(checkout_id, payment_method, transaction_ref) -> Checkout`
آینه‌ی `submit_manual_payment` روی `Checkout`.

#### `async def approve_manual_checkout(bot, checkout_id) -> Checkout`
آینه‌ی `approve_manual_payment`؛ `checkout.status="paid"`، سپس `fulfill_checkout`.

#### `async def reject_manual_checkout(checkout_id) -> None`
آینه‌ی `reject_manual_payment`.

### `async def save_shipping_info(order_id, method, name, phone, address) -> Order`
اطلاعات ارسال یک سفارش فیزیکی را ذخیره می‌کند (این تابع توسط ویزارد ارسال در `bot/runtime.py` بعد از این‌که خریدار روی دکمه‌ی «📦 Enter Shipping Info» بزند صدا زده می‌شود).

### `_invoice_number(order: Order) -> str`
- **چه‌کار می‌کند:** یک شماره فاکتور خوانا می‌سازد: ۶ کاراکتر اول hex از `bot_id` (با حروف بزرگ) + خط تیره + `order.id` با ۶ رقم صفر-پد شده. مثلاً `"A1B2C3-000042"`.

### `async def _decrement_stock(product_id) -> None`
- **چه‌کار می‌کند:** یک `UPDATE` اتمیک با شرط `WHERE Product.id == product_id AND stock_quantity IS NOT NULL AND stock_quantity > 0` که مقدار را ۱ واحد کم می‌کند.
- **چرا این‌طور نوشته شده (خیلی مهم برای concurrency):** این WHERE هم‌زمان دو کار می‌کند:
  1. اگر `stock_quantity` اصلاً `NULL` باشد (موجودی ردیابی نمی‌شود)، هیچ کاری انجام نمی‌شود.
  2. اگر `stock_quantity` از قبل `0` یا کمتر باشد، `UPDATE` هیچ ردیفی را match نمی‌کند و موجودی هرگز منفی نمی‌شود — این دقیقاً همان چیزی است که در بخش `create_order` به‌عنوان محافظ واقعی race condition اشاره شد؛ چون این عملیات در سطح خودِ دیتابیس اتمیک است (نه select-then-update در پایتون)، دو فراخوانی هم‌زمان `_decrement_stock` برای همان محصول با موجودی ۱، فقط یکی موفق به کم‌کردن می‌شود.

### `async def fulfill_order(bot: Bot, order: Order) -> None`

این یکی از حساس‌ترین توابع کل پروژه است چون **می‌تواند بیش از یک‌بار برای یک سفارش صدا زده شود** و باید idempotent (بی‌اثر در تکرار) بماند. منابعی که آن را صدا می‌زنند: `verify_zarinpal_payment`، `verify_stripe_payment`، `approve_manual_payment`، و به‌صورت غیرمستقیم `fulfill_checkout` (که به‌ازای هر `Order` مرتبط یک‌بار آن را صدا می‌زند).

- **مرحله به مرحله:**
  1. محصول سفارش را می‌خواند؛ اگر پیدا نشد (مثلاً حذف شده)، بی‌سروصدا برمی‌گردد (کاری انجام نمی‌شود).
  2. **مسیر فیزیکی ناقص:** اگر `product.product_type == "physical"` و `order.shipping_address` هنوز خالی است، به خریدار پیام «پرداخت تأیید شد، لطفاً اطلاعات ارسال را وارد کنید» با یک دکمه‌ی اینلاین `ship_info:{order.id}` می‌فرستد و **بلافاصله `return` می‌کند** — یعنی تحویل واقعی (و مهم‌تر، کاهش موجودی و ست‌شدن `status="fulfilled"`) اینجا اتفاق نمی‌افتد؛ اتفاق می‌افتد وقتی ویزارد ارسال در `bot/runtime.py` اطلاعات را جمع کند و **دوباره `fulfill_order` را صدا بزند** — این بار `order.shipping_address` پر است، پس این شرط رد می‌شود و ادامه‌ی تابع اجرا می‌شود. کامنت بالای تابع دقیقاً همین را توضیح می‌دهد: چرا کاهش موجودی (`_decrement_stock`) بعد از این `return` زودهنگام قرار گرفته — باید دقیقاً یک‌بار، فقط در فراخوانی‌ای که واقعاً تحویل نهایی انجام می‌دهد، اجرا شود.
  3. `_decrement_stock(product.id)` صدا زده می‌شود (اتمیک، طبق بالا).
  4. بر اساس `product.product_type` یکی از این شاخه‌ها اجرا می‌شود:
     - **`"digital"`**: پیام تأیید + `delivery_text` (اگر باشد) به‌صورت یک پیام ترکیبی ارسال می‌شود؛ اگر `delivery_file_url` باشد، در یک پیام جدا هم فرستاده می‌شود.
     - **`CONTENT_UNLOCK_TYPE`** (`"content_unlock"`): `ContentItem` متصل به این محصول را پیدا می‌کند. اگر پیدا شد، چک می‌کند آیا یک `ContentUnlock` با همین `(bot_id, subscriber_telegram_id, content_item_id)` از قبل وجود دارد یا نه — **این چک idempotency در سطح داده است**: اگر از قبل باز شده، رکورد تکراری اضافه نمی‌شود (وگرنه اجرای دوباره‌ی `fulfill_order` یک `UniqueConstraint("uq_content_unlock")` را نقض می‌کند و خطا می‌دهد). اگر وجود نداشت، یک `ContentUnlock(source="purchase")` می‌سازد. سپس پیام «Unlocked» + بدنه‌ی آیتم (اگر باشد) می‌فرستد، و لینک (از `product.delivery_file_url` یا در نبود آن `item.link_url`) در پیام جدا ارسال می‌شود.
     - **`"access"`**: `BotSubscriber` متناظر را پیدا می‌کند و `access_level` را به `product.access_level_name` تنظیم می‌کند؛ سپس پیام تأیید ارسال می‌شود. **توجه:** اگر `BotSubscriber` پیدا نشود (خریدار هرگز `/start` نزده)، هیچ خطایی داده نمی‌شود، فقط دسترسی اعطا نمی‌شود ولی پیام تأیید همچنان (خارج از بلوک `if subscriber is not None`) فرستاده می‌شود — این یک ناسازگاری بالقوه است (پیام می‌گوید «دسترسی تغییر کرد» حتی اگر واقعاً هیچ `BotSubscriber` رکوردی به‌روز نشده باشد).
     - **`"physical"`** (وقتی به اینجا می‌رسیم یعنی `shipping_address` از قبل پر است): فقط پیام «سفارش به‌زودی ارسال می‌شود» فرستاده می‌شود.
     - **`"subscription"`**: `BotSubscriber` را پیدا می‌کند؛ `base` را برابر «حداکثر بین الان و `subscription_until` فعلی (اگر هنوز نگذشته)» محاسبه می‌کند، سپس `new_until = base + timedelta(days=subscription_days)`. **چرا از «بیشینه‌ی الان/انقضای فعلی» شروع می‌شود، نه صرفاً `subscription_until` قدیمی:** تا تمدید **پیش از انقضا** روزهای جدید را روی زمان باقی‌مانده اضافه (stack) کند، نه این‌که آن را دور بریزد؛ اگر اشتراک از قبل منقضی شده باشد (`subscription_until < now`)، شمارش از «الان» شروع می‌شود نه از یک تاریخ گذشته. پیام تأیید فقط اگر `new_until is not None` (یعنی `BotSubscriber` پیدا شده باشد) فرستاده می‌شود.
  5. **پس از دیسپچ نوع محصول**، در یک `session` جدا: `order.status = "fulfilled"` ست می‌شود، و `order.invoice_number = row.invoice_number or _invoice_number(row)` — یعنی **فقط اگر شماره فاکتور قبلاً ست نشده باشد** یک شماره‌ی جدید تولید می‌شود؛ این هم بخشی از استراتژی idempotency است — اگر تابع دوباره صدا زده شود (که طبق طراحی این تابع اصلاً نباید در حالت عادی رخ دهد چون فراخوان‌ها `status != "pending"` را چک می‌کنند)، شماره فاکتور عوض نمی‌شود.
  6. در پایان، `generate_invoice(order)` صدا زده می‌شود و PDF نتیجه با `bot.send_document` به خریدار فرستاده می‌شود.
- **چرا و چطور idempotent نگه داشته شده (جمع‌بندی):** سه لایه محافظت وجود دارد:
  1. **لایه‌ی بیرونی (فراخوان‌ها):** `verify_zarinpal_payment`/`verify_stripe_payment`/معادل‌های checkout همگی قبل از verify کردن دوباره چک می‌کنند `order.status != "pending"` و اگر پرداخت از قبل تأیید شده، اصلاً `fulfill_order` را دوباره صدا نمی‌زنند. یعنی در مسیر عادی، `fulfill_order` روی یک سفارش **فقط یک‌بار واقعی** (به معنای «یک‌بار که واقعاً تا انتها می‌رود») اجرا می‌شود.
  2. **استثنای عمدی و طراحی‌شده:** تنها حالتی که `fulfill_order` **باید** دوباره روی همان سفارش صدا زده شود، مسیر کالای فیزیکی ناقص‌الاطلاعات است — جایی که خودِ همین تابع صراحتاً وسط کار `return` می‌کند و منتظر می‌ماند ویزارد ارسال دوباره صدایش بزند. برای همین مورد، ترتیب کد (کاهش موجودی *بعد* از این return زودهنگام) تضمین می‌کند که موجودی فقط در فراخوانی نهایی (که واقعاً تحویل می‌دهد) کم شود، نه در فراخوانی اول که فقط شماره‌شناسه‌ی سفارش را دارد ولی هنوز آدرس ندارد.
  3. **لایه‌ی داده (دفاع در عمق برای race واقعی/نادر):** حتی اگر به هر دلیلی (race condition نادر بین دو کال‌بک هم‌زمان، همان‌طور که در `verify_zarinpal_payment` توضیح داده شد) این تابع دوبار روی یک سفارش «paid» اجرا شود، دو محافظ داده مانع خرابی جدی می‌شوند: `_decrement_stock` با `WHERE stock_quantity > 0` هرگز کمتر از صفر نمی‌رود، و در مسیر `content_unlock`، چک `existing is None` قبل از `session.add(ContentUnlock(...))` مانع نقض `UniqueConstraint("uq_content_unlock")` و مانع «مصرف مضاعف سهمیه» می‌شود. با این حال، برای انواع `"digital"`/`"access"`/`"subscription"`/`"physical"` هیچ محافظ صریحی در برابر ارسال پیام دوباره یا (برای `subscription`) تمدید دوباره‌ی زمان اشتراک وجود ندارد — اگر واقعاً در آن پنجره‌ی race نادر دوبار اجرا شود، خریدار ممکن است دو پیام تحویل/دو فاکتور بگیرد یا اشتراکش دوبار تمدید شود؛ این ریسک پروژه آگاهانه با تکیه بر لایه‌ی اول (چک `status != "pending"`) کوچک نگه داشته، نه با قفل صریح ردیف یا تراکنش سریالایزبل.
- **ارتباط با فایل‌های دیگر:** `bot/runtime.py` (هندلر دکمه‌ی «Enter Shipping Info»، اطلاع‌رسانی کامنت پست‌ها)، `bot/premium_content.py` (مصرف‌کننده‌ی `ContentUnlock`/`subscription_until`)، `bot/inventory.py` (منطق نمایش/گزارش موجودی که از همین ستون‌ها تغذیه می‌شود).

### `async def fulfill_checkout(bot: Bot, checkout: Checkout) -> None`
- **چه‌کار می‌کند:**
  1. در یک `session`، `checkout.status = "paid"` ست و commit می‌شود.
  2. در یک `session` دوم، همه‌ی `Order`هایی که `checkout_id == checkout.id` دارند خوانده می‌شوند و همه‌شان `status = "paid"` می‌شوند (commit یک‌جا).
  3. سپس در یک حلقه، `fulfill_order(bot, order)` برای **هرکدام جداگانه** صدا زده می‌شود.
- **چرا وضعیت `Order` را صریحاً به `"paid"` ست می‌کند قبل از فراخوانی `fulfill_order`:** کامنت تأکید می‌کند این باید دقیقاً مثل رفتار `approve_manual_payment`/`verify_*_payment` باشد — که همیشه `Order.status = "paid"` را قبل از `fulfill_order` ست می‌کنند — چون یک کالای فیزیکی که پرداخت شده اما هنوز منتظر اطلاعات ارسال است باید `"paid"` بخواند، نه `"pending"` (که به‌غلط یعنی هنوز پرداخت نشده).
- **موارد خاص:** یک فاکتور PDF و یک پیام جدا **به‌ازای هر Order** فرستاده می‌شود، نه یک فاکتور ترکیبی برای کل Checkout (طبق کامنت، این تصمیم طراحی عمدی است). اگر یکی از `Order`ها در حلقه خطا بدهد (مثلاً `bot.send_document` fail شود)، بقیه‌ی `Order`های همان Checkout همچنان به‌صورت مستقل در فراخوانی‌های بعدی خودشان از طریق چک `status != "pending"`... در واقع اینجا دیگر `status` روی `"paid"` است نه `"pending"`، پس اگر `fulfill_checkout` نیمه‌کاره خطا بدهد و دوباره صدا زده شود (مثلاً یک retry دستی)، دیگر آن چک بیرونی معمول (`status != "pending"`) این تابع را متوقف نمی‌کند چون خود `fulfill_checkout` مستقیم از verify_* صدا زده می‌شود، ولی `fulfill_order` داخلی‌اش همچنان idempotency خودش (چک `ContentUnlock` موجود، `_decrement_stock` شرطی، `invoice_number` موجود) را دارد.

### `async def _fetch_logo_image(url: str) -> ImageReader | None`
- **چه‌کار می‌کند:** لوگوی برندسازی فاکتور را از `url` دانلود می‌کند (تایم‌اوت ۸ ثانیه)؛ اگر status کد HTTP غیر ۲۰۰ باشد یا هر استثنایی رخ دهد، `None` برمی‌گرداند.
- **چرا:** طبق کامنت، یک URL خراب/غیرقابل‌دسترس نباید هرگز کل تولید فاکتور را fail کند — همان فلسفه‌ی graceful-omit همه‌جای این ماژول: نبود لوگو یعنی فقط لوگو رسم نمی‌شود.

### `async def generate_invoice(order: Order) -> bytes`

تولید فاکتور PDF فارسی، احتمالاً پیچیده‌ترین بخش از نظر جزئیات چیدمان (layout).

- **مرحله به مرحله:**
  1. `product` و `settings` مربوط به سفارش خوانده می‌شوند.
  2. `payment_label`: یک دیکشنری نگاشت `order.payment_method` انگلیسی به برچسب فارسی (`"زرین‌پال"`, `"کارت به کارت"`, `"Stripe"` (بدون ترجمه), `"رمزارز"`, `"TON"`)؛ مقدار پیش‌فرض `"-"` اگر مقداری تطبیق نداشته باشد.
  3. اگر `settings.invoice_logo_url` تنظیم شده، `_fetch_logo_image` صدا زده می‌شود.
  4. یک بوم (`canvas.Canvas`) با اندازه‌ی A4 ساخته می‌شود. `right_margin`، `left_margin`، و `value_anchor` (لنگر ستون مقدار، ۵۵ میلی‌متر سمت چپ حاشیه‌ی راست) محاسبه می‌شوند.
  5. تابع داخلی `row(y_mm, label, value, size=12)`: **نکته‌ی مهم طراحی** که در کامنت توضیح داده شده — برچسب (label) و مقدار (value) به‌عنوان **دو رشته‌ی کاملاً جدا** رسم می‌شوند، هرکدام جداگانه از `_fa()` عبور می‌کنند، **نه این‌که اول به‌هم بچسبند و بعد یک‌جا reshape شوند**. دلیل: اگر `"برچسب: مقدار"` یک‌جا concatenate و بعد از `get_display()` (bidi) عبور کند، موقعیت مقدار (که معمولاً ASCII/عددی است، مثل مبلغ یا شناسه‌ی تلگرام) در رشته‌ی نهایی جابه‌جا می‌شود و reportlab+pypdf آن بخش را در رسم/استخراج به‌طور بی‌صدا از دست می‌دهند. با دو ستون لنگر‌شده‌ی جدا (`right_margin` برای برچسب، `value_anchor` برای مقدار) این مشکل کاملاً دور زده می‌شود و ضمناً این چیدمان استاندارد فاکتورهای دوزبانه هم هست. عرض هر رشته با `c.stringWidth(...)` محاسبه می‌شود تا از سمت راست به چپ درست تراز شود (چون متن فارسی راست‌چین است).
  6. تابع `title(y_mm, text, size=18)`: مشابه اما بدون ستون مقدار — فقط یک متن راست‌چین (برای عنوان فاکتور و خطوط پاورقی).
  7. تابع `wrapped_lines(text, max_width_mm, size)`: پیاده‌سازی دستی word-wrap — کلمات را یکی‌یکی به `current` اضافه می‌کند و اگر عرض `_fa(candidate)` از `max_width` بیشتر شود، خط را می‌بندد و کلمه‌ی جدید را شروع خط بعدی می‌کند. توجه: عرض‌سنجی روی متن reshape/bidi‌شده انجام می‌شود تا اندازه‌گیری دقیق باشد.
  8. اگر `logo` موجود باشد، با `c.drawImage(...)` در گوشه‌ی بالا-چپ (`left_margin`, نزدیک بالای صفحه) با ابعاد ۲۵×۲۵ میلی‌متر و `preserveAspectRatio=True` رسم می‌شود؛ هر استثنا (فرمت تصویر خراب/پشتیبانی‌نشده) بی‌صدا نادیده گرفته می‌شود تا فاکتور خراب نشود.
  9. عنوان فاکتور (`settings.invoice_business_name` یا پیش‌فرض `"فاکتور فروش"`) در `y=20mm` رسم می‌شود.
  10. اگر `settings.invoice_address` موجود باشد، با `wrapped_lines(..., 90, 10)` بسته‌بندی و خط‌به‌خط با `row()` رسم می‌شود (فقط خط اول برچسب `"آدرس:"` می‌گیرد، بقیه برچسب خالی).
  11. ردیف‌های اصلی فاکتور به‌ترتیب رسم می‌شوند، هرکدام `y += 10`: شماره فاکتور، تاریخ (`order.updated_at`, فرمت `%Y-%m-%d %H:%M` — **توجه:** از `updated_at` استفاده می‌شود نه `created_at`، چون `updated_at` زمان واقعی fulfillment/آخرین تغییر را نشان می‌دهد)، نام محصول، مبلغ (با کاما جداکننده‌ی هزارگان + واحد «تومان»)، روش پرداخت، شناسه‌ی خریدار (تلگرام).
  12. اگر `order.shipping_method` ست شده باشد (سفارش فیزیکی)، چهار ردیف اضافه (روش ارسال، گیرنده، تلفن، آدرس) رسم می‌شود.
  13. اگر `settings.invoice_footer_note` موجود باشد، در `y=280mm` (نزدیک پایین صفحه A4 که ۲۹۷mm ارتفاع دارد) با `wrapped_lines(..., 170, 9)` بسته‌بندی می‌شود و **حداکثر ۴ خط** (`footer_lines[:4]`) رسم می‌شود — این cap عمدی است تا یک یادداشت خیلی طولانی از پایین صفحه بیرون نزند.
  14. `c.showPage()` و `c.save()` صدا زده می‌شوند و بایت‌های PDF از `buffer.getvalue()` برگردانده می‌شوند.
- **موارد خاص/edge case:**
  - اگر `product is None` (محصول حذف شده)، در ردیف «محصول» مقدار `"-"` نشان داده می‌شود؛ تابع خطا نمی‌دهد.
  - اگر `settings is None` (فروشگاه هنوز تنظیمات ندارد)، عنوان پیش‌فرض و بدون آدرس/پاورقی/لوگو استفاده می‌شود — همه‌ی چک‌ها با `settings and settings.xxx` محافظت شده‌اند.
  - تابع تک‌صفحه‌ای طراحی شده (`c.showPage()` فقط یک‌بار) — اگر محتوا (مثلاً آدرس بسیار طولانی + پاورقی طولانی + اطلاعات ارسال) بیش از حد باشد، ممکن است خطوط از انتهای صفحه بیرون بزنند یا روی هم بیفتند؛ کدی برای صفحه‌بندی چندگانه (multi-page) وجود ندارد.
- **ارتباط با بقیه‌ی پروژه:** توسط `fulfill_order` صدا زده می‌شود؛ فونت از `bot/assets/Vazirmatn-Regular.ttf` می‌آید؛ برندسازی از `ShopSettings` (که در `bot/handlers/tools/shop.py` یا مشابه توسط مالک تنظیم می‌شود) خوانده می‌شود.

---

### جمع‌بندی ارتباط بین فایل‌ها

- `bot/db/base.py` زیرساخت اتصال و مهاجرت دستی را فراهم می‌کند؛ `bot/db/models.py` را import می‌کند تا مدل‌ها روی `Base` ثبت شوند.
- `bot/db/encrypted_types.py` توسط `bot/db/models.py` برای ستون‌های حساس (`token`, `phone_number`, `zarinpal_merchant_id`, `card_number`, `stripe_secret_key`, `crypto_wallet_address`, `ton_wallet_address`, `flow_definition`, `payload`, `text` در `BroadcastLog`) استفاده می‌شود.
- `bot/db/models.py` توسط تقریباً همه‌ی ماژول‌های منطقی پروژه (`bot/shop.py`, `bot/runtime.py`, `bot/premium_content.py`, `bot/inventory.py`, `bot/content_nav.py`, `bot/platform_billing.py`, `bot/admin_panel.py`, `bot/commerce_mode.py`, `bot/live.py`, `bot/guide.py` و غیره) به‌عنوان تعریف اسکیمای مشترک import می‌شود.
- `bot/shop.py` به `bot/pricing.py` (محاسبه‌ی قیمت تعدیل‌شده‌ی کمپین و فرمت نمایش)، `bot/session.py` (ساخت `AiohttpSession` برای نمونه‌ی موقت `Bot`)، و `bot/db/base.py`/`bot/db/models.py` وابسته است، و خودش توسط `bot/runtime.py` و `bot/webapp_server.py` مصرف می‌شود.
