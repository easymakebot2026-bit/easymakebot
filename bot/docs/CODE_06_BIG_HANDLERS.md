# مستند فنی: `content_list.py` و `shop.py`

## `bot/handlers/tools/content_list.py`

این فایل بزرگ‌ترین هندلر پروژه (۱۰۵۸ خط) و پیاده‌سازی ابزار **«4️⃣ Content List»** از منوی Build & Edit Tools است — یعنی مدیریت درخت محتوای یک ربات ساخته‌شده (`ContentItem`): افزودن/ویرایش/حذف آیتم، دسته‌بندی تودرتو (parent/child)، جستجو با کد میانبر، پست‌گذاری برای مشترکین (`BotPost`)، و ایمپورت/اکسپورت اکسل چندزبانه. یک `Router` با نام `content_list` است که در `bot/runtime.py` (یا معادل آن، dispatcher اصلی ربات‌ساز) رجیستر می‌شود. این فایل همچنین محل تصمیم‌گیری یک‌باره‌ی «حالت تجاری» (Shop در برابر Subscription) برای هر بات است و منطق آن را با `bot/handlers/tools/shop.py` به اشتراک می‌گذارد.

### ثابت‌ها و ساختارهای سطح ماژول

- **`ADD_ITEM_FIELDS`**: لیست مراحل متنی ویزارد «➕ Add» به ترتیب: `title`، `body`، `image_url` (اختیاری)، `link_url` (اختیاری)، `code` (اختیاری، یکتا در سطح بات). مرحله‌ی «کدام دسته‌بندی» جداست و بعد از این‌ها با دکمه پرسیده می‌شود.
- **`EDIT_ITEM_FIELDS`**: همان لیست بالا منهای `code` — ویرایش هرگز کد یا `parent_id` آیتم را عوض نمی‌کند؛ جابه‌جایی دسته فقط از مسیر «🔀 Group» ممکن است.
- **`PRODUCT_TYPE_BUTTON_TO_KEY`**: نگاشت متن دکمه به کلید نوع محصول: `"📦 Physical" → "physical"`، `"💾 Digital" → "digital"`، `"🎫 Access / Membership" → "access"`.
- **`POST_PUBLISH_BUTTON_TEXT = "📢 Publish to subscribers"`**

---

### توابع کمکی (بدون دکوریتور)

#### `_send_menu(message: Message) -> None`
- **تریگر:** ندارد؛ فراخوانی داخلی از تقریباً همه‌ی هندلرهای این فایل پس از پایان یک عملیات.
- **کار:** پیام «Manage this bot's content items…» را همراه با `content_list_menu_keyboard()` (`bot/keyboards.py`) می‌فرستد — کیبورد اصلی ابزار: 📋 View / ➕ Add / ✏️ Edit / 🗑 Delete / 📢 Add Post / 🔀 Group / 📥 Download Sample Excel / 📤 Upload Excel / Cancel.

#### `_send_step(message, state, index) -> None`
- **کار:** موتور مرحله‌به‌مرحله‌ی بخش «محتوای متنی» ویزارد Add. اگر `index` از طول `ADD_ITEM_FIELDS` رد شود یعنی پرسش‌های متنی تمام شده‌اند:
  - `wizard_index=None`، `wizard_phase="content_done"` ثبت می‌شود.
  - حالت تجاری بات با `commerce_mode.get_commerce_mode(bot_id)` خوانده می‌شود.
  - اگر **Subscription** باشد: `is_product=False` ست می‌شود (یک آیتم در حالت اشتراک هرگز مجزا فروخته نمی‌شود) و مستقیم به `_maybe_send_premium_step(..., _send_category_step)` می‌رود.
  - در غیر این صورت (Shop) پرسش «Is this item for sale؟» با `content_for_sale_keyboard()` نمایش داده می‌شود.
  - اگر هنوز مرحله باقی مانده: کیبورد `content_skip_keyboard()` (اگر فیلد اختیاری) یا `content_input_cancel_keyboard()` نمایش داده می‌شود.

#### `_send_category_step(message, state) -> None`
- **کار:** همه‌ی آیتم‌های بات را با `content_nav.get_all_items` می‌گیرد و `content_category_picker_keyboard(items)` را برای انتخاب دسته‌ی پدر (اختیاری) نشان می‌دهد.

#### `_send_premium_step(message, state) -> None`
- **کار:** پرسش «🔒 Is this a premium item؟» را با `content_premium_keyboard()` می‌فرستد. مستقل از «for sale» است — یک آیتم می‌تواند هم‌زمان premium، هم قابل‌خرید مجزا، هر دو، یا هیچ‌کدام باشد.

#### `_maybe_send_premium_step(message, state, next_step) -> None`
- **کار:** فقط در حالت **Subscription** واقعاً پرسش premium را نشان می‌دهد (`_send_premium_step`)؛ در حالت **Shop** مستقیماً `is_premium=False` را ذخیره کرده و `next_step` را صدا می‌زند — یعنی بات‌های فروشگاهی هرگز محتوای اشتراکی/premium ندارند.

#### `_send_type_field_step(message, state, index) -> None`
- **کار:** بعد از «Yes, for sale» → «Digital/Physical/Access»، فیلدهای اختصاصی نوع محصول را از `TYPE_FIELDS` (وارد شده از `bot/shop.py`) یکی‌یکی می‌پرسد. با پایان یافتن فیلدها، `_maybe_send_premium_step(..., _send_category_step)` صدا زده می‌شود.

#### `_send_children(message, bot_id, parent_id, back_target) -> bool`
- **کار:** فرزندان یک گره را با `content_nav.get_children` می‌گیرد؛ اگر خالی بود `False` برمی‌گرداند (چیزی نمی‌فرستد)؛ در غیر این صورت با `content_nav.folder_ids_among` مشخص می‌کند کدام‌یک خودشان «پوشه» هستند (برای آیکون 📂) و لیست را با `content_items_keyboard` می‌فرستد.

#### `_send_edit_step(message, state, index) -> None`
- **کار:** موتور مرحله‌ای ویزارد ویرایش؛ برخلاف Add، مقدار فعلی هر فیلد را هم زیر پرسش نشان می‌دهد (`Current value: …`). با پایان `EDIT_ITEM_FIELDS`، `_maybe_send_premium_step(..., _save_edit)` صدا زده می‌شود.

#### `_save_edit(message, state) -> None`
- **کار:** `is_premium` را در payload می‌گذارد و `content_nav.upsert_item(bot_id, payload, item_id=...)` را صدا می‌زند. اگر آیتم دیگر وجود نداشت (`None` برگشت) پیام خطا و بازگشت به منو؛ در غیر این صورت `sync_bot_commands(bot_id)` (بات‌رانتایم را از تغییرات — مثلاً کد میانبر جدید — باخبر می‌کند) و «Item updated ✅».

#### `_act_on_resolved_item(message, state, item, mode) -> None`
- **کار:** نقطه‌ی مشترک سه فلوی Edit/Delete/Group پس از یافتن آیتم هدف (چه با کد، چه با Browse):
  - `mode == "delete"` → تأییدیه‌ی حذف با `content_delete_confirm_keyboard(item.id)`.
  - `mode == "group"` → لیست دسته‌های ممکن با `content_group_target_keyboard`.
  - `mode == "edit"` → داده‌های فعلی آیتم را در `wizard_payload` می‌ریزد، state را `ContentListStates.edit_field_wizard` می‌کند و اولین مرحله‌ی ویرایش را می‌فرستد.

---

### هندلرهای اصلی

