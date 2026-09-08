# مستند فنی هندلرها و کیبوردهای easymakebot

این مستند خط‌به‌خط دوازده فایل هسته‌ای مسیرهای `bot/handlers/` و `bot/keyboards.py` را پوشش می‌دهد. برای هر فایل، هدف کلی و سپس تک‌تک توابع/هندلرها با تریگر دقیق، رفتار مرحله‌به‌مرحله، پارامترها، موارد خاص و ارتباط با سایر ماژول‌ها توضیح داده شده است.

---

## `bot/handlers/start.py`

این فایل نقطه‌ی ورود کاربر به کل پلتفرم easymakebot است: هندلر `/start` و کل فرایند اختیاری «اشتراک‌گذاری شماره تلفن» برای بومی‌سازی راهنما (فارسی/انگلیسی) را پیاده می‌کند. همچنین `/help` را ارائه می‌دهد. State مربوط به این جریان از `OnboardingStates` (در `bot/states.py`) می‌آید و متن‌های راهنما از `bot/guide.py` گرفته می‌شود.

### `_save_phone_and_continue(message, state, phone) -> None`
- **دکوریتور/تریگر:** تابع کمکی داخلی است (نه هندلر مستقیم)، از دو هندلر `receive_phone` و `receive_typed_phone` صدا زده می‌شود.
- **چه‌کار می‌کند:** رکورد `User` متناظر با `telegram_id` پیام را در دیتابیس پیدا می‌کند، فیلد `phone_number` را با مقدار `phone` آپدیت و `commit` می‌کند؛ سپس FSM state را پاک (`state.clear()`) کرده، پیام تشکر با `ReplyKeyboardRemove()` می‌فرستد و `send_platform_guide(message, phone)` (از `bot/guide.py`) را برای ارسال راهنمای بومی‌سازی‌شده فراخوانی می‌کند.
- **پارامترها:** `message` (شیء پیام آیوگرام)، `state` (`FSMContext`)، `phone` (رشته‌ی شماره‌ی نهایی‌شده با `+`).
- **ارتباط با سایر فایل‌ها:** به `bot/db/models.py:User` و `bot/guide.py:send_platform_guide` وابسته است.

### `cmd_start(message, state) -> None`
- **دکوریتور/تریگر:** `@router.message(CommandStart())` — یعنی هر پیام `/start` (بدون نیاز به state خاص).
- **چه‌کار می‌کند:**
  1. `telegram_id` کاربر را می‌خواند و در جدول `User` جستجو می‌کند؛ اگر کاربر جدید است، رکورد تازه می‌سازد.
  2. `state.clear()` — یعنی هرگونه context قبلی مثل `active_bot_id` (ربات انتخاب‌شده‌ی قبلی) پاک می‌شود؛ چون `/start` همیشه صفحه‌ی سطح‌بالای «هیچ رباتی انتخاب نشده» است.
  3. پیام خوش‌آمدگویی به همراه `welcome_keyboard()` (از `bot/keyboards.py`) می‌فرستد.
  4. اگر کاربر قبلاً شماره تلفن ثبت کرده (`phone is not None`، حتی رشته‌ی خالی که یعنی «قبلاً Skip زده»)، مستقیم `send_platform_guide` صدا زده می‌شود و تابع تمام می‌شود.
  5. در غیر این صورت وارد state `OnboardingStates.waiting_for_phone` می‌شود و پیام درخواست شماره تلفن (`PHONE_PROMPT`) را با کیبورد `phone_share_keyboard()` (از `bot/guide.py`) می‌فرستد.
- **موارد خاص:** مقدار `""` (رشته خالی، نه `None`) برای `phone_number` یعنی «قبلاً پرسیده شده و کاربر Skip زده» — پس دیگر دوباره پرسیده نمی‌شود؛ همان قرارداد در `bot/flow_engine.py` (نود `guide_video`) هم استفاده می‌شود.
- **ارتباط:** `bot/keyboards.py:welcome_keyboard`، `bot/guide.py`، `bot/states.py:OnboardingStates`.

### `receive_phone(message, state) -> None`
- **دکوریتور/تریگر:** `@router.message(OnboardingStates.waiting_for_phone, F.contact)` — فقط وقتی state روی `waiting_for_phone` است و پیام حاوی یک `contact` (اشتراک‌گذاری مخاطب/شماره از طریق دکمه) باشد.
- **چه‌کار می‌کند:** شماره را از `message.contact.phone_number` می‌خواند، اگر با `+` شروع نمی‌شد اضافه می‌کند، سپس `_save_phone_and_continue` را صدا می‌زند.

### `skip_phone(message, state) -> None`
- **دکوریتور/تریگر:** `@router.message(OnboardingStates.waiting_for_phone, F.text == SKIP_BUTTON_TEXT)` — دکمه «⏭ Skip» در همان state.
- **چه‌کار می‌کند:** مقدار `phone_number` کاربر را به `""` (رشته خالی) تنظیم می‌کند (نه `None`) تا بعداً دوباره پرسیده نشود، state را پاک می‌کند، پیام «Okay ✅» می‌فرستد و `send_platform_guide(message, None)` صدا می‌زند (چون `phone=None` یعنی راهنمای انگلیسی پیش‌فرض نشان داده شود).

### `receive_typed_phone(message, state) -> None`
- **دکوریتور/تریگر:** `@router.message(OnboardingStates.waiting_for_phone, F.text)` — هر متن دیگری در همان state (پایین‌ترین اولویت نسبت به دو هندلر بالا).
- **چه‌کار می‌کند:** با `normalize_typed_phone(message.text)` (از `bot/guide.py`) سعی می‌کند شماره‌ی تایپ‌شده را اعتبارسنجی کند (باید با `+` و کد کشور باشد). اگر نامعتبر بود، پیام خطای `TYPED_PHONE_INVALID` با کیبورد دوباره ارسال می‌شود. اگر معتبر بود `_save_phone_and_continue` صدا زده می‌شود.

### `cmd_help(message) -> None`
- **دکوریتور/تریگر:** `@router.message(Command("help"))`.
- **چه‌کار می‌کند:** یک پیام ثابت شامل فهرست دستورهای اصلی پلتفرم (`/start`, `/mybots`, `/newbot`, `/live`, `/help`) و راهنمای کوتاه استفاده از کیبوردها ارسال می‌کند. هیچ تعامل با دیتابیس یا state ندارد.

---

## `bot/handlers/my_bots.py`

این فایل مسئول نمایش فهرست ربات‌های ساخته‌شده‌ی کاربر («My Bots») و ورود به محیط ساخت/ویرایش یک ربات مشخص است. سه نقطه‌ی ورود دارد: دکمه‌ی reply-keyboard، دستور `/mybots`، و کال‌بک انتخاب یک ربات از لیست.

### `_render_my_bots(telegram_id) -> tuple[str, InlineKeyboardMarkup]`
- **دکوریتور/تریگر:** تابع کمکی داخلی، هندلر نیست.
- **چه‌کار می‌کند:** کاربر را با `telegram_id` پیدا می‌کند، سپس همه‌ی رکوردهای `BuiltBot` متعلق به او را (مرتب‌شده بر اساس `created_at`) می‌خواند. اگر ربات نداشته باشد متن «You haven't built any bots yet.» برمی‌گرداند، وگرنه «Your bots:». کیبورد را با `my_bots_keyboard(bots)` (از `bot/keyboards.py`) می‌سازد.

### `show_my_bots(message) -> None`
- **دکوریتور/تریگر:** `@router.message(F.text == MY_BOTS_BUTTON_TEXT)` — یعنی دکمه‌ی متنی «🤖 My Bots».
- **چه‌کار می‌کند:** `_render_my_bots` را صدا می‌زند، سپس به متن یک نکته‌ی راهنمای اضافی (`help_text.tip_suffix("my_bots", ...)`) می‌چسباند و پیام را با کیبورد اینلاین ارسال می‌کند.
- **تفاوت با `cmd_my_bots`:** فقط این نسخه `tip_suffix` را اضافه می‌کند.

### `cmd_my_bots(message) -> None`
- **دکوریتور/تریگر:** `@router.message(Command("mybots"))`.
- **چه‌کار می‌کند:** همان کار `show_my_bots` ولی بدون افزودن `tip_suffix`.

