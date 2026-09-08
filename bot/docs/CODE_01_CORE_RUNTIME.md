# مستندسازی فنی easymakebot — بخش هسته اجرا (bot/)

---

## `bot/main.py`

این فایل نقطه‌ی ورود (entry point) کل پلتفرم easymakebot است؛ یعنی همان ربات اصلی که خودِ کاربران با آن صحبت می‌کنند تا ربات‌های تلگرامی خودشان را بدون کدنویسی بسازند (نه ربات‌های ساخته‌شده توسط کاربران — آن‌ها را `bot/runtime.py` اجرا می‌کند). وظیفه‌ی این فایل، مقداردهی اولیه‌ی `Bot` و `Dispatcher` از aiogram 3، ثبت تمام روترها (`router`) به ترتیب اولویت درست، راه‌اندازی دیتابیس، روشن کردن ربات‌های از‌پیش‌ساخته‌شده (built bots)، اجرای task‌های پس‌زمینه (loop انقضای Live و کمپین قیمت)، بالا آوردن وب‌سرور Mini App، و در نهایت شروع polling خود ربات اصلی است.

### `async def _retry_on_network_error(coro_factory, *, attempts: int = 5, base_delay: float = 2.0)`
- **چه‌کار می‌کند:** یک تابع کمکی generic است که یک coroutine factory (یعنی تابعی بدون آرگومان که یک coroutine برمی‌گرداند، نه خودِ coroutine — چون coroutine فقط یک‌بار قابل await است و برای retry باید هر بار از نو ساخته شود) را می‌گیرد و آن را حداکثر `attempts` بار اجرا می‌کند. اگر `TelegramNetworkError` رخ دهد، با backoff نمایی (`base_delay * 2^(attempt-1)`، یعنی ۲، ۴، ۸، ۱۶ ثانیه...) صبر می‌کند و دوباره امتحان می‌کند. اگر در آخرین تلاش هم شکست بخورد، exception را دوباره raise می‌کند (`raise` بدون آرگومان در بلوک `except`).
- **پارامترها:** `coro_factory` تابع سازنده‌ی coroutine؛ `attempts` تعداد تلاش‌ها؛ `base_delay` تأخیر پایه به ثانیه.
- **موارد خاص/edge case:** طبق کامنت خود کد، این تابع برای پوشش دادن تماس‌های یک‌باره‌ی قبل از شروع polling (مثل `set_my_commands` و `delete_webhook`) نوشته شده، چون `dp.start_polling` خودش داخلی retry دارد ولی فقط بعد از شروع polling؛ قبل از آن یک خطای شبکه‌ی گذرا می‌توانست کل پروسه — از جمله همه‌ی ربات‌های ساخته‌شده‌ی در حال اجرا — را از کار بیندازد.

### `async def main() -> None`
- **چه‌کار می‌کند:** به ترتیب زیر عمل می‌کند:
  1. `config = load_config()` را از `bot/config.py` می‌خواند.
  2. یک نمونه‌ی `Bot` با `token=config.bot_token`، `session=make_session()` (از `bot/session.py`) و `default=DefaultBotProperties(parse_mode=ParseMode.HTML)` (یعنی همه‌ی پیام‌ها به‌طور پیش‌فرض HTML پارس می‌شوند مگر خلافش گفته شود) می‌سازد.
  3. یک `Dispatcher` با `MemoryStorage` برای FSM می‌سازد (state ماشین‌های حالت در حافظه نگه‌داری می‌شوند، نه Redis/دیتابیس).
  4. یک middleware با نام `_help_tip` را روی `dp.callback_query.outer_middleware` ثبت می‌کند (توضیح جدا در ادامه).
  5. روترها را به ترتیب خاصی با `dp.include_router(...)` ثبت می‌کند — این ترتیب حیاتی است چون aiogram روترها را به همان ترتیب ثبت، امتحان می‌کند تا اولین‌بار یک handler match شود.
  6. `await init_db()` از `bot/db/base.py` را صدا می‌زند تا جداول دیتابیس ساخته/آماده شوند.
  7. `await start_all_built_bots()` از `bot/runtime.py` را صدا می‌زند تا هر ربات ساخته‌شده‌ای که هنوز در بازه‌ی Live است، polling خودش را شروع کند.
  8. دو task پس‌زمینه با `asyncio.create_task` می‌سازد: `run_live_expiry_loop()` و `run_campaign_expiry_loop()` (هر دو از `bot/runtime.py`).
  9. `await start_webapp_server(config.bot_token, config.webapp_port)` را صدا می‌زند تا سرور Mini App ویژوال فلو بیلدر (`webapp/dist/`) و endpointهای `/api/flow` بالا بیاید.
  10. با `_retry_on_network_error` منوی دستورهای نیتیو تلگرام (`/start`، `/mybots`، `/newbot`، `/live`، `/help`) را با `bot.set_my_commands` ثبت می‌کند.
  11. با `_retry_on_network_error` وبهوک را حذف می‌کند (`delete_webhook(drop_pending_updates=True)`) تا مطمئن شود ربات در حالت polling است و آپدیت‌های معلق‌مانده را دور می‌ریزد.
  12. در نهایت `await dp.start_polling(bot)` را صدا می‌زند که تا ابد اجرا می‌ماند (event loop اصلی برنامه).
- **پارامترها:** ندارد.
- **موارد خاص/edge case:** توجه به کامنت‌های مهم داخل کد:
  - `/cancel` (یعنی `cancel_router`) اول از همه ثبت می‌شود تا بتواند از هر state دلخواهی خارج کند، صرف‌نظر از این‌که کدام state-scoped router بعداً می‌آید.
  - روترهای وابسته به state (منتظر ورودی متنی آزاد، مثلاً نام یک دستور که ممکن است دقیقاً `/start` باشد) باید **قبل از** `start_router` که فیلتر عمومی `CommandStart()` دارد ثبت شوند؛ وگرنه ورودی وسط یک flow چند مرحله‌ای اشتباهاً به‌عنوان دستور `/start` گلوبال تفسیر می‌شد.

#### middleware داخلی: `async def _help_tip(handler, event, data)`
- **چه‌کار می‌کند:** یک `outer_middleware` روی `dp.callback_query` است که دور تمام هندلرهای callback اجرا می‌شود. ابتدا `result = await handler(event, data)` را صدا می‌زند (یعنی اجازه می‌دهد هندلر واقعی کامل اجرا شود)، سپس تلاش می‌کند یک نکته‌ی راهنمای یک/دو خطی فارسی-انگلیسی زیر پاسخ بفرستد: `callback_data` رویداد را می‌خواند، بررسی می‌کند آیا `help_text.has_tip(key)` (از `bot/help_text.py`) برای آن کلید تعریف شده، زبان مالک را با `owner_prefers_persian` (از `bot/guide.py`) تشخیص می‌دهد، و اگر متنی برگشت (`help_text.tip(key, is_fa)`) آن را با `event.message.answer(line)` می‌فرستد.
- **پارامترها:** `handler` هندلر واقعی بعدی در زنجیره، `event` آبجکت `CallbackQuery`، `data` دیکشنری context aiogram.
- **موارد خاص/edge case:** کل بلوک ارسال نکته داخل `try/except Exception` قرار دارد و فقط لاگ می‌کند — طراحی عمدی است که یک شکست در ارسال نکته‌ی راهنما هرگز نباید جریان اصلی هندلر را خراب کند یا exception را بالا ببرد. همچنین چک `event.message is not None` لازم است چون بعضی callback query ها پیام مرتبط ندارند (مثلاً از inline mode).

---

## `bot/config.py`

این فایل تمام تنظیمات و متغیرهای محیطی (environment variables) پروژه را در یک `dataclass` به نام `Config` جمع می‌کند و از فایل `.env` (با `python-dotenv`) می‌خواند. نقطه‌ی مرکزی پیکربندی است — هرجای دیگر پروژه که نیاز به توکن، آدرس دیتابیس، اطلاعات درگاه پرداخت پلتفرم یا آدرس سایت مارکتینگ باشد، از طریق `load_config()` همین‌جا خوانده می‌شود.