#### `open_content_list(message, state) -> None`
- **تریگر:** `@router.message(F.text == "4️⃣ Content List")`
- **کار:** اگر بات فعالی انتخاب نشده باشد خطا می‌دهد. `action_mode` و state را ریست می‌کند. اگر `commerce_mode` بات هنوز تعیین نشده (`None`)، `commerce_mode_source="content_tool"` را در FSM ذخیره کرده و `commerce_mode_keyboard()` را نشان می‌دهد (پرسش یک‌بار‌مصرف Shop/Subscription). در غیر این صورت نکته‌ی راهنما (`help_text.tip_suffix("tool:content_list", ...)`) و منوی اصلی را می‌فرستد.
- **موارد خاص:** انتخاب حالت تجاری **قابل تغییر نیست** — پیام صریحاً همین را می‌گوید.

#### `choose_commerce_mode(message, state) -> None`
- **تریگر:** `@router.message(F.text.in_({COMMERCE_MODE_SHOP_TEXT, COMMERCE_MODE_SUBSCRIPTION_TEXT}))` یعنی متن‌های دقیق `"🏪 Shop (sell individual products)"` یا `"🔁 Subscription (content archive)"`.
- **چرا مشترک است:** این هندلر تنها یک‌بار در `content_list.py` تعریف شده اما هر دو ابزار (`shop.py:open_shop` هم) همین کیبورد را نشان می‌دهند، چون یک دکمه‌ی reply هیچ payload پنهانی حمل نمی‌کند (برخلاف callback_data). راه‌حل: هر ابزار پیش از نمایش کیبورد یک پرچم `commerce_mode_source` (`"content_tool"` یا `"shop_tool"`) در FSM data می‌گذارد؛ این هندلر بر اساس همان پرچم تصمیم می‌گیرد بعد از ثبت حالت، کاربر را به کدام منو برگرداند (اگر `"shop_tool"` باشد با import محلی `from bot.handlers.tools.shop import _send_menu as _send_shop_menu` به منوی Shop می‌رود، وگرنه به منوی Content List خودش).
- **کار:** `commerce_mode.set_commerce_mode(bot_id, mode)` را صدا می‌زند، نکته‌ی راهنمای متناسب (`mode:shop:` یا `mode:subscription:`) را نشان می‌دهد.

#### `back_to_menu(callback, state) -> None`
- **تریگر:** `@router.callback_query(F.data == "content:menu")`
- **کار:** هنوز به‌صورت callback لازم است چون `content_delete_confirm_keyboard` و `content_group_target_keyboard` دکمه‌ی «لغو/Cancel» خودشان را روی همین callback_data می‌فرستند (این دو کیبورد inline باقی مانده‌اند، برخلاف بقیه که reply شده‌اند).

#### `back_to_menu_text(message, state) -> None`
- **تریگر:** `@router.message(F.text == CONTENT_BACK_BUTTON_TEXT)` یعنی `"🔙 Back to Content List"`.
- **کار:** معادل reply-keyboard همان بازگشت.

#### `list_items(message, state) -> None`
- **تریگر:** `@router.message(F.text == "📋 View")`
- **کار:** `_send_children(message, bot_id, None, "menu")` (ریشه‌ی درخت)؛ اگر خالی بود «No content items yet.».

#### `list_at(callback, state) -> None`
- **تریگر:** `@router.callback_query(F.data.startswith("content:list_at:"))`
- **کار:** پیمایش درخت دسته‌بندی. اگر target == `"top"` ریشه؛ وگرنه `parent_id` را از callback می‌خواند، `get_item` را می‌خواند و `back_target` را طوری تعیین می‌کند که دکمه‌ی «🔙 Back» به سطح والدِ همین پوشه برگردد (یا `"top"` اگر خود این پوشه در ریشه بود).

#### `select_item(callback, state) -> None`
- **تریگر:** `@router.callback_query(F.data.startswith("content:select:"))`
- **کار:** آیتم را می‌خواند و مالکیت آن روی `bot_id` فعلی را چک می‌کند. اول تلاش می‌کند فرزندانش را نشان دهد (`_send_children`) — یعنی اگر آیتم خودش «پوشه» باشد وارد آن می‌شود. اگر پوشه نبود (`drilled=False`):
  - اگر `action_mode` در FSM ست شده باشد (یعنی از مسیر «📋 Browse instead» در فلوی Edit/Delete/Group آمده)، مستقیم `_act_on_resolved_item` صدا زده می‌شود.
  - در غیر این صورت جزئیات آیتم نمایش داده می‌شود: عنوان، بدنه، در صورت وجود `product_id` قیمت فروش (`shop.get_product` → `product.price:,} تومان`)، تصویر، لینک — همراه `content_item_detail_keyboard`.

#### `delete_item(callback, state) -> None`
- **تریگر:** `@router.callback_query(F.data.startswith("content:delete:"))`
- **کار:** اگر آیتم فرزند دارد (`get_children`)، حذف را رد می‌کند («This has sub-items — delete those first.»؛ حذف آبشاری پشتیبانی نمی‌شود). در غیر این صورت با یک سشن مستقیم SQLAlchemy حذف می‌شود (نه از طریق `content_nav`)، مالکیت بات چک می‌شود، سپس `sync_bot_commands(bot_id)`.
- **موارد خاص:** این هندلر مستقیماً روی جدول کار می‌کند نه از طریق `content_nav` — تفاوتی نسبت به بقیه‌ی مسیرهای CRUD این فایل.

#### `new_item(message, state) -> None`
- **تریگر:** `@router.message(F.text == "➕ Add")`
- **کار:** `wizard_payload={}` می‌گذارد، state را `ContentListStates.add_item_wizard` می‌کند، نکته‌ی راهنمای `"content:new"` و اولین قدم (`_send_step(..., 0)`) را می‌فرستد.

#### `wizard_skip(message, state) -> None`
- **تریگر:** `@router.message(ContentListStates.add_item_wizard, F.text == SKIP_BUTTON_TEXT)` یعنی `"⏭ Skip"`.
- **کار:** بسته به `wizard_phase` (`"content"` یا فاز فیلدهای نوع محصول) فیلد فعلی را `None` می‌کند و مرحله‌ی بعد را می‌فرستد. اگر فیلد اختیاری نباشد، Skip رد می‌شود.

#### `for_sale_yes(message, state) -> None`
- **تریگر:** state `add_item_wizard`، متن دقیق `"💰 Yes, it's for sale"`.
- **کار:** `is_product=True`، `wizard_phase="price"`؛ پرسش قیمت به تومان.

#### `for_sale_no(message, state) -> None`
- **تریگر:** state `add_item_wizard`، متن `"➖ No"`.
- **کار:** `is_product=False`؛ می‌رود به `_maybe_send_premium_step(..., _send_category_step)`.

#### `premium_yes_add` / `premium_no_add`
- **تریگر:** state `add_item_wizard`، متن دقیق `"🔒 Yes, premium"` یا `"➖ No, free"`.
- **کار:** `is_premium` را ثبت می‌کند و مستقیماً `_send_category_step` را صدا می‌زند (این دو فقط در حالت Subscription قابل‌رسیدن‌اند، چون `_maybe_send_premium_step` در Shop اصلاً این دکمه‌ها را نشان نمی‌دهد).

#### `choose_product_type(message, state) -> None`
- **تریگر:** state `add_item_wizard`، `F.text.in_(PRODUCT_TYPE_BUTTON_TO_KEY)` — یعنی یکی از `"📦 Physical"` / `"💾 Digital"` / `"🎫 Access / Membership"`.
- **کار:** `product_type` را ثبت و اولین فیلد اختصاصی نوع را می‌فرستد (`_send_type_field_step(..., 0)`).