### `select_bot(callback, state) -> None`
- **دکوریتور/تریگر:** `@router.callback_query(F.data.startswith("select_bot:"))` — کال‌بک‌دیتای دکمه‌های ساخته‌شده در `my_bots_keyboard` که به شکل `select_bot:<bot_id>` است.
- **چه‌کار می‌کند:**
  1. `bot_id` را از `callback.data` استخراج می‌کند.
  2. با `live.get_owned_built_bot(bot_id, callback.from_user.id)` بررسی مالکیت انجام می‌شود — **نه** `get_built_bot` ساده، چون `bot_id` مستقیماً از ورودی کاربر (callback_data) می‌آید و باید تأیید مالکیت شود پیش از اینکه در `active_bot_id` state ذخیره شود.
  3. اگر ربات پیدا نشد یا متعلق به این کاربر نبود، `callback.answer("Bot not found.", show_alert=True)` و پایان.
  4. در غیر این صورت `active_bot_id` را در FSM state ذخیره می‌کند (`state.update_data(active_bot_id=str(built_bot.id))`).
  5. اگر ربات توسط ادمین پلتفرم معلق (`live.is_bot_suspended`) شده باشد، پیام وضعیت تعلیق نشان داده می‌شود و بازمی‌گردد (این چک از انقضا اولویت بالاتری دارد).
  6. اگر منقضی شده باشد (`live.is_bot_expired`)، پیام وضعیت به همراه راهنمای رفتن به `/live` نشان داده می‌شود.
  7. در حالت عادی، پیام خوش‌آمد به محیط ساخت/ویرایش همراه با کیبورد `tools_reply_keyboard()` ارسال می‌شود.
  8. اگر `webapp_keyboard(_config.webapp_url, built_bot.id)` مقدار غیر `None` برگرداند (یعنی `WEBAPP_URL` تنظیم شده)، دکمه‌ی «🎨 Visual Builder» هم به‌عنوان پیام جدا اضافه می‌شود.
- **ارتباط:** `bot/live.py` (توابع `get_owned_built_bot`, `is_bot_suspended`, `is_bot_expired`, `suspension_status_text`, `status_text`)، `bot/keyboards.py` (`my_bots_keyboard`, `tools_reply_keyboard`, `webapp_keyboard`)، `bot/config.py`.

---

## `bot/handlers/create_bot.py`

مسئول جریان ساخت ربات جدید: گرفتن توکن از کاربر، اعتبارسنجی آن روی API تلگرام، و ثبت رکورد `BuiltBot` جدید در دیتابیس. state آن `CreateBotStates` است.

### `_ask_for_token(message, state, tip_key) -> None`
- **دکوریتور/تریگر:** تابع کمکی داخلی.
- **چه‌کار می‌کند:** وارد state `CreateBotStates.waiting_for_token` می‌شود، پیام «Send me the token you got from @BotFather.» را می‌فرستد (با `cancel_reply_keyboard()`)؛ اگر `tip_key` داده شده باشد، `tip_suffix` هم اضافه می‌شود.

### `ask_for_token(message, state) -> None`
- **دکوریتور/تریگر:** `@router.message(F.text == CREATE_BOT_BUTTON_TEXT)` — دکمه‌ی «➕ Create New Bot».
- **چه‌کار می‌کند:** `_ask_for_token` را با `tip_key="create_bot"` صدا می‌زند (یعنی نکته‌ی راهنمای مربوط به دریافت توکن از BotFather نمایش داده می‌شود).

### `cmd_new_bot(message, state) -> None`
- **دکوریتور/تریگر:** `@router.message(Command("newbot"))`.
- **چه‌کار می‌کند:** `_ask_for_token` را با `tip_key=None` صدا می‌زند (بدون نکته‌ی اضافه).

### `receive_token(message, state) -> None`
- **دکوریتور/تریگر:** `@router.message(CreateBotStates.waiting_for_token)` — هر پیام در این state.
- **چه‌کار می‌کند:**
  1. متن پیام را به عنوان توکن می‌گیرد (`strip()`).
  2. یک نمونه‌ی موقت `Bot(token=token, session=make_session())` می‌سازد و `get_me()` را صدا می‌زند تا اعتبار توکن (و دسترسی شبکه) بررسی شود.
  3. اگر Exception رخ دهد (توکن نامعتبر است)، پیام خطا فرستاده و از تابع خارج می‌شود؛ در بلوک `finally` سشن HTTP موقت (`temp_bot.session.close()`) همیشه بسته می‌شود، حتی در حالت خطا.
  4. در صورت موفقیت، کاربر (`User`) در دیتابیس پیدا یا ساخته می‌شود (`flush()` برای گرفتن `id` پیش از commit نهایی).
  5. یک رکورد `BuiltBot` جدید با `owner_id`, `token`, `bot_username` (از `bot_info.username`)، `display_name` (از `full_name` یا در نبود آن `username` یا «Unnamed») ساخته و `commit`/`refresh` می‌شود.
  6. state فعلی پاک شده و `active_bot_id` جدید در آن ذخیره می‌شود.
  7. پیام موفقیت («Bot "..." registered successfully ✅ ...») با `tools_reply_keyboard()` ارسال می‌شود؛ توضیح داده می‌شود که ربات هنوز روی تلگرام فعال نیست تا `/live` زده شود.
  8. مثل `select_bot`، اگر `webapp_keyboard` مقدار داشته باشد، دکمه‌ی Visual Builder هم اضافه می‌شود.
- **موارد خاص:** توکن به‌صورت رمزنگاری‌شده در ستون `token` (نوع `EncryptedString` در `bot/db/models.py`) ذخیره می‌شود. هیچ چک تکراری‌نبودن توکن اینجا انجام نمی‌شود (احتمالاً روی سطح دیتابیس/سرویس دیگری کنترل می‌شود).
- **ارتباط:** `bot/session.py:make_session`, `bot/db/models.py:User/BuiltBot`, `bot/keyboards.py`.

---

## `bot/handlers/cancel.py`

پیاده‌ساز عملیات سراسری «لغو» (Cancel) که هر فرایند چندمرحله‌ای در حال اجرا را متوقف می‌کند و کاربر را یا به منوی ابزارهای همان ربات (اگر ربات فعالی انتخاب شده) یا به منوی خوش‌آمد سطح بالا برمی‌گرداند.

### `_reset_state(state) -> str | None`
- **دکوریتور/تریگر:** تابع کمکی داخلی.
- **چه‌کار می‌کند:** داده‌های فعلی state را می‌خواند؛ اگر `active_bot_id` در آن باشد، state را به `None` تنظیم کرده و فقط `active_bot_id` را نگه می‌دارد (یعنی flow لغو می‌شود ولی انتخاب ربات باقی می‌ماند)؛ در غیر این صورت کل state پاک می‌شود (`state.clear()`). مقدار `bot_id` (یا `None`) را برمی‌گرداند.

### `_send_cancelled(message, state) -> None`
- **دکوریتور/تریگر:** تابع کمکی داخلی.
- **چه‌کار می‌کند:** `_reset_state` را صدا می‌زند؛ اگر `bot_id` وجود داشت، پیام «Cancelled ❌ Back to the tools menu.» با `tools_reply_keyboard()` می‌فرستد؛ در غیر این صورت پیام «Cancelled ❌ What would you like to do?» با `welcome_keyboard()`.

### `cancel_command(message, state) -> None`
- **دکوریتور/تریگر:** `@router.message(Command("cancel"))`.
- **چه‌کار می‌کند:** `_send_cancelled` را صدا می‌زند.

### `cancel_text(message, state) -> None`
- **دکوریتور/تریگر:** `@router.message(F.text == CANCEL_BUTTON_TEXT)` — دکمه‌ی متنی «❌ Cancel».
- **چه‌کار می‌کند:** همان `_send_cancelled`.
- **موارد خاص:** طبق کامنت داخل کد، متن «❌ Cancel» در کل اپلیکیشن *فقط* برای این عمل سراسری رزرو شده است؛ هر ابزار دیگری که یک دکمه‌ی «برگشت به منوی خودش» دارد از متن‌های متفاوتی مثل «🔙 Back to Shop Menu» استفاده می‌کند تا با این match سراسری تداخل نکند. این router باید در `bot/main.py` **قبل از** روترهای مختص هر state ثبت شود تا همیشه اولویت داشته باشد.

### `cancel_callback(callback, state) -> None`
- **دکوریتور/تریگر:** `@router.callback_query(F.data == "cancel_flow")`.
- **چه‌کار می‌کند:** `_send_cancelled(callback.message, state)` را صدا زده، سپس `callback.answer()` می‌کند تا آیکن لودینگ تلگرام روی دکمه ناپدید شود. این callback_data در چندین کیبورد اینلاین دیگر (مثل `content_category_picker_keyboard` و `live_plans_keyboard` در `bot/keyboards.py`) هم استفاده می‌شود.

---

## `bot/handlers/tools_menu.py`

دروازه‌ی ورودی به منوی پنج‌گانه‌ی ابزارهای ساخت/ویرایش («🛠 Build & Edit Tools»). قبل از نمایش منو، وضعیت زنده‌بودن/تعلیق ربات را چک می‌کند.

### `show_tools(message, state) -> None`
- **دکوریتور/تریگر:** `@router.message(F.text == TOOLS_MENU_BUTTON_TEXT)` — دکمه‌ی «🛠 Build & Edit Tools».
- **چه‌کار می‌کند:**
  1. `active_bot_id` را از FSM state می‌خواند.
  2. اگر `bot_id` وجود داشته باشد، `live.get_built_bot(bot_id)` را می‌خواند (بدون چک مالکیت — چون `bot_id` از یک state از‌پیش‌تأییدشده می‌آید، نه ورودی مستقیم کاربر).
  3. اگر ربات معلق باشد (`is_bot_suspended`)، پیام وضعیت تعلیق نمایش داده و بازمی‌گردد (اولویت بالاتر از انقضا).
  4. اگر ربات منقضی باشد (`is_bot_expired`)، پیام وضعیت و راهنمای رفتن به `/live` نمایش داده و بازمی‌گردد — یعنی کل شبکه‌ی ابزارها پشت «زنده‌بودن» ربات قفل است.
  5. در غیر این صورت، پیام «Choose one of the tools below:» با `tools_menu_keyboard()` (شبکه‌ی ۵ دکمه‌ی ابزار) ارسال می‌شود.
