"""Short how-to tips shown on an easymakebot builder screen — Persian or
English, picked the same way as the onboarding guide (bot/guide.py:
owner_prefers_persian).

Two delivery mechanisms share this same HELP dict:
- The reply-keyboard-driven builder screens (Tools, and each of the 5 tools'
  own menus/wizards) call `tip_suffix(key, tg_user)` and append the result
  directly onto that screen's own message text — no separate follow-up
  message, matching "guidance lives on the screen itself".
- Whatever still runs on inline keyboards (the dynamic per-record pickers,
  /live, /easybotadmin) keeps using the `dp.callback_query.outer_middleware`
  in bot/main.py, which sends the tip as a separate follow-up message after
  the callback handler runs.

Keyed by exact match, or a key ending in ":" matching any prefix. No entry ->
no tip (silent).
"""

TIP_ICON = "\U0001F4A1"  # 💡

# key -> (Persian, English). Keep each to a couple of short lines.
HELP: dict[str, tuple[str, str]] = {
    # --- Top level ---
    "my_bots": (
        "لیست ربات‌هاییه که ساختی. روی هرکدوم بزنی وارد محیط ویرایش همون ربات می‌شی.",
        "Your built bots. Tap one to enter its build/edit environment.",
    ),
    "create_bot": (
        "برای ساخت ربات جدید، اول از @BotFather یه توکن بگیر و همون رو اینجا بفرست.\n"
        "توکن مثل «123456:ABC-...» ئه.",
        "To add a bot, first get a token from @BotFather, then send it here.\n"
        "A token looks like \"123456:ABC-...\".",
    ),
    "select_bot:": (
        "وارد محیط این ربات شدی. از منوی «Build & Edit Tools» پایین صفحه ابزارها رو ببین.",
        "You're now editing this bot. Open \"Build & Edit Tools\" at the bottom to configure it.",
    ),
    # --- Tools menu ---
    "tool:define_command": (
        "دستورها رو می‌سازی — مثل /start یا /menu. برای هر دستور یه پیام یا دکمه تعریف می‌کنی.",
        "Create commands like /start or /menu. Each command sends a message or shows buttons.",
    ),
    "tool:force_join": (
        "کاربر رو مجبور می‌کنه قبل از استفاده از ربات، عضو کانال(های) تو بشه.",
        "Forces users to join your channel(s) before the bot will respond.",
    ),
    "tool:message_to_all": (
        "یه دستور می‌سازی که باهاش می‌تونی به همه‌ی کاربرای ربات یک‌جا پیام بفرستی.",
        "Makes a command you can later use to broadcast one message to every user of the bot.",
    ),
    "tool:content_list": (
        "لیست محتوا: خبر/محصول/درس/آهنگ و... . کاربر توی منوی دکمه‌ای می‌بینه و انتخاب می‌کنه.\n"
        "می‌تونی تک‌تک وارد کنی یا با فایل اکسل/CSV یک‌جا آپلود کنی.",
        "A browsable list of items (news / products / lessons / tracks…). Users pick from a "
        "button menu. Add them one by one, or bulk-upload an .xlsx / .csv.",
    ),
    "tool:shop": (
        "فروشگاه/اشتراک ربات: محصول یا پلن، روش‌های پرداخت، سفارش‌ها و کمپین تخفیف.",
        "Your bot's shop / subscription: products or plans, payment methods, orders, and sales.",
    ),
    "show_commands": (
        "همه‌ی دستورهایی که تا الان برای این ربات ساختی رو نشون می‌ده.",
        "Lists every command you've defined for this bot so far.",
    ),
    # --- Commerce mode (asked once) ---
    "mode:shop:": (
        "حالت فروشگاه: کالا/خدمت تکی می‌فروشی. سبد خرید و پرداخت تک‌مرحله‌ای.\n"
        "این انتخاب بعداً قابل تغییر نیست.",
        "Shop mode: you sell individual products/services, with a cart and one-off payments.\n"
        "This choice can't be changed later.",
    ),
    "mode:subscription:": (
        "حالت اشتراک: آرشیو محتوا پشت اشتراک قفل می‌شه. کاربر بعد از سهمیه‌ی رایگان باید "
        "مشترک بشه (یا تک‌آیتم بخره).\nاین انتخاب بعداً قابل تغییر نیست.",
        "Subscription mode: your content archive is locked behind a subscription. After a free "
        "preview quota, users subscribe (or buy a single item).\nThis choice can't be changed later.",
    ),
    # --- Content List ---
    "content:new": (
        "افزودن یک آیتم دستی. عنوان و متن اجباریه؛ عکس، لینک و کد اختیاریه.",
        "Add one item by hand. Title and body are required; image, link and code are optional.",
    ),
    "content:add_post": (
        "یه پست (عکس یا ویدیو + کپشن) بساز که فوراً برای همه‌ی مشترکین ربات‌ات ارسال بشه — "
        "مثل کانال، ولی داخل خودِ ربات. کاربرا می‌تونن لایک بزنن و کامنت بذارن.",
        "Create a post (photo/video + caption) sent straight to every subscriber — like a "
        "channel, but inside the bot itself. Users can like and comment on it.",
    ),
    "content:edit": (
        "یه آیتم موجود رو ویرایش می‌کنی — با زدن کدش یا انتخاب از لیست.",
        "Edit an existing item — by its code, or by browsing to it.",
    ),
    "content:delete_start": (
        "حذف یک آیتم. آیتمی که زیرمجموعه داره اول باید زیرمجموعه‌هاش حذف بشن.",
        "Delete an item. An item with sub-items needs those removed first.",
    ),
    "content:group_start": (
        "یه آیتم رو زیر یه دسته می‌بری (یا به سطح بالا برمی‌گردونی). این‌طوری منوی تودرتو می‌سازی.",
        "Move an item under a category (or back to the top level) — this builds the nested menu.",
    ),
    "content:sample": (
        "یه فایل نمونه دانلود می‌کنی، پرش می‌کنی و برمی‌گردونی. زبان هدرها رو انتخاب کن.\n"
        "فایل اکسل خودت هم قبوله؛ اسم ستون‌ها هوشمند تطبیق داده می‌شن.",
        "Download a template, fill it in, upload it back. Pick the header language.\n"
        "Your own spreadsheet works too — column names are matched loosely.",
    ),
    "content:sample:": (
        "نمونه به این زبان ساخته شد. ستون Category رو با عنوان یه ردیف دیگه پر کن تا تودرتو بشه؛ "
        "ستون Code اختیاریه (آپلود دوباره با همون کد = به‌روزرسانی به‌جای تکرار).",
        "Template built in this language. Put another row's Title in \"Category\" to nest it; "
        "\"Code\" is optional (re-uploading with the same Code updates instead of duplicating).",
    ),
    "content:upload": (
        "فایل رو به‌صورت سند (نه عکس) بفرست — xlsx یا csv. سطر هدر لازم نیست سطر اول باشه.",
        "Send the file as a document (not a photo) — .xlsx or .csv. The header row needn't be row 1.",
    ),
    "content:for_sale:yes": (
        "این آیتم قیمت و دکمه‌ی خرید می‌گیره و از همون خط پرداخت فروشگاه رد می‌شه.",
        "This item gets a price and a Buy button, wired into the shop's payment pipeline.",
    ),
    "content:for_sale:no": (
        "این آیتم فقط نمایشیه؛ قیمت و دکمه‌ی خرید نداره.",
        "This item is display-only — no price, no Buy button.",
    ),
    "content:premium:yes": (
        "دیدن این آیتم نیاز به اشتراک فعال داره (بعد از تموم‌شدن سهمیه‌ی پیش‌نمایش رایگان).\n"
        "می‌تونی قیمت تک‌خرید هم براش بذاری.",
        "Viewing this needs an active subscription (after the free-preview quota is used up).\n"
        "You can also set a single-purchase price for it.",
    ),
    "content:premium:no": (
        "این آیتم برای همه آزاده؛ قفل اشتراک نداره.",
        "This item is free for everyone — no subscription lock.",
    ),
    "content:ptype:": (
        "نوع کالا: فیزیکی (آدرس پستی می‌گیره)، دیجیتال (لینک/متن تحویل)، یا دسترسی/عضویت.",
        "Product kind: physical (asks for a shipping address), digital (delivers a link/text), "
        "or access/membership.",
    ),
    # --- Shop ---
    "shop:products": (
        "لیست محصول/پلن‌های این ربات. روی هرکدوم بزنی جزئیات و حذف رو می‌بینی.",
        "This bot's products/plans. Tap one for its detail and a delete option.",
    ),
    "shop:new": (
        "افزودن محصول/پلن جدید: اسم، قیمت (تومان)، توضیح، عکس، بعد فیلدهای مخصوص نوعش.",
        "Add a product/plan: name, price (Toman), description, image, then its type-specific fields.",
    ),
    "shop:payments": (
        "روش‌های پرداخت رو اینجا وارد می‌کنی. هر کدوم خالی باشه، به خریدار پیشنهاد نمی‌شه.",
        "Enter your payment methods here. Any you leave blank simply isn't offered to buyers.",
    ),
    "shop:orders": (
        "آخرین سفارش‌ها. سفارش کارت‌به‌کارت رو خودت اینجا تأیید یا رد می‌کنی.",
        "Recent orders. You approve or reject card-to-card payments here.",
    ),
    "shop:free_preview": (
        "چند آیتم پولی رو کاربر می‌تونه رایگان ببینه قبل از اینکه اشتراک لازم بشه.",
        "How many premium items a user may view free before a subscription is required.",
    ),
    "shop:unlock_price": (
        "قیمت پیش‌فرض «باز کردن فقط یک آیتم» برای کسی که اشتراک نداره. ۰ = خاموش.\n"
        "برای هر آیتم جداگانه هم می‌شه قیمت گذاشت.",
        "Default price to unlock just one item for a non-subscriber. 0 = off.\n"
        "You can also set a per-item price.",
    ),
    "shop:campaign": (
        "یه تخفیف (یا افزایش) موقت روی همه‌ی قیمت‌ها یک‌جا. تعداد روز می‌ذاری و سرِ موعد "
        "خودکار به قیمت‌های قبل برمی‌گرده — بدون آپلود فایل یا ویرایش دستی.",
        "A temporary discount (or markup) on every price at once. Set a number of days; it "
        "auto-reverts to the old prices when time's up — no file re-upload, no manual edits.",
    ),
    "shop:campaign:discount": (
        "درصد تخفیف رو بفرست (۱ تا ۹۰). قیمت‌ها به نزدیک‌ترین ۱۰۰۰ تومان گرد می‌شن.\n"
        "مشتری قیمت قدیم رو خط‌خورده کنار قیمت جدید می‌بینه.",
        "Send the discount percent (1–90). Prices round to the nearest 1,000 Toman.\n"
        "Buyers see the old price struck through next to the new one.",
    ),
    "shop:campaign:markup": (
        "درصد افزایش رو بفرست. روی همه‌ی قیمت‌ها اعمال می‌شه و سرِ موعد برمی‌گرده.",
        "Send the markup percent. Applied to every price, and reverts when time's up.",
    ),
    "shop:campaign:end": (
        "کمپین همین الان تموم شد و همه‌ی قیمت‌ها دقیقاً به مقدار قبل برگشتن.",
        "The campaign ended now and every price is back to exactly what it was.",
    ),
    "shop:set_zarinpal": (
        "Merchant ID زرین‌پال (یه UUID). فقط برای کاربرای ایران نمایش داده می‌شه.",
        "Your Zarinpal Merchant ID (a UUID). Only shown to Iranian buyers.",
    ),
    "shop:set_card": (
        "شماره کارت و نام صاحب کارت برای پرداخت کارت‌به‌کارت. تأیید پرداخت با خودته.",
        "Card number + holder name for card-to-card. You confirm each payment yourself.",
    ),
    "shop:set_stripe": (
        "کلید Secret استرایپ برای پرداخت بین‌المللی (ویزا/مسترکارت). قیمت روی این مسیر دلاره.",
        "Your Stripe secret key for international cards. Prices are treated as USD on this path.",
    ),
    "shop:set_crypto": (
        "آدرس کیف‌پول و نام شبکه (مثلاً USDT TRC20). تأیید دستیه.",
        "Wallet address + network label (e.g. USDT TRC20). Manual approval.",
    ),
    "shop:set_ton": (
        "آدرس کیف‌پول TON. تأیید پرداخت دستیه.",
        "Your TON wallet address. Manual payment approval.",
    ),
    # --- Force Join ---
    "force_join:list": (
        "کانال‌هایی که کاربر باید عضو بشه. اضافه/حذف از همین‌جا.",
        "The channels a user must join. Add or remove them here.",
    ),
    "force_join:new": (
        "یوزرنیم کانال رو با @ بفرست. ربات باید توی اون کانال ادمین باشه.",
        "Send the channel's @username. The bot must be an admin in that channel.",
    ),
    "force_join:toggle": (
        "گیت عضویت اجباری روشن/خاموش شد. خاموش که باشه، لیست کانال‌ها دست‌نخورده می‌مونه.",
        "Toggled the join gate on/off. Turning it off keeps your channel list untouched.",
    ),
}


def _match(key: str) -> tuple[str, str] | None:
    if key in HELP:
        return HELP[key]
    for k, v in HELP.items():
        if k.endswith(":") and key.startswith(k):
            return v
    return None


def has_tip(key: str) -> bool:
    return _match(key) is not None


def tip(key: str, is_fa: bool) -> str | None:
    entry = _match(key)
    if entry is None:
        return None
    return f"{TIP_ICON} {entry[0] if is_fa else entry[1]}"


async def tip_suffix(key: str, tg_user) -> str:
    """"\n\n💡 ..." ready to append to a screen's own message text, or ""
    if `key` has no registered tip. For reply-keyboard-driven screens —
    see the module docstring."""
    from bot.guide import owner_prefers_persian

    is_fa = await owner_prefers_persian(tg_user)
    line = tip(key, is_fa)
    return f"\n\n{line}" if line else ""