#### `wizard_receive(message, state) -> None`
- **تریگر:** `@router.message(ContentListStates.add_item_wizard)` (catch-all، آخرین هندلر ثبت‌شده روی این state — همه‌ی دکمه‌های دقیق بالا زودتر رجیستر شده‌اند و اولویت دارند).
- **کار:** بسته به `wizard_phase`:
  - `"price"`: باید فقط رقم باشد؛ ذخیره و رفتن به `"type_select"` (پرسش نوع محصول با `content_product_type_keyboard()`).
  - `"type_fields"`: فیلد جاری `TYPE_FIELDS[product_type][index]` را می‌خواند، خالی‌نبودن (مگر اختیاری) را چک می‌کند، ذخیره و مرحله‌ی بعد.
  - در غیر این‌صورت (`"content"`): فیلد `ADD_ITEM_FIELDS[index]`. اگر فیلد `code` باشد و متن خالی نباشد، با `content_nav.get_item_by_code` یکتا بودن کد در سطح بات چک می‌شود؛ در صورت تکراری بودن، خطا و تکرار پرسش.

#### `wizard_save_with_parent(callback, state) -> None`
- **تریگر:** `@router.callback_query(F.data.startswith("content:parent:"), ContentListStates.add_item_wizard)` — یعنی کاربر روی یکی از دکمه‌های `content_category_picker_keyboard` (`content:parent:<id>` یا `content:parent:top`) زده.
- **کار:** آخرین گام ویزارد Add. در یک سشن:
  - اگر `is_product=True`، یک ردیف `Product` جدید می‌سازد (قیمت، `product_type`، `delivery_text`/`delivery_file_url`/`access_level_name`/`subscription_days` بسته به نوع)، `session.flush()` برای گرفتن `product.id` قبل از لینک کردن به آیتم محتوا.
  - سپس `ContentItem` را با `parent_id` انتخاب‌شده، `product_id` (اگر ساخته شد)، `code`، `is_premium` می‌سازد.
  - `sync_bot_commands(bot_id)` و بازگشت به منو.

---

#### `start_add_post(message, state) -> None`
- **تریگر:** `@router.message(F.text == "📢 Add Post")`
- **کار:** state → `ContentListStates.add_post_wizard`، `post_phase="media"`. توضیح می‌دهد این قابلیت جایگزین کانال جداگانه است و پرسش «Send a photo or video» را می‌فرستد.

#### `post_wizard_receive(message, state) -> None`
- **تریگر:** `@router.message(ContentListStates.add_post_wizard)` (catch-all، بعد از `publish_post` رجیستر شده).
- **کار:** بسته به `post_phase`:
  - `"media"`: باید `message.photo` یا `message.video` باشد؛ `media_type`/`file_id` ذخیره می‌شود. اگر خود پیام کپشن داشت، مستقیم پیش‌نمایش (`_send_post_preview`)؛ وگرنه پرسش کپشن جداگانه با `post_phase="caption"`.
  - `"caption"`: کپشن خالی رد می‌شود؛ ذخیره و `_send_post_preview`.

#### `_send_post_preview(message, state) -> None`
- **کار:** پیام‌نما را با `answer_photo`/`answer_video` و کپشن نشان می‌دهد، همراه کیبوردی حاوی `POST_PUBLISH_BUTTON_TEXT` («📢 Publish to subscribers») و Cancel.

#### `publish_post(message, state, bot: Bot) -> None`
- **تریگر:** `@router.message(ContentListStates.add_post_wizard, F.text == POST_PUBLISH_BUTTON_TEXT)`.
- **چرا `Bot` جدا از توکن ربات‌ساز:** پارامتر `bot: Bot` که aiogram خودش تزریق می‌کند همان **بات ربات‌ساز (easymakebot)** است — همان‌جایی که owner در حال چت با ابزار Build & Edit است. اما مشترکین (`BotSubscriber`) در **بات ساخته‌شده‌ی خود owner** عضو شده‌اند، نه در ربات‌ساز. بنابراین:
  1. `built_bot = BuiltBot` از دیتابیس خوانده می‌شود (برای گرفتن `built_bot.token`).
  2. فایل آپلودی با `bot.get_file` / `bot.download_file` از **بات ربات‌ساز** دانلود می‌شود، چون `file_id` که در مرحله‌ی قبل گرفته شده فقط روی همین بات معتبر است (Telegram `file_id` بین بات‌ها منتقل‌پذیر نیست).
  3. یک نمونه‌ی موقت `Bot(token=built_bot.token, session=make_session())` (`bot/session.py`) ساخته می‌شود — این «بات موقت» با توکن خودِ ربات owner صحبت می‌کند تا پست واقعاً از طرف بات owner برای مشترکینش ارسال شود، نه از طرف ربات‌ساز.
  - یک ردیف `BotPost` ساخته می‌شود (ابتدا با `media_file_id=""`).
  - همه‌ی `BotSubscriber` این بات و `telegram_id` مالک (owner) خوانده می‌شوند.
  - ابتدا نسخه‌ای برای **خود owner** فرستاده می‌شود (`_send_via_temp_bot`) — این هم به‌عنوان نسخه‌ی تأییدی عمل می‌کند و هم `file_id`ای معتبر روی بات owner («delivered_file_id») تولید می‌کند که برای بقیه‌ی مشترکین بدون آپلود مجدد بایت‌ها استفاده می‌شود.
  - برای هر مشترک دیگر (owner دوباره skip می‌شود) ارسال با `try/except` انجام می‌شود تا خطای یک نفر بقیه را متوقف نکند؛ شمارنده‌ی `sent` نگه داشته می‌شود.
  - در `finally`، `temp_bot.session.close()` فراخوانی می‌شود تا سشن HTTP نشتی نداشته باشد.
  - در پایان `BotPost.media_file_id` با `delivered_file_id` آپدیت و ذخیره می‌شود، و پیام «✅ Published — delivered to N subscriber(s).» نشان داده می‌شود.
- **موارد خاص:** اگر `bot_id`، `file_id` یا `caption` نبود (سشن خراب/از دست‌رفته)، خطای «Something went wrong» و توقف. اگر ارسال به owner یا هر مشترک با استثنا مواجه شود، فقط لاگ هشدار می‌شود و ادامه می‌یابد.

---

#### `start_edit` / `start_delete` / `start_group`
- **تریگر:** به‌ترتیب `F.text == "✏️ Edit"` / `"🗑 Delete"` / `"🔀 Group (parent/child)"`.
- **کار:** هر سه یک الگوی مشترک دارند: `action_mode` را (`"edit"`/`"delete"`/`"group"`) در FSM می‌گذارند، state را `ContentListStates.lookup_wizard` می‌کنند، و پرسش «کد آیتم را بفرست یا Browse بزن» را با `content_lookup_keyboard()` نشان می‌دهند (به‌همراه نکته‌ی راهنمای مربوط به هرکدام: `content:edit`, `content:delete_start`, `content:group_start`).

#### `lookup_browse(message, state) -> None`
- **تریگر:** state `lookup_wizard`، متن `"📋 Browse instead"`.
- **کار:** به‌جای دریافت کد، لیست ریشه‌ی محتوا را نشان می‌دهد (`_send_children`)؛ کاربر با کلیک روی یک آیتم برگ در `select_item` وارد شاخه‌ی `action_mode` می‌شود (چون آنجا چک `mode = data.get("action_mode")` وجود دارد).

#### `lookup_receive(message, state) -> None`
- **تریگر:** `@router.message(ContentListStates.lookup_wizard)` (catch-all).
- **کار:** کد وارد شده را با `content_nav.get_item_by_code` جست‌وجو می‌کند (case-insensitive). نبود آیتم → پیام خطا و تکرار پرسش با همان کیبورد. یافتن آیتم → `_act_on_resolved_item(message, state, item, mode)`.