- **موارد خاص:** اگر اصلاً `bot_id` در state نباشد (یعنی کاربر هیچ رباتی انتخاب نکرده)، مستقیماً منوی ابزارها نشان داده می‌شود بدون هیچ چک وضعیتی — رفتار فعلی این‌طور نوشته شده که کنترل انتخاب‌نبودن ربات به عهده‌ی خود ابزارهای داخلی (مثل `force_join.py`) گذاشته شده که خودشان پیام «First select a bot from "My Bots".» می‌دهند.
- **ارتباط:** `bot/live.py`, `bot/keyboards.py:tools_menu_keyboard`.

---

## `bot/handlers/easybotadmin.py`

بزرگ‌ترین و مهم‌ترین فایل این گروه: پنل کامل مدیریت پلتفرم برای `PLATFORM_ADMIN_ID` (دستور `/easybotadmin`). طبق کامنت بالای فایل، **هر تک هندلر** با فیلتر `_is_platform_admin = IsPlatformAdmin(_config.platform_admin_id)` (از `bot/filters/admin.py`) محافظت می‌شود و برای هیچ‌کس دیگری در دسترس نیست — همان فیلتری که روی `/send_to_all` در `bot/handlers/admin_broadcast.py` هم اعمال شده. منطق کوئری/تغییر دیتابیس در `bot/admin_panel.py` نگه‌داری می‌شود؛ این فایل فقط سیم‌کشی هندلرهای تلگرام است.

### `_bot_status_line(built_bot) -> str`
- **دکوریتور/تریگر:** تابع کمکی.
- **چه‌کار می‌کند:** بر اساس اولویت suspended > live > expired > never-activated، یک خط وضعیت متنی برمی‌گرداند («🚫 Suspended (...)»، «🔓 Live until ...»، «🔒 Expired» یا «⏸ Never activated»).

### `_send_menu(message) -> None`
- **چه‌کار می‌کند:** پیام «🛡 easymakebot Platform Admin Panel» را با `admin_panel_menu_keyboard()` می‌فرستد.

### `_send_bot_detail(message, bot_id) -> bool`
- **چه‌کار می‌کند:** با `admin_panel.get_bot_detail(bot_id)` جزئیات کامل ربات (خود ربات، مالک، تعداد subscriber، تعداد سفارش پرداخت‌شده، درآمد) را می‌گیرد؛ اگر `None` بود `False` برمی‌گرداند. در غیر این صورت متن جزئیات (نام، یوزرنیم، مالک، وضعیت، تعداد subscriber، تعداد سفارش/درآمد به تومان، تاریخ ساخت) را با `admin_bot_detail_keyboard(built_bot)` می‌فرستد و `True` برمی‌گرداند.

### `open_admin_panel(message) -> None`
- **دکوریتور/تریگر:** `@router.message(CommandFilter("easybotadmin"), _is_platform_admin)` — دستور `/easybotadmin`.
- **چه‌کار می‌کند:** `_send_menu(message)` را صدا می‌زند.

### `back_to_admin_menu(callback, state) -> None`
- **دکوریتور/تریگر:** `@router.callback_query(F.data == "admin:menu", _is_platform_admin)`.
- **چه‌کار می‌کند:** `state.set_state(None)` (پاک کردن هر state جاری) و نمایش دوباره‌ی منوی اصلی ادمین.

### `show_stats(callback) -> None` — `admin:stats`
- **دکوریتور/تریگر:** `@router.callback_query(F.data == "admin:stats", _is_platform_admin)`.
- **چه‌کار می‌کند:** `admin_panel.get_platform_stats()` و `admin_panel.list_recent_activity(5)` را می‌خواند و گزارشی شامل: تعداد کاربران، تعداد کل ربات‌ها (به‌همراه شمار زنده/منقضی/هرگز-فعال‌نشده/معلق)، تعداد کل subscriberها روی همه‌ی ربات‌ها، تعداد محصولات، تعداد سفارش‌ها (و چند‌تای آن پرداخت‌شده)، مجموع درآمد به تومان، و بخش «📰 آخرین فعالیت‌ها» (۵ ربات جدید، ۵ سفارش اخیر با یوزرنیم ربات و مبلغ، ۵ کاربر جدید) نمایش می‌دهد. کیبورد پاسخ `admin_stats_keyboard()` است.

### `export_report(callback, bot) -> None` — `admin:export`
- **دکوریتور/تریگر:** `@router.callback_query(F.data == "admin:export", _is_platform_admin)`.
- **چه‌کار می‌کند:** ابتدا `callback.answer("Generating…")` برای بازخورد فوری؛ سپس `admin_panel.generate_report_excel()` یک فایل اکسل کامل (سه شیت: Users, Bots, Orders) در حافظه می‌سازد و آن را با `BufferedInputFile` به نام `easymakebot_platform_report.xlsx` به‌صورت داکیومنت ارسال می‌کند.

### `show_users(callback) -> None` — `admin:users`
- **دکوریتور/تریگر:** `@router.callback_query(F.data == "admin:users", _is_platform_admin)`.
- **چه‌کار می‌کند:** `_send_users_page(callback.message, 0)` — صفحه‌ی اول لیست کاربران (۲۰تایی، `PAGE_SIZE = 20`).

### `show_users_page(callback) -> None` — `admin:users_page:<offset>`
- **دکوریتور/تریگر:** `@router.callback_query(F.data.startswith("admin:users_page:"), _is_platform_admin)`.
- **چه‌کار می‌کند:** `offset` را از callback_data استخراج می‌کند و `_send_users_page` را با آن صفحه می‌خواند (صفحه‌بندی از طریق دکمه‌های «⬅️ Prev» / «➡️ Next» که `admin_users_keyboard` می‌سازد).

### `show_user_detail(callback) -> None` — `admin:user:<user_id>`
- **دکوریتور/تریگر:** `@router.callback_query(F.data.startswith("admin:user:"), _is_platform_admin)`.
- **چه‌کار می‌کند:** `user_id` را از callback_data می‌گیرد و `admin_panel.get_user_detail(user_id)` را می‌خواند. اگر پیدا نشد alert «User not found.». در غیر این صورت شناسه، آیدی تلگرام، تاریخ عضویت، شماره تلفن (اگر موجود) و فهرست ربات‌های آن کاربر همراه وضعیت هرکدام را نشان می‌دهد؛ کیبورد `admin_user_detail_keyboard(bots)` — هر ربات یک دکمه به `admin:bot:<id>`.

### `show_bots(callback) -> None` — `admin:bots`
- **دکوریتور/تریگر:** `@router.callback_query(F.data == "admin:bots", _is_platform_admin)`.
- **چه‌کار می‌کند:** صفحه‌ی اول تمام ربات‌های پلتفرم (بدون فیلتر مالک) را نشان می‌دهد.

### `show_bots_page(callback) -> None` — `admin:bots_page:<offset>`
- **دکوریتور/تریگر:** `@router.callback_query(F.data.startswith("admin:bots_page:"), _is_platform_admin)`.
- **چه‌کار می‌کند:** صفحه‌بندی مشابه کاربران، برای فهرست ربات‌ها.

### `show_bot_detail(callback) -> None` — `admin:bot:<bot_id>`
- **دکوریتور/تریگر:** `@router.callback_query(F.data.startswith("admin:bot:"), _is_platform_admin)`.
- **چه‌کار می‌کند:** `_send_bot_detail` را صدا می‌زند؛ اگر پیدا نشد alert نمایش می‌دهد.

### `start_suspend(callback, state) -> None` — `admin:suspend:<bot_id>` (تعلیق)
- **دکوریتور/تریگر:** `@router.callback_query(F.data.startswith("admin:suspend:"), _is_platform_admin)`.
- **چه‌کار می‌کند:** `bot_id` را در `admin_target_bot_id` (FSM data) ذخیره می‌کند، وارد state `AdminPanelStates.waiting_for_suspend_reason` می‌شود و از ادمین می‌خواهد دلیل تعلیق را بنویسد (توضیح می‌دهد که این تعلیق را هیچ خرید پلنی نمی‌تواند خنثی کند)؛ کیبورد `admin_bot_cancel_keyboard(bot_id)` (دکمه‌ی «🔙 Cancel» به `admin:bot:<id>`).

### `receive_suspend_reason(message, state) -> None`
- **دکوریتور/تریگر:** `@router.message(AdminPanelStates.waiting_for_suspend_reason, _is_platform_admin)`.
- **چه‌کار می‌کند:** متن دلیل تعلیق را می‌خواند؛ اگر خالی بود خطا نمایش داده و دوباره منتظر می‌ماند. در غیر این صورت `admin_panel.suspend_bot(bot_id, reason)` را صدا می‌زند — که ربات را `suspended=True` می‌کند، `suspension_reason` را ذخیره می‌کند و **polling تلگرامی ربات ساخته‌شده را متوقف می‌کند** (`stop_built_bot` در `bot/runtime.py`)، یعنی آن ربات عملاً آفلاین می‌شود. state پاک شده، پیام تأیید و دوباره جزئیات ربات نمایش داده می‌شود.