### کلاس `Config` (dataclass)
- **چه‌کار می‌کند:** یک ساختار داده‌ی immutable (چون `@dataclass` ساده بدون `frozen=True` هست، ولی معمولاً به‌عنوان تنظیمات فقط-خواندنی استفاده می‌شود) برای نگه‌داری همه‌ی مقادیر پیکربندی. فیلدهای مهم:
  - `bot_token`, `database_url`, `platform_admin_id`, `webapp_url`, `webapp_port`: تنظیمات پایه‌ی خودِ ربات easymakebot.
  - `video_url_fa` / `video_url_en`: لینک ویدیوهای آموزشی به دو زبان (استفاده در `bot/guide.py`).
  - `platform_zarinpal_merchant_id`, `platform_stripe_secret_key`, `platform_ton_wallet_address`: اطلاعات پرداخت **خودِ پلتفرم** برای فروش پلن‌های `/live` (در `bot/platform_billing.py`) — طبق کامنت کد، این‌ها با تنظیمات پرداخت هر ربات (`bot/shop.py`'s `ShopSettings`) که مخصوص هر ربات است فرق دارند؛ این‌جا یک نسخه برای کل پلتفرم است. همه اختیاری‌اند و نبودشان یعنی آن مسیر پرداخت به‌صورت خاموش (graceful-omit) نمایش داده نمی‌شود.
  - `website_url`, `website_activation_key`: آدرس و کلید سایت مارکتینگ easymakebot، برای فعال‌سازی پلن با کد خریداری‌شده از سایت؛ هر دو باید ست باشند وگرنه گزینه‌ی «Activate with code» در `/live` مخفی می‌ماند.
  - `website_plans_url`: آدرسی که کاربر ایرانی برای **خرید** پلن به آن هدایت می‌شود (در مرورگر، نه داخل تلگرام) چون طبق کامنت، پرداخت باید از IP ایرانی سایت انجام شود، نه از سرور ربات که ممکن است خارج از ایران باشد + VPN تلگرام کاربر که با درگاه تداخل می‌کند.
  - `platform_onbot_zarinpal`: یک بولین که مشخص می‌کند آیا خودِ ربات (نه سایت) اجازه دارد مستقیماً پرداخت زرین‌پال برای کاربران ایرانی راه بیندازد. طبق کامنت، این فقط باید `true` باشد اگر خودِ سرور ربات هم روی IP ایران است، چون ترکیب IP خارجی سرور + VPN خریدار هر دو با درگاه تداخل می‌کنند.

### `def load_config() -> Config`
- **چه‌کار می‌کند:** مقادیر را یک‌به‌یک از `os.getenv(...)` می‌خواند:
  - رشته‌های خالی برای مقادیر اختیاری با الگوی `os.getenv(...) or None` به `None` تبدیل می‌شوند (یعنی رشته‌ی خالی هم "تنظیم‌نشده" حساب می‌شود).
  - `website_url` و `website_plans_url` با `.rstrip("/")` اسلش انتهایی را حذف می‌کنند تا بعداً وقتی مسیر به آن‌ها append می‌شود (`f"{website_url}/plans/"`) دابل‌اسلش پیش نیاید.
  - اگر `website_plans_url` تنظیم نشده باشد ولی `website_url` باشد، به‌صورت خودکار `f"{website_url}/plans/"` ساخته می‌شود (مقدار پیش‌فرض مشتق‌شده).
  - `platform_onbot_zarinpal` با چک کردن این‌که مقدار رشته‌ای (پس از lower و strip) در مجموعه‌ی `{"1","true","yes","on"}` باشد، به بولین تبدیل می‌شود.
  - سپس دو اعتبارسنجی اجباری انجام می‌شود: اگر `bot_token` خالی باشد `ValueError` با پیام راهنما پرتاب می‌شود (بگو `.env.example` را کپی کن)؛ اگر `platform_admin_id_raw` خالی باشد هم `ValueError` پرتاب می‌شود (بگو آی‌دی عددی تلگرام را از `@userinfobot` بگیر). این دو مقدار **باید** موجود باشند چون بدون توکن اصلاً ربات بالا نمی‌آید و بدون آی‌دی ادمین، `bot/filters/admin.py:IsPlatformAdmin` معنا ندارد.
  - در پایان یک نمونه‌ی `Config` با همه‌ی مقادیر پردازش‌شده برمی‌گرداند؛ `platform_admin_id` با `int(...)` به عدد تبدیل می‌شود.
- **پارامترها:** ندارد (از env می‌خواند).
- **موارد خاص/edge case:** اعتبارسنجی failfast — اگر توکن یا آی‌دی ادمین نباشد، برنامه همان لحظه‌ی راه‌اندازی با پیام خطای واضح متوقف می‌شود، نه این‌که بعداً در وسط اجرا crash کند.

---

## `bot/session.py`

یک فایل بسیار کوچک و تک‌مسئولیتی که فقط یک نقطه‌ی مرکزی برای ساخت `AiohttpSession` (session HTTP زیرین که aiogram برای صحبت با API تلگرام استفاده می‌کند) فراهم می‌کند. علت وجودش این است که هم `bot/main.py` (برای ربات اصلی) و هم `bot/runtime.py` (برای هر ربات ساخته‌شده، از جمله `sync_bot_commands` که یک `Bot` موقت می‌سازد) باید session بسازند؛ داشتن این تابع یعنی اگر بعداً نیاز به تنظیمات خاص session (مثل timeout یا proxy) پیش بیاید، فقط یک‌جا تغییر لازم است.

### `def make_session() -> AiohttpSession`
- **چه‌کار می‌کند:** فقط `return AiohttpSession()` — یک نمونه‌ی جدید و ساده از session مبتنی بر aiohttp که aiogram پیش‌فرض استفاده می‌کند، بدون هیچ تنظیم اضافه.
- **پارامترها:** ندارد.
- **موارد خاص/edge case:** ندارد — این تابع عمداً ساده نگه داشته شده؛ کل ارزشش در متمرکز بودنش است نه در منطق داخلی‌اش.

---

## `bot/filters/admin.py`

این فایل یک `BaseFilter` سفارشی aiogram تعریف می‌کند که برای محدود کردن هندلرهای حساس (مثل پنل ادمین پلتفرم در `bot/handlers/easybotadmin.py`) به فقط یک کاربر تلگرامی خاص — همان کسی که در `PLATFORM_ADMIN_ID` تنظیم شده — استفاده می‌شود. مکانیزم کنترل دسترسی سطح-پلتفرم (نه سطح یک ربات ساخته‌شده) دقیقاً همین‌جا تعریف شده.

### کلاس `IsPlatformAdmin(BaseFilter)`

#### `def __init__(self, platform_admin_id: int) -> None`
- **چه‌کار می‌کند:** آی‌دی عددی تلگرامی ادمین پلتفرم را روی `self.platform_admin_id` ذخیره می‌کند تا در `__call__` استفاده شود.
- **پارامترها:** `platform_admin_id` — معمولاً از `config.platform_admin_id` (که در `bot/config.py` ساخته شده) پاس داده می‌شود، مثلاً `IsPlatformAdmin(config.platform_admin_id)`.

#### `async def __call__(self, message: Message) -> bool`
- **چه‌کار می‌کند:** این متد است که aiogram به‌عنوان خودِ فیلتر صدا می‌زند (چون در پایتون `__call__` یعنی نمونه‌ی کلاس قابل فراخوانی مثل تابع می‌شود). چک می‌کند `message.from_user` مقدار `None` نباشد **و** `message.from_user.id` برابر `self.platform_admin_id` باشد. اگر هر دو شرط برقرار بود `True` برمی‌گرداند و aiogram اجازه می‌دهد هندلر اجرا شود؛ در غیر این صورت `False` و هندلر اصلاً صدا زده نمی‌شود (بدون هیچ پیام خطا به کاربر — سکوت کامل، انگار دستور اصلاً وجود ندارد).
- **پارامترها:** `message` — پیام تلگرامی که این فیلتر رویش چک می‌شود.
- **موارد خاص/edge case:** چک `message.from_user is not None` لازم است چون بعضی پیام‌های خاص تلگرام (مثلاً از کانال‌ها) ممکن است `from_user` نداشته باشند و بدون این چک یک `AttributeError` رخ می‌داد.

---

## `bot/states.py`

این فایل تمام گروه‌های state ماشین حالت (FSM) پروژه را با `aiogram.fsm.state.StatesGroup` تعریف می‌کند. هر ویزارد یا جریان چند-مرحله‌ای چه در ربات اصلی easymakebot و چه داخل هر ربات ساخته‌شده (که در `bot/runtime.py` اجرا می‌شود) یک `StatesGroup` مخصوص خودش این‌جا دارد. فایل صرفاً تعریف State هاست؛ منطق واقعی هر state در هندلرهای مربوطه (در `bot/handlers/` یا `bot/runtime.py`) است.

هر state با `State()` ساخته می‌شود که یک نمونه‌ی marker بدون منطق داخلی است؛ بنابراین برای هرکدام فقط نقش‌شان طبق کامنت‌های خود فایل و نامشان توضیح داده می‌شود:

### `class CreateBotStates(StatesGroup)`
- `waiting_for_token`: منتظر توکن تلگرامی که کاربر از BotFather گرفته، هنگام ساخت ربات جدید (`bot/handlers/create_bot.py`).

### `class DefineCommandStates(StatesGroup)`
- `waiting_for_command_name`: منتظر نام دستوری که کاربر می‌خواهد تعریف کند (چت-محور، معادل قدیمی‌تر ویژوال فلو بیلدر).
- `start_wizard`, `confirm_start_wizard`: مراحل ویزارد تعریف محتوای `/start` (متن خوش‌آمدگویی، اطلاعات تماس و...) و تأیید نهایی آن.

### `class MessageToAllStates(StatesGroup)`
- `waiting_for_command_name`: منتظر نام دستوری که پیام همگانی (broadcast) به آن متصل می‌شود.

### `class ForceJoinStates(StatesGroup)`
- `waiting_for_channel_name`: منتظر نام/آی‌دی کانالی که به‌عنوان شرط عضویت اجباری اضافه می‌شود (`bot/force_join_gate.py`).

### `class ContentListStates(StatesGroup)`
- `add_item_wizard`: افزودن یک آیتم محتوا به‌صورت مرحله‌به‌مرحله.
- `add_post_wizard`: «Add Post» — عکس/ویدیو + کپشن که به همه‌ی مشترکین broadcast می‌شود.
- `waiting_for_excel`: منتظر فایل اکسل برای ایمپورت گروهی محتوا.
- `lookup_wizard`: مرحله‌ی مشترک «کد را بفرست یا مرور کن» که هم در Edit، هم Delete و هم Group استفاده می‌شود.
- `edit_field_wizard`: ویرایش یک فیلد خاص از یک آیتم محتوا موجود.

### `class ShopStates(StatesGroup)`
سمت ابزار چتی فروشگاه (`bot/handlers/tools/shop.py`) — طبق docstring خود کلاس. شامل ویزارد افزودن محصول (`add_product_wizard`) و مجموعه‌ای از state های تک-فیلدی برای تنظیم درگاه‌های پرداخت و فاکتور: `waiting_for_zarinpal_id`, `waiting_for_card_number`, `waiting_for_card_holder`, `waiting_for_stripe_key`, `waiting_for_crypto_address`, `waiting_for_crypto_label`, `waiting_for_ton_address`, `waiting_for_free_preview_limit` (محدودیت پیش‌نمایش رایگان محتوای پولی)، `waiting_for_default_unlock_price` (قیمت پیش‌فرض آنلاک محتوا)، `waiting_for_campaign_percent`/`waiting_for_campaign_days` (کمپین تخفیف قیمت)، `waiting_for_invoice_business_name`/`waiting_for_invoice_logo_url`/`waiting_for_invoice_address`/`waiting_for_invoice_footer_note` (اطلاعات فاکتور PDF)، `waiting_for_import_file` (ایمپورت محصولات).

### `class AdminBroadcastStates(StatesGroup)`
- `waiting_for_message`: منتظر متن پیامی که ادمین پلتفرم به همه‌ی مالکان ربات‌ها broadcast می‌کند.

### `class OnboardingStates(StatesGroup)`
- `waiting_for_phone`: مرحله‌ی اختیاری اشتراک شماره تلفن در `/start` **خودِ easymakebot**، برای بومی‌سازی راهنما (`bot/guide.py`).

### `class BuiltBotBroadcastStates(StatesGroup)`
- `waiting_for_message`: معادل `AdminBroadcastStates` ولی داخل FSM یک ربات ساخته‌شده (`bot/runtime.py`) — مالک آن ربات پیام broadcast خودش را می‌فرستد.

### `class SubscriberOnboardingStates(StatesGroup)`
- `waiting_for_phone`: همان الگوی اشتراک/رد شماره تلفن اختیاری، اما برای یک **مشترک** یک ربات ساخته‌شده، استفاده‌شده در بلاک `guide_video` فلو (`bot/flow_engine.py`).

### `class ShopOrderStates(StatesGroup)`
سمت ربات ساخته‌شده (`bot/runtime.py`) — جریان خرید خودِ خریدار:
- `waiting_for_transaction_ref`: منتظر شماره پیگیری تراکنش برای خرید تک‌محصولی.
- `shipping_wizard`: ویزارد آدرس ارسال فیزیکی.
- `waiting_for_checkout_transaction_ref`: مثل بالا ولی مخصوص تسویه‌ی سبد خرید. طبق کامنت خود کد، **عمداً** از `waiting_for_transaction_ref` جدا نگه داشته شده تا یک خرید مستقیم (Buy) و یک Checkout سبدی که هم‌زمان در جریان‌اند، داده‌ی FSM‌شان با هم قاطی نشود.

### `class PostCommentStates(StatesGroup)`
- `waiting_for_comment`: سمت ربات ساخته‌شده — نوشتن کامنت روی یک پست.

### `class AdminPanelStates(StatesGroup)`
مخصوص `/easybotadmin` (`bot/handlers/easybotadmin.py`)، طبق کامنت خودِ فایل با `bot/filters/admin.py:IsPlatformAdmin` روی همه‌ی هندلرهایش گیت شده:
- `waiting_for_suspend_reason`: دلیل تعلیق یک ربات.
- `waiting_for_delete_confirmation`: باید یوزرنیم دقیق (`@username`) ربات را برای تأیید حذف تایپ کند.
- `waiting_for_rename`: نام جدید ربات.

### `class LivePlanStates(StatesGroup)`
مخصوص خرید پلن پرداخت پلتفرمی در `/live` (`bot/handlers/live.py` + `bot/platform_billing.py`):
- `waiting_for_ton_tx_hash`: منتظر هش تراکنش TON.
- `waiting_for_activation_code`: بازخوانی (redeem) کد فعال‌سازی خریداری‌شده از سایت مارکتینگ (`bot/website_client.py`) برای ربات فعلاً انتخاب‌شده.
- `waiting_for_activation_code_phone`: طبق کامنت، اشتراک یک‌باره‌ی شماره تلفن **پیش از اولین فعال‌سازی پولی** اگر شماره‌ی تأییدشده‌ی تلگرامی از قبل برای این مالک نداریم (برای ردیابی/پاسخگویی در تقلب — بنگرید `bot/handlers/live.py`). کد فعال‌سازی/پلن+روش انتخابی در داده‌ی FSM نگه داشته می‌شود تا بعد از دریافت شماره ادامه یابد.
- `waiting_for_plan_payment_phone`: همان الگو ولی برای مسیر پرداخت مستقیم (نه کد فعال‌سازی).

---

## `bot/flow_engine.py`

این فایل مفسر (interpreter) گراف‌هایی است که Mini App ویژوال فلو بیلدر (webapp/) ذخیره می‌کند (در `bot/db/models.py:BuiltBot.flow_definition`). یعنی وقتی مالک یک ربات به‌جای دستورهای چتی سنتی، با کشیدن-و-رها‌کردن (drag & drop) یک جریان مکالمه می‌سازد، اجرای واقعی آن جریان روی هر پیام ورودی این‌جا انجام می‌شود. طبق docstring بالای فایل، در نسخه‌ی فعلی (v1) فقط زنجیره‌های خطی (linear chain) پشتیبانی می‌شوند — یک زنجیره به‌ازای هر دستور trigger، بدون شاخه‌بندی (branching). شکل گراف شامل `nodes` (هر کدام `id`, `type`, `data`) و `edges` (`source` → `target`) است.

انواع نود (node type) طبق docstring: `trigger` (نقطه‌ی ورود، خودش اجرا نمی‌شود)، `send_message`، `force_join_gate`، `guide_video`، `content_list`، `shop`، `broadcast` (فقط یک نشانگر/placeholder — broadcast واقعی توسط `BuiltBotBroadcastStates` در `bot/runtime.py` مدیریت می‌شود).

### `def _normalize_command(raw: str) -> str`
- **چه‌کار می‌کند:** یک دستور خام (که در ابزار builder به‌صورت متن آزاد وارد می‌شود) را نرمال‌سازی می‌کند: `strip()` می‌کند، `lower()` می‌کند، و اگر با `/` شروع نشده باشد یک `/` جلویش اضافه می‌کند. طبق کامنت، این کار باعث می‌شود `"menu"`, `"/Menu "` و `"/menu"` همه به یک دستور یکسان match شوند — چون کاربر داخل UI ممکن است هرکدام از این فرمت‌ها را تایپ کند.
- **پارامترها:** `raw` — رشته‌ی خام ورودی (می‌تواند `None` یا خالی هم باشد چون `(raw or "")` استفاده شده).

### `def find_trigger_node(flow: dict[str, Any], command: str) -> dict[str, Any] | None`
- **چه‌کار می‌کند:** روی `flow["nodes"]` پیمایش می‌کند و اولین نودی که `type == "trigger"` دارد **و** فرمان نرمال‌شده‌ی `node["data"]["command"]` با فرمان نرمال‌شده‌ی ورودی برابر است را برمی‌گرداند. اگر پیدا نشد `None`.
- **پارامترها:** `flow` — دیکشنری کامل گراف (`BuiltBot.flow_definition`)؛ `command` — دستوری که باید جستجو شود (مثلاً `"/start"`).
- **این تابع در `bot/runtime.py` هم مستقیماً import و استفاده می‌شود** — هم در `_should_use_flow_for_start` (برای چک این‌که آیا اصلاً یک trigger برای `/start` در فلو تعریف شده) و هم در `_has_flow_trigger` (فیلتر تشخیص دستورهای دلخواه تعریف‌شده در فلو).

### `def _next_node(flow: dict[str, Any], node_id: str) -> dict[str, Any] | None`
- **چه‌کار می‌کند:** اولین `edge` که `source` آن برابر `node_id` است را پیدا می‌کند، سپس نودی با `id` برابر `edge["target"]` را برمی‌گرداند. یعنی گام بعدی زنجیره را از روی لیست یال‌ها پیدا می‌کند. اگر یالی از این نود خارج نشود یا نود مقصد پیدا نشود، `None`.
- **پارامترها:** `flow` — همان گراف؛ `node_id` — شناسه‌ی نود فعلی.
- **موارد خاص/edge case:** فرض بر این است که هر نود حداکثر یک یال خروجی دارد (زنجیره‌ی خطی)؛ اگر چند یال با همان `source` وجود داشته باشد فقط اولی که در پیمایش `for` پیدا شود انتخاب می‌شود (رفتار تعریف‌نشده برای شاخه‌بندی، که طبق docstring اصلاً پشتیبانی نمی‌شود).

### `async def _subscriber_phone(bot_id: uuid.UUID, user_id: int) -> str | None`
- **چه‌کار می‌کند:** یک session دیتابیس async باز می‌کند (`async_session_maker`) و رکورد `BotSubscriber` مربوط به `bot_id` و `telegram_id == user_id` را می‌خواند؛ اگر پیدا شد `subscriber.phone_number` را برمی‌گرداند، وگرنه `None`.
- **پارامترها:** `bot_id` — UUID ربات ساخته‌شده؛ `user_id` — آی‌دی تلگرامی کاربر مشترک.
- **تعامل با فایل دیگر:** از `bot.db.models.BotSubscriber` و `bot.db.base.async_session_maker` استفاده می‌کند.

### `async def run_flow(bot: Bot, bot_id: uuid.UUID, flow: dict[str, Any], command: str, message: Message, state: FSMContext) -> bool`
- **چه‌کار می‌کند:** تابع اصلی اجرای فلو. مراحل:
  1. `node = find_trigger_node(flow, command)` — نود trigger مربوط به دستور را پیدا می‌کند؛ اگر پیدا نشد **فوراً `False`** برمی‌گرداند تا caller (در `bot/runtime.py`) بداند باید به هندلینگ قدیمی (legacy) برگردد.
  2. یک `set()` به نام `visited` می‌سازد برای جلوگیری از حلقه‌ی بی‌نهایت — طبق کامنت کد، ابزار builder جلوی کشیدن یک یال حلقه‌ای (loop، مثلاً `n3 -> n2`) را نمی‌گیرد، که بدون این محافظت باعث اسپم بی‌پایان به کاربر می‌شد. علاوه بر چک تکرار نود، یک سقف مطلق هم دارد (`len(visited) < 100`) به‌عنوان محافظت اضافی (belt-and-braces).
  3. با `node = _next_node(flow, node["id"])` از نود trigger عبور می‌کند و شروع به پیمایش زنجیره می‌کند؛ در هر تکرار حلقه‌ی `while`:
     - اگر `node_id` قبلاً در `visited` بوده، حلقه `break` می‌شود (تشخیص حلقه).
     - `node_id` به `visited` اضافه می‌شود.
     - بر اساس `node_type` رفتار متفاوتی اجرا می‌شود:
       - **`send_message`**: `message.answer(data.get("text") or "")` — متن ذخیره‌شده را می‌فرستد.
       - **`force_join_gate`**: با `missing_join_channels` (از `bot/force_join_gate.py`) چک می‌کند کاربر عضو کانال‌های اجباری هست یا نه؛ اگر کانالی جا مانده، پیام join و کیبورد `force_join_keyboard` را می‌فرستد و **فوراً `return True`** می‌کند — یعنی پیمایش همان‌جا متوقف می‌شود (کاربر باید دوباره تریگر را بزند، مثلاً با دکمه‌ی "I've Joined"؛ اجرای دوباره‌ی فلو بی‌ضرر است چون پیام‌های قبلی دوباره فرستاده می‌شوند اما بی‌آزار است طبق کامنت).
       - **`guide_video`**: با `_subscriber_phone` چک می‌کند آیا شماره تلفن این مشترک قبلاً ثبت شده؛ اگر نه، `state` را به `SubscriberOnboardingStates.waiting_for_phone` می‌برد، `resume_flow_command=command` را در FSM data ذخیره می‌کند (تا بعد از پاسخ کاربر بشود فلو را از همین نقطه ادامه داد — این resume در `bot/runtime.py:_save_subscriber_phone_and_resume` مصرف می‌شود)، پیام دوزبانه‌ی اشتراک شماره را با `phone_share_keyboard()` می‌فرستد و `return True` می‌کند (توقف پیمایش). اگر شماره موجود بود، مستقیم `send_built_bot_guide(message, phone)` (از `bot/guide.py`) را صدا می‌زند و به گام بعد ادامه می‌دهد.
       - **`content_list`**: با `get_children(bot_id, None)` (از `bot/content_nav.py`) آیتم‌های سطح-ریشه‌ی محتوا را می‌گیرد؛ اگر خالی بود چیزی نمی‌فرستد (silent skip)؛ وگرنه `folder_ids_among` را برای تشخیص کدام آیتم پوشه است صدا می‌زند و با `content_menu_keyboard(items, folder_ids, select_prefix="content_item:")` (از `bot/keyboards.py`) یک منوی دکمه‌ای می‌فرستد. تپ‌کردن روی دکمه‌ها با هندلر `content_item:*` در `bot/runtime.py` مدیریت می‌شود.
       - **`shop`**: با `shop.get_standalone_products(bot_id)` (از `bot/shop.py`) محصولات مستقل (نه محصولات وصل‌شده به یک `ContentItem`) را می‌گیرد — طبق کامنت عمداً محصولات وصل به محتوا حذف می‌شوند چون آن‌ها از طریق `content_list` قابل مرور هستند و اضافه‌کردنشان این‌جا باعث دوبار نمایش می‌شد. سپس محصولات ناموجود (`stock_quantity == 0`) را فیلتر می‌کند (طبق کامنت، یک‌جور مخفی‌کردن ملایم مشابه «هنوز محصولی نیست»، ولی همچنان در لیست مدیریتی «📦 Products» برای مالک نمایش داده می‌شود). لیست را به ۴۰ تا محدود می‌کند چون تلگرام روی سایز `reply_markup` سقف دارد و این نود، برخلاف ابزار مدیریتی مالک، صفحه‌بندی (pagination) ندارد. یک دکمه‌ی `🧺 View Cart` (`callback_data="cart_view"`) هم به انتها اضافه می‌کند و پیام را می‌فرستد. اگر لیست خالی بود، هیچی نمی‌فرستد.
       - **`broadcast`**: هیچ رفتاری ندارد (فقط comment) — طبق docstring یک نشانگر placeholder صرف است.
     - در انتهای هر تکرار `node = _next_node(flow, node["id"])` گام بعدی را می‌گیرد و اگر `None` شد یا سقف ۱۰۰ رد شد، حلقه تمام می‌شود.
  4. در پایان بی‌قید-و-شرط `True` برمی‌گرداند (چه پیمایش کامل تمام شده باشد چه در یک gate متوقف شده باشد).
- **پارامترها:** `bot` — نمونه‌ی `Bot` همان ربات ساخته‌شده (نه ربات اصلی easymakebot)؛ `bot_id` — UUID ربات در دیتابیس؛ `flow` — گراف کامل؛ `command` — دستوری که این اجرا را trigger کرده؛ `message` — پیام ورودی کاربر؛ `state` — `FSMContext` مربوط به این کاربر/چت.
- **مقدار بازگشتی:** `bool` — `False` یعنی «هیچ trigger ای برای این دستور نیست، caller باید fallback بزند»؛ `True` یعنی «پیمایش انجام شد (کامل یا متوقف‌شده در یک gate)».
- **تعامل با فایل‌های دیگر:** `bot.shop` (`get_standalone_products`)، `bot.content_nav` (`folder_ids_among`, `get_children`)، `bot.db.base` (`async_session_maker`)، `bot.db.models` (`BotSubscriber`)، `bot.force_join_gate` (`force_join_keyboard`, `missing_join_channels`)، `bot.guide` (`phone_share_keyboard`, `send_built_bot_guide`)، `bot.keyboards` (`CONTENT_MENU_HEADING`, `content_menu_keyboard`)، `bot.states` (`SubscriberOnboardingStates`). و خودش از `bot/runtime.py` در چند نقطه (`handle_start`, `handle_force_join_check`, `handle_flow_command`, `_save_subscriber_phone_and_resume`) صدا زده می‌شود.

---

## `bot/runtime.py`

این فایل قلب اجرایی کل پلتفرم است — نه ربات مدیریتی easymakebot، بلکه هر رباتی که یک کاربر ساخته و منتشر کرده (built bot). به‌ازای هر ربات فعال، یک نمونه‌ی مستقل `Bot` + `Dispatcher` با polling خودش در یک `asyncio.Task` جدا اجرا می‌شود (چند ربات هم‌زمان، هرکدام مستقل، در یک پروسه‌ی پایتون). این فایل مسئول تمام رفتار واقعی که کاربر نهایی (buyer/subscriber) در آن ربات‌ها می‌بیند است: پردازش `/start` (چه با ویژوال فلو، چه با ویزارد قدیمی چت-محور)، همگام‌سازی منوی دستورهای تلگرام، مرور محتوا (پوشه‌ها/پست‌ها)، لایک/کامنت روی پست‌ها، فروشگاه (خرید تکی و سبدی، درگاه‌های Zarinpal/Stripe/کارت‌به‌کارت/کریپتو/TON، تأیید دستی سفارش توسط مالک، ویزارد آدرس ارسال فیزیکی)، broadcast مالک، و مدیریت چرخه‌ی عمر polling هر ربات (شروع، توقف، انقضای Live، تعلیق).

سطح ماژول قبل از هر تابع، چند مقدار سراسری تعریف می‌شود:
- `_config = load_config()`: پیکربندی پلتفرم (از `bot/config.py`) که همه‌ی ربات‌های ساخته‌شده مشترکاً از آن استفاده می‌کنند (مثلاً `webapp_url` برای callback درگاه‌های پرداخت).
- `_running_bots: dict[str, asyncio.Task]`: نگاشت `str(bot_id)` → task در حال اجرا، به‌عنوان registry سراسری همه‌ی ربات‌های در حال polling در همین پروسه.
- `_EMB_LINK`, `_PAY_DISCLAIMER_IRREVERSIBLE`, `_PAY_DISCLAIMER_GATEWAY`: متن‌های ثابت اعلان سلب مسئولیت پرداخت (دوزبانه فارسی/انگلیسی) که یادآوری می‌کنند easymakebot یک پلتفرم بی‌طرف است، نه فروشنده — طبق کامنت، تا خریدار بداند طرف معامله (و هر اختلافی) با مالک ربات است، نه با easymakebot. نسخه‌ی «Irreversible» برای پرداخت‌های دستی (کارت‌به‌کارت/کریپتو/TON — که بازگشت‌ناپذیرند)، نسخه‌ی «Gateway» برای درگاه‌های آنلاین (Zarinpal/Stripe) استفاده می‌شود.

### `async def _send_pay_disclaimer(message: Message, *, irreversible: bool) -> None`
- **چه‌کار می‌کند:** بسته به `irreversible`، یکی از دو متن ثابت بالا را با `parse_mode="HTML"` و `link_preview_options=LinkPreviewOptions(is_disabled=True)` (جلوگیری از پیش‌نمایش لینک تلگرام) می‌فرستد.
- **پارامترها:** `message` — پیامی که پاسخ زیرش فرستاده می‌شود؛ `irreversible` — کدام نسخه‌ی متن.
- **موارد خاص/edge case:** کل بدنه در `try/except Exception` قرار دارد و فقط `logger.warning(..., exc_info=True)` می‌کند — طبق کامنت صریح کد (`# noqa: BLE001`)، ارسال این پیام سلب‌مسئولیت هرگز نباید کل جریان پرداخت را بشکند، پس شکست آن نادیده گرفته می‌شود.

### `def _format_start_message(payload: dict[str, Any]) -> str`
- **چه‌کار می‌کند:** پیام `/start` قدیمی (legacy، تعریف‌شده با ویزارد چت‌محور «Define Command») را از یک دیکشنری `payload` (که در `Command.payload` ذخیره شده) می‌سازد. ابتدا `welcome_text` (یا `"Welcome!"` پیش‌فرض اگر خالی) را با یک خط خالی زیرش می‌گذارد؛ سپس هر کدام از فیلدهای تماس که موجود باشند (`admin_telegram_id`, `admin_phone`, `website`, `instagram`, `youtube`, `facebook`, `x`) را به‌صورت یک خط `"Label: value"` اضافه می‌کند؛ در آخر همه را با `\n` به هم می‌چسباند، و خطوط کاملاً خالی را فیلتر می‌کند (`if line != ""`).
- **پارامترها:** `payload` — دیکشنری تنظیمات `/start` که مالک از طریق ویزارد وارد کرده.
- **موارد خاص/edge case:** با `.get(...)` روی هر فیلد کار می‌کند، پس نبودن هرکدام از فیلدهای تماس فقط باعث حذف آن خط می‌شود، نه خطا.

### `async def _should_use_flow_for_start(bot_id: uuid.UUID, built_bot: BuiltBot | None) -> bool`
- **چه‌کار می‌کند:** طبق docstring، فقط برای `/start` هر دو مسیر (ویژوال فلو بیلدر و ویزارد قدیمی «Define Command») می‌توانند رفتار را تعریف کنند؛ این تابع تعیین می‌کند کدام‌یک باید فعال باشد — هرکدام که **آخرین بار ذخیره‌شده** برنده است، تا هر دو مسیر همیشه کاملاً قابل استفاده بمانند. منطق:
  1. اگر `built_bot` نباشد یا `flow_definition` نداشته باشد → `False`.
  2. اگر در فلو نودی از نوع trigger برای `/start` پیدا نشود (`find_trigger_node(...) is None`) → `False`.
  3. رکورد `Command` قدیمی برای `/start` را از دیتابیس می‌خواند.
  4. اگر رکورد قدیمی وجود نداشته باشد (`legacy is None`) → `True` (فلو تنها گزینه است، پس برنده است).
  5. اگر `built_bot.flow_updated_at is None` باشد (یعنی این فلو از قبل از این‌که ستون `flow_updated_at` اضافه شود ذخیره شده — بدون timestamp) → `False`؛ طبق کامنت، در این حالت به timestamp ویزارد قدیمی اعتماد می‌شود، به‌جای فرض کردن این‌که فلوی بدون-زمان جدیدتر است.
  6. در غیر این صورت مقایسه‌ی مستقیم زمان: `built_bot.flow_updated_at > legacy.updated_at`.
- **پارامترها:** `bot_id` — UUID ربات؛ `built_bot` — رکورد `BuiltBot` (ممکن است `None` باشد).
- **موارد خاص/edge case:** این تابع تنها برای `/start` استفاده می‌شود؛ برای دستورهای دیگری که در فلو تعریف شده‌اند، طبق کامنت این تابع، همیشه فلو حاکم است چون معادل قدیمی برای آن‌ها اصلاً وجود ندارد (بنگرید `handle_flow_command`).

### `async def _get_owner_telegram_id(bot_id: uuid.UUID) -> int | None`
- **چه‌کار می‌کند:** با یک `JOIN` بین `User` و `BuiltBot` (`BuiltBot.owner_id == User.id`)، `telegram_id` مالک یک ربات ساخته‌شده را برمی‌گرداند. این مقدار در `_run_bot` یک‌بار در ابتدای اجرای هر ربات محاسبه و در closure نگه داشته می‌شود (`owner_telegram_id`)، تا در فیلترهای هندلرهای متعدد (مثل `F.from_user.id == owner_telegram_id`) استفاده شود.
- **پارامترها:** `bot_id` — UUID ربات.

### `async def _broadcast_to_subscribers(bot_id: uuid.UUID, command_name: str, message: Message) -> int`
- **چه‌کار می‌کند:** لیست همه‌ی `BotSubscriber` مربوط به این ربات را می‌خواند، سپس برای هرکدام با `message.copy_to(subscriber.telegram_id)` همان پیام مالک را کپی می‌کند (کپی به‌جای forward، پس بدون برچسب «Forwarded from»). هر خطای ارسال (مثلاً کاربری که ربات را بلاک کرده) را جداگانه `try/except` می‌کند و فقط لاگ warning می‌زند، بدون این‌که کل broadcast متوقف شود. شمارنده‌ی `sent` را افزایش می‌دهد. در پایان یک رکورد `BroadcastLog` با `bot_id`, `command_name`, متن پیام (یا `"[non-text message]"` اگر نه متن نه کپشن داشت)، و `recipient_count=sent` می‌سازد و commit می‌کند. عدد `sent` را برمی‌گرداند.
- **پارامترها:** `bot_id`, `command_name` (برای چه دستوری این broadcast تعریف شده بود، برای لاگ)، `message` (پیام مالک که باید کپی شود).
- **موارد خاص/edge case:** هر شکست تحویل به یک مشترک منفرد جدا مدیریت می‌شود تا بلاک‌کردن یک کاربر مانع رسیدن پیام به بقیه نشود.

### `_COMMAND_DESCRIPTIONS` (دیکشنری سطح-ماژول)
نگاشت `command_type` → توضیح انگلیسی کوتاه که در `sync_bot_commands` برای پر کردن توضیح دستورها در منوی نیتیو تلگرام استفاده می‌شود (مثلاً `"broadcast"` → `"Owner: broadcast a message to all users"`).

### `async def sync_bot_commands(bot_id: uuid.UUID) -> None`
- **چه‌کار می‌کند:** منوی دستور نیتیو تلگرام (`/`) هر ربات ساخته‌شده را از صفر می‌سازد و روی همان ربات ست می‌کند، فقط بر اساس چیزی که **همین ربات** واقعاً تعریف کرده — طبق کامنت، تا یک ربات تازه‌ساز شکل منوی رباتی دیگر را به ارث نبرد.
  1. رکورد `BuiltBot` را می‌خواند (اگر نبود، `return` بی‌سروصدا).
  2. `token` و `flow = built_bot.flow_definition or {}` را می‌گیرد.
  3. همه‌ی رکوردهای `Command` این ربات را می‌خواند.
  4. `kinds: dict[str, str]` می‌سازد: برای هر `Command` که نامش با `/` شروع شود، `kinds[c.name] = c.command_type`.
  5. برای هر نود trigger در فلو، اگر دستورش با `/` شروع شود، با `kinds.setdefault(name, "flow")` اضافه‌اش می‌کند (اگر از قبل موجود بود دست‌نخورده می‌ماند — یعنی نوع `Command` قدیمی نسبت به نوع `"flow"` اولویت دارد در این نگاشت).
  6. اگر `has_any_content(bot_id)` (از `bot/content_nav.py`) `True` بود، `/content` را با نوع `"content"` اضافه می‌کند (فقط وقتی چیزی برای مرور وجود دارد).
  7. اگر `shop.get_products(bot_id)` چیزی برگرداند، `/cart` را با نوع `"cart"` اضافه می‌کند (فقط وقتی چیزی قابل‌فروش وجود دارد).
  8. تابع داخلی `_describe(name, kind)`: اگر `name == "/start"` همیشه `"Start the bot"` برمی‌گرداند — طبق کامنت، چون `command_type` ذخیره‌شده برای `/start` می‌تواند stale/تصادفی باشد (مثلاً رکوردهای قدیمی که با `"broadcast"` ذخیره شده‌اند)، پس توضیح `/start` هرگز از داده مشتق نمی‌شود؛ در غیر این صورت `_COMMAND_DESCRIPTIONS.get(kind, "Command")`.
  9. لیست نهایی `BotCommand` را با `sorted(kinds.items())` (ترتیب الفبایی) می‌سازد و به ۱۰۰ تا محدود می‌کند (سقف خودِ تلگرام روی تعداد دستورها).
  10. یک `Bot` **موقت** با همان `token` و `make_session()` می‌سازد (چون این تابع باید بتواند مستقل از این‌که ربات در حال polling هست یا نه صدا زده شود — مثلاً هنگام ذخیره‌ی یک فرمان جدید از پنل مدیریتی)، `set_my_commands(bot_commands)` را صدا می‌زند، در `except` فقط لاگ warning می‌کند، و در `finally` حتماً `temp_bot.session.close()` می‌کند تا connection leak نشود.
- **پارامترها:** `bot_id` — UUID ربات.
- **کِی صدا زده می‌شود:** طبق docstring، «هر وقت دستورها یا فلوی یک ربات تغییر کند، به‌علاوه یک‌بار در startup» — و همچنین در انتهای `_run_bot` (`await sync_bot_commands(bot_id)`) قبل از شروع polling.

### `async def _run_bot(bot_id: uuid.UUID, token: str) -> None`
این تابع بدنه‌ی اصلی اجرای یک ربات ساخته‌شده است — یک `Bot` و `Dispatcher` مستقل می‌سازد و **ده‌ها هندلر تو در تو (nested)** روی همان `dp` ثبت می‌کند (الگوی closure — همه به `bot_id`, `bot`, `dp`, `owner_telegram_id` دسترسی دارند بدون پاس دادن صریح). چون این تابع فوق‌العاده بزرگ است، هر هندلر و تابع کمکی داخلی‌اش را جدا شرح می‌دهم. ابتدای تابع:
```python
bot = Bot(token=token, session=make_session())
dp = Dispatcher()
owner_telegram_id = await _get_owner_telegram_id(bot_id)
```
سپس در انتهای تابع (بعد از تعریف همه‌ی هندلرها):
```python
try:
    await bot.delete_webhook(drop_pending_updates=True)
    await sync_bot_commands(bot_id)
    await dp.start_polling(bot)
except Exception:
    logger.exception("Built bot %s crashed", bot_id)
finally:
    await bot.session.close()
```
یعنی وبهوک پاک می‌شود (به polling سوییچ می‌کند و آپدیت‌های قدیمی معلق دور ریخته می‌شوند)، منوی دستورها sync می‌شود، و polling شروع می‌شود؛ هر crash کامل لاگ می‌شود (نه raise) تا crash یک ربات، بقیه‌ی ربات‌های در حال اجرا در همان پروسه را با خودش پایین نکشد؛ و در هر صورت (موفق یا شکست) session بسته می‌شود تا connection leak نشود.

اکنون هندلرها و توابع کمکی داخلی، به همان ترتیبی که در کد ظاهر می‌شوند:

#### `async def _register_subscriber(user_id: int) -> None`
- **چه‌کار می‌کند:** چک می‌کند آیا رکورد `BotSubscriber` برای `(bot_id, user_id)` از قبل موجود است؛ اگر نه، یک رکورد جدید می‌سازد و commit می‌کند. این تابع idempotent است (اگر قبلاً وجود داشته باشد کاری نمی‌کند).
- **کجا صدا زده می‌شود:** در `handle_start`, `handle_force_join_check`, `handle_flow_command`, `handle_possible_content_code` — یعنی هر مسیری که می‌تواند اولین تعامل یک کاربر جدید با این ربات باشد.

#### `async def _complete_start(message: Message, user_id: int) -> None`
- **چه‌کار می‌کند:** مسیر legacy تکمیل `/start`: `_register_subscriber(user_id)` را صدا می‌زند، رکورد `Command` با `name == "/start"` را می‌خواند، `payload = command.payload if command and command.payload else {}` و پیام نهایی را با `_format_start_message(payload)` می‌سازد و می‌فرستد.

#### `@dp.message(CommandStart()) async def handle_start(message: Message, state: FSMContext) -> None`
- **چه‌کار می‌کند:** هندلر اصلی دستور `/start`. مراحل:
  1. رکورد `BuiltBot` را می‌خواند.
  2. `if await _should_use_flow_for_start(bot_id, built_bot):` — اگر فلو باید فعال باشد، مشترک را ثبت می‌کند و `run_flow(bot, bot_id, built_bot.flow_definition, "/start", message, state)` را صدا می‌زند؛ اگر `handled` (که همیشه `True` یا `False` بر اساس این‌که trigger پیدا شد یا نه) صحیح بود، `return` می‌کند.
  3. اگر به این‌جا رسید (یعنی فلو فعال نبود، یا `run_flow` به هر دلیل `False` برگرداند)، مسیر legacy را ادامه می‌دهد: اگر `built_bot.force_join_enabled` و کانالی جا مانده باشد (`missing_join_channels`)، پیام join می‌فرستد و متوقف می‌شود.
  4. در غیر این صورت `_complete_start(message, message.from_user.id)` را صدا می‌زند.
- **پارامترها:** `message`, `state` (تزریق‌شده توسط aiogram).

#### `@dp.callback_query(F.data == "force_join_check") async def handle_force_join_check(callback: CallbackQuery, state: FSMContext) -> None`
- **چه‌کار می‌کند:** وقتی کاربر دکمه‌ی «I've Joined» را می‌زند: دوباره `missing_join_channels` را چک می‌کند؛ اگر هنوز چیزی جا مانده، با `callback.answer(..., show_alert=True)` هشدار می‌دهد و متوقف می‌شود. اگر همه چیز اوکی بود، `callback.answer("Thanks for joining! ✅")` و `callback.message.delete()` (پیام join را پاک می‌کند)، سپس دقیقاً همان منطق دو‌مسیره‌ی `handle_start` را تکرار می‌کند (فلو یا `_complete_start`) اما بدون چک دوباره‌ی force-join (چون همین الان تأیید شد).
- **موارد خاص/edge case:** `callback.message.delete()` می‌تواند در تئوری شکست بخورد (مثلاً اگر پیام خیلی قدیمی باشد) ولی این‌جا try/except ندارد — یعنی اگر شکست بخورد استثنا بالا می‌رود؛ در عمل معمولاً بلافاصله بعد از ارسال پیام join این اتفاق می‌افتد، پس ریسک کم است.

#### `def _content_keyboard(items, back_to_id, at_root, folder_ids) -> InlineKeyboardMarkup`
- **چه‌کار می‌کند:** یک دکمه‌ی «🔙 Back» می‌سازد (اگر `at_root` نباشد) با `callback_data=f"content_nav:{back_target}"` که `back_target` یا `"root"` است یا `str(back_to_id)`، سپس با `content_menu_keyboard` (از `bot/keyboards.py`) کیبورد کامل را می‌سازد.

#### `async def _send_content_children(message, parent_id, grandparent_id, heading) -> bool`
- **چه‌کار می‌کند:** با `get_children(bot_id, parent_id)` (از `bot/content_nav.py`) فرزندان یک پوشه (یا سطح ریشه اگر `parent_id is None`) را می‌گیرد؛ اگر خالی بود `False` برمی‌گرداند. وگرنه `folder_ids_among` را برای مشخص کردن کدام آیتم پوشه است صدا می‌زند و پیام با کیبورد `_content_keyboard` می‌فرستد؛ `True` برمی‌گرداند.
- **استفاده‌شده در:** `handle_content_item` (وقتی درون یک پوشه می‌رود)، `handle_content_nav` (Back)، `handle_content_command` (`/content`)، `handle_possible_content_code`.

#### `async def _shop_product_for(item)`
- **چه‌کار می‌کند:** طبق docstring، برای یک آیتم محتوا (`ContentItem`) محصول واقعی فروشگاهی متصل‌شده را برمی‌گرداند، یا `None`. اگر `item.product_id` نداشته باشد `None`. وگرنه محصول را با `shop.get_product` می‌گیرد و اگر `product is None` یا `product.product_type == shop.CONTENT_UNLOCK_TYPE` باشد باز `None` برمی‌گرداند — چون طبق کامنت، محصول مخفی «آنلاک همین آیتم» (حالت اشتراک/subscription) یک محصول واقعی فروشگاهی نیست و **نباید** دکمه‌ی خرید/سبد روی آیتمی نمایش دهد که بیننده از قبل آنلاک کرده.

#### `async def _content_post_markup(item, back_target: str) -> InlineKeyboardMarkup`
- **چه‌کار می‌کند:** کیبورد زیر یک «پست» محتوا را می‌سازد: اگر `item.link_url` باشد دکمه‌ی «🔗 Open» (URL button)، اگر محصول واقعی فروشگاهی داشته باشد (`_shop_product_for`) دکمه‌های «🛒 Buy Now» و «➕ Add to Cart»، سپس یک ردیف carousel `◀️ i/n ▶️` بین خواهر-و-برادرها (siblings) — با پیدا کردن ایندکس آیتم فعلی در لیست siblings (`get_children(bot_id, item.parent_id)`) و ساخت دکمه‌های ناوبری به قبلی/بعدی فقط اگر بیش از یک sibling وجود داشته باشد، و در نهایت «🔙 Back to list».

#### `async def _send_content_post(target: Message, item, *, edit: bool) -> None`
- **چه‌کار می‌کند:** یک آیتم محتوا را به‌عنوان «پست» رندر می‌کند — تنها نقطه‌ی گِیت پرمیوم (premium gate) برای هر دو مسیر ورود (لیست و کد میان‌بر). منطق:
  1. `back_target` را از `item.parent_id` می‌سازد.
  2. اگر `item.is_premium`، با `premium_content.check_and_record_access(bot_id, target.chat.id, item)` (از `bot/premium_content.py`) چک می‌کند آیا دسترسی مجاز است (این تابع همچنین رکورد دسترسی را ثبت می‌کند — لاگ پیش‌نمایش رایگان مصرف‌شده). اگر مجاز نبود:
     - پلن‌های اشتراک را با `premium_content.get_subscription_plans(bot_id)` می‌گیرد.
     - قیمت آنلاک تک‌آیتمی (à-la-carte) را با `premium_content.effective_unlock_price(bot_id, item)` می‌گیرد؛ اگر مقداری داشت، یک محصول مخفی آنلاک با `shop.ensure_unlock_product(bot_id, item, unlock_base)` می‌سازد/می‌گیرد و دکمه‌ی «🔓 Unlock just this — قیمت» اضافه می‌کند؛ خط تخفیف (`pricing.savings_line`) هم محاسبه می‌شود.
     - برای هر پلن اشتراک یک دکمه با قیمت فرمت‌شده (`pricing.format_price`) اضافه می‌کند.
     - دکمه‌ی Back اضافه می‌کند.
     - متن پیام بسته به این‌که پلن/آنلاک موجود است یا نه، متفاوت انتخاب می‌شود — اگر هیچ‌کدام نبود، پیام می‌گوید «هیچ پلنی تنظیم نشده، با مالک تماس بگیرید».
     - با `_render_post` نمایش داده می‌شود و **تابع همین‌جا return می‌کند** (پست واقعی هرگز نمایش داده نمی‌شود).
  3. اگر دسترسی مجاز بود (یا آیتم اصلاً پرمیوم نبود): کپشن `"📌 {title}\n\n{body}"` ساخته می‌شود؛ اگر محصول واقعی فروشگاهی وصل بود (`_shop_product_for`)، قیمت و خط تخفیف به کپشن اضافه می‌شود.
  4. کیبورد با `_content_post_markup` ساخته می‌شود و `_render_post(target, caption, item.image_url or None, markup, edit=edit)` صدا زده می‌شود.
- **پارامترها:** `target` — پیامی که پست باید رویش/زیرش نمایش داده شود؛ `item` — رکورد `ContentItem`؛ `edit` — اگر `True` پیام موجود در جا ویرایش می‌شود (برای carousel)، اگر `False` پیام جدید فرستاده می‌شود.

#### `async def _render_post(target, text, image_url, markup, *, edit: bool) -> None`
- **چه‌کار می‌کند:** لایه‌ی پایین‌سطح رندر: اگر `image_url` باشد، سعی می‌کند به‌عنوان عکس نمایش دهد؛ اگر `edit=True` اول تلاش می‌کند `target.edit_media(...)` کند (تبدیل درجا)، و اگر شکست خورد (مثلاً پیام قبلی متن ساده بود نه عکس — تلگرام اجازه‌ی edit بین این دو نوع را نمی‌دهد) پیام قبلی را `delete()` می‌کند (خودش هم داخل `try/except` که اگر حذف هم شکست خورد نادیده گرفته می‌شود) و سپس با `answer_photo(...)` پیام تازه می‌فرستد؛ اگر ارسال عکس هم شکست خورد (مثلاً URL نامعتبر)، فقط `logger.warning` می‌کند و به مسیر متنی سقوط می‌کند (fallback). اگر اصلاً `image_url` نبود یا مسیر عکس شکست خورد: اگر `edit=True` تلاش می‌کند `target.edit_text(...)`، در شکست پیام را حذف می‌کند؛ در پایان `target.answer(text, reply_markup=markup)` پیام متنی جدید می‌فرستد.
- **موارد خاص/edge case:** طبق کامنت docstring، این الگوی delete+resend لازم است چون تلگرام اجازه نمی‌دهد یک پیام «عکس» را به «متن» ادیت کرد یا برعکس؛ تابع این تبدیل‌ها را شفاف مدیریت می‌کند تا caller نگران نوع پیام قبلی نباشد.

#### `@dp.callback_query(F.data.startswith("content_item:")) async def handle_content_item(callback) -> None`
- **چه‌کار می‌کند:** `item_id` را از `callback.data` استخراج می‌کند، آیتم را با `get_item(item_id)` می‌گیرد؛ اگر آیتم نبود یا متعلق به ربات دیگری بود (`item.bot_id != bot_id` — محافظت در برابر cross-bot data leak از طریق callback_data دستکاری‌شده)، هشدار می‌دهد و متوقف می‌شود. وگرنه با `_send_content_children` تلاش می‌کند درون آن به‌عنوان پوشه برود (اگر فرزند دارد)؛ اگر `drilled_in` بود، تمام؛ وگرنه `_send_content_post(callback.message, item, edit=False)` — یعنی به‌عنوان یک leaf/پست نمایش می‌دهد.

#### `@dp.callback_query(F.data.startswith("content_post:")) async def handle_content_post(callback) -> None`
- **چه‌کار می‌کند:** دکمه‌های ◀️/▶️ روی یک پست — همان چک اعتبار bot_id، سپس `_send_content_post(callback.message, item, edit=True)` — با `edit=True` پیام موجود درجا به sibling بعدی/قبلی تغییر می‌کند، طبق docstring تا مرور یک کاتالوگ باعث تلنبار شدن پیام‌های جدید نشود.

#### `@dp.callback_query(F.data == "noop") async def handle_noop(callback) -> None`
- **چه‌کار می‌کند:** فقط `callback.answer()` — برای دکمه‌ی نمایشی «شماره‌گذاری صفحه» (`i / n`) در carousel که واقعاً کلیک‌پذیر نیست ولی باید callback را acknowledge کند تا تلگرام spinner لودینگ را متوقف کند.

#### `@dp.callback_query(F.data.startswith("content_nav:")) async def handle_content_nav(callback) -> None`
- **چه‌کار می‌کند:** دکمه‌ی Back. `target` را از `callback.data` می‌گیرد؛ اگر `"root"` بود `parent_id=None, grandparent_id=None`؛ وگرنه `parent_id = int(target)` و رکورد پوشه را می‌خواند (با همان چک `bot_id`)، `grandparent_id = folder.parent_id`. سپس `_send_content_children(...)` را صدا می‌زند؛ اگر چیزی برای نمایش نبود (`sent` نادرست) پیام «No items here.» می‌فرستد.

#### `@dp.message(CommandFilter("content")) async def handle_content_command(message) -> None`
- **چه‌کار می‌کند:** دستور `/content` — `_send_content_children(message, None, None, "📚 Choose an item:")`؛ اگر خالی بود «No content yet.» می‌فرستد.

#### `@dp.callback_query(F.data.startswith("post_like:")) async def handle_post_like(callback) -> None`
- **چه‌کار می‌کند:** لایک/آنلایک روی یک `BotPost`. `post_id` و `liker_id` را می‌گیرد؛ داخل یک session، رکورد `BotPost` را می‌خواند (اگر نبود یا bot_id نمی‌خورد، هشدار). چک می‌کند آیا `PostLike` قبلی برای این `(post_id, liker_telegram_id)` وجود دارد: اگر بله، حذفش می‌کند و `post.like_count = max(0, post.like_count - 1)` (محافظت در برابر منفی شدن شمارنده) و `liked_now=False`؛ اگر نه، رکورد جدید `PostLike` می‌سازد، `post.like_count += 1`، `liked_now=True`. commit می‌کند، سپس `callback.answer(...)` متناسب و تلاش می‌کند `callback.message.edit_reply_markup` را با شمارنده‌های تازه به‌روزرسانی کند — این کار در `try/except` است چون اگر markup از قبل همان مقدار بود یا پیام stale شده، تلگرام خطا می‌دهد که بی‌اهمیت است.

#### `@dp.callback_query(F.data.startswith("post_comment:")) async def handle_post_comment_button(callback, state) -> None`
- **چه‌کار می‌کند:** دکمه‌ی «کامنت» زیر یک پست. پست را چک می‌کند، سپس `comment_post_id`, `comment_chat_id`, `comment_message_id` را در FSM data ذخیره می‌کند (تا بعداً پیام اصلی برای به‌روزرسانی شمارنده پیدا شود)، `state` را `PostCommentStates.waiting_for_comment` می‌کند و از کاربر متن کامنت را می‌خواهد.

#### `@dp.message(PostCommentStates.waiting_for_comment) async def handle_post_comment_text(message, state) -> None`
- **چه‌کار می‌کند:** متن کامنت را از data قبلی می‌گیرد، `state` را پاک می‌کند (`state.set_state(None)`) — قبل از هر بازگشت زودهنگام، تا این state هرگز گیر نکند. اگر `post_id` نبود، بی‌سروصدا `return`. اگر متن خالی بود، پیام «Empty comment» و return. وگرنه رکورد `PostComment` می‌سازد، `post.comment_count += 1`، commit. پیام تشکر می‌فرستد. اگر `chat_id`/`orig_message_id` موجود بود، تلاش می‌کند markup پیام اصلی پست را با شمارنده‌ی تازه به‌روز کند (در `try/except`). در پایان اگر `owner_telegram_id` موجود بود، به مالک اطلاع کامنت جدید را با نام/یوزرنیم کامنت‌گذار می‌فرستد (در `try/except`، لاگ اگر شکست خورد).

#### `@dp.callback_query(F.data.startswith("shop_product:")) async def handle_shop_product(callback) -> None`
- **چه‌کار می‌کند:** جزئیات یک محصول را نمایش می‌دهد: `shop.get_product(product_id)` را می‌گیرد (چک `bot_id`)، متن با نام/توضیح/قیمت فرمت‌شده (`pricing.format_price`) و خط تخفیف می‌سازد، کیبورد «🛒 Buy Now» + «➕ Add to Cart» می‌سازد. اگر `product.image_url` بود تلاش می‌کند `answer_photo` کند؛ در شکست (`except`) فقط لاگ و به مسیر متنی سقوط می‌کند.

#### `@dp.callback_query(F.data.startswith("shop_buy:")) async def handle_shop_buy(callback) -> None`
- **چه‌کار می‌کند:** با `shop.create_order(bot_id, product_id, callback.from_user.id)` سفارش می‌سازد (این تابع در `bot/shop.py` منطق کاهش موجودی/چک stock را دارد؛ اگر `None` برگرداند یعنی احتمالاً ناموجود شده — پیام «Not available — it may be sold out.»). سپس `shop.get_shop_settings(bot_id)` را می‌خواند و بر اساس این‌که کدام درگاه‌ها تنظیم شده‌اند (`zarinpal_merchant_id`, `card_number`, `stripe_secret_key`, `crypto_wallet_address`, `ton_wallet_address`) دکمه‌های متناظر می‌سازد. اگر هیچ‌کدام تنظیم نشده بود، پیام «Payment isn't set up» می‌فرستد؛ وگرنه لیست دکمه‌ها را می‌فرستد.

#### `@dp.callback_query(F.data.startswith("shop_pay:zarinpal:")) async def handle_pay_zarinpal(callback) -> None`
- **چه‌کار می‌کند:** سفارش را می‌گیرد (چک `bot_id`)، `shop.start_zarinpal_payment(order, _config.webapp_url)` را صدا می‌زند (این تابع در `bot/shop.py` درخواست به API زرین‌پال می‌زند و URL پرداخت برمی‌گرداند یا `None` در شکست). اگر `None` بود پیام خطا؛ وگرنه دکمه‌ی URL «🔗 Pay Now» می‌فرستد و `_send_pay_disclaimer(..., irreversible=False)` را صدا می‌زند (چون این یک درگاه آنلاین است، نه پرداخت دستی).

#### `@dp.callback_query(F.data.startswith("shop_pay:stripe:")) async def handle_pay_stripe(callback) -> None`
- **چه‌کار می‌کند:** دقیقاً همان الگوی Zarinpal، ولی با `shop.start_stripe_payment`.

#### `async def _start_manual_payment(callback, state, order_id, method, info_text) -> None`
- **چه‌کار می‌کند:** تابع مشترک برای سه روش پرداخت دستی (کارت‌به‌کارت، کریپتو، TON) — طبق کامنت بالای بلوک کد، هر سه یک جریان مشترک «خریدار شماره تراکنش می‌فرستد، مالک تأیید/رد می‌کند» را به اشتراک می‌گذارند (`bot/shop.py:submit_manual_payment`)، فقط متن اطلاعاتی نمایش‌داده‌شده به خریدار فرق دارد. سفارش را چک می‌کند، در FSM data `card_order_id` و `card_payment_method` را ذخیره می‌کند، `state` را `ShopOrderStates.waiting_for_transaction_ref` می‌کند، متن اطلاعات پرداخت + مبلغ را می‌فرستد و از خریدار می‌خواهد شماره پیگیری تراکنش را بفرستد؛ در پایان `_send_pay_disclaimer(..., irreversible=True)` (چون این پرداخت‌های دستی بازگشت‌ناپذیرند).

#### `handle_pay_card`, `handle_pay_crypto`, `handle_pay_ton`
- **چه‌کار می‌کنند:** هرکدام تنظیمات مربوطه‌ی فروشگاه (`settings.card_number`, `settings.crypto_wallet_address`, `settings.ton_wallet_address`) را چک می‌کنند (اگر تنظیم نشده، هشدار «not set up for this bot»)، سپس با متن اطلاعاتی خاص خودشان (شماره کارت + نام دارنده، آدرس ولت کریپتو با برچسب شبکه، آدرس ولت TON) `_start_manual_payment` را صدا می‌زنند.

#### `@dp.message(ShopOrderStates.waiting_for_transaction_ref) async def receive_transaction_ref(message, state) -> None`
- **چه‌کار می‌کند:** شماره تراکنشی که خریدار فرستاده را دریافت می‌کند. `order_id` و `method` را از FSM data می‌گیرد؛ اگر سفارش پیدا نشد `state.clear()` و بی‌صدا خارج می‌شود. اگر متن خالی بود، دوباره می‌خواهد یا `/cancel` بزند. وگرنه `shop.submit_manual_payment(order_id, method, ref)` را صدا می‌زند (که رکورد سفارش را وارد وضعیت «در انتظار بررسی» می‌کند)، `state.clear()`، پیام تشکر به خریدار. اگر `owner_telegram_id` موجود بود، اطلاعات کامل سفارش (محصول، قیمت، روش پرداخت، خریدار، شماره تراکنش) را همراه دکمه‌های «✅ Confirm» / «❌ Reject» به مالک می‌فرستد (در `try/except`).

#### `@dp.callback_query(F.data.startswith("order_approve:"), F.from_user.id == owner_telegram_id) async def handle_order_approve(callback) -> None`
- **چه‌کار می‌کند:** فقط اگر کلیک‌کننده مالک همین ربات باشد (فیلتر دوم) اجرا می‌شود. `shop.approve_manual_payment(bot, order_id)` را صدا می‌زند (که در `bot/shop.py` سفارش را تکمیل و به خریدار اطلاع می‌دهد/تحویل می‌دهد — `fulfill_order`)، سپس `callback.answer("Approved ✅")` و اگر سفارش پیدا شد، دکمه‌های Confirm/Reject را از پیام حذف می‌کند (`edit_reply_markup(reply_markup=None)`) تا دوباره قابل‌کلیک نباشد.

#### `handle_order_reject` (فیلتر مشابه با `order_reject:`)
- **چه‌کار می‌کند:** `shop.reject_manual_payment(order_id)` را صدا می‌زند، دکمه‌ها را حذف می‌کند، و به خریدار پیام «پرداختت رد شد» می‌فرستد (در `try/except`).

#### `@dp.callback_query(F.data.startswith("ship_info:")) async def start_shipping_wizard(callback, state) -> None`
- **چه‌کار می‌کند:** ویزارد ارسال فیزیکی را شروع می‌کند: `order_id` را در FSM data می‌گذارد، `state` را `ShopOrderStates.shipping_wizard` می‌کند، کیبوردی از روش‌های ارسال (`shop.SHIPPING_METHODS`) می‌سازد و می‌فرستد.

#### `_shipping_step_prompts`, `_shipping_steps` (ثابت‌های محلی)
دیکشنری/لیست مراحل ویزارد آدرس: `name` → «Recipient's full name?»، `phone` → «Phone number?»، `address` → «Full shipping address?»؛ `_shipping_steps` ترتیب کلیدها را نگه می‌دارد.

#### `async def _send_shipping_step(message, state, index: int) -> None`
- **چه‌کار می‌کند:** موتور ویزارد چند-مرحله‌ای مبتنی بر ایندکس. اگر `index >= len(_shipping_steps)` یعنی همه‌ی مراحل جواب داده شده‌اند: داده‌های جمع‌آوری‌شده را از FSM data می‌خواند و `shop.save_shipping_info(order_id, method, name, phone, address)` را صدا می‌زند (که رکورد سفارش را با اطلاعات آدرس به‌روز می‌کند)، `state.clear()`، پیام تشکر، و **بلافاصله `shop.fulfill_order(bot, order)` را صدا می‌زند** (یعنی تحویل واقعی/ارسال فاکتور تازه بعد از این‌که آدرس کامل شد اتفاق می‌افتد). اگر هنوز مرحله باقی مانده، `shipping_step=index` را در data ذخیره می‌کند و پرامپت متناظر را می‌فرستد.

#### `@dp.callback_query(F.data.startswith("ship_method:"), ShopOrderStates.shipping_wizard) async def pick_shipping_method(callback, state) -> None`
- **چه‌کار می‌کند:** روش ارسال انتخاب‌شده را در data ذخیره می‌کند، `callback.answer()` و `_send_shipping_step(callback.message, state, 0)` را برای شروع اولین مرحله (نام) صدا می‌زند.

#### `@dp.message(ShopOrderStates.shipping_wizard) async def shipping_wizard_receive(message, state) -> None`
- **چه‌کار می‌کند:** پاسخ متنی هر مرحله را دریافت می‌کند. اگر `"shipping_method"` هنوز در data نباشد (یعنی کاربر هنوز روی دکمه‌ی روش ارسال نزده و به‌جایش متن فرستاده)، بی‌سروصدا `return` می‌شود (صبر می‌کند تا دکمه زده شود). وگرنه `index` فعلی را می‌خواند، کلید متناظر (`shipping_{step}`) را در data ذخیره می‌کند و `_send_shipping_step(message, state, index + 1)` را برای مرحله‌ی بعد صدا می‌زند.

#### `@dp.callback_query(F.data.startswith("cart_add:")) async def handle_cart_add(callback) -> None`
- **چه‌کار می‌کند:** با `shop.add_to_cart(bot_id, callback.from_user.id, product_id)` محصول را به سبد اضافه می‌کند (اگر از قبل بود، `added=False` — یعنی این تابع idempotent است و دوباره اضافه نمی‌کند)؛ پیام «Added to cart ✅» یا «Already in your cart» می‌فرستد، و یک دکمه‌ی میان‌بر «🧺 View Cart» زیرش می‌گذارد.

#### `async def _send_cart(message, buyer_telegram_id) -> None`
- **چه‌کار می‌کند:** محتوای سبد خرید را نمایش می‌دهد. `shop.get_cart_items(bot_id, buyer_telegram_id)` — لیست `(CartItem, Product)` — را می‌گیرد؛ اگر خالی، «🧺 Your cart is empty.». وگرنه مجموع قیمت فعلی و قیمت اصلی (پیش از تخفیف) را جمع می‌زند، برای هر آیتم یک ورودی `entries` می‌سازد (شامل عکس محصول در صورت وجود، دکمه‌ی «❌ Remove»، کپشن قیمت)، و با تابع مشترک `send_item_list` (از `bot/list_render.py` — که مسئول رندر لیستی از آیتم‌ها به‌صورت عکس یا خلاصه‌ی متنی است) نمایش می‌دهد، به‌همراه یک متن خلاصه (`summary`) با جمع کل و دکمه‌ی «💳 Checkout» به‌عنوان `footer_rows`.

#### `handle_cart_view` (`cart_view`) و `handle_cart_command` (`/cart`)
- هر دو صرفاً `_send_cart` را با `chat`/`from_user.id` متناسب صدا می‌زنند.

#### `@dp.callback_query(F.data.startswith("cart_remove:")) async def handle_cart_remove(callback) -> None`
- **چه‌کار می‌کند:** `shop.remove_from_cart(cart_item_id, bot_id, callback.from_user.id)` را صدا می‌زند (این تابع همچنین محدود می‌کند فقط صاحب همان سبد بتواند حذف کند)، سپس دوباره `_send_cart` را برای نمایش سبد به‌روزشده صدا می‌زند.

#### `@dp.callback_query(F.data == "cart_checkout") async def handle_cart_checkout(callback) -> None`
- **چه‌کار می‌کند:** با `shop.create_checkout(bot_id, callback.from_user.id)` رکورد `Checkout` می‌سازد (اگر سبد خالی باشد `None` و پیام هشدار)؛ سپس دقیقاً همان الگوی `handle_shop_buy` را برای ساخت دکمه‌های درگاه پرداخت تکرار می‌کند، ولی این‌بار با `callback_data=f"cart_pay:{method}:{checkout.id}"` (پیشوند `cart_pay` به‌جای `shop_pay`) و مبلغ کل (`checkout.total_price`) در متن.

#### `handle_cart_pay_zarinpal`, `handle_cart_pay_stripe`
- معادل دقیق `handle_pay_zarinpal`/`handle_pay_stripe` ولی روی `Checkout` به‌جای `Order` (`shop.start_zarinpal_checkout` / `shop.start_stripe_checkout`).

#### `async def _start_manual_checkout_payment(callback, state, checkout_id, method, info_text) -> None`
- معادل `_start_manual_payment` ولی برای `Checkout`: در FSM data `cart_checkout_id`/`cart_payment_method` ذخیره می‌کند، `state` را `ShopOrderStates.waiting_for_checkout_transaction_ref` می‌کند (نه `waiting_for_transaction_ref` — عمداً جدا، طبق کامنت `bot/states.py`).

#### `handle_cart_pay_card`, `handle_cart_pay_crypto`, `handle_cart_pay_ton`
- معادل نسخه‌های تک-سفارشی‌شان، ولی روی `_start_manual_checkout_payment`.

#### `@dp.message(ShopOrderStates.waiting_for_checkout_transaction_ref) async def receive_checkout_transaction_ref(message, state) -> None`
- **چه‌کار می‌کند:** معادل `receive_transaction_ref` ولی برای checkout: `shop.submit_manual_checkout_payment(checkout_id, method, ref)`، و به مالک با دکمه‌های `cart_approve:`/`cart_reject:` اطلاع می‌دهد.

#### `handle_cart_approve` / `handle_cart_reject` (فیلتر `F.from_user.id == owner_telegram_id`)
- **چه‌کار می‌کنند:** معادل `handle_order_approve`/`handle_order_reject` ولی با `shop.approve_manual_checkout(bot, checkout_id)` / `shop.reject_manual_checkout(checkout_id)`.

#### `async def _save_subscriber_phone_and_resume(message, state, phone, thanks_text) -> None`
- **چه‌کار می‌کند:** نقطه‌ی مشترک بعد از این‌که مشترک شماره تلفن خود را داد (یا رد کرد). رکورد `BotSubscriber` را می‌یابد و `phone_number = phone` را ست/commit می‌کند (اگر رکورد پیدا نشد، بی‌صدا ادامه می‌دهد). `command = data.get("resume_flow_command", "/start")` را از FSM data می‌خواند (ذخیره‌شده توسط `bot/flow_engine.py`'s `guide_video` node یا مسیر `/start`)، `state.clear()`، پیام تشکر با `ReplyKeyboardRemove()` (کیبورد سفارشی share/skip را حذف می‌کند)، سپس اگر `built_bot.flow_definition` موجود بود، **دوباره `run_flow(...)` را با همان دستور `command` صدا می‌زند** — یعنی فلو از همان‌جایی که برای گرفتن شماره متوقف شده بود، از نو resume/replay می‌شود (طبق کامنت‌های `bot/flow_engine.py`، replay بی‌خطر است چون پیام‌های قبلی دوباره فرستاده شدن مشکلی ایجاد نمی‌کند).
- **پارامترها:** `phone` — شماره‌ی نهایی («» یعنی «پرسیده شد و رد شد»، طبق کامنت مشخص‌شده)، `thanks_text` — متن تشکر متناسب با مسیر (share یا skip).

#### `receive_subscriber_phone` (فیلتر `F.contact`)
- **چه‌کار می‌کند:** شماره از `message.contact.phone_number` گرفته می‌شود؛ اگر با `+` شروع نشود، یکی اضافه می‌شود (نرمال‌سازی فرمت بین‌المللی). سپس `_save_subscriber_phone_and_resume(..., "Thanks! 🙌")`.

#### `skip_subscriber_phone` (فیلتر `F.text == SKIP_BUTTON_TEXT`)
- **چه‌کار می‌کند:** رد کردن اشتراک شماره — `phone=""` (نه `None`) پاس داده می‌شود؛ طبق کامنت کد، این علامتی است که «قبلاً پرسیده و رد شده» بوده تا `bot/flow_engine.py`'s `guide_video` دوباره از کاربر نپرسد.

#### `receive_typed_subscriber_phone` (فیلتر `F.text`)
- **چه‌کار می‌کند:** وقتی کاربر به‌جای دکمه‌ی contact، شماره را تایپ می‌کند: با `normalize_typed_phone(message.text)` (از `bot/guide.py`) اعتبارسنجی و نرمال‌سازی می‌شود؛ اگر `None` برگردد (فرمت نامعتبر)، پیام خطای `TYPED_PHONE_INVALID` با کیبورد دوباره فرستاده می‌شود. وگرنه ادامه‌ی مسیر معمولی.

#### `async def _has_flow_trigger(message: Message) -> bool`
- **چه‌کار می‌کند:** یک **فیلتر** (نه صرفاً چک داخل هندلر) — طبق کامنت کد، عمداً به‌جای این‌که داخل خود handler چک شود، به‌عنوان یک aiogram filter پیاده شده، تا اگر دستور match نکرد، پیام به هندلر بعدی (مثلاً `handle_owner_command`) fall-through کند نه این‌که بی‌صدا بلعیده شود. چک می‌کند متن با `/` شروع شود و برابر `/start` نباشد (چون `/start` را `handle_start` جدا مدیریت می‌کند)؛ توکن دستور را استخراج می‌کند (`split()[0].split("@")[0]` — حذف آرگومان‌های بعد از دستور و حذف `@botusername` که تلگرام در گروه‌ها اضافه می‌کند)؛ اگر `BuiltBot` یا `flow_definition` نبود `False`؛ وگرنه `find_trigger_node(...) is not None` را برمی‌گرداند.

#### `@dp.message(_has_flow_trigger) async def handle_flow_command(message, state) -> None`
- **چه‌کار می‌کند:** طبق docstring، اجرای فلو برای هر دستور **غیر از** `/start` (که `handle_start` قبلاً پوشش داده) — به فلو ویژوال اجازه می‌دهد دستورهای دلخواه تعریف کند، همان قابلیتی که ابزار چتی «Define Command» می‌دهد. توکن دستور را استخراج می‌کند، `BuiltBot` را می‌خواند، `_register_subscriber` را صدا می‌زند، و `run_flow(bot, bot_id, built_bot.flow_definition, command_token, message, state)` را اجرا می‌کند.

#### `@dp.message(BuiltBotBroadcastStates.waiting_for_message, CommandFilter("cancel"), F.from_user.id == owner_telegram_id) async def cancel_broadcast(message, state) -> None`
- **چه‌کار می‌کند:** اگر مالک وسط تایپ پیام broadcast دستور `/cancel` بزند، `state.clear()` و پیام «Broadcast cancelled ❌».

#### `@dp.message(BuiltBotBroadcastStates.waiting_for_message, F.from_user.id == owner_telegram_id) async def handle_broadcast_message(message, state) -> None`
- **چه‌کار می‌کند:** پیام واقعی broadcast مالک را می‌گیرد، `command_name` را از FSM data می‌خواند، `state.clear()`، `_broadcast_to_subscribers(bot_id, command_name, message)` را صدا می‌زند و تعداد گیرندگان را گزارش می‌دهد.

#### `@dp.message(F.text.startswith("/"), F.from_user.id == owner_telegram_id) async def handle_owner_command(message, state) -> None`
- **چه‌کار می‌کند:** هر دستور دیگری که مالک بفرستد و توسط هندلرهای بالاتر (فلو، start و غیره) match نشده باشد، به این‌جا می‌رسد. رکورد `Command` با `name == command_token` **و** `command_type == "broadcast"` را جستجو می‌کند؛ اگر پیدا نشد بی‌صدا `return` (یعنی این دستوری‌است که تعریف نشده یا نوعش broadcast نیست). اگر پیدا شد، `state` را `BuiltBotBroadcastStates.waiting_for_message` می‌کند و از مالک متن broadcast را می‌خواهد.
- **موارد خاص/edge case:** این هندلر آخرین fallback برای دستورهای مالک است — طبق ترتیب ثبت هندلرها در aiogram، تا این‌جا برسد یعنی هیچ‌کدام از `handle_start`, `_has_flow_trigger` و... این پیام را نگرفته‌اند.

#### `@dp.message(F.text, ~F.text.startswith("/")) async def handle_possible_content_code(message) -> None`
- **چه‌کار می‌کند:** طبق docstring، آخرین fallback مطلق: فقط وقتی هیچ state-scoped handler و هیچ command handler دیگری match نکرده، متن آزاد پیام را با کدهای میان‌بر محتوا (`bot/db/models.py:ContentItem.code`) مقایسه می‌کند (`get_item_by_code(bot_id, message.text or "")`). اگر پیدا نشد، بی‌صدا `return` (متن نامرتبط، نادیده گرفته می‌شود). اگر پیدا شد، مشترک را ثبت می‌کند و مستقیم به آن آیتم می‌پرد — دقیقاً همان الگوی «پوشه vs leaf» که `handle_content_item` دارد (`_send_content_children` سپس در صورت نبودن فرزند `_send_content_post`).

---

بعد از تعریف تمام هندلرهای بالا، `_run_bot` وارد بلوک نهایی `try/except/finally` می‌شود که پیش‌تر توضیح داده شد (حذف وبهوک، sync دستورها، شروع polling، لاگ crash، بستن session).

### `def start_built_bot(bot_id: uuid.UUID, token: str) -> None`
- **چه‌کار می‌کند:** شروع (یا ری‌استارت) task پولینگ زنده‌ی یک ربات ساخته‌شده. `key = str(bot_id)` را در `_running_bots` چک می‌کند؛ اگر یک task موجود و هنوز تمام‌نشده (`not existing.done()`) دارد، **هیچ‌کاری نمی‌کند** (idempotent guard — از اجرای دوبار polling روی یک توکن جلوگیری می‌کند، که تلگرام آن را با خطای "terminated by other getUpdates request" رد می‌کند). وگرنه `asyncio.create_task(_run_bot(bot_id, token))` را می‌سازد و در `_running_bots[key]` ذخیره می‌کند.
- **پارامترها:** `bot_id`, `token`.
- **صدا زده می‌شود از:** `start_all_built_bots` (در startup) و جاهای دیگری در پروژه (مثل هنگام فعال‌سازی trial/خرید پلن یا unsuspend توسط ادمین — طبق کامنت `run_live_expiry_loop`).

### `def stop_built_bot(bot_id: uuid.UUID) -> None`
- **چه‌کار می‌کند:** task پولینگ ربات را از `_running_bots` بیرون می‌کشد (`pop`) و اگر وجود داشت و هنوز تمام نشده، `task.cancel()` می‌کند. طبق docstring، idempotent است — اگر ربات اصلاً در حال اجرا نبود، هیچ اتفاقی نمی‌افتد (بدون خطا).
- **کِی صدا زده می‌شود:** وقتی بازه‌ی Live یک ربات (`bot/live.py`) منقضی شود یا ادمین آن را تعلیق کند.

### `async def start_all_built_bots() -> None`
- **چه‌کار می‌کند:** در startup صدا زده می‌شود. تمام رکوردهای `BuiltBot` را می‌خواند، فیلتر می‌کند فقط آن‌هایی که `live_until is not None and live_until > now and not suspended` باشند — طبق docstring، رباتی که هرگز Live نشده، پلن/trialش منقضی شده، یا suspend شده، «ثبت‌شده ولی روی تلگرام خاموش» می‌ماند. برای هرکدام `start_built_bot(id, token)` صدا می‌زند و در پایان تعداد را لاگ می‌کند.

### `async def run_live_expiry_loop(interval_seconds: int = 300) -> None`
- **چه‌کار می‌کند:** یک حلقه‌ی `while True` بی‌پایان که هر ۵ دقیقه (پیش‌فرض) یک‌بار می‌خوابد و چک می‌کند. طبق docstring صریح، این loop تنها مسیر **توقف** (نه شروع) است — چون فعال‌سازی (شروع trial، خرید پلن، رفع تعلیق توسط ادمین) بلافاصله و مستقیماً `start_built_bot` را از جای دیگری صدا می‌زند؛ این loop فقط باید انقضا یا تعلیق را رصد کند.
  1. `running_ids` را از کلیدهای `_running_bots` می‌سازد؛ اگر خالی بود `continue` (چیزی برای چک نیست).
  2. رکوردهای `BuiltBot` با `id IN running_ids` را می‌خواند.
  3. برای هرکدام: اگر `suspended`، `stop_built_bot` صدا می‌زند و لاگ می‌کند؛ در غیر این صورت اگر `live_until` گذشته باشد (`<= now`)، همین‌طور متوقف می‌کند.
  4. کل بدنه‌ی حلقه در `try/except Exception` قرار دارد و `logger.exception` می‌کند — تا یک خطای گذرا (مثلاً مشکل موقت دیتابیس) کل loop پس‌زمینه را برای همیشه نکشد؛ حلقه در تکرار بعدی دوباره تلاش می‌کند.
- **پارامترها:** `interval_seconds` — فاصله‌ی هر چک، پیش‌فرض ۳۰۰ ثانیه.

### `async def run_campaign_expiry_loop(interval_seconds: int = 300) -> None`
- **چه‌کار می‌کند:** حلقه‌ی مشابه بالا، ولی برای کمپین‌های تخفیف قیمت (`bot/shop.py:PriceCampaign`). هر تکرار `shop.expire_due_campaigns()` را صدا می‌زند — این تابع در `bot/shop.py` هر کمپینی که `ends_at`ش گذشته را پیدا کرده، قیمت‌ها را به قیمت پیش از کمپین برمی‌گرداند، و لیست `bot_id` های تحت تأثیر را برمی‌گرداند؛ برای هرکدام یک خط لاگ اطلاعاتی می‌زند. طبق docstring، **برای همه‌ی ربات‌ها** (چه Live چه غیر Live) اجرا می‌شود تا داده‌ی قیمت همیشه صحیح بماند، حتی اگر ربات در آن لحظه polling نداشته باشد. همان الگوی `try/except Exception` + `logger.exception` برای مقاومت در برابر خطای گذرا.
- **پارامترها:** `interval_seconds` — پیش‌فرض ۳۰۰ ثانیه.