#### `edit_wizard_skip` / `premium_yes_edit` / `premium_no_edit` / `edit_wizard_receive`
- **تریگر‌ها:** همگی روی `ContentListStates.edit_field_wizard` — به‌ترتیب `F.text == SKIP_BUTTON_TEXT`، `"🔒 Yes, premium"`، `"➖ No, free"`، و catch-all.
- **کار:** الگوی مشابه `wizard_skip`/`wizard_receive` ولی برای `EDIT_ITEM_FIELDS`. دو هندلر premium مستقیماً `_save_edit` را صدا می‌زنند (چون این آخرین قدم ویرایش است، برخلاف Add که بعد از premium هنوز پرسش دسته‌بندی باقی مانده).

#### `group_to(callback, state) -> None`
- **تریگر:** `@router.callback_query(F.data.startswith("content:groupto:"))` با فرمت `content:groupto:<item_id>:<target>`.
- **کار:** `content_nav.reparent_item(bot_id, item_id, new_parent_id)` را صدا می‌زند که خودش چک مالکیت بات و چرخه (`would_cycle`) را انجام می‌دهد. موفقیت → `sync_bot_commands` + «Item moved ✅»؛ شکست → پیام «may create a loop, or no longer belong to this bot».

---

### ایمپورت/اکسپورت اکسل

#### `download_sample(message) -> None`
- **تریگر:** `F.text == "📥 Download Sample Excel"`.
- **کار:** توضیح می‌دهد که هم می‌شود نمونه گرفت هم کاتالوگ خودِ کاربر (با هدرهای هر یک از ۱۰ زبان) آپلود کرد، و کیبورد زبان (`content_sample_lang_keyboard(SAMPLE_LANGUAGES)`) را نشان می‌دهد. `SAMPLE_LANGUAGES` از `bot/content_import.py` می‌آید: `fa، en، ar، tr، ru، fr، de، es، it، ko`.

#### `download_sample_lang(message) -> None`
- **تریگر:** `@router.message(F.text.in_(_SAMPLE_LABEL_TO_CODE))` — یعنی متن دقیق یکی از برچسب‌های زبان مثل `"🇮🇷 فارسی"`، `"🇬🇧 English"` و... (`_SAMPLE_LABEL_TO_CODE` نگاشت معکوس `SAMPLE_LANGUAGES` است).
- **کار:** `content_import.generate_sample_excel(lang)` یک فایل `.xlsx` می‌سازد (با `openpyxl`، هدر و سه ردیف نمونه‌ی تودرتو: دسته‌ی بالا > زیر‌دسته > آیتم واقعی با یک `Code`) و آن را با `answer_document` ارسال می‌کند؛ کپشن توضیح می‌دهد که ستون `Category` اختیاری است (عنوان دقیق یک ردیف دیگر برای تودرتو کردن)، `Code` اختیاری است (آپلود دوباره‌ی همان فایل با همان کد، upsert می‌کند نه duplicate)، و `Action=Delete` حذف می‌کند.

#### `start_upload(message, state) -> None`
- **تریگر:** `F.text == "📤 Upload Excel"`.
- **کار:** state → `ContentListStates.waiting_for_excel`؛ توضیح که هدر باید در ۱۵ ردیف اول باشد و می‌تواند فارسی/انگلیسی/هر یک از ۱۰ زبان باشد.

#### `receive_excel(message, state, bot: Bot) -> None`
- **تریگر:** `@router.message(ContentListStates.waiting_for_excel, F.document)`.
- **کار:** مهم‌ترین منطق ایمپورت:
  1. فایل با `bot.download(message.document)` گرفته می‌شود؛ `content_import.parse_content_excel(bytes, filename=...)` صدا زده می‌شود (تشخیص `.xlsx`/`.csv`، تشخیص هدر در ۱۵ ردیف اول، تطبیق نام ستون در ۱۰ زبان با نرمال‌سازی حروف عربی/فارسی مشابه `ي↔ی`، `ك↔ک`).
  2. اگر `ValueError` بیفتد (هدر شناسایی نشد) پیام خطا با متن دقیق exception نمایش داده می‌شود.
  3. اگر هیچ ردیفی معتبر نبود («No rows with a title…») خطا.
  4. در یک سشن: همه‌ی `ContentItem`های موجود بات خوانده می‌شوند و سه دیکشنری کمکی ساخته می‌شود: `title_to_id`، `parent_map` (`item.id → parent_id`)، `code_to_id`.
  5. برای هر ردیف پارس‌شده:
     - `action == "delete"`: با `code_to_id` هدف را پیدا کرده و در صورت وجود حذف می‌کند (`deleted_count`).
     - در غیر این‌صورت: اگر `code` با یک آیتم موجود مطابقت داشت، همان آیتم آپدیت می‌شود (upsert بر مبنای Code)؛ وگرنه `ContentItem` جدید ساخته می‌شود. زوج `(item, category)` در `touched` نگه داشته می‌شود.
  6. `session.flush()` تا PK آیتم‌های تازه ساخته‌شده معلوم شود، سپس `title_to_id`/`parent_map` به‌روزرسانی می‌شوند.
  7. برای هر `(item, category)`: اگر `category` (متن) خالی بود رد می‌شود؛ `candidate_parent_id` از `title_to_id[category]` گرفته می‌شود؛ اگر خودِ آیتم بود یا پیدا نشد رد می‌شود؛ سپس **`would_cycle(item.id, candidate_parent_id, parent_map)`** چک می‌شود — اگر ست‌کردن این والد باعث حلقه در درخت شود (walk رو به بالا از `candidate_parent_id` تا رسیدن به `item.id` یا `None`، حداکثر ۵۰ گام)، این ردیف نادیده گرفته می‌شود؛ در غیر این صورت `item.parent_id` و `parent_map` آپدیت می‌شوند.
  8. `session.commit()`، سپس `sync_bot_commands(bot_id)` و خلاصه‌ی نتیجه («N item(s) added/updated, M deleted ✅»).
- **موارد خاص:** جابه‌جایی دسته با اکسل کاملاً **قبل از commit نهایی روی state درون‌حافظه‌ای `parent_map`** انجام می‌شود — یعنی چند ردیف در یک آپلود می‌توانند زنجیروار به هم لینک شوند (مثلاً ردیف ۲ زیر ردیف ۱، ردیف ۳ زیر ردیف ۲) بدون این‌که false-positive حلقه تشخیص داده شود، چون `parent_map` به‌محض ساخته‌شدن هر آیتم آپدیت می‌شود.

#### `receive_excel_invalid(message) -> None`
- **تریگر:** `@router.message(ContentListStates.waiting_for_excel)` (catch-all برای وقتی سند فرستاده نشده).
- **کار:** یادآوری «Please send the file as a document…».

---

### ویزارد افزودن آیتم — نمای کلی جریان

```
➕ Add
 → title → body → image_url(skip) → link_url(skip) → code(skip, یکتا)
   [پایان ADD_ITEM_FIELDS]
   ├─ Subscription mode: is_product=False → premium? → دسته‌بندی → ذخیره
   └─ Shop mode: "برای فروش است؟"
        ├─ No → premium همیشه False (Shop هرگز premium ندارد) → دسته‌بندی → ذخیره
        └─ Yes → قیمت (فقط رقم) → نوع محصول (Physical/Digital/Access)
             → فیلدهای اختصاصی TYPE_FIELDS[نوع]
             → premium همیشه False → دسته‌بندی (content:parent:*) → ذخیره‌ی Product + ContentItem
```

نکته‌ی کلیدی: **is_premium** و **is_product/for-sale** دو محور مستقل‌اند اما در عمل به‌خاطر `commerce_mode`، متقابلاً منحصر به فردند — یک بات هرگز هر دو محور را هم‌زمان فعال نمی‌بیند (Shop فقط for-sale می‌دهد، Subscription فقط premium می‌دهد)، چون `commerce_mode` یک‌بار برای کل بات انتخاب می‌شود.

---

## `bot/handlers/tools/shop.py`