### `do_unsuspend(callback) -> None` — `admin:unsuspend:<bot_id>` (رفع تعلیق)
- **دکوریتور/تریگر:** `@router.callback_query(F.data.startswith("admin:unsuspend:"), _is_platform_admin)`.
- **چه‌کار می‌کند:** `admin_panel.unsuspend_bot(bot_id)` را صدا می‌زند — که `suspended=False` و `suspension_reason=None` می‌کند، و اگر `live_until` هنوز در آینده باشد ربات را دوباره روی تلگرام فعال می‌کند (`start_built_bot`). پیام «Unsuspended ✅» و جزئیات جدید ربات نمایش داده می‌شود.

### `show_grant_menu(callback) -> None` — `admin:grant:<bot_id>`
- **دکوریتور/تریگر:** `@router.callback_query(F.data.startswith("admin:grant:"), _is_platform_admin)`.
- **چه‌کار می‌کند:** منوی مدت‌زمان اعطای دسترسی زنده (bypass کردن پرداخت/آزمایشی) را با `admin_grant_access_keyboard(bot_id)` نمایش می‌دهد (گزینه‌ها: +30 روز، +90 روز، +365 روز، ♾ دائمی).

### `do_grant_access(callback) -> None` — `admin:grantdays:<bot_id>:<days|permanent>`
- **دکوریتور/تریگر:** `@router.callback_query(F.data.startswith("admin:grantdays:"), _is_platform_admin)`.
- **چه‌کار می‌کند:** callback_data را با `:` split می‌کند و `bot_id`، `days_raw` را می‌گیرد؛ اگر `days_raw == "permanent"` باشد `days=None`، وگرنه به عدد صحیح تبدیل می‌شود. `admin_panel.grant_bot_access(bot_id, days)` صدا زده می‌شود که `live_until` را به‌روز می‌کند (برای `days=None` معادل ۳۶۵۰ روز / تقریباً ۱۰ سال به‌عنوان «دائمی») و اگر ربات معلق نباشد آن را روی تلگرام استارت می‌کند. پیام «🎁 @username is now live ...» با ذکر بازه نمایش داده می‌شود؛ اگر ربات همچنان معلق باشد یادداشتی اضافه می‌شود که با وجود اعطای دسترسی، هنوز باید رفع تعلیق شود.

### `start_rename(callback, state) -> None` — `admin:rename:<bot_id>`
- **دکوریتور/تریگر:** `@router.callback_query(F.data.startswith("admin:rename:"), _is_platform_admin)`.
- **چه‌کار می‌کند:** `bot_id` را در state ذخیره می‌کند، وارد `AdminPanelStates.waiting_for_rename` می‌شود و از نام جدید می‌پرسد.

### `receive_rename(message, state) -> None`
- **دکوریتور/تریگر:** `@router.message(AdminPanelStates.waiting_for_rename, _is_platform_admin)`.
- **چه‌کار می‌کند:** متن نام جدید را می‌گیرد (اگر خالی بود خطا)، `admin_panel.rename_bot(bot_id, new_name)` را صدا می‌زند (فیلد `display_name` را عوض می‌کند)، پیام تأیید و جزئیات جدید ربات را نشان می‌دهد.

### `start_delete(callback, state) -> None` — `admin:delete:<bot_id>` (حذف — با تایپ تأییدی)
- **دکوریتور/تریگر:** `@router.callback_query(F.data.startswith("admin:delete:"), _is_platform_admin)`.
- **چه‌کار می‌کند:** جزئیات ربات (`get_bot_detail`) را می‌خواند؛ اگر پیدا نشد alert. در غیر این صورت `bot_id` و **یوزرنیم دقیق ربات** (`built_bot.bot_username`) را در FSM data (`admin_target_bot_id`, `admin_delete_username`) ذخیره می‌کند، وارد state `AdminPanelStates.waiting_for_delete_confirmation` می‌شود و هشدار می‌دهد که این حذف کامل و بدون بازگشت است (همه‌ی دستورها، محتوا، محصولات، سفارش‌ها، subscriberها، تنظیمات فروشگاه)، و می‌خواهد ادمین برای تأیید **یوزرنیم ربات را دقیقاً تایپ کند**.
- **مورد خاص کلیدی (مطابق درخواست):** حذف ربات صرفاً با زدن دکمه انجام نمی‌شود؛ ادمین باید متن یوزرنیم ربات را عیناً در چت تایپ کند تا حذف واقعاً اجرا شود — یک قفل دو‌مرحله‌ای در برابر حذف تصادفی به‌دلیل ماهیت کسکید (cascade) عملیات.

### `receive_delete_confirmation(message, state) -> None`
- **دکوریتور/تریگر:** `@router.message(AdminPanelStates.waiting_for_delete_confirmation, _is_platform_admin)`.
- **چه‌کار می‌کند:** متن تایپ‌شده (`typed`) را با `expected` (یوزرنیم ذخیره‌شده در state) مقایسه می‌کند. اگر برابر نبود، پیام «Doesn't match. Type exactly "..." to confirm, or /cancel to abort.» نمایش داده می‌شود و state همچنان باز می‌ماند (کاربر می‌تواند دوباره تلاش کند یا `/cancel` بزند). اگر دقیقاً برابر بود، `admin_panel.delete_bot(bot_id)` صدا زده می‌شود که:
  1. ابتدا `stop_built_bot(bot_id)` (پولینگ ربات را متوقف می‌کند).
  2. رکورد `BuiltBot` را از دیتابیس حذف می‌کند؛ به لطف `cascade="all, delete-orphan"` روی روابط مدل (`bot/db/models.py`)، تمام رکوردهای وابسته (دستورها، آیتم‌های محتوا، محصولات، سفارش‌ها، تنظیمات فروشگاه، کانال‌های Force Join) هم به‌طور خودکار حذف می‌شوند.
  پس از موفقیت پیام «🗑 Deleted @username and everything under it.» نمایش داده و منوی اصلی ادمین دوباره باز می‌شود.

### `start_broadcast_from_panel(callback, state) -> None` — `admin:broadcast`
- **دکوریتور/تریگر:** `@router.callback_query(F.data == "admin:broadcast", _is_platform_admin)`.
- **چه‌کار می‌کند:** وارد همان state ای می‌شود که `bot/handlers/admin_broadcast.py` استفاده می‌کند (`AdminBroadcastStates.waiting_for_message`) و از پیام همگانی می‌پرسد؛ منطق واقعی ارسال در `send_broadcast` (در فایل `admin_broadcast.py`) پیاده‌سازی شده — این‌جا فقط همان state از منوی ادمین هم فعال می‌شود تا دو مسیر ورودی (`/send_to_all` و دکمه‌ی منوی ادمین) به یک هندلر برسند.

### فهرست کامل callback_dataهای این فایل
| callback_data | هندلر | توضیح |
|---|---|---|
| `admin:menu` | `back_to_admin_menu` | بازگشت به منوی اصلی |
| `admin:stats` | `show_stats` | آمار پلتفرم و فعالیت اخیر |
| `admin:export` | `export_report` | خروجی اکسل کامل |
| `admin:users` | `show_users` | صفحه‌ی اول لیست کاربران |
| `admin:users_page:<offset>` | `show_users_page` | صفحه‌بندی کاربران |
| `admin:user:<user_id>` | `show_user_detail` | جزئیات یک کاربر |
| `admin:bots` | `show_bots` | صفحه‌ی اول لیست همه ربات‌ها |
| `admin:bots_page:<offset>` | `show_bots_page` | صفحه‌بندی ربات‌ها |
| `admin:bot:<bot_id>` | `show_bot_detail` | جزئیات یک ربات |
| `admin:suspend:<bot_id>` | `start_suspend` | شروع فرایند تعلیق |
| `admin:unsuspend:<bot_id>` | `do_unsuspend` | رفع تعلیق فوری |
| `admin:grant:<bot_id>` | `show_grant_menu` | منوی انتخاب مدت اعطای دسترسی |
| `admin:grantdays:<bot_id>:<days|permanent>` | `do_grant_access` | اعطای زمان زنده بودن |
| `admin:rename:<bot_id>` | `start_rename` | شروع فرایند تغییر نام |
| `admin:delete:<bot_id>` | `start_delete` | شروع فرایند حذف (نیاز به تایپ تأییدی) |
| `admin:broadcast` | `start_broadcast_from_panel` | ورود به state ارسال پیام همگانی |

**ارتباط کلی با سایر فایل‌ها:** `bot/admin_panel.py` (منطق دیتابیس)، `bot/live.py` (`is_bot_suspended`, `is_bot_live`, `is_bot_expired`)، `bot/filters/admin.py` (`IsPlatformAdmin`)، `bot/states.py` (`AdminPanelStates`, `AdminBroadcastStates`)، `bot/keyboards.py` (تمام کیبوردهای `admin_*`)، `bot/runtime.py` (`start_built_bot`, `stop_built_bot` — که در `admin_panel.py` صدا زده می‌شوند).

---

## `bot/handlers/admin_broadcast.py`