این فایل (۹۱۰ خط، `Router(name="shop")`) پیاده‌سازی ابزار **«5️⃣ Shop»** است — مدیریت محصولات فروشگاه (یا در حالت Subscription، پلن‌های اشتراک)، روش‌های پرداخت، سفارش‌های اخیر، و چهار قابلیت تازه‌ی نسخه‌ی v2: **📥 Import Products**، **📊 Sales & Stock**، **🧾 Invoice Branding**، و **🎉 Sale / Campaign**. تمام منطق دیتابیسی سنگین (سفارش، پرداخت، فاکتور PDF) در `bot/shop.py` است؛ این فایل فقط لایه‌ی چت/FSM/کیبورد است.

### ثابت‌ها

- **`CORE_FIELDS`**: مراحل ثابتِ هر محصول جدید، صرف‌نظر از نوع: `name`، `price` (رقمی)، `description`، `image_url` (اختیاری).
- **`PRODUCT_TYPE_BUTTON_TO_KEY`**: همان نگاشت `content_list.py` (physical/digital/access).

### توابع کمکی

#### `_send_menu(message, bot_id) -> None`
- **کار:** `commerce_mode.get_commerce_mode` را می‌خواند؛ برچسب منو را «shop» یا «subscription plans» می‌کند و `shop_menu_keyboard(mode)` را نشان می‌دهد. کیبورد شامل: 📦 Products/📋 Plans + ➕ Add Product/➕ Add Plan، 💳 Payment Methods + 📋 Recent Orders، 📥 Import Products + 📊 Sales & Stock، 🧾 Invoice Branding، (فقط در Subscription: 🎁 Free Preview Limit + 🔓 Single-item Price)، 🎉 Sale / Campaign، Cancel.

#### `_current_fields(phase, product_type) -> list[dict]`
- **کار:** انتخاب `CORE_FIELDS` یا `TYPE_FIELDS[product_type]` بر اساس فاز جاری ویزارد.

#### `_send_core_step(message, state, index) -> None`
- **کار:** مثل `content_list.py:_send_step` اما برای محصول مستقل. با پایان `CORE_FIELDS`: اگر حالت **Subscription** باشد، `product_type="subscription"` را مستقیم (بدون نمایش کیبورد نوع) ست می‌کند و می‌رود به `_send_type_step` — چون در این حالت «هر محصول یک پلن اشتراک است»، انتخابگر نوع بی‌معناست. در حالت Shop، `shop_product_type_keyboard()` نمایش داده می‌شود.

#### `_send_type_step(message, state, index) -> None`
- **کار:** فیلدهای اختصاصی نوع (`TYPE_FIELDS`) را می‌پرسد؛ با پایان یافتن، `_save_product` صدا زده می‌شود.

#### `_save_product(message, state) -> None`
- **کار:** `price` و (در صورت وجود) `subscription_days` را به عدد تبدیل می‌کند (خطای تبدیل → صفر/None بی‌سروصدا)، یک `Product` جدید می‌سازد و کامیت می‌کند؛ state ریست، پیام «Product added ✅»، بازگشت به منو.

---

### هندلرهای منو و ناوبری

#### `open_shop(message, state) -> None`
- **تریگر:** `@router.message(F.text == "5️⃣ Shop")`
- **کار:** اگر بات فعال نبود خطا. اگر `commerce_mode` تعیین نشده، `commerce_mode_source="shop_tool"` را ست کرده و کیبورد انتخاب حالت را نشان می‌دهد (هندلرش در `content_list.py:choose_commerce_mode` است — نگاه کنید به توضیح آن‌جا). وگرنه نکته‌ی راهنمای `"tool:shop"` و منوی اصلی.

#### `back_to_menu(callback, state) -> None`
- **تریگر:** `@router.callback_query(F.data == "shop:menu")`.
- **کار:** فقط چون `shop_products_keyboard` (کیبورد inline صفحه‌بندی‌شده‌ی محصولات) دکمه‌ی Back خودش را به همین callback می‌فرستد، این هندلر باقی مانده است.

#### `back_to_menu_text(message, state) -> None`
- **تریگر:** `@router.message(F.text == SHOP_BACK_BUTTON_TEXT)` یعنی `"🔙 Back to Shop Menu"`.
- **موارد خاص:** طبق کامنت کد، عمداً **بدون شرط روی state** و زودتر از هندلرهای catch-all هر ویزارد رجیستر شده تا همیشه اولویت را ببرد — دقیقاً مثل دکمه‌ی سراسری «❌ Cancel» در `cancel.py`، برای این‌که کاربر بتواند از وسط هر مرحله (مثلاً تنظیم کمپین نیمه‌کاره) خارج شود.

#### `_send_products_page(message, bot_id, offset) -> bool`
- **کار:** یک صفحه از `shop.get_products_page(bot_id, offset, PRODUCTS_PAGE_SIZE)` (`PRODUCTS_PAGE_SIZE = 30`) می‌گیرد؛ اگر خالی بود `False`. وگرنه با `shop_products_keyboard(page, offset, has_more, PRODUCTS_PAGE_SIZE)` (کیبورد inline با دکمه‌های ⬅️ Prev / ➡️ Next) نمایش می‌دهد.

#### `list_products(message, state) -> None`
- **تریگر:** `@router.message(F.text.in_(set(SHOP_PRODUCTS_BUTTON_TEXTS.values())))` — یعنی `"📦 Products"` (حالت shop) یا `"📋 Plans"` (حالت subscription)، هر دو یک هندلر.
- **کار:** صفحه‌ی صفر را می‌فرستد؛ خالی بود → «No products yet.»؛ در غیر این صورت نکته‌ی راهنمای `"shop:products"`.

#### `list_products_page(callback, state) -> None`
- **تریگر:** `@router.callback_query(F.data.startswith("shop:products_page:"))`.
- **کار:** `offset` را از انتهای callback_data می‌خواند و صفحه‌ی مربوطه را می‌فرستد.

#### `select_product(callback, state) -> None`
- **تریگر:** `@router.callback_query(F.data.startswith("shop:select:"))`.
- **کار:** جزئیات محصول (نام، توضیح، قیمت با فرمت `{:,} تومان`، نوع با برچسب فارسی/ایموجی — `type_labels`، و در صورت `access` نام سطح دسترسی) + `shop_product_detail_keyboard(product.id)` (فقط دکمه‌ی 🗑 Delete و Back).

#### `delete_product(callback, state) -> None`
- **تریگر:** `@router.callback_query(F.data.startswith("shop:delete:"))`.
- **کار:** حذف مستقیم SQL (با چک مالکیت بات)، بدون بررسی وابستگی (برخلاف حذف آیتم محتوا که وابستگی فرزندان را چک می‌کرد — محصول چنین محدودیتی ندارد).

---

### ویزارد افزودن محصول

#### `new_product(message, state) -> None`
- **تریگر:** `@router.message(F.text.in_(set(SHOP_ADD_BUTTON_TEXTS.values())))` — `"➕ Add Product"` یا `"➕ Add Plan"`.
- **کار:** `wizard_payload={}`، state → `ShopStates.add_product_wizard`، نکته‌ی راهنمای `"shop:new"`، اولین گام `CORE_FIELDS`.

#### `wizard_skip(message, state) -> None`
- **تریگر:** state `add_product_wizard`، `F.text == SKIP_BUTTON_TEXT`.
- **کار:** مشابه معادل `content_list.py`، با فرق این‌که از `_current_fields(phase, product_type)` استفاده می‌کند.

#### `choose_type(message, state) -> None`
- **تریگر:** state `add_product_wizard`، `F.text.in_(PRODUCT_TYPE_BUTTON_TO_KEY)`.
- **کار:** `product_type` را ثبت و `_send_type_step(..., 0)`.

#### `wizard_receive(message, state) -> None`
- **تریگر:** `@router.message(ShopStates.add_product_wizard)` (catch-all).
- **کار:** فیلد جاری را از `_current_fields` می‌گیرد؛ برای `price` یا `subscription_days`، فقط رقم پذیرفته می‌شود (`isdigit`)؛ سپس فاز بعدی (`core` یا `type`).

---

### روش‌های پرداخت — «💳 Payment Methods»

#### `payments_menu(message, state) -> None`
- **تریگر:** `F.text == "💳 Payment Methods"`.
- **کار:** `shop.get_shop_settings(bot_id)` را می‌خواند و `shop_payments_keyboard(settings)` را نشان می‌دهد. توضیح: «هرکدام تنظیم نشده باشد صرفاً به خریدار پیشنهاد نمی‌شود».

#### الگوی کیبورد پویا «✅ suffix»
`bot/keyboards.py:shop_payment_labels(settings)` برای هر روش پرداخت دو برچسب دارد — یکی وقتی مقدار قبلاً تنظیم شده (با ✅ در انتها، مثلاً `"💳 Zarinpal ✅"`) و یکی وقتی تنظیم نشده (`"💳 Set Zarinpal ID"`). هر هندلر شروع تنظیم روی **هر دو متن** با `F.text.in_({...})` گوش می‌دهد تا هم اولین‌بار تنظیم‌کردن و هم ویرایش مجدد یک مقدار موجود را پوشش دهد.

#### `_upsert_shop_settings(bot_id, **fields) -> None`
- **کار:** helper مشترکِ همه‌ی مسیرهای زیر: `ShopSettings` بات را می‌خواند یا می‌سازد، فیلدهای دلخواه را با `setattr` ست می‌کند، کامیت.

##### Zarinpal
- `set_zarinpal_start`: تریگر `F.text.in_({"💳 Zarinpal ✅", "💳 Set Zarinpal ID"})` → state `waiting_for_zarinpal_id`.
- `receive_zarinpal_id`: `zarinpal_merchant_id` را ذخیره می‌کند.

##### کارت‌به‌کارت
- `set_card_start`: تریگر `F.text.in_({"🏦 Card-to-Card ✅", "🏦 Set Card-to-Card"})` → state `waiting_for_card_number`.
- `receive_card_number`: شماره کارت را موقتاً در `pending_card_number` نگه می‌دارد → state `waiting_for_card_holder`.
- `receive_card_holder`: نام صاحب حساب را می‌گیرد و هر دو (`card_number`, `card_holder_name`) را با هم ذخیره می‌کند — یعنی این دو فیلد همیشه با هم ست/آپدیت می‌شوند (توجه: `shop_payment_labels` هم چک می‌کند هر دو مقدار موجود باشد تا ✅ نشان دهد).

##### Stripe (USD)
- `set_stripe_start`: تریگر `F.text.in_({"🌍 Stripe (USD) ✅", "🌍 Set Stripe (USD, international)"})` → state `waiting_for_stripe_key`. توضیح: مخصوص خریدارانی که خارج از ایران با دلار پرداخت می‌کنند.
- `receive_stripe_key`: کلید مخفی Stripe (`sk_live_`/`sk_test_`) را ذخیره می‌کند.

##### کریپتو
- `set_crypto_start`: تریگر `F.text.in_({"🪙 Crypto ✅", "🪙 Set Crypto Wallet"})` → state `waiting_for_crypto_address`.
- `receive_crypto_address`: آدرس کیف پول موقتاً در `pending_crypto_address` → state `waiting_for_crypto_label`.
- `receive_crypto_label`: برچسب شبکه/ارز (مثلاً «USDT (TRC20)») + آدرس ذخیره‌شده با هم commit می‌شوند.

##### TON
- `set_ton_start`: تریگر `F.text.in_({"💎 TON ✅", "💎 Set TON Wallet"})` → state `waiting_for_ton_address`.
- `receive_ton_address`: `ton_wallet_address` را ذخیره می‌کند.

- **موارد خاص مشترک:** `zarinpal_merchant_id`، `card_number`، `stripe_secret_key`، `crypto_wallet_address`، `ton_wallet_address` همگی `EncryptedString` در مدل `ShopSettings` هستند (رمزنگاری در سطح ستون) — این فایل هیچ کاری برای رمزنگاری نمی‌کند، مسئولیتش در لایه‌ی مدل/دیتابیس است. کریپتو و TON، برخلاف Zarinpal/Stripe، تأیید آنلاین ندارند — خریدار خودش تراکنش را ثبت می‌کند و owner دستی تأیید می‌کند (`bot/shop.py:submit_manual_payment`).

---

### 🧾 Invoice Branding — چهار فیلد قابل تنظیم

#### `invoice_settings_menu(message, state) -> None`
- **تریگر:** `F.text == "🧾 Invoice Branding"`.
- **کار:** `settings` را می‌خواند و توضیح می‌دهد این تنظیمات روی فاکتور PDF بعد از خرید (`bot/shop.py:generate_invoice`) اثر می‌گذارد؛ هرچه ست نشود، صرفاً روی فاکتور ظاهر نمی‌شود. کیبورد `shop_invoice_keyboard(settings)` چهار ردیف دارد که هرکدام از `shop_invoice_labels(settings)` می‌آید:

| فیلد | برچسب «تنظیم‌نشده» | برچسب «تنظیم‌شده» | ستون مدل |
|---|---|---|---|
| نام کسب‌وکار | `🏢 Set Business Name` | `🏢 Business Name ✅` | `invoice_business_name` |
| لوگو | `🖼 Set Logo (image URL)` | `🖼 Logo ✅` | `invoice_logo_url` |
| آدرس | `📍 Set Address` | `📍 Address ✅` | `invoice_address` |
| یادداشت پانویس | `📝 Set Footer Note` | `📝 Footer Note ✅` | `invoice_footer_note` |

هرکدام همان الگوی «✅ suffix» بالا را دارند.

##### نام کسب‌وکار
- `set_invoice_business_name_start`: تریگر `F.text.in_({"🏢 Business Name ✅", "🏢 Set Business Name"})` → state `waiting_for_invoice_business_name`.
- `receive_invoice_business_name`: ذخیره‌ی `invoice_business_name`؛ سپس **بازگشت به همان زیرمنوی Invoice** (فراخوانی مستقیم `invoice_settings_menu(message, state)`، نه `_send_menu`) — تا کاربر بتواند بدون رفتن به منوی اصلی، فیلد بعدی فاکتور را هم تنظیم کند. این رفتار در هر چهار فیلد فاکتور یکسان است (برخلاف روش‌های پرداخت که بعد از ذخیره به منوی اصلی Shop برمی‌گردند).

##### لوگو
- `set_invoice_logo_start`: تریگر `F.text.in_({"🖼 Logo ✅", "🖼 Set Logo (image URL)"})` → state `waiting_for_invoice_logo_url`.
- `receive_invoice_logo`: `invoice_logo_url` را ذخیره می‌کند؛ پیام تأیید صراحتاً می‌گوید «اگر URL قابل دریافت نباشد، فاکتور فقط آن را نادیده می‌گیرد» — منطبق با `bot/shop.py:_fetch_logo_image` که خطای دانلود را می‌بلعد و `None` برمی‌گرداند به‌جای کرش‌کردن فاکتور.

##### آدرس
- `set_invoice_address_start` / `receive_invoice_address`: تریگر `F.text.in_({"📍 Address ✅", "📍 Set Address"})`؛ `invoice_address` (چندخطی، `Text`) را ذخیره می‌کند.