پیاده‌سازی دستور `/send_to_all` — ارسال یک پیام از طرف ادمین پلتفرم به **همه‌ی سازندگان ربات** (نه به کاربران نهایی ربات‌های ساخته‌شده). این فایل هم با همان فیلتر `IsPlatformAdmin` محافظت می‌شود.

### `ask_broadcast_message(message, state) -> None`
- **دکوریتور/تریگر:** `@router.message(Command("send_to_all"), _is_platform_admin)`.
- **چه‌کار می‌کند:** وارد state `AdminBroadcastStates.waiting_for_message` می‌شود و از ادمین می‌خواهد پیامی که باید به همه‌ی سازندگان ربات ارسال شود را بفرستد؛ کیبورد `cancel_inline_keyboard()` (دکمه‌ی inline لغو).

### `send_broadcast(message, state) -> None`
- **دکوریتور/تریگر:** `@router.message(AdminBroadcastStates.waiting_for_message, _is_platform_admin)`.
- **چه‌کار می‌کند:**
  1. تمام کاربرانی که حداقل یک `BuiltBot` دارند را با یک `JOIN` بین `User` و `BuiltBot` (با `distinct()`) استخراج می‌کند — یعنی فقط سازندگان ربات، نه هر کاربری که با ربات اصلی easymakebot تعامل داشته.
  2. برای هرکدام پیام را با `message.copy_to(owner.telegram_id)` کپی/ارسال می‌کند (این پیام همان پیامی است که ادمین به ربات easymakebot فرستاده).
  3. اگر ارسال به یک کاربر خطا بدهد (مثلاً کاربر ربات را بلاک کرده)، خطا با `logger.warning` لاگ می‌شود و ادامه می‌دهد (بدون توقف کل عملیات).
  4. در پایان state پاک می‌شود و پیام «Message sent to N bot creator(s) ✅» نمایش داده می‌شود.
- **ارتباط:** `bot/filters/admin.py`, `bot/db/models.py:User/BuiltBot`, `bot/states.py:AdminBroadcastStates`, `bot/keyboards.py:cancel_inline_keyboard`. همچنین همان state از داخل `bot/handlers/easybotadmin.py` (دکمه‌ی `admin:broadcast`) هم فعال می‌شود — یعنی این هندلر `send_broadcast` نقطه‌ی مشترک هر دو مسیر ورودی است.

---

## `bot/handlers/tools/define_command.py`

ابزار شماره‌ی ۱ («1️⃣ Define Command») برای تعریف دستورهای سفارشی روی یک ربات ساخته‌شده. شامل دو مسیر است: تعریف یک دستور ساده (فقط نام)، و یک ویزارد چندمرحله‌ای مخصوص وقتی نام دستور `/start` است (که اطلاعات کامل معرفی ربات را جمع‌آوری می‌کند).

### `_skip_keyboard() -> ReplyKeyboardMarkup`، `_phone_keyboard() -> ReplyKeyboardMarkup`، `_save_keyboard() -> ReplyKeyboardMarkup`
- توابع کمکی برای ساخت کیبوردهای موقتی ویزارد `/start` (دکمه‌ی «⏭ Skip»، دکمه‌ی اشتراک‌گذاری شماره تلفن، دکمه‌ی «✅ Save /start command» — همه به‌همراه «❌ Cancel»).

### `_send_step(message, state, index) -> None`
- **چه‌کار می‌کند:** بر اساس `index` در لیست `START_WIZARD_FIELDS` (۸ فیلد: `welcome_text`, `admin_telegram_id`, `admin_phone`, `website`, `instagram`, `youtube`, `facebook`, `x`)، اگر `index` از انتهای لیست عبور کرده باشد وارد state `confirm_start_wizard` می‌شود و می‌پرسد آیا مقادیر ذخیره شوند؛ در غیر این‌صورت `wizard_index` را در state ذخیره کرده و بسته به نوع فیلد (`phone`, `optional`, یا معمولی) پرامپت و کیبورد مناسب را می‌فرستد.

### `_open(message, state) -> None`
- **چه‌کار می‌کند:** `active_bot_id` را از state می‌خواند؛ اگر نبود پیام «First select a bot from "My Bots".» و پایان. سپس چک می‌کند آیا `/start` قبلاً برای این ربات تعریف شده یا نه؛ اگر نه، متن راهنمای اضافه‌ای پیشنهاد می‌دهد که اولین دستور `/start` باشد. وارد state `DefineCommandStates.waiting_for_command_name` می‌شود و به متن یک `tip_suffix("tool:define_command", ...)` می‌چسباند.

### `start_define_command(message, state) -> None`
- **دکوریتور/تریگر:** `@router.message(F.text == "1️⃣ Define Command")`.
- **چه‌کار می‌کند:** `_open(message, state)` را صدا می‌زند.

### `receive_command_name(message, state) -> None`
- **دکوریتور/تریگر:** `@router.message(DefineCommandStates.waiting_for_command_name)`.
- **چه‌کار می‌کند:** متن پیام (نام دستور) را می‌خواند؛ اگر با `/` شروع نشود خطا. اگر دقیقاً `/start` باشد، `wizard_payload={}` تنظیم شده و وارد state `DefineCommandStates.start_wizard` می‌شود و `_send_step(message, state, 0)` (اولین سؤال ویزارد) اجرا می‌شود. در غیر این صورت (دستور معمولی)، رکورد `Command` با `command_type="custom"` در دیتابیس ساخته می‌شود (اگر از قبل وجود نداشت)، `sync_bot_commands(bot_id)` (از `bot/runtime.py`) صدا زده می‌شود تا منوی «/» ربات روی تلگرام به‌روز شود، و پیام «Command "..." registered ✅» به‌همراه دعوت به تعریف دستور بعدی نمایش داده می‌شود.

### `wizard_skip(message, state) -> None`
- **دکوریتور/تریگر:** `@router.message(DefineCommandStates.start_wizard, F.text == START_WIZARD_SKIP_TEXT)` — دکمه‌ی «⏭ Skip» در حین ویزارد `/start`.
- **چه‌کار می‌کند:** فیلد جاری را می‌خواند؛ اگر `optional` نبود (Skip مجاز نیست) پیام خطا. وگرنه مقدار آن فیلد را `None` می‌گذارد و به مرحله‌ی بعد می‌رود.

### `wizard_receive(message, state) -> None`
- **دکوریتور/تریگر:** `@router.message(DefineCommandStates.start_wizard)` — هر پیام دیگر (غیر از Skip) در حین ویزارد.
- **چه‌کار می‌کند:**
  - اگر فیلد جاری `phone` باشد: از `message.contact` یا از متن تایپ‌شده (باید با `PHONE_RE` مطابقت داشته باشد، یعنی `+` و ۶ تا ۱۵ رقم) مقدار را می‌گیرد؛ در غیر این صورت پیام خطای اعتبارسنجی.
  - در غیر این صورت متن پیام گرفته می‌شود؛ اگر خالی باشد و فیلد `optional` نباشد خطا؛ اگر فیلد `admin_telegram_id` باشد، متن باید با `TELEGRAM_ID_RE` (باید با `@` شروع شود و ۵ تا ۳۲ کاراکتر باشد) مطابقت کند وگرنه پیام خطای اختصاصی همان فیلد نشان داده می‌شود.
  - مقدار نهایی در `wizard_payload[field["key"]]` ذخیره و به مرحله‌ی بعد (`_send_step(..., index+1)`) می‌رود.

### `wizard_save(message, state) -> None`
- **دکوریتور/تریگر:** `@router.message(DefineCommandStates.confirm_start_wizard, F.text == START_WIZARD_SAVE_TEXT)` — دکمه‌ی «✅ Save /start command».
- **چه‌کار می‌کند:** رکورد `Command` با نام `/start` را در دیتابیس پیدا می‌کند؛ اگر نبود با `command_type="start"` و `payload=payload` (دیکشنری کامل جواب‌های ویزارد) می‌سازد، وگرنه فقط `payload` رکورد موجود را جایگزین می‌کند. `sync_bot_commands(bot_id)` را صدا می‌زند، دوباره وارد state `waiting_for_command_name` می‌شود (برای امکان تعریف دستور بعدی بدون بازگشت به منو) و پیام موفقیت به‌همراه دعوت به دستور بعدی می‌فرستد.

### `show_commands(message, state) -> None`
- **دکوریتور/تریگر:** `@router.message(F.text == "📋 Show Commands")`.
- **چه‌کار می‌کند:** تمام رکوردهای `Command` مربوط به ربات فعال را می‌خواند (مرتب‌شده بر اساس `created_at`)؛ اگر خالی بود پیام «No commands have been defined...». در غیر این صورت فهرستی می‌سازد که هر دستور را با آیکن 📢 (اگر `command_type == "broadcast"`) و تاریخ آخرین ویرایش نشان می‌دهد، و در انتها `tip_suffix("show_commands", ...)` اضافه می‌شود.
- **ارتباط:** `bot/runtime.py:sync_bot_commands`, `bot/db/models.py:Command`, `bot/keyboards.py` (`cancel_reply_keyboard`, `show_commands_button`, `tools_reply_keyboard`), `bot/states.py:DefineCommandStates`, `bot/help_text.py`.

---