##### یادداشت پانویس
- `set_invoice_footer_start` / `receive_invoice_footer`: تریگر `F.text.in_({"📝 Footer Note ✅", "📝 Set Footer Note"})`؛ `invoice_footer_note` را ذخیره می‌کند (مثلاً سیاست بازگشت کالا یا پیام تشکر).

**ارتباط با `bot/shop.py`:** این چهار ستون در `generate_invoice(order)` مصرف می‌شوند: `invoice_business_name` سرتیتر فاکتور (پیش‌فرض «فاکتور فروش» اگر تنظیم نشده)، `invoice_logo_url` گوشه‌ی بالا-چپ (با `_fetch_logo_image`)، `invoice_address` زیر عنوان با `wrapped_lines`، `invoice_footer_note` در پایین صفحه. فاکتور با فونت فارسی `Vazirmatn` و reshape/bidi (`_fa()`) رندر می‌شود.

---

### 📊 Sales & Stock

#### `sales_stats(message, state) -> None`
- **تریگر:** `F.text == "📊 Sales & Stock"`.
- **کار:** خروجی `bot/inventory.py:get_shop_stats(bot_id)` را مستقیماً به متن فارسی/انگلیسی ترجمه می‌کند:
  - `📦 Products: {product_count}`
  - `🧾 Orders: {order_count} ({paid_order_count} paid)`
  - `💰 Revenue: {revenue:,}`
  - اگر `stats["profit"]` مقدار داشت (یعنی حداقل یک سفارش پرداخت‌شده روی محصولی با `cost_price` ست‌شده وجود دارد): `📈 Estimated profit: {profit:,} (only counting products with a cost price set)`.
  - اگر `top_products` غیرخالی: تا ۵ محصول برتر بر اساس تعداد سفارش پرداخت‌شده، هرکدام با `orders` و `revenue`.
  - اگر `low_stock` غیرخالی: محصولاتی با `stock_quantity <= LOW_STOCK_THRESHOLD` (=۵)؛ برچسب `OUT OF STOCK` اگر `stock <= 0` وگرنه `"{stock} left"`.
- **منطق موجودی (در `bot/inventory.py`):** `revenue` مجموع `Order.price` برای وضعیت‌های `PAID_STATUSES` (از `bot/admin_panel.py`) است — یک تخمین ساده که واحد پول/روش پرداخت را در نظر نمی‌گیرد. `profit` بر اساس `cost_price` **فعلی** هر محصول محاسبه می‌شود، نه اسنپ‌شات لحظه‌ی خرید — یعنی تغییر بعدیِ قیمت خرید، سود گذشته را هم بازمحاسبه می‌کند (این محدودیت صراحتاً در docstring ماژول اعلام شده). این ماژول یک آینه‌ی کوچک‌تر و بات-محورِ `bot/admin_panel.py` (که دید کل پلتفرم را دارد) است.

---

### 📥 Import Products

#### `import_products_menu(message, state) -> None`
- **تریگر:** `F.text == "📥 Import Products"`.
- **کار:** توضیح می‌دهد این قابلیت برای افزودن/آپدیت انبوه محصولات با نام/قیمت/موجودی/بهای‌تمام‌شده است؛ آپلود دوباره‌ی فایل با همان Code، محصول را جای‌گزین (upsert) می‌کند و `Action=Delete` حذف می‌کند. کیبورد `shop_import_keyboard()`: 🇬🇧 Sample (EN) + 🇮🇷 Sample (FA)، 📤 Upload File، Back.

#### `send_sample_en` / `send_sample_fa`
- **تریگر‌ها:** `F.text == "🇬🇧 Sample (EN)"` و `F.text == "🇮🇷 Sample (FA)"`.
- **کار:** `shop_import.generate_sample_products_excel("en"/"fa")` — برخلاف نمونه‌ی ۱۰‌زبانه‌ی `content_import.py`، این ایمپورتر **فقط انگلیسی و فارسی** را پوشش می‌دهد (طبق کامنت فایل، برای مدیریت‌پذیر ماندن scope). ستون‌های نمونه: `Name, Description, Price, Cost Price, Stock, Image URL, Code, Action` (یا معادل فارسی). فایل با `answer_document` ارسال می‌شود؛ کپشن نسخه‌ی فارسی به فارسی نوشته شده («این فایل رو پر کن…»).

#### `start_import_upload(message, state) -> None`
- **تریگر:** `F.text == "📤 Upload File"`.
- **کار:** state → `ShopStates.waiting_for_import_file`.

#### `receive_import_file(message, state, bot: Bot) -> None`
- **تریگر:** `@router.message(ShopStates.waiting_for_import_file, F.document)`.
- **کار:**
  1. فایل دانلود می‌شود؛ `shop_import.parse_products_workbook(bytes, filename)` صدا زده می‌شود — منطق مشابه `content_import.py` (تشخیص هدر در ۱۵ ردیف اول، `.xlsx`/`.csv`، مترادف ستون فارسی/انگلیسی) اما با ستون‌های فروش: `name, description, price, cost_price, stock, image_url, code, action`. یک ردیف قابل‌فروش حداقل به `Name` و `Price` عددی نیاز دارد؛ ردیف حذف فقط به `Code` نیاز دارد.
  2. خطای پارس یا فایل بدون ردیف معتبر → پیام خطا.
  3. `shop.upsert_products_from_import(bot_id, items)` صدا زده می‌شود — این تابع در `bot/shop.py` بر اساس ستون **`Product.import_code`** (نه `code` عمومی محتوا) upsert می‌کند: ردیف با کد منطبق بر یک `import_code` موجود آپدیت می‌شود، بدون کد یا کد جدید همیشه محصول تازه می‌سازد، و `action=="delete"` محصول منطبق را حذف می‌کند.
  4. نتیجه (`created`, `updated`, `deleted`) در پیام «Import done ✅ — N added, M updated, K deleted.» نمایش داده می‌شود.
- **موارد خاص:** محصولات ایمپورت‌شده همیشه `product_type="physical"` می‌گیرند (چون فایل ایمپورت فیلدی برای انتخاب مکانیزم تحویل ندارد)؛ owner که محصول دیجیتال/دسترسی/اشتراک با تحویل اختصاصی می‌خواهد باید همچنان از ویزارد دستی «➕ Add Product» استفاده کند.

---

### 🎁 Free Preview Limit و 🔓 Single-item Price (فقط Subscription)

#### `set_free_preview_start` / `receive_free_preview_limit`
- **تریگر:** `F.text == "🎁 Free Preview Limit"` → state `waiting_for_free_preview_limit`.
- **کار:** مقدار فعلی از `premium_content.get_free_preview_limit(bot_id)` (پیش‌فرض ۱) خوانده و نشان داده می‌شود؛ ورودی باید عدد صحیح ≥۰ باشد؛ با `premium_content.set_free_preview_limit` ذخیره می‌شود. این عدد تعیین می‌کند یک مشترک قبل از نیاز به اشتراک، چند آیتم premium را رایگان ببیند (`bot/premium_content.py:check_and_record_access`).

#### `set_unlock_price_start` / `receive_unlock_price`
- **تریگر:** `F.text == "🔓 Single-item Price"` → state `waiting_for_default_unlock_price`.
- **کار:** قیمت پیش‌فرض (تومان) که یک غیرمشترک بعد از اتمام سهمیه‌ی رایگان، برای باز کردن **فقط یک** آیتم premium (بدون خرید اشتراک کامل) می‌پردازد. ارسال `0` این قابلیت را خاموش می‌کند. مقدار با `shop.set_default_unlock_price(bot_id, value or None)` ذخیره می‌شود که خودش چک می‌کند آیا کمپین قیمتی فعالی هست — اگر بله، مقدار واردشده به‌عنوان baseline پیش‌کمپین (`original_default_unlock_price`) ذخیره و نسخه‌ی زنده با درصد کمپین تعدیل می‌شود.

---

### 🎉 Sale / Campaign — تخفیف/افزایش زمان‌دار قیمت

#### `_campaign_status_text(campaign) -> str`
- **کار:** helper نمایشی: درصد و جهت (`discount`→«off» / `markup`→«up»)، زمان باقی‌مانده تا `ends_at` (روز/ساعت)، و تاریخ پایان به UTC.

#### `campaign_menu(message, state) -> None`
- **تریگر:** `F.text == "🎉 Sale / Campaign"`.
- **کار:** ابتدا `shop.expire_due_campaigns()` را صدا می‌زند (بازگردانی تنبل/lazy اگر کمپینی همین الان منقضی شده باشد، پیش از این‌که تایمر پس‌زمینه‌ی `bot/runtime.py` به آن برسد)، سپس `shop.get_active_campaign(bot_id)`. اگر کمپینی فعال است وضعیتش نشان داده می‌شود؛ وگرنه توضیح داده می‌شود که این تخفیف/افزایش روی **همه‌ی قیمت‌ها** یک‌جا اعمال می‌شود (محصولات، پلن‌ها، قیمت‌های unlock تک‌آیتمی) و بعد از پایان مدت، خودکار برمی‌گردد.

#### `campaign_end(message, state) -> None`
- **تریگر:** `F.text == "🔚 End Campaign Now"`.
- **کار:** `shop.end_price_campaign(bot_id)` — همه‌ی `original_*` را فوری روی قیمت‌های زنده برمی‌گرداند.

#### `campaign_pick_direction(message, state) -> None`
- **تریگر:** `F.text.in_({"📉 Discount", "📈 Markup"})`.
- **کار:** `campaign_direction` (`"discount"`/`"markup"`) ذخیره، state → `waiting_for_campaign_percent`؛ محدوده‌ی مجاز درصد را نشان می‌دهد (تخفیف ۱–۹۰، افزایش ۱–۵۰۰).

#### `campaign_receive_percent(message, state) -> None`
- **تریگر:** state `waiting_for_campaign_percent`.
- **کار:** عدد بین ۱ و سقف (بسته به جهت) اعتبارسنجی می‌شود؛ ذخیره؛ state → `waiting_for_campaign_days`؛ پرسش تعداد روز (۱–۹۰).

#### `campaign_receive_days(message, state) -> None`
- **تریگر:** `@router.message(ShopStates.waiting_for_campaign_days)` (catch-all — بعد از `campaign_apply` رجیستر شده چون آن یک فیلتر متنی دقیق‌تر دارد).
- **کار:** عدد روز بین ۱ و ۹۰ اعتبارسنجی می‌شود؛ `n_products = len(shop.get_products(bot_id))` و تاریخ بازگشت محاسبه می‌شود؛ خلاصه‌ی نهایی («Ready: X% off on N product/plan(s) + all single-item unlock prices for D day(s)…») با کیبورد `shop_campaign_confirm_keyboard()` («✅ Apply» / Back) نمایش داده می‌شود. توضیح می‌دهد قیمت‌ها به نزدیک‌ترین ۱٬۰۰۰ تومان گرد می‌شوند.

#### `campaign_apply(message, state) -> None`
- **تریگر:** `@router.message(ShopStates.waiting_for_campaign_days, F.text == "✅ Apply")` — یک فیلتر دقیق‌تر روی همان state، پس زودتر از `campaign_receive_days` چک می‌شود.
- **کار:** اگر `direction`/`percent`/`days` در FSM موجود نبود («کمپین منقضی شده») خطا. وگرنه `shop.start_price_campaign(bot_id, direction, percent, days)` صدا زده می‌شود که:
  - اسنپ‌شات هر `Product.price` را در `original_price` می‌گیرد و قیمت زنده را با `pricing.adjusted_price` تعدیل می‌کند.
  - همان کار را برای هر `ContentItem.unlock_price` غیر-`None` انجام می‌دهد.
  - `ShopSettings.default_unlock_price` (اگر ست شده) را هم تعدیل می‌کند.
  - یک ردیف `PriceCampaign(status="active")` می‌سازد.
  - اگر از قبل کمپینی فعال بود، `None` برمی‌گرداند (باید اول تمام شود) — پیام «A campaign is already running — end it first.» به کاربر.
- **موارد خاص:** بازگردانی خودکار توسط یک حلقه‌ی زمان‌بندی در `bot/runtime.py` انجام می‌شود که `shop.expire_due_campaigns()` را صدا می‌زند؛ این هندلر خودش تایمر ندارد، فقط ایجاد/پایان دستی کمپین را مدیریت می‌کند.

---

### 📋 Recent Orders

#### `recent_orders(message, state) -> None`
- **تریگر:** `F.text == "📋 Recent Orders"`.
- **کار:** تا ۲۰ سفارش اخیر (`shop.list_recent_orders`) را می‌گیرد؛ برای هرکدام نام محصول را با `shop.get_product(order.product_id)` جداگانه واکشی می‌کند (یک کوئری اضافه به‌ازای هر سفارش — بدون join)، و خط `#{id} — {product_name} — {price:,} تومان — {status}` را می‌سازد؛ اگر `order.checkout_id` ست بود (یعنی این سفارش بخشی از یک سبد خرید/Checkout چندآیتمی بوده، نه خرید تکی) علامت `(cart)` اضافه می‌شود.

---

## خلاصه‌ی وابستگی‌های بین‌ماژولی

| ماژول | نقشی که برای این دو هندلر ایفا می‌کند |
|---|---|
| `bot/commerce_mode.py` | نگه‌داری `BuiltBot.commerce_mode` (`shop`/`subscription`)؛ خوانده می‌شود در تقریباً هر قدم منشعب هر دو فایل؛ فقط یک‌بار قابل تنظیم است. |
| `bot/shop.py` | منبع `TYPE_FIELDS` (فیلدهای اختصاصی نوع محصول، مشترک بین دو فایل)، همه‌ی CRUD محصول/سفارش/تنظیمات فروشگاه/کمپین قیمتی/فاکتور PDF. |
| `bot/shop_import.py` | پارسر اکسل مخصوص محصولات فروشگاه (EN/FA)، استفاده‌شده در `receive_import_file`. |
| `bot/inventory.py` | آمار فروش/موجودی نمایش داده‌شده در `sales_stats`. |
| `bot/content_nav.py` | تمام عملیات درخت محتوا (`get_children`, `upsert_item`, `reparent_item`, `would_cycle`, ...) که `content_list.py` روی آن‌ها سوار است. |
| `bot/content_import.py` | پارسر/تولیدکننده‌ی اکسل ۱۰‌زبانه‌ی محتوا، استفاده‌شده در `download_sample_lang`/`receive_excel`. |
| `bot/premium_content.py` | منطق gating اشتراک/پیش‌نمایش رایگان؛ `set_free_preview_start`/`set_unlock_price_start` در `shop.py` روی آن نوشته می‌شوند و در زمان اجرا (`bot/runtime.py`) خوانده می‌شوند. |
| `bot/keyboards.py` | تمام کیبوردهای reply/inline هر دو فایل، شامل الگوی «✅ suffix» برای پرداخت و فاکتور. |
| `bot/states.py` | `ContentListStates` و `ShopStates` — تعریف همه‌ی state های FSM استفاده‌شده. |
| `bot/runtime.py` | `sync_bot_commands` (بعد از هر تغییر محتوا/کد میانبر صدا زده می‌شود)؛ همچنین دیسپچر ربات‌های ساخته‌شده که در زمان اجرا محتوا/فروشگاه را به کاربر نهایی نشان می‌دهد و حلقه‌ی انقضای کمپین را اجرا می‌کند. |
| `bot/session.py` | `make_session()` برای ساخت سشن HTTP بات موقت (`Add Post` در `content_list.py`). |