## `bot/handlers/tools/force_join.py`

ابزار شماره‌ی ۲ («2️⃣ Force Join») برای مدیریت لیست کانال‌هایی که کاربران نهایی باید قبل از استفاده از ربات ساخته‌شده در آن‌ها عضو شوند. مدل مرتبط `JoinChannel` است و پرچم `force_join_enabled` روی خود `BuiltBot`.

### `_send_menu(message, bot_id, *, extra="") -> None`
- **چه‌کار می‌کند:** رکورد `BuiltBot` را می‌خواند تا بفهمد `force_join_enabled` روشن است یا خاموش؛ متن وضعیت («🔒 currently ON» یا «🔓 currently OFF») را می‌سازد و کیبورد `force_join_menu_keyboard(enabled)` را می‌فرستد.

### `open_force_join(message, state) -> None`
- **دکوریتور/تریگر:** `@router.message(F.text == "2️⃣ Force Join")`.
- **چه‌کار می‌کند:** اگر `active_bot_id` در state نبود پیام «First select a bot from "My Bots".». وگرنه `state.set_state(None)` (پاک کردن هر state قبلی این ابزار) و نمایش منو با `tip_suffix("tool:force_join", ...)`.

### `back_to_menu(callback, state) -> None` — `force_join:menu`
- **دکوریتور/تریگر:** `@router.callback_query(F.data == "force_join:menu")`.
- **چه‌کار می‌کند:** `editing_channel_id` و `pending_channel_name` را از state پاک می‌کند، state را `None` می‌کند و منوی Force Join را دوباره نشان می‌دهد.

### `list_channels(message, state) -> None`
- **دکوریتور/تریگر:** `@router.message(F.text == "📋 List Channels")`.
- **چه‌کار می‌کند:** همه‌ی `JoinChannel`های ربات فعال را می‌خواند؛ اگر خالی بود پیام «No channels have been defined yet.». وگرنه با `force_join_channels_keyboard(channels)` (هر کانال یک دکمه با callback_data به شکل `force_join:select:<id>`) لیست را نشان می‌دهد.

### `new_channel(message, state) -> None`
- **دکوریتور/تریگر:** `@router.message(F.text == "➕ Define New Channel")`.
- **چه‌کار می‌کند:** `editing_channel_id=None` می‌گذارد (یعنی این‌بار حالت «افزودن»، نه «ویرایش»)، وارد state `ForceJoinStates.waiting_for_channel_name` می‌شود و می‌خواهد یوزرنیم کانال با `@` ارسال شود.

### `select_channel(callback, state) -> None` — `force_join:select:<channel_id>`
- **دکوریتور/تریگر:** `@router.callback_query(F.data.startswith("force_join:select:"))`.
- **چه‌کار می‌کند:** `channel_id` را از callback_data می‌گیرد، در `editing_channel_id` ذخیره می‌کند (این‌بار حالت «ویرایش»)، وارد همان state `waiting_for_channel_name` می‌شود و می‌خواهد نام درست کانال دوباره وارد شود.

### `cancel_edit(message, state) -> None`
- **دکوریتور/تریگر:** `@router.message(ForceJoinStates.waiting_for_channel_name, F.text == FORCE_JOIN_BACK_BUTTON_TEXT)` — دکمه‌ی «🔙 Back to Force Join Menu».
- **چه‌کار می‌کند:** `editing_channel_id`/`pending_channel_name` را پاک می‌کند، state را ریست می‌کند و منو را دوباره نشان می‌دهد.

### `confirm_channel(message, state) -> None`
- **دکوریتور/تریگر:** `@router.message(ForceJoinStates.waiting_for_channel_name, F.text == "✅ Confirm")`.
- **چه‌کار می‌کند:** `pending_channel_name` را از state می‌خواند؛ اگر خالی بود («Nothing to save.») برمی‌گردد. اگر `editing_channel_id` مقدار داشت، رکورد موجود `JoinChannel` را می‌یابد و `username` آن را به‌روز می‌کند؛ در غیر این صورت رکورد جدید `JoinChannel(bot_id=bot_id, username=username)` می‌سازد. بعد از commit، state پاک شده («Saved successfully ✅») و منو دوباره نمایش داده می‌شود.

### `receive_channel_name(message, state) -> None`
- **دکوریتور/تریگر:** `@router.message(ForceJoinStates.waiting_for_channel_name)` — پایین‌ترین اولویت در همین state (بعد از دو هندلر متنی بالا).
- **چه‌کار می‌کند:** متن را با `CHANNEL_USERNAME_RE` (باید با `@` شروع شود، ۵ تا ۳۲ کاراکتر) اعتبارسنجی می‌کند؛ اگر نامعتبر بود خطا و دوباره منتظر می‌ماند. اگر معتبر بود، آن را در `pending_channel_name` ذخیره می‌کند و بسته به این‌که در حالت «ویرایش» یا «افزودن» است، متن تأیید مناسب («Update the channel to "..."?» یا «Add "..." to the list?») به‌همراه کیبورد `force_join_confirm_keyboard()` نمایش می‌دهد.

### `toggle_force_join(message, state) -> None`
- **دکوریتور/تریگر:** `@router.message(F.text.in_({"🔓 Disable Force Join", "🔒 Enable Force Join"}))` — یعنی هردو متن دکمه‌ی روشن/خاموش‌کردن با یک هندلر مدیریت می‌شوند.
- **چه‌کار می‌کند:** رکورد `BuiltBot` را می‌خواند؛ اگر پیدا نشد خطا. اگر `force_join_enabled` در حال حاضر `False` است (یعنی می‌خواهیم روشنش کنیم)، ابتدا چک می‌کند حداقل یک `JoinChannel` تعریف‌شده باشد؛ اگر نبود، پیام «Define at least one channel before enabling Force Join.» و از روشن‌کردن جلوگیری می‌کند. در غیر این صورت مقدار `force_join_enabled` را toggle (نقیض) می‌کند، commit می‌شود، پیام «Force Join enabled ✅» یا «Force Join disabled» نمایش داده و منو دوباره رندر می‌شود.
- **موارد خاص:** برخلاف `define_command.py`، این ابزار `sync_bot_commands` را صدا نمی‌زند چون Force Join روی رفتار پیام‌های ورودی ربات اعمال می‌شود نه روی منوی دستورها؛ منطق واقعی اجرای این محدودیت (چک عضویت) در سطح runtime ربات ساخته‌شده (`bot/runtime.py`) پیاده‌سازی می‌شود، نه این‌جا.
- **ارتباط:** `bot/db/models.py:BuiltBot/JoinChannel`, `bot/states.py:ForceJoinStates`, `bot/keyboards.py` (تمام کیبوردهای `force_join_*`), `bot/help_text.py`.

---

## `bot/handlers/tools/message_to_all.py`

ابزار شماره‌ی ۳ («3️⃣ Broadcast») برای تعریف یک دستور که، وقتی مالک ربات آن را روی ربات ساخته‌شده‌اش صدا بزند، پیام همراه آن را به همه‌ی کاربران آن ربات مشخص ارسال کند. برخلاف `admin_broadcast.py` (که سراسر پلتفرم و فقط برای ادمین است)، این ابزار مخصوص یک ربات ساخته‌شده و در دسترس هر سازنده‌ی رباتی است.

### `start_message_to_all(message, state) -> None`
- **دکوریتور/تریگر:** `@router.message(F.text == "3️⃣ Broadcast")`.
- **چه‌کار می‌کند:** اگر `active_bot_id` در state نبود پیام «First select a bot from "My Bots".». وگرنه وارد state `MessageToAllStates.waiting_for_command_name` می‌شود و توضیح می‌دهد که نام دستوری که با `/` شروع می‌شود باید تعریف شود و از این پس هر پیام همراه آن دستور، به همه‌ی کاربران ربات ارسال خواهد شد؛ `tip_suffix("tool:message_to_all", ...)` هم اضافه می‌شود.

### `receive_broadcast_command_name(message, state) -> None`
- **دکوریتور/تریگر:** `@router.message(MessageToAllStates.waiting_for_command_name)`.
- **چه‌کار می‌کند:** متن پیام (نام دستور) را می‌خواند؛ اگر با `/` شروع نشد خطا و دوباره منتظر می‌ماند. سپس رکورد `Command` با همان `name` را برای این `bot_id` جستجو می‌کند: اگر وجود نداشت، رکورد جدید با `command_type="broadcast"` می‌سازد؛ اگر وجود داشت، `command_type` رکورد موجود را به `"broadcast"` تغییر می‌دهد (یعنی می‌تواند یک دستور معمولی از قبل تعریف‌شده را به یک دستور broadcast تبدیل کند). سپس `sync_bot_commands(bot_id)` صدا زده می‌شود، state پاک می‌شود و پیام موفقیت («Command "..." registered for group messaging 📢✅») با `tools_reply_keyboard()` ارسال می‌شود.
- **موارد خاص:** هیچ محدودیتی روی این‌که این دستور از قبل نوع دیگری داشته باشد وجود ندارد — به‌سادگی نوعش overwrite می‌شود؛ منطق واقعی «هنگام دریافت این دستور روی ربات ساخته‌شده، بعدی‌ترین پیام را به همه بفرست» در `bot/runtime.py` (dispatcher خود ربات ساخته‌شده، با state از نوع `BuiltBotBroadcastStates`) پیاده‌سازی می‌شود؛ این فایل فقط دستور را ثبت می‌کند.
- **ارتباط:** `bot/runtime.py:sync_bot_commands`, `bot/db/models.py:Command`, `bot/states.py:MessageToAllStates`, `bot/keyboards.py` (`cancel_reply_keyboard`, `show_commands_button`, `tools_reply_keyboard`).

---

## `bot/keyboards.py`

این فایل هیچ هندلری ندارد — فقط سازنده‌ی تمام کیبوردهای (`ReplyKeyboardMarkup` و `InlineKeyboardMarkup`) استفاده‌شده در سراسر پلتفرم easymakebot است، از منوی خوش‌آمد گرفته تا پنل کامل ادمین. هدف طراحی، جدا نگه‌داشتن ساختار دکمه‌ها از منطق هندلرها است تا تغییر ظاهر منو نیازی به دست‌کاری منطق نداشته باشد. یک قرارداد تکرارشونده در این فایل الگوی «✅ suffix» است: بسیاری از دکمه‌های تنظیمات (پرداخت، اطلاعات فاکتور و ...) بسته به این‌که مقدار مربوطه از قبل در دیتابیس ست شده یا نه، برچسب متفاوتی می‌گیرند — مثلاً «💳 Set Zarinpal ID» تبدیل می‌شود به «💳 Zarinpal ✅» وقتی `zarinpal_merchant_id` مقدار داشته باشد؛ چون این‌ها reply-keyboard هستند (نه inline)، تنها راه انتقال «آیا قبلاً تنظیم شده یا نه» از طریق خودِ متن دکمه است.

### `welcome_keyboard() -> ReplyKeyboardMarkup`
- کیبورد سطح بالای «هیچ رباتی انتخاب نشده»: دو دکمه‌ی «🤖 My Bots» و «➕ Create New Bot».
- **استفاده در:** `bot/handlers/start.py:cmd_start`, `bot/handlers/cancel.py:_send_cancelled` (وقتی `active_bot_id` وجود ندارد).

### `my_bots_keyboard(bots) -> InlineKeyboardMarkup`
- برای هر ربات یک دکمه‌ی اینلاین با متن `<آیکن> <display_name>` و `callback_data=f"select_bot:{b.id}"` می‌سازد. آیکن پویا است: `🚫` اگر ربات معلق باشد (`suspended`)، `🔒` اگر منقضی شده (`live_until <= now`)، وگرنه `🤖`. یک دکمه‌ی همیشگی «➕ Create New Bot» با `callback_data="create_bot"` در انتها اضافه می‌شود.
- **استفاده در:** `bot/handlers/my_bots.py` (`show_my_bots`, `cmd_my_bots` از طریق `_render_my_bots`).

### `tools_reply_keyboard() -> ReplyKeyboardMarkup`
- یک دکمه: «🛠 Build & Edit Tools».
- **استفاده در:** `bot/handlers/my_bots.py:select_bot`، `bot/handlers/create_bot.py:receive_token`، `bot/handlers/cancel.py:_send_cancelled` (وقتی `active_bot_id` هست)، `bot/handlers/tools/define_command.py:wizard_save`، `bot/handlers/tools/message_to_all.py`.

### `tools_menu_keyboard() -> ReplyKeyboardMarkup`
- شبکه‌ی ۲ دکمه در هر ردیف از لیست ثابت `TOOLS` (۵ ابزار: Define Command, Force Join, Broadcast, Content List, Shop).
- **استفاده در:** `bot/handlers/tools_menu.py:show_tools`.

### `show_commands_button() -> ReplyKeyboardMarkup`
- دو دکمه: «📋 Show Commands» و «❌ Cancel».
- **استفاده در:** `bot/handlers/tools/define_command.py` (`_open`, `receive_command_name`, `wizard_save`), `bot/handlers/tools/message_to_all.py:start_message_to_all`.

### `cancel_inline_keyboard() -> InlineKeyboardMarkup`
- یک دکمه‌ی اینلاین «❌ Cancel» با `callback_data="cancel_flow"`.
- **استفاده در:** جاهایی که هنوز از دکمه‌های اینلاین دیگر استفاده می‌کنند: `bot/handlers/admin_broadcast.py`, `bot/handlers/easybotadmin.py:start_broadcast_from_panel`, و (طبق کامنت) `/live`.

### `cancel_reply_keyboard() -> ReplyKeyboardMarkup`
- یک دکمه: «❌ Cancel» (نسخه‌ی reply-keyboard، برای صفحاتی که ورودی متنی می‌گیرند).
- **استفاده در:** `bot/handlers/create_bot.py` (`_ask_for_token`, `receive_token`)، `bot/handlers/tools/define_command.py` (چند نقطه)، `bot/handlers/tools/message_to_all.py`.

### `force_join_toggle_label(enabled) -> str`
- برمی‌گرداند «🔓 Disable Force Join» اگر `enabled=True`، وگرنه «🔒 Enable Force Join». الگوی متن-پویا (نه دکمه، بلکه یک تابع کمکی متنی).

### `force_join_menu_keyboard(enabled) -> ReplyKeyboardMarkup`
- سه ردیف: («📋 List Channels», «➕ Define New Channel»)، (دکمه‌ی toggle بر اساس `force_join_toggle_label(enabled)`)، («❌ Cancel»).
- **استفاده در:** `bot/handlers/tools/force_join.py:_send_menu`.

### `force_join_channels_keyboard(channels) -> InlineKeyboardMarkup`
- یک دکمه‌ی اینلاین به ازای هر کانال (متن = یوزرنیم کانال، `callback_data=f"force_join:select:{c.id}"`)، به‌علاوه یک دکمه‌ی «❌ Cancel» با `callback_data="force_join:menu"`.
- **استفاده در:** `bot/handlers/tools/force_join.py:list_channels`.

### `force_join_confirm_keyboard() -> ReplyKeyboardMarkup`
- دو دکمه: «✅ Confirm» و «🔙 Back to Force Join Menu» (`FORCE_JOIN_BACK_BUTTON_TEXT`).
- **استفاده در:** `bot/handlers/tools/force_join.py:receive_channel_name`.

### `force_join_input_cancel_keyboard() -> ReplyKeyboardMarkup`
- یک دکمه: «🔙 Back to Force Join Menu».
- **استفاده در:** `bot/handlers/tools/force_join.py` (`new_channel`, `select_channel`, `receive_channel_name` هنگام خطا).

### `content_list_menu_keyboard`، `post_engagement_keyboard`، `content_sample_lang_keyboard`، `content_lookup_keyboard`، `content_delete_confirm_keyboard`، `content_group_target_keyboard`، `_content_back_button`، `content_item_label`، `content_menu_keyboard`، `content_items_keyboard`، `content_item_detail_keyboard`، `content_category_picker_keyboard`، `content_input_cancel_keyboard`، `content_skip_keyboard`، `content_for_sale_keyboard`، `content_premium_keyboard`، `content_product_type_keyboard`
- این گروه به ابزار «4️⃣ Content List» تعلق دارند (فایل `bot/handlers/tools/content_list.py`، خارج از محدوده‌ی این مستند) و در محدوده‌ی درخواست شما فقط برای تکمیل تصویر کلی فایل فهرست می‌شوند؛ نکته‌ی کلیدی: `content_item_label` الگوی نمادگذاری پویا دارد — پیشوند `📂` اگر آیتم پوشه/زیرمنو باشد و پیشوند `🔒` اگر آیتم premium باشد، و این تابع میان رندر runtime ربات (`bot/runtime.py`)، سازنده‌ی بصری فلو (`bot/flow_engine.py`) و همین ابزار owner مشترک است.

### `commerce_mode_keyboard`، `COMMERCE_MODE_SHOP_TEXT`، `COMMERCE_MODE_SUBSCRIPTION_TEXT`
- دو دکمه برای انتخاب حالت کسب‌وکار («🏪 Shop» یا «🔁 Subscription») — پرسیده می‌شود اولین باری که مالک ابزار Shop یا Content List را باز می‌کند و `commerce_mode` هنوز تنظیم نشده.

### `shop_menu_keyboard`، `shop_invoice_labels`، `shop_import_keyboard`، `shop_invoice_keyboard`، `shop_campaign_keyboard`، `shop_campaign_confirm_keyboard`، `shop_products_keyboard`، `shop_product_detail_keyboard`، `shop_product_type_keyboard`، `shop_payment_labels`، `shop_payments_keyboard`، `shop_skip_keyboard`، `shop_input_cancel_keyboard`
- همگی متعلق به ابزار «5️⃣ Shop» (فایل `bot/handlers/tools/shop.py`، خارج از محدوده‌ی این مستند). نکته‌ی مهم برای تکمیل تصویر: `shop_payment_labels(settings)` و `shop_invoice_labels(settings)` دقیقاً همان الگوی «✅ suffix» را پیاده می‌کنند — مثلاً کلید `zarinpal` برچسب «💳 Zarinpal ✅» می‌گیرد اگر `settings.zarinpal_merchant_id` مقدار داشته باشد، وگرنه «💳 Set Zarinpal ID»؛ همین الگو برای Card-to-Card (نیازمند هم شماره کارت و هم نام دارنده کارت)، Stripe، Crypto، TON و چهار فیلد invoice-branding تکرار می‌شود.

### `live_plans_keyboard(plans, methods, show_trial, show_redeem=False, plans_url=None, is_fa=False) -> InlineKeyboardMarkup`
- برای هر ترکیب `(plan, method)` یک دکمه با `callback_data=f"live:pay:{plan['key']}:{method}"` می‌سازد. اگر `methods` خالی باشد ولی `plans_url` مقدار داشته باشد (یعنی روش پرداخت آنلاین روی خود ربات نیست، مثلاً برای کاربران ایرانی) یک دکمه‌ی لینک خارجی «🌐 خرید پلن روی سایت» / «🌐 Buy a plan on the website» اضافه می‌شود. اگر `show_redeem=True` دکمه‌ی «🎟 فعال‌سازی با کد» با `callback_data="live:redeem"` اضافه می‌شود. اگر `show_trial=True` دکمه‌ی «🧪 Go live on a trial basis (72h)» با `callback_data="live:trial"` اضافه می‌شود. در انتها همیشه دکمه‌ی «❌ Cancel» (`callback_data="cancel_flow"`) هست.
- **استفاده در:** `bot/handlers/live.py` (خارج از دامنه‌ی این مستند، ولی نقطه‌ی اتصال با `bot/live.py:LIVE_PLANS`).

### `live_region_keyboard() -> InlineKeyboardMarkup`
- دو دکمه: «🇮🇷 Iran» (`callback_data="live:region:iran"`) و «🌍 Outside Iran» (`callback_data="live:region:international"`) — برای انتخاب منطقه‌ی روش پرداخت.

### `live_ton_admin_keyboard(payment_id) -> InlineKeyboardMarkup`
- دو دکمه («✅ Confirm»، «❌ Reject») که به `PLATFORM_ADMIN_ID` (نه مالک ربات) فرستاده می‌شود تا یک تراکنش TON دستی را تأیید/رد کند: `callback_data` به شکل `live:ton_approve:<payment_id>` یا `live:ton_reject:<payment_id>`.

### `video_keyboard(video_url, is_fa) -> InlineKeyboardMarkup | None`
- اگر `video_url` خالی باشد `None` برمی‌گرداند (تنظیم‌نشده در `.env`). وگرنه یک دکمه‌ی لینک ویدیو («🎥 آموزش ویدیویی» یا «🎥 Video Tutorial»).
- **استفاده در:** `bot/guide.py:_send` (که از `send_platform_guide` در `bot/handlers/start.py` فراخوانی می‌شود).

### `webapp_keyboard(webapp_url, bot_id) -> InlineKeyboardMarkup | None`
- اگر `webapp_url` تنظیم نشده یا با `https://` شروع نمی‌شود `None` برمی‌گرداند (تلگرام دکمه‌ی `web_app` بدون HTTPS را رد می‌کند). وگرنه یک دکمه‌ی «🎨 Visual Builder» با `WebAppInfo(url=f"{webapp_url}?bot_id={bot_id}")`.
- **استفاده در:** `bot/handlers/my_bots.py:select_bot`، `bot/handlers/create_bot.py:receive_token`.

### `admin_panel_menu_keyboard() -> InlineKeyboardMarkup`
- منوی اصلی پنل ادمین: «📊 Stats & Activity» (`admin:stats`)، ردیف («👥 Users» = `admin:users`، «🤖 All Bots» = `admin:bots`)، «📢 Broadcast to All» (`admin:broadcast`).
- **استفاده در:** `bot/handlers/easybotadmin.py:_send_menu`.

### `admin_users_keyboard(users, offset, has_more, page_size=20) -> InlineKeyboardMarkup`
- یک دکمه به ازای هر کاربر («👤 {telegram_id}»، `callback_data=f"admin:user:{u.id}"`)؛ ردیف صفحه‌بندی «⬅️ Prev»/«➡️ Next» با callback_dataهای `admin:users_page:<offset>`؛ دکمه‌ی پایانی «🔙 Back» (`admin:menu`).
- **استفاده در:** `bot/handlers/easybotadmin.py:_send_users_page`.

### `admin_bots_keyboard(bots, offset, has_more, page_size=20) -> InlineKeyboardMarkup`
- یک دکمه به ازای هر ربات با آیکن `🚫` (معلق) یا `🤖` و متن `{display_name} (@{bot_username})`، `callback_data=f"admin:bot:{b.id}"`؛ صفحه‌بندی مشابه بالا با `admin:bots_page:<offset>`؛ «🔙 Back» به `admin:menu`.
- **استفاده در:** `bot/handlers/easybotadmin.py:_send_bots_page`.

### `admin_bot_detail_keyboard(built_bot) -> InlineKeyboardMarkup`
- ردیف اول پویاست: اگر `built_bot.suspended` باشد «✅ Unsuspend» (`admin:unsuspend:<id>`)، وگرنه «🚫 Suspend» (`admin:suspend:<id>`). سپس «🎁 Grant Access» (`admin:grant:<id>`)، «✏️ Rename» (`admin:rename:<id>`)، «🗑 Delete Bot» (`admin:delete:<id>`)، «🔙 Back to Bots» (`admin:bots`).
- **استفاده در:** `bot/handlers/easybotadmin.py:_send_bot_detail`.

### `admin_grant_access_keyboard(bot_id) -> InlineKeyboardMarkup`
- گزینه‌های مدت زمان: «+30 days» (`admin:grantdays:<id>:30`)، «+90 days» (`admin:grantdays:<id>:90`)، «+365 days» (`admin:grantdays:<id>:365`)، «♾ Permanent» (`admin:grantdays:<id>:permanent`)، و «🔙 Cancel» (`admin:bot:<id>`).
- **استفاده در:** `bot/handlers/easybotadmin.py:show_grant_menu`.

### `admin_user_detail_keyboard(bots) -> InlineKeyboardMarkup`
- یک دکمه به ازای هر ربات آن کاربر («🤖 {display_name}»، `callback_data=f"admin:bot:{b.id}"`) و دکمه‌ی «🔙 Back to Users» (`admin:users`).
- **استفاده در:** `bot/handlers/easybotadmin.py:show_user_detail`.

### `admin_stats_keyboard() -> InlineKeyboardMarkup`
- دو دکمه: «📥 Export Full Report (Excel)» (`admin:export`) و «🔙 Back» (`admin:menu`).
- **استفاده در:** `bot/handlers/easybotadmin.py:show_stats`.

### `admin_bot_cancel_keyboard(bot_id) -> InlineKeyboardMarkup`
- یک دکمه‌ی عمومی «🔙 Cancel» با `callback_data=f"admin:bot:{bot_id}"` — بازگشت به صفحه‌ی جزئیات همان ربات؛ در پرامپت‌های متنی سه فرایند (دلیل تعلیق، تغییر نام، تأیید حذف) استفاده می‌شود.
- **استفاده در:** `bot/handlers/easybotadmin.py` (`start_suspend`, `receive_suspend_reason`, `start_rename`, `receive_rename`, `start_delete`, `receive_delete_confirmation`).

---

## جدول خلاصه‌ی وابستگی بین فایل‌ها

| فایل | وابسته به |
|---|---|
| `start.py` | `bot/guide.py`, `bot/keyboards.py`, `bot/states.py:OnboardingStates`, `bot/db/models.py:User` |
| `my_bots.py` | `bot/live.py`, `bot/help_text.py`, `bot/keyboards.py`, `bot/config.py` |
| `create_bot.py` | `bot/session.py`, `bot/help_text.py`, `bot/keyboards.py`, `bot/states.py:CreateBotStates`, `bot/db/models.py` |
| `cancel.py` | `bot/keyboards.py` (`CANCEL_BUTTON_TEXT`, `tools_reply_keyboard`, `welcome_keyboard`) |
| `tools_menu.py` | `bot/live.py`, `bot/keyboards.py` |
| `easybotadmin.py` | `bot/admin_panel.py`, `bot/live.py`, `bot/filters/admin.py`, `bot/keyboards.py`, `bot/states.py` (`AdminBroadcastStates`, `AdminPanelStates`) |
| `admin_broadcast.py` | `bot/filters/admin.py`, `bot/keyboards.py`, `bot/states.py:AdminBroadcastStates` |
| `tools/define_command.py` | `bot/help_text.py`, `bot/runtime.py:sync_bot_commands`, `bot/keyboards.py`, `bot/states.py:DefineCommandStates`, `bot/db/models.py:Command` |
| `tools/force_join.py` | `bot/help_text.py`, `bot/keyboards.py`, `bot/states.py:ForceJoinStates`, `bot/db/models.py` (`BuiltBot`, `JoinChannel`) |
| `tools/message_to_all.py` | `bot/help_text.py`, `bot/runtime.py:sync_bot_commands`, `bot/keyboards.py`, `bot/states.py:MessageToAllStates`, `bot/db/models.py:Command` |
| `keyboards.py` | تنها به `aiogram.types` و `datetime` وابسته است؛ خودش توسط تقریباً همه‌ی فایل‌های بالا import می‌شود |
