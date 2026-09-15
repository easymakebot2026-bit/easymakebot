import io
from datetime import datetime, timedelta, timezone

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from openpyxl import load_workbook
from sqlalchemy import select

from bot import commerce_mode, help_text, inventory, premium_content, shop, shop_import
from bot.db.base import async_session_maker
from bot.db.models import Product, ShopSettings
from bot.guide import owner_prefers_persian
from bot.keyboards import (
    SHOP_ADD_BUTTON_TEXTS_ALL,
    SHOP_BACK_BUTTON_TEXTS,
    SHOP_CAMPAIGN_APPLY_TEXTS,
    SHOP_CAMPAIGN_DISCOUNT_MARKUP_TEXTS,
    SHOP_CAMPAIGN_END_TEXTS,
    SHOP_INVOICE_LIST_BUTTON_TEXTS,
    SHOP_PRODUCTS_BUTTON_TEXTS_ALL,
    SHOP_UPLOAD_BUTTON_TEXTS,
    SKIP_BUTTON_TEXTS,
    commerce_mode_keyboard,
    delivery_mode_button_to_key,
    invoice_period_label,
    product_type_button_to_key,
    shop_campaign_confirm_keyboard,
    shop_campaign_direction_from_text,
    shop_campaign_keyboard,
    shop_delivery_mode_keyboard,
    shop_import_keyboard,
    shop_input_cancel_keyboard,
    shop_invoice_button_texts_all,
    shop_invoice_keyboard,
    shop_invoice_period_keyboard,
    shop_menu_keyboard,
    shop_menu_static_texts_all,
    shop_payment_button_texts_all,
    shop_payments_keyboard,
    shop_product_detail_keyboard,
    shop_product_type_keyboard,
    shop_products_keyboard,
    shop_skip_keyboard,
    shop_tax_toggle_text,
    shop_tax_toggle_texts_all,
    tool_button_texts,
)
from bot.shop import TYPE_FIELDS, type_field_prompt
from bot.states import ShopStates

router = Router(name="shop")

# Steps always asked when adding a product, before its type-specific fields.
# Bilingual (prompt_en/prompt_fa) — owner-only wizard data, same pattern as
# bot/handlers/tools/content_list.py:ADD_ITEM_FIELDS.
CORE_FIELDS = [
    {"key": "name", "prompt_en": "Enter the product's name.", "prompt_fa": "نام محصول رو وارد کن."},
    {
        "key": "price",
        "prompt_en": "Enter the price in Toman (numbers only).",
        "prompt_fa": "قیمت رو به تومان وارد کن (فقط عدد).",
    },
    {
        "key": "description",
        "prompt_en": "Enter a short description.",
        "prompt_fa": "یه توضیح کوتاه وارد کن.",
    },
    {
        "key": "image_url",
        "prompt_en": "Enter an image URL (optional).",
        "prompt_fa": "آدرس تصویر رو وارد کن (اختیاری).",
        "optional": True,
    },
]


def _core_field_prompt(field: dict, is_fa: bool) -> str:
    return field["prompt_fa"] if is_fa else field["prompt_en"]


PRODUCT_TYPE_BUTTON_TO_KEY = product_type_button_to_key()
DELIVERY_MODE_BUTTON_TO_KEY = delivery_mode_button_to_key()

# Static (settings-independent) frozensets covering every state (✅-set /
# not-yet-set) and both languages a payment/invoice button could ever show —
# see keyboards.py:shop_payment_button_texts_all for why these must be
# computed once, statically, rather than from a live ShopSettings row.
_PAYMENT_TEXTS = shop_payment_button_texts_all()
_INVOICE_TEXTS = shop_invoice_button_texts_all()
_MENU_STATIC_TEXTS = shop_menu_static_texts_all()
_TAX_TOGGLE_TEXTS = shop_tax_toggle_texts_all()


async def _send_menu(message: Message, bot_id: str, is_fa: bool) -> None:
    mode = await commerce_mode.get_commerce_mode(bot_id)
    if is_fa:
        label = "فروشگاه" if mode != commerce_mode.MODE_SUBSCRIPTION else "پلن‌های اشتراک"
        text = f"مدیریت {label} این ربات."
    else:
        label = "shop" if mode != commerce_mode.MODE_SUBSCRIPTION else "subscription plans"
        text = f"Manage this bot's {label}."
    await message.answer(text, reply_markup=shop_menu_keyboard(mode or commerce_mode.MODE_SHOP, is_fa))


def _current_fields(phase: str, product_type: str | None) -> list[dict]:
    return CORE_FIELDS if phase == "core" else TYPE_FIELDS.get(product_type, [])


async def _send_core_step(message: Message, state: FSMContext, index: int, is_fa: bool) -> None:
    if index >= len(CORE_FIELDS):
        await state.update_data(wizard_index=None)
        data = await state.get_data()
        bot_id = data.get("active_bot_id")
        mode = await commerce_mode.get_commerce_mode(bot_id)
        if mode == commerce_mode.MODE_SUBSCRIPTION:
            # Every product in Subscription mode IS a subscription plan —
            # no type picker needed, there's only one kind here.
            await state.update_data(product_type="subscription")
            await _send_type_step(message, state, 0, is_fa)
            return
        text = "این محصول چه نوعیه؟" if is_fa else "What type of product is this?"
        await message.answer(text, reply_markup=shop_product_type_keyboard(is_fa))
        return

    await state.update_data(wizard_index=index, wizard_phase="core")
    field = CORE_FIELDS[index]
    keyboard = shop_skip_keyboard(is_fa) if field.get("optional") else shop_input_cancel_keyboard(is_fa)
    await message.answer(_core_field_prompt(field, is_fa), reply_markup=keyboard)


async def _send_type_step(message: Message, state: FSMContext, index: int, is_fa: bool) -> None:
    data = await state.get_data()
    product_type = data.get("product_type")
    fields = TYPE_FIELDS.get(product_type, [])

    if index >= len(fields):
        if product_type == "digital":
            await _send_delivery_mode_step(message, is_fa)
        else:
            await _save_product(message, state, is_fa)
        return

    await state.update_data(wizard_index=index, wizard_phase="type")
    field = fields[index]
    keyboard = shop_skip_keyboard(is_fa) if field.get("optional") else shop_input_cancel_keyboard(is_fa)
    await message.answer(type_field_prompt(field, is_fa), reply_markup=keyboard)


async def _save_product(message: Message, state: FSMContext, is_fa: bool) -> None:
    data = await state.get_data()
    payload = data.get("wizard_payload", {})
    bot_id = data.get("active_bot_id")
    product_type = data.get("product_type", "digital")
    delivery_mode = data.get("delivery_mode", "static") if product_type == "digital" else "static"

    try:
        price = int(payload.get("price") or 0)
    except ValueError:
        price = 0

    subscription_days = None
    if payload.get("subscription_days"):
        try:
            subscription_days = int(payload["subscription_days"])
        except ValueError:
            subscription_days = None

    async with async_session_maker() as session:
        product = Product(
            bot_id=bot_id,
            name=payload.get("name") or "",
            description=payload.get("description") or "",
            price=price,
            image_url=payload.get("image_url"),
            product_type=product_type,
            delivery_text=payload.get("delivery_text"),
            delivery_file_url=payload.get("delivery_file_url"),
            access_level_name=payload.get("access_level_name"),
            subscription_days=subscription_days,
            delivery_mode=delivery_mode,
            delivery_api_url=data.get("delivery_api_url"),
            delivery_api_headers=data.get("delivery_api_headers"),
            delivery_api_body_template=data.get("delivery_api_body_template"),
            delivery_api_response_path=data.get("delivery_api_response_path"),
            delivery_api_extra_vars=data.get("delivery_api_extra_vars"),
        )
        session.add(product)
        await session.commit()
        await session.refresh(product)
        new_product_id = product.id

    pending_pool_items = data.get("pending_pool_items")
    if delivery_mode == "pool" and pending_pool_items:
        await shop.add_pool_items(new_product_id, pending_pool_items)

    await state.set_state(None)
    text = "محصول اضافه شد ✅" if is_fa else "Product added ✅"
    await message.answer(text)
    await _send_menu(message, bot_id, is_fa)


async def _send_delivery_mode_step(message: Message, is_fa: bool) -> None:
    text = (
        "این محصول دیجیتال چطور تحویل داده بشه؟"
        if is_fa
        else "How should this digital product be delivered?"
    )
    await message.answer(text, reply_markup=shop_delivery_mode_keyboard(is_fa))


@router.message(ShopStates.add_product_wizard, F.text.in_(DELIVERY_MODE_BUTTON_TO_KEY))
async def choose_delivery_mode(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    mode = DELIVERY_MODE_BUTTON_TO_KEY[message.text]
    await state.update_data(delivery_mode=mode)

    if mode == "static":
        await _save_product(message, state, is_fa)
        return

    if mode == "pool":
        await state.set_state(ShopStates.waiting_for_pool_items)
        text = (
            "آیتم‌های استخر رو بفرست — یکی در هر خط (کپی/پیست)، یا یه فایل متنی/اکسل آپلود کن. "
            "هر آیتم فقط یه‌بار، به یه خریدار داده می‌شه. می‌تونی الان رد کنی و بعداً از صفحه‌ی "
            "محصول اضافه کنی."
            if is_fa
            else "Send the pool items — one per line (paste text), or upload a text/Excel file. "
            "Each item is handed to exactly one buyer, once. You can skip this now and add "
            "items later from the product's page."
        )
        await message.answer(text, reply_markup=shop_skip_keyboard(is_fa))
        return

    # mode == "api"
    await state.set_state(ShopStates.waiting_for_api_url)
    text = (
        "آدرس API که موقع تحویل صدا زده بشه رو وارد کن (باید با http:// یا https:// شروع بشه)."
        if is_fa
        else "Enter the API URL to call at delivery time (must start with http:// or https://)."
    )
    await message.answer(text, reply_markup=shop_input_cancel_keyboard(is_fa))


@router.callback_query(F.data.startswith("shop:add_pool:"))
async def add_pool_items_start(callback: CallbackQuery, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(callback.from_user)
    product_id = int(callback.data.split(":")[-1])
    await state.update_data(pool_target_product_id=product_id)
    await state.set_state(ShopStates.waiting_for_pool_items)
    text = (
        "آیتم‌های جدید رو بفرست — یکی در هر خط (کپی/پیست)، یا یه فایل متنی/اکسل آپلود کن."
        if is_fa
        else "Send the new items — one per line (paste text), or upload a text/Excel file."
    )
    await callback.message.answer(text, reply_markup=shop_input_cancel_keyboard(is_fa))
    await callback.answer()


@router.message(ShopStates.waiting_for_pool_items, F.text.in_(SKIP_BUTTON_TEXTS))
async def skip_pool_items(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    data = await state.get_data()
    if data.get("pool_target_product_id") is not None:
        await state.set_state(None)
        await _send_menu(message, data.get("active_bot_id"), is_fa)
        return
    await _save_product(message, state, is_fa)


@router.message(ShopStates.waiting_for_pool_items, F.document)
async def receive_pool_items_file(message: Message, state: FSMContext, bot: Bot) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    file = await bot.download(message.document)
    try:
        items = _parse_pool_items_file(file.read(), filename=message.document.file_name)
    except ValueError as exc:
        retry = "دوباره امتحان کن، یا رد کن." if is_fa else "Try again, or skip."
        await message.answer(f"{exc}\n\n{retry}", reply_markup=shop_skip_keyboard(is_fa))
        return
    await _apply_pool_items(message, state, is_fa, items)


@router.message(ShopStates.waiting_for_pool_items, F.text)
async def receive_pool_items_text(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    items = (message.text or "").splitlines()
    await _apply_pool_items(message, state, is_fa, items)


async def _apply_pool_items(message: Message, state: FSMContext, is_fa: bool, items: list[str]) -> None:
    cleaned = [item.strip() for item in items if item and item.strip()]
    data = await state.get_data()
    target_product_id = data.get("pool_target_product_id")

    if target_product_id is not None:
        added = await shop.add_pool_items(target_product_id, cleaned)
        await state.set_state(None)
        text = (
            f"{added} آیتم به استخر اضافه شد ✅" if is_fa else f"{added} item(s) added to the pool ✅"
        )
        await message.answer(text)
        await _send_menu(message, data.get("active_bot_id"), is_fa)
        return

    pending = data.get("pending_pool_items", [])
    pending.extend(cleaned)
    await state.update_data(pending_pool_items=pending)
    text = (
        f"{len(pending)} آیتم آماده‌ست. می‌تونی بازم بفرستی، یا رد کن تا محصول ذخیره بشه."
        if is_fa
        else f"{len(pending)} item(s) ready. Send more, or skip to save the product."
    )
    await message.answer(text, reply_markup=shop_skip_keyboard(is_fa))


def _parse_pool_items_file(data: bytes, filename: str | None) -> list[str]:
    """One payload string per pool item — from a plain text/CSV file (one
    per line) or an .xlsx workbook (first non-empty cell of each row)."""
    name = (filename or "").lower()
    if name.endswith(".xlsx"):
        try:
            workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        except Exception as exc:
            raise ValueError("Couldn't read that Excel file. Make sure it's a valid .xlsx.") from exc
        sheet = workbook.active
        items = []
        for row in sheet.iter_rows(values_only=True):
            for cell in row:
                if cell is not None and str(cell).strip():
                    items.append(str(cell).strip())
                    break
        return items

    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Couldn't read that file as text or as an .xlsx workbook.") from exc
    return [line.strip() for line in text.splitlines() if line.strip()]


@router.message(ShopStates.waiting_for_api_url)
async def receive_api_url(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    url = (message.text or "").strip()
    if not url.lower().startswith(("http://", "https://")):
        err = (
            "آدرس باید با http:// یا https:// شروع بشه. دوباره امتحان کن."
            if is_fa
            else "The URL must start with http:// or https://. Try again."
        )
        await message.answer(err, reply_markup=shop_input_cancel_keyboard(is_fa))
        return
    await state.update_data(delivery_api_url=url)
    await state.set_state(ShopStates.waiting_for_api_headers)
    text = (
        "هدرهای HTTP رو وارد کن (اختیاری) — هر کدوم تو یه خط، به شکل `Key: Value`. اگه لازم نیست رد کن."
        if is_fa
        else "Enter any HTTP headers (optional) — one per line, as `Key: Value`. Skip if not needed."
    )
    await message.answer(text, reply_markup=shop_skip_keyboard(is_fa))


@router.message(ShopStates.waiting_for_api_headers, F.text.in_(SKIP_BUTTON_TEXTS))
async def skip_api_headers(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    await state.set_state(ShopStates.waiting_for_api_body_template)
    await _prompt_api_body(message, is_fa)


@router.message(ShopStates.waiting_for_api_headers)
async def receive_api_headers(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    headers = _parse_key_value_lines(message.text or "")
    await state.update_data(delivery_api_headers=headers)
    await state.set_state(ShopStates.waiting_for_api_body_template)
    await _prompt_api_body(message, is_fa)


async def _prompt_api_body(message: Message, is_fa: bool) -> None:
    text = (
        "قالب بدنه‌ی درخواست رو وارد کن. از {{...}} برای متغیرها استفاده کن — مثلاً order_id، "
        "buyer_telegram_id، product_name، product_description، price، یا هر متغیر سفارشی که "
        "بعداً تعریف می‌کنی."
        if is_fa
        else "Enter the request body template. Use {{...}} for variables — e.g. order_id, "
        "buyer_telegram_id, product_name, product_description, price, or any custom variable "
        "you define next."
    )
    await message.answer(text, reply_markup=shop_input_cancel_keyboard(is_fa))


@router.message(ShopStates.waiting_for_api_body_template)
async def receive_api_body_template(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    text = (message.text or "").strip()
    if not text:
        err = "این فیلد نمی‌تونه خالی باشه." if is_fa else "This field can't be empty."
        await message.answer(err, reply_markup=shop_input_cancel_keyboard(is_fa))
        return
    await state.update_data(delivery_api_body_template=text)
    await state.set_state(ShopStates.waiting_for_api_response_path)
    prompt = (
        "پاسخ API معمولاً JSON هست. مسیر فیلدی که باید ارسال بشه رو وارد کن (مثلاً data.config_url)، "
        "یا رد کن تا کل پاسخ خام ارسال بشه."
        if is_fa
        else "The API's response is usually JSON. Enter the path to the field that should be "
        "delivered (e.g. data.config_url), or skip to send the raw response as-is."
    )
    await message.answer(prompt, reply_markup=shop_skip_keyboard(is_fa))


@router.message(ShopStates.waiting_for_api_response_path, F.text.in_(SKIP_BUTTON_TEXTS))
async def skip_api_response_path(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    await state.set_state(ShopStates.waiting_for_api_extra_vars)
    await _prompt_api_extra_vars(message, is_fa)


@router.message(ShopStates.waiting_for_api_response_path)
async def receive_api_response_path(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    await state.update_data(delivery_api_response_path=(message.text or "").strip())
    await state.set_state(ShopStates.waiting_for_api_extra_vars)
    await _prompt_api_extra_vars(message, is_fa)


async def _prompt_api_extra_vars(message: Message, is_fa: bool) -> None:
    text = (
        "متغیرهای سفارشی این محصول رو وارد کن (اختیاری) — هر کدوم تو یه خط، به شکل `key: value` "
        "(مثلاً duration_days: 30). این‌ها هم تو قالب بدنه قابل استفاده‌ن. اگه لازم نیست رد کن."
        if is_fa
        else "Enter this product's custom variables (optional) — one per line, as `key: value` "
        "(e.g. duration_days: 30). These are also usable in the body template. Skip if not needed."
    )
    await message.answer(text, reply_markup=shop_skip_keyboard(is_fa))


@router.message(ShopStates.waiting_for_api_extra_vars, F.text.in_(SKIP_BUTTON_TEXTS))
async def skip_api_extra_vars(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    await _save_product(message, state, is_fa)


@router.message(ShopStates.waiting_for_api_extra_vars)
async def receive_api_extra_vars(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    extra_vars = _parse_key_value_lines(message.text or "")
    await state.update_data(delivery_api_extra_vars=extra_vars)
    await _save_product(message, state, is_fa)


def _parse_key_value_lines(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if key:
            result[key] = value
    return result


@router.message(F.text.in_(tool_button_texts("shop")))
async def open_shop(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    data = await state.get_data()
    bot_id = data.get("active_bot_id")
    if bot_id is None:
        text = 'اول از «ربات‌های من» یه ربات انتخاب کن.' if is_fa else 'First select a bot from "My Bots".'
        await message.answer(text)
        return

    await state.set_state(None)
    mode = await commerce_mode.get_commerce_mode(bot_id)
    if mode is None:
        await state.update_data(commerce_mode_source="shop_tool")
        text = (
            "قبل از مدیریت این بخش، انتخاب کن این ربات چطور کسب‌وکار می‌کنه — بعداً قابل تغییر "
            "نیست، پس با دقت انتخاب کن:"
            if is_fa
            else "Before managing this, choose how this bot does business — this can't be "
            "changed later, so pick carefully:"
        )
        await message.answer(text, reply_markup=commerce_mode_keyboard(is_fa))
        return

    tip = await help_text.tip_suffix("tool:shop", message.from_user)
    if tip:
        await message.answer(tip.strip())
    await _send_menu(message, bot_id, is_fa)


@router.callback_query(F.data == "shop:menu")
async def back_to_menu(callback: CallbackQuery, state: FSMContext) -> None:
    """Still needed as a callback handler: shop_products_keyboard (dynamic,
    still inline) routes its own Back here."""
    is_fa = await owner_prefers_persian(callback.from_user)
    data = await state.get_data()
    bot_id = data.get("active_bot_id")
    await state.set_state(None)
    await _send_menu(callback.message, bot_id, is_fa)
    await callback.answer()


@router.message(F.text.in_(SHOP_BACK_BUTTON_TEXTS))
async def back_to_menu_text(message: Message, state: FSMContext) -> None:
    """Unconditional on state (registered early, ahead of every wizard's
    generic catch-all below) so it always wins, e.g. abandoning an in-progress
    campaign setup — same reasoning as the global "❌ Cancel" in cancel.py."""
    is_fa = await owner_prefers_persian(message.from_user)
    data = await state.get_data()
    bot_id = data.get("active_bot_id")
    await state.set_state(None)
    await _send_menu(message, bot_id, is_fa)


PRODUCTS_PAGE_SIZE = 30


async def _send_products_page(message: Message, bot_id: str, offset: int, is_fa: bool) -> bool:
    """Sends one page and returns True, or returns False (sends nothing) if
    there's nothing at this offset — only meaningful at offset 0, since the
    Prev/Next buttons never target a past-the-end offset themselves."""
    page, has_more = await shop.get_products_page(bot_id, offset, PRODUCTS_PAGE_SIZE)
    if not page:
        return False

    text = (
        f"یه محصول انتخاب کن (نمایش {offset + 1}-{offset + len(page)}):"
        if is_fa
        else f"Select a product (showing {offset + 1}-{offset + len(page)}):"
    )
    await message.answer(
        text,
        reply_markup=shop_products_keyboard(page, offset, has_more, PRODUCTS_PAGE_SIZE, is_fa),
    )
    return True


@router.message(F.text.in_(SHOP_PRODUCTS_BUTTON_TEXTS_ALL))
async def list_products(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    data = await state.get_data()
    bot_id = data.get("active_bot_id")

    tip = await help_text.tip_suffix("shop:products", message.from_user)
    sent = await _send_products_page(message, bot_id, 0, is_fa)
    if not sent:
        text = "هنوز محصولی وجود نداره." if is_fa else "No products yet."
        await message.answer(text)
        return
    if tip:
        await message.answer(tip.strip())


@router.callback_query(F.data.startswith("shop:products_page:"))
async def list_products_page(callback: CallbackQuery, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(callback.from_user)
    offset = int(callback.data.split(":")[-1])
    data = await state.get_data()
    bot_id = data.get("active_bot_id")

    await _send_products_page(callback.message, bot_id, offset, is_fa)
    await callback.answer()


@router.callback_query(F.data.startswith("shop:select:"))
async def select_product(callback: CallbackQuery, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(callback.from_user)
    product_id = int(callback.data.split(":")[-1])
    product = await shop.get_product(product_id)

    data = await state.get_data()
    bot_id = data.get("active_bot_id")

    if product is None or str(product.bot_id) != str(bot_id):
        text = "محصول پیدا نشد." if is_fa else "Product not found."
        await callback.answer(text, show_alert=True)
        return

    if is_fa:
        type_labels = {"physical": "📦 فیزیکی", "digital": "💾 دیجیتال", "access": "🎫 دسترسی"}
        lines = [
            f"📦 {product.name}",
            "",
            product.description,
            f"\n💰 {product.price:,} تومان",
            f"نوع: {type_labels.get(product.product_type, product.product_type)}",
        ]
        if product.product_type == "access" and product.access_level_name:
            lines.append(f"سطح دسترسی: {product.access_level_name}")
    else:
        type_labels = {"physical": "📦 Physical", "digital": "💾 Digital", "access": "🎫 Access"}
        lines = [
            f"📦 {product.name}",
            "",
            product.description,
            f"\n💰 {product.price:,} Toman",
            f"Type: {type_labels.get(product.product_type, product.product_type)}",
        ]
        if product.product_type == "access" and product.access_level_name:
            lines.append(f"Access level: {product.access_level_name}")

    show_pool_button = False
    if product.product_type == "digital" and product.delivery_mode == "pool":
        show_pool_button = True
        counts = await shop.pool_counts(product.id)
        lines.append(
            f"استخر آیتم: {counts['available']} موجود، {counts['assigned']} تحویل‌شده"
            if is_fa
            else f"Item pool: {counts['available']} available, {counts['assigned']} delivered"
        )
    elif product.product_type == "digital" and product.delivery_mode == "api":
        lines.append("تحویل: تماس زنده با API" if is_fa else "Delivery: live API call")

    await callback.message.answer(
        "\n".join(lines),
        reply_markup=shop_product_detail_keyboard(product.id, is_fa, show_pool_button=show_pool_button),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("shop:delete:"))
async def delete_product(callback: CallbackQuery, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(callback.from_user)
    product_id = int(callback.data.split(":")[-1])
    data = await state.get_data()
    bot_id = data.get("active_bot_id")

    async with async_session_maker() as session:
        result = await session.execute(select(Product).where(Product.id == product_id))
        product = result.scalar_one_or_none()
        if product is not None and str(product.bot_id) == str(bot_id):
            await session.delete(product)
            await session.commit()

    text = "محصول حذف شد ✅" if is_fa else "Product deleted ✅"
    await callback.message.answer(text)
    await _send_menu(callback.message, bot_id, is_fa)
    await callback.answer()


@router.message(F.text.in_(SHOP_ADD_BUTTON_TEXTS_ALL))
async def new_product(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    await state.update_data(wizard_payload={})
    await state.set_state(ShopStates.add_product_wizard)
    tip = await help_text.tip_suffix("shop:new", message.from_user)
    if tip:
        await message.answer(tip.strip())
    await _send_core_step(message, state, 0, is_fa)


@router.message(ShopStates.add_product_wizard, F.text.in_(SKIP_BUTTON_TEXTS))
async def wizard_skip(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    data = await state.get_data()
    phase = data.get("wizard_phase", "core")
    index = data.get("wizard_index", 0)
    fields = _current_fields(phase, data.get("product_type"))
    field = fields[index]

    if not field.get("optional"):
        text = "این فیلد رو نمی‌شه رد کرد." if is_fa else "This field can't be skipped."
        await message.answer(text, reply_markup=shop_skip_keyboard(is_fa))
        return

    payload = data.get("wizard_payload", {})
    payload[field["key"]] = None
    await state.update_data(wizard_payload=payload)

    if phase == "core":
        await _send_core_step(message, state, index + 1, is_fa)
    else:
        await _send_type_step(message, state, index + 1, is_fa)


@router.message(ShopStates.add_product_wizard, F.text.in_(PRODUCT_TYPE_BUTTON_TO_KEY))
async def choose_type(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    await state.update_data(product_type=PRODUCT_TYPE_BUTTON_TO_KEY[message.text])
    await _send_type_step(message, state, 0, is_fa)


@router.message(ShopStates.add_product_wizard)
async def wizard_receive(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    data = await state.get_data()
    phase = data.get("wizard_phase", "core")
    index = data.get("wizard_index", 0)
    fields = _current_fields(phase, data.get("product_type"))
    field = fields[index]
    payload = data.get("wizard_payload", {})

    text = (message.text or "").strip()
    if not text and not field.get("optional"):
        err = "این فیلد نمی‌تونه خالی باشه. دوباره امتحان کن." if is_fa else "This field can't be empty. Please try again."
        await message.answer(
            err,
            reply_markup=shop_input_cancel_keyboard(is_fa),
        )
        return

    if field["key"] in ("price", "subscription_days") and not text.isdigit():
        err = "لطفاً فقط عدد وارد کن (بدون نماد ارز)." if is_fa else "Please enter numbers only (no currency symbols)."
        await message.answer(
            err,
            reply_markup=shop_input_cancel_keyboard(is_fa),
        )
        return

    payload[field["key"]] = text or None
    await state.update_data(wizard_payload=payload)

    if phase == "core":
        await _send_core_step(message, state, index + 1, is_fa)
    else:
        await _send_type_step(message, state, index + 1, is_fa)


@router.message(F.text.in_(_MENU_STATIC_TEXTS["payments"]))
async def payments_menu(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    data = await state.get_data()
    bot_id = data.get("active_bot_id")
    settings = await shop.get_shop_settings(bot_id)
    text = (
        "روش‌های پرداخت — هر کدوم که تنظیم نشه، به خریدارها پیشنهاد داده نمی‌شه."
        if is_fa
        else "Payment methods — whichever isn't set simply won't be offered to buyers."
    )
    text += await help_text.tip_suffix("shop:payments", message.from_user)
    await message.answer(text, reply_markup=shop_payments_keyboard(settings, is_fa))


async def _upsert_shop_settings(bot_id: str, **fields) -> None:
    async with async_session_maker() as session:
        result = await session.execute(select(ShopSettings).where(ShopSettings.bot_id == bot_id))
        settings = result.scalar_one_or_none()
        if settings is None:
            settings = ShopSettings(bot_id=bot_id)
            session.add(settings)
        for key, value in fields.items():
            setattr(settings, key, value)
        await session.commit()


@router.message(F.text.in_(_PAYMENT_TEXTS["zarinpal"]))
async def set_zarinpal_start(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    await state.set_state(ShopStates.waiting_for_zarinpal_id)
    text = "شناسه‌ی پذیرنده‌ی زرین‌پالت رو بفرست." if is_fa else "Send your Zarinpal merchant ID."
    text += await help_text.tip_suffix("shop:set_zarinpal", message.from_user)
    await message.answer(text, reply_markup=shop_input_cancel_keyboard(is_fa))


@router.message(ShopStates.waiting_for_zarinpal_id)
async def receive_zarinpal_id(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    data = await state.get_data()
    bot_id = data.get("active_bot_id")

    await _upsert_shop_settings(bot_id, zarinpal_merchant_id=(message.text or "").strip())
    await state.set_state(None)
    text = "شناسه‌ی زرین‌پال ذخیره شد ✅" if is_fa else "Zarinpal merchant ID saved ✅"
    await message.answer(text)
    await _send_menu(message, bot_id, is_fa)


@router.message(F.text.in_(_PAYMENT_TEXTS["card"]))
async def set_card_start(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    await state.set_state(ShopStates.waiting_for_card_number)
    text = "شماره کارت برای پرداخت‌های کارت‌به‌کارت رو بفرست." if is_fa else "Send the card number for card-to-card payments."
    text += await help_text.tip_suffix("shop:set_card", message.from_user)
    await message.answer(text, reply_markup=shop_input_cancel_keyboard(is_fa))


@router.message(ShopStates.waiting_for_card_number)
async def receive_card_number(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    await state.update_data(pending_card_number=(message.text or "").strip())
    await state.set_state(ShopStates.waiting_for_card_holder)
    text = "نام صاحب کارت رو بفرست." if is_fa else "Send the card holder's name."
    await message.answer(
        text, reply_markup=shop_input_cancel_keyboard(is_fa)
    )


@router.message(ShopStates.waiting_for_card_holder)
async def receive_card_holder(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    data = await state.get_data()
    bot_id = data.get("active_bot_id")

    await _upsert_shop_settings(
        bot_id,
        card_number=data.get("pending_card_number"),
        card_holder_name=(message.text or "").strip(),
    )
    await state.set_state(None)
    text = "اطلاعات کارت‌به‌کارت ذخیره شد ✅" if is_fa else "Card-to-card details saved ✅"
    await message.answer(text)
    await _send_menu(message, bot_id, is_fa)


@router.message(F.text.in_(_PAYMENT_TEXTS["stripe"]))
async def set_stripe_start(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    await state.set_state(ShopStates.waiting_for_stripe_key)
    text = (
        "کلید سری استرایپت رو بفرست (با sk_live_ یا sk_test_ شروع می‌شه). "
        "از استرایپ برای خریدارهایی که از خارج ایران با دلار پرداخت می‌کنن استفاده کن."
        if is_fa
        else "Send your Stripe secret key (starts with sk_live_ or sk_test_). "
        "Use Stripe for buyers paying in USD from outside Iran."
    )
    text += await help_text.tip_suffix("shop:set_stripe", message.from_user)
    await message.answer(text, reply_markup=shop_input_cancel_keyboard(is_fa))


@router.message(ShopStates.waiting_for_stripe_key)
async def receive_stripe_key(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    data = await state.get_data()
    bot_id = data.get("active_bot_id")

    await _upsert_shop_settings(bot_id, stripe_secret_key=(message.text or "").strip())
    await state.set_state(None)
    text = "کلید استرایپ ذخیره شد ✅" if is_fa else "Stripe key saved ✅"
    await message.answer(text)
    await _send_menu(message, bot_id, is_fa)


@router.message(F.text.in_(_PAYMENT_TEXTS["crypto"]))
async def set_crypto_start(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    await state.set_state(ShopStates.waiting_for_crypto_address)
    text = "آدرس کیف پول ارز دیجیتالت رو بفرست (مثلاً یه آدرس USDT)." if is_fa else "Send your crypto wallet address (e.g. a USDT address)."
    text += await help_text.tip_suffix("shop:set_crypto", message.from_user)
    await message.answer(text, reply_markup=shop_input_cancel_keyboard(is_fa))


@router.message(ShopStates.waiting_for_crypto_address)
async def receive_crypto_address(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    await state.update_data(pending_crypto_address=(message.text or "").strip())
    await state.set_state(ShopStates.waiting_for_crypto_label)
    text = (
        'برچسب شبکه/ارزی که خریدارها باید ببینن رو بفرست (مثلاً «USDT (TRC20)»).'
        if is_fa
        else 'Send the network/currency label buyers should see (e.g. "USDT (TRC20)").'
    )
    await message.answer(
        text,
        reply_markup=shop_input_cancel_keyboard(is_fa),
    )


@router.message(ShopStates.waiting_for_crypto_label)
async def receive_crypto_label(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    data = await state.get_data()
    bot_id = data.get("active_bot_id")

    await _upsert_shop_settings(
        bot_id,
        crypto_wallet_address=data.get("pending_crypto_address"),
        crypto_network_label=(message.text or "").strip(),
    )
    await state.set_state(None)
    text = "کیف پول ارز دیجیتال ذخیره شد ✅" if is_fa else "Crypto wallet saved ✅"
    await message.answer(text)
    await _send_menu(message, bot_id, is_fa)


@router.message(F.text.in_(_PAYMENT_TEXTS["ton"]))
async def set_ton_start(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    await state.set_state(ShopStates.waiting_for_ton_address)
    text = "آدرس کیف پول TON‌ت رو بفرست." if is_fa else "Send your TON wallet address."
    text += await help_text.tip_suffix("shop:set_ton", message.from_user)
    await message.answer(text, reply_markup=shop_input_cancel_keyboard(is_fa))


@router.message(ShopStates.waiting_for_ton_address)
async def receive_ton_address(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    data = await state.get_data()
    bot_id = data.get("active_bot_id")

    await _upsert_shop_settings(bot_id, ton_wallet_address=(message.text or "").strip())
    await state.set_state(None)
    text = "کیف پول TON ذخیره شد ✅" if is_fa else "TON wallet saved ✅"
    await message.answer(text)
    await _send_menu(message, bot_id, is_fa)


@router.message(F.text.in_(_MENU_STATIC_TEXTS["invoice"]))
async def invoice_settings_menu(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    data = await state.get_data()
    bot_id = data.get("active_bot_id")
    settings = await shop.get_shop_settings(bot_id)
    text = (
        "فاکتور PDF‌ای که خریدارها بعد از خرید می‌گیرن رو شخصی‌سازی کن — نام کسب‌وکار، لوگو، "
        "آدرس، تلفن، یادداشت پایانی و مهر و امضا. مالیات بر ارزش‌افزوده ۱۰٪ رو هم از همینجا "
        "فعال/غیرفعال کن. هرچی تنظیم نشه، فقط نمایش داده نمی‌شه."
        if is_fa
        else "Customize the PDF invoice buyers get after a purchase — business name, "
        "logo, address, phone, a footer note, and a signature/stamp image. Turn the 10% "
        "VAT on/off here too. Anything left unset just doesn't appear."
    )
    text += await help_text.tip_suffix("shop:invoice", message.from_user)
    await message.answer(text, reply_markup=shop_invoice_keyboard(settings, is_fa))


@router.message(F.text.in_(_INVOICE_TEXTS["business_name"]))
async def set_invoice_business_name_start(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    await state.set_state(ShopStates.waiting_for_invoice_business_name)
    text = (
        "نام کسب‌وکار/فروشگاه که بالای فاکتور چاپ می‌شه رو بفرست."
        if is_fa
        else "Send the business/store name to print at the top of the invoice."
    )
    await message.answer(
        text,
        reply_markup=shop_input_cancel_keyboard(is_fa),
    )


@router.message(ShopStates.waiting_for_invoice_business_name)
async def receive_invoice_business_name(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    data = await state.get_data()
    bot_id = data.get("active_bot_id")

    await _upsert_shop_settings(bot_id, invoice_business_name=(message.text or "").strip())
    await state.set_state(None)
    text = "نام کسب‌وکار ذخیره شد ✅" if is_fa else "Business name saved ✅"
    await message.answer(text)
    await invoice_settings_menu(message, state)


@router.message(F.text.in_(_INVOICE_TEXTS["logo"]))
async def set_invoice_logo_start(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    await state.set_state(ShopStates.waiting_for_invoice_logo_url)
    text = (
        "یه آدرس مستقیم تصویر (png/jpg) برای لوگویی که بالا-چپ فاکتور نشون داده می‌شه بفرست."
        if is_fa
        else "Send a direct image URL (png/jpg) for the logo shown top-left on the invoice."
    )
    await message.answer(
        text,
        reply_markup=shop_input_cancel_keyboard(is_fa),
    )


@router.message(ShopStates.waiting_for_invoice_logo_url)
async def receive_invoice_logo(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    data = await state.get_data()
    bot_id = data.get("active_bot_id")

    await _upsert_shop_settings(bot_id, invoice_logo_url=(message.text or "").strip())
    await state.set_state(None)
    text = (
        "لوگو ذخیره شد ✅ (اگه آدرس قابل‌دریافت نباشه، فاکتور فقط ازش رد می‌شه)"
        if is_fa
        else "Logo saved ✅ (if the URL can't be fetched, the invoice just skips it)"
    )
    await message.answer(text)
    await invoice_settings_menu(message, state)


@router.message(F.text.in_(_INVOICE_TEXTS["address"]))
async def set_invoice_address_start(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    await state.set_state(ShopStates.waiting_for_invoice_address)
    text = "آدرس کسب‌وکار که روی فاکتور چاپ می‌شه رو بفرست." if is_fa else "Send the business address to print on the invoice."
    await message.answer(
        text,
        reply_markup=shop_input_cancel_keyboard(is_fa),
    )


@router.message(ShopStates.waiting_for_invoice_address)
async def receive_invoice_address(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    data = await state.get_data()
    bot_id = data.get("active_bot_id")

    await _upsert_shop_settings(bot_id, invoice_address=(message.text or "").strip())
    await state.set_state(None)
    text = "آدرس ذخیره شد ✅" if is_fa else "Address saved ✅"
    await message.answer(text)
    await invoice_settings_menu(message, state)


@router.message(F.text.in_(_INVOICE_TEXTS["footer_note"]))
async def set_invoice_footer_start(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    await state.set_state(ShopStates.waiting_for_invoice_footer_note)
    text = (
        "یه یادداشت کوتاه پایانی بفرست (مثلاً سیاست بازگشت کالا یا یه پیام تشکر)."
        if is_fa
        else "Send a short footer note (e.g. a return policy or thank-you line)."
    )
    await message.answer(
        text,
        reply_markup=shop_input_cancel_keyboard(is_fa),
    )


@router.message(ShopStates.waiting_for_invoice_footer_note)
async def receive_invoice_footer(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    data = await state.get_data()
    bot_id = data.get("active_bot_id")

    await _upsert_shop_settings(bot_id, invoice_footer_note=(message.text or "").strip())
    await state.set_state(None)
    text = "یادداشت پایانی ذخیره شد ✅" if is_fa else "Footer note saved ✅"
    await message.answer(text)
    await invoice_settings_menu(message, state)


@router.message(F.text.in_(_INVOICE_TEXTS["business_phone"]))
async def set_invoice_business_phone_start(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    await state.set_state(ShopStates.waiting_for_invoice_business_phone)
    text = "شماره تلفن کسب‌وکار که پایین فاکتور چاپ می‌شه رو بفرست." if is_fa else "Send the business phone number to print at the bottom of the invoice."
    await message.answer(
        text,
        reply_markup=shop_input_cancel_keyboard(is_fa),
    )


@router.message(ShopStates.waiting_for_invoice_business_phone)
async def receive_invoice_business_phone(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    data = await state.get_data()
    bot_id = data.get("active_bot_id")

    await _upsert_shop_settings(bot_id, invoice_business_phone=(message.text or "").strip())
    await state.set_state(None)
    text = "تلفن کسب‌وکار ذخیره شد ✅" if is_fa else "Business phone saved ✅"
    await message.answer(text)
    await invoice_settings_menu(message, state)


@router.message(F.text.in_(_INVOICE_TEXTS["signature"]))
async def set_invoice_signature_start(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    await state.set_state(ShopStates.waiting_for_invoice_signature_url)
    text = (
        "یه آدرس مستقیم تصویر (png/jpg) از مهر یا امضاتون برای پایین فاکتور بفرست."
        if is_fa
        else "Send a direct image URL (png/jpg) of your stamp/signature for the bottom of the invoice."
    )
    await message.answer(
        text,
        reply_markup=shop_input_cancel_keyboard(is_fa),
    )


@router.message(ShopStates.waiting_for_invoice_signature_url)
async def receive_invoice_signature(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    data = await state.get_data()
    bot_id = data.get("active_bot_id")

    await _upsert_shop_settings(bot_id, invoice_signature_url=(message.text or "").strip())
    await state.set_state(None)
    text = (
        "مهر و امضا ذخیره شد ✅ (اگه آدرس قابل‌دریافت نباشه، فاکتور فقط یه کادر خالی نشون می‌ده)"
        if is_fa
        else "Signature/stamp saved ✅ (if the URL can't be fetched, the invoice just shows an empty box)"
    )
    await message.answer(text)
    await invoice_settings_menu(message, state)


@router.message(F.text.in_(_TAX_TOGGLE_TEXTS))
async def toggle_tax(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    data = await state.get_data()
    bot_id = data.get("active_bot_id")
    settings = await shop.get_shop_settings(bot_id)
    now_enabled = not bool(settings and settings.tax_enabled)

    await _upsert_shop_settings(bot_id, tax_enabled=now_enabled)
    if now_enabled:
        text = (
            "مالیات بر ارزش‌افزوده ۱۰٪ فعال شد — از این به بعد به فاکتورهای جدید اضافه می‌شه."
            if is_fa
            else "10% VAT is now ON — it'll be added to new invoices from now on."
        )
    else:
        text = "مالیات بر ارزش‌افزوده غیرفعال شد." if is_fa else "VAT is now OFF."
    await message.answer(text)
    await invoice_settings_menu(message, state)


def _invoice_period_since(period: str) -> datetime:
    now = datetime.now(timezone.utc)
    if period == "day":
        return now - timedelta(days=1)
    if period == "week":
        return now - timedelta(days=7)
    if period == "month":
        return now - timedelta(days=30)
    return now - timedelta(days=365)


@router.message(F.text.in_(SHOP_INVOICE_LIST_BUTTON_TEXTS))
async def invoice_list_menu(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    text = "بازه‌ی زمانی رو انتخاب کن:" if is_fa else "Choose a time range:"
    await message.answer(text, reply_markup=shop_invoice_period_keyboard(is_fa))


@router.callback_query(F.data.startswith("shop_invlist:"))
async def invoice_list_show(callback: CallbackQuery, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(callback.from_user)
    period = callback.data.split(":", 1)[1]
    data = await state.get_data()
    bot_id = data.get("active_bot_id")
    since = _invoice_period_since(period)
    invoices = await shop.list_issued_invoices(bot_id, since)
    await callback.answer()

    label = invoice_period_label(period, is_fa)
    if not invoices:
        text = f"فاکتوری در بازه‌ی {label} صادر نشده." if is_fa else f"No invoices issued in the {label} range."
        await callback.message.answer(text)
        return

    header = f"🧾 فاکتورهای {label} ({len(invoices)}):" if is_fa else f"🧾 {label} invoices ({len(invoices)}):"
    lines = [header]
    for inv in invoices[:30]:
        items_line = "، ".join(inv["items"]) if is_fa else ", ".join(inv["items"])
        if is_fa:
            entry = (
                f"\n#{inv['invoice_number']} — {inv['date']:%Y-%m-%d %H:%M}\n"
                f"  اقلام: {items_line}\n"
                f"  مبلغ: {inv['total']:,} تومان\n"
                f"  خریدار: {inv['buyer_telegram_id']}"
            )
            if inv["phone"]:
                entry += f"\n  تلفن: {inv['phone']}"
            if inv["address"]:
                entry += f"\n  آدرس: {inv['address']}"
        else:
            entry = (
                f"\n#{inv['invoice_number']} — {inv['date']:%Y-%m-%d %H:%M}\n"
                f"  Items: {items_line}\n"
                f"  Total: {inv['total']:,} Toman\n"
                f"  Buyer: {inv['buyer_telegram_id']}"
            )
            if inv["phone"]:
                entry += f"\n  Phone: {inv['phone']}"
            if inv["address"]:
                entry += f"\n  Address: {inv['address']}"
        lines.append(entry)

    text = "\n".join(lines)
    if len(text) > 3900:  # Telegram's 4096-char message cap, with headroom
        text = text[:3900] + "\n…"
    await callback.message.answer(text)


@router.message(F.text.in_(_MENU_STATIC_TEXTS["stats"]))
async def sales_stats(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    data = await state.get_data()
    bot_id = data.get("active_bot_id")
    stats = await inventory.get_shop_stats(bot_id)

    if is_fa:
        lines = [
            f"📦 محصولات: {stats['product_count']}",
            f"🧾 سفارش‌ها: {stats['order_count']} ({stats['paid_order_count']} پرداخت‌شده)",
            f"💰 درآمد: {stats['revenue']:,}",
        ]
        if stats["profit"] is not None:
            lines.append(
                f"📈 سود تخمینی: {stats['profit']:,} "
                "(فقط محصول‌هایی که قیمت تمام‌شده تنظیم شده حساب می‌شن)"
            )
        if stats["top_products"]:
            lines.append("\n🏆 پرفروش‌ترین‌ها:")
            for p in stats["top_products"]:
                lines.append(f"  • {p['name']} — {p['orders']} سفارش, {p['revenue']:,}")
        if stats["low_stock"]:
            lines.append("\n⚠️ موجودی کم / تمام‌شده:")
            for p in stats["low_stock"]:
                label = "تمام شده" if p["stock"] <= 0 else f"{p['stock']} باقی‌مونده"
                lines.append(f"  • {p['name']} — {label}")
    else:
        lines = [
            f"📦 Products: {stats['product_count']}",
            f"🧾 Orders: {stats['order_count']} ({stats['paid_order_count']} paid)",
            f"💰 Revenue: {stats['revenue']:,}",
        ]
        if stats["profit"] is not None:
            lines.append(
                f"📈 Estimated profit: {stats['profit']:,} "
                "(only counting products with a cost price set)"
            )
        if stats["top_products"]:
            lines.append("\n🏆 Top products:")
            for p in stats["top_products"]:
                lines.append(f"  • {p['name']} — {p['orders']} orders, {p['revenue']:,}")
        if stats["low_stock"]:
            lines.append("\n⚠️ Low / out of stock:")
            for p in stats["low_stock"]:
                label = "OUT OF STOCK" if p["stock"] <= 0 else f"{p['stock']} left"
                lines.append(f"  • {p['name']} — {label}")

    text = "\n".join(lines)
    text += await help_text.tip_suffix("shop:stats", message.from_user)
    await message.answer(text)


@router.message(F.text.in_(_MENU_STATIC_TEXTS["import"]))
async def import_products_menu(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    text = (
        "محصولات رو از اکسل خودت گروهی اضافه یا به‌روزرسانی کن — نام، قیمت، موجودی و قیمت "
        "تمام‌شده، همه تو یه فایل. یه نمونه دانلود کن تا ستون‌ها رو ببینی، یا فایل .xlsx/.csv "
        "خودت رو آپلود کن (اسم ستون‌های مطابق، فارسی یا انگلیسی).\n\n"
        "آپلود دوباره‌ی فایل با همون کد، اون محصول‌ها رو جای‌گذاری می‌کنه به‌جای تکرار؛ "
        "اقدام = حذف، مورد مطابق رو حذف می‌کنه."
        if is_fa
        else "Bulk-add or update products from your own spreadsheet — name, price, "
        "stock and cost, all in one file. Download a sample to see the columns, "
        "or upload your own .xlsx/.csv (matching column names in English or Persian).\n\n"
        "Re-uploading a file with the same Code updates those products in place "
        "instead of duplicating them; Action = Delete removes the matching one."
    )
    text += await help_text.tip_suffix("shop:import", message.from_user)
    await message.answer(text, reply_markup=shop_import_keyboard(is_fa))


@router.message(F.text == "🇬🇧 Sample (EN)")
async def send_sample_en(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    data = shop_import.generate_sample_products_excel("en")
    file = BufferedInputFile(data, filename="products_template_en.xlsx")
    caption = "این فایل رو پر کن و با «📤 آپلود فایل» دوباره بفرست." if is_fa else "Fill this in and send it back with \"📤 Upload File\"."
    await message.answer_document(
        file,
        caption=caption,
        reply_markup=shop_import_keyboard(is_fa),
    )


@router.message(F.text == "🇮🇷 Sample (FA)")
async def send_sample_fa(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    data = shop_import.generate_sample_products_excel("fa")
    file = BufferedInputFile(data, filename="products_template_fa.xlsx")
    await message.answer_document(
        file,
        caption="این فایل رو پر کن و دوباره با «📤 آپلود فایل» بفرست.",
        reply_markup=shop_import_keyboard(is_fa),
    )


@router.message(F.text.in_(SHOP_UPLOAD_BUTTON_TEXTS))
async def start_import_upload(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    await state.set_state(ShopStates.waiting_for_import_file)
    text = (
        "فایل رو به‌صورت داکیومنت بفرست — .xlsx یا .csv. لازم نیست ردیف هدر اولین ردیف باشه."
        if is_fa
        else "Send the file as a document — .xlsx or .csv. The header row doesn't "
        "have to be the first row."
    )
    text += await help_text.tip_suffix("shop:import_upload", message.from_user)
    await message.answer(text, reply_markup=shop_input_cancel_keyboard(is_fa))


@router.message(ShopStates.waiting_for_import_file, F.document)
async def receive_import_file(message: Message, state: FSMContext, bot: Bot) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    data = await state.get_data()
    bot_id = data.get("active_bot_id")

    file = await bot.download(message.document)
    try:
        items = shop_import.parse_products_workbook(file.read(), filename=message.document.file_name)
    except ValueError as exc:
        retry = "دوباره امتحان کن، یا /cancel رو بفرست تا لغو بشه." if is_fa else "Try again, or send /cancel to abort."
        await message.answer(f"{exc}\n\n{retry}")
        return

    if not items:
        text = (
            "هیچ ردیفی با نام و قیمت عددی (یا کد برای حذف) تو این فایل پیدا نشد. "
            "دوباره امتحان کن، یا /cancel رو بفرست."
            if is_fa
            else "No rows with a Name and a numeric Price (or a Code to delete) were found "
            "in that file. Try again, or send /cancel."
        )
        await message.answer(text)
        return

    result = await shop.upsert_products_from_import(bot_id, items)
    await state.set_state(None)
    if is_fa:
        text = (
            f"وارد کردن انجام شد ✅ — {result['created']} اضافه شد، {result['updated']} "
            f"به‌روزرسانی شد، {result['deleted']} حذف شد."
        )
    else:
        text = (
            f"Import done ✅ — {result['created']} added, {result['updated']} updated, "
            f"{result['deleted']} deleted."
        )
    await message.answer(text)
    await _send_menu(message, bot_id, is_fa)


@router.message(F.text.in_(_MENU_STATIC_TEXTS["free_preview"]))
async def set_free_preview_start(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    data = await state.get_data()
    bot_id = data.get("active_bot_id")
    current = await premium_content.get_free_preview_limit(bot_id)

    await state.set_state(ShopStates.waiting_for_free_preview_limit)
    text = (
        f"یه مشترک چند آیتم پرمیوم رو می‌تونه رایگان ببینه قبل از اینکه اشتراک لازم بشه؟ "
        f"(الان {current})"
        if is_fa
        else f"How many premium content items can a subscriber view for free before a subscription "
        f"is required? (currently {current})"
    )
    text += await help_text.tip_suffix("shop:free_preview", message.from_user)
    await message.answer(text, reply_markup=shop_input_cancel_keyboard(is_fa))


@router.message(ShopStates.waiting_for_free_preview_limit)
async def receive_free_preview_limit(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    data = await state.get_data()
    bot_id = data.get("active_bot_id")
    text = (message.text or "").strip()

    if not text.isdigit():
        err = "لطفاً یه عدد صحیح وارد کن (۰ یا بیشتر)." if is_fa else "Please enter a whole number (0 or more)."
        await message.answer(
            err, reply_markup=shop_input_cancel_keyboard(is_fa)
        )
        return

    await premium_content.set_free_preview_limit(bot_id, int(text))
    await state.set_state(None)
    result_text = f"سقف پیش‌نمایش رایگان روی {text} تنظیم شد ✅" if is_fa else f"Free preview limit set to {text} ✅"
    await message.answer(result_text)
    await _send_menu(message, bot_id, is_fa)


# --- Single-item unlock price (subscription mode à-la-carte) ---


@router.message(F.text.in_(_MENU_STATIC_TEXTS["unlock_price"]))
async def set_unlock_price_start(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    data = await state.get_data()
    bot_id = data.get("active_bot_id")
    current = await shop.get_default_unlock_price(bot_id)
    if is_fa:
        current_txt = f"{current:,} تومان" if current else "خاموش (خرید تک‌آیتمی پیشنهاد نمی‌شه)"
    else:
        current_txt = f"{current:,} Toman" if current else "off (no single-item purchase offered)"

    await state.set_state(ShopStates.waiting_for_default_unlock_price)
    if is_fa:
        text = (
            "قیمت پیش‌فرض (تومان) که یه غیرمشترک برای رفع قفل فقط یه آیتم پرمیوم می‌پردازه، "
            "بعد از تموم شدن پیش‌نمایش‌های رایگانش. برای خاموش کردنش ۰ بفرست.\n\n"
            f"الان: {current_txt}"
        )
    else:
        text = (
            "Default price (Toman) a non-subscriber pays to unlock just one premium item, "
            "after their free previews are used up. Send 0 to turn it off.\n\n"
            f"Currently: {current_txt}"
        )
    text += await help_text.tip_suffix("shop:unlock_price", message.from_user)
    await message.answer(text, reply_markup=shop_input_cancel_keyboard(is_fa))


@router.message(ShopStates.waiting_for_default_unlock_price)
async def receive_unlock_price(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    data = await state.get_data()
    bot_id = data.get("active_bot_id")
    text = (message.text or "").strip().replace(",", "")

    if not text.isdigit():
        err = "لطفاً یه عدد صحیح تومان وارد کن (یا ۰ برای خاموش کردن)." if is_fa else "Please enter a whole number of Toman (or 0 to turn it off)."
        await message.answer(
            err,
            reply_markup=shop_input_cancel_keyboard(is_fa),
        )
        return

    value = int(text)
    await shop.set_default_unlock_price(bot_id, value or None)
    await state.set_state(None)
    if is_fa:
        result_text = "قیمت تک‌آیتمی خاموش شد ✅" if not value else f"قیمت تک‌آیتمی روی {value:,} تومان تنظیم شد ✅"
    else:
        result_text = "Single-item price turned off ✅" if not value else f"Single-item price set to {value:,} Toman ✅"
    await message.answer(result_text)
    await _send_menu(message, bot_id, is_fa)


# --- Time-boxed price campaign (sale / markup, auto-reverts) ---


def _campaign_status_text(campaign, is_fa: bool) -> str:
    remaining = campaign.ends_at - datetime.now(timezone.utc)
    days, rem = divmod(int(remaining.total_seconds()), 86400)
    hours = rem // 3600
    if is_fa:
        verb = "تخفیف" if campaign.direction == "discount" else "افزایش قیمت"
        left = f"{days} روز و {hours} ساعت" if remaining.total_seconds() > 0 else "همین الان"
        return (
            f"🎉 کمپین فعال: {campaign.percent}٪ {verb} روی همه‌ی قیمت‌ها.\n"
            f"به‌صورت خودکار در {campaign.ends_at:%Y-%m-%d %H:%M} UTC برمی‌گرده ({left} باقی‌مونده)."
        )
    verb = "off" if campaign.direction == "discount" else "up"
    left = f"{days}d {hours}h" if remaining.total_seconds() > 0 else "ending now"
    return (
        f"🎉 Active campaign: {campaign.percent}% {verb} on every price.\n"
        f"Reverts automatically on {campaign.ends_at:%Y-%m-%d %H:%M} UTC ({left} left)."
    )


@router.message(F.text.in_(_MENU_STATIC_TEXTS["campaign"]))
async def campaign_menu(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    data = await state.get_data()
    bot_id = data.get("active_bot_id")
    await state.set_state(None)

    await shop.expire_due_campaigns()  # lazy revert if one just lapsed
    campaign = await shop.get_active_campaign(bot_id)
    if campaign is not None:
        text = _campaign_status_text(campaign, is_fa)
    else:
        text = (
            "یه تخفیف موقت (یا افزایش قیمت) رو روی *همه‌ی* قیمت‌های این ربات یه‌جا اعمال کن — "
            "محصول‌ها، پلن‌ها و قیمت‌های رفع قفل تک‌آیتمی. تعداد روزهایی که اجرا بشه رو تنظیم "
            "کن؛ وقتی تموم شد، همه‌ی قیمت‌ها خودکار برمی‌گردن. نیاز به آپلود دوباره‌ی فایل یا "
            "ویرایش تک‌تک آیتم‌ها نیست."
            if is_fa
            else "Apply a temporary discount (or markup) to *every* price for this bot at once — "
            "products, plans and single-item unlock prices. Set how many days it runs; when "
            "that's up, every price snaps back automatically. No file re-upload, no per-item edits."
        )
        text += await help_text.tip_suffix("shop:campaign", message.from_user)
    await message.answer(text, reply_markup=shop_campaign_keyboard(campaign is not None, is_fa))


@router.message(F.text.in_(SHOP_CAMPAIGN_END_TEXTS))
async def campaign_end(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    data = await state.get_data()
    bot_id = data.get("active_bot_id")
    ended = await shop.end_price_campaign(bot_id)
    if is_fa:
        text = "کمپین پایان یافت — قیمت‌ها برگردوندن شدن ✅" if ended else "کمپین فعالی وجود نداره."
    else:
        text = "Campaign ended — prices restored ✅" if ended else "No active campaign."
    await message.answer(text)
    await _send_menu(message, bot_id, is_fa)


@router.message(F.text.in_(SHOP_CAMPAIGN_DISCOUNT_MARKUP_TEXTS))
async def campaign_pick_direction(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    direction = shop_campaign_direction_from_text(message.text) or "discount"
    await state.update_data(campaign_direction=direction)
    await state.set_state(ShopStates.waiting_for_campaign_percent)
    cap = "1–90" if direction == "discount" else "1–500"
    if is_fa:
        verb = "تخفیف" if direction == "discount" else "افزایش قیمت"
        text = f"چند درصد؟ ({verb}, {cap})"
    else:
        text = f"By what percent? ({'discount' if direction == 'discount' else 'markup'}, {cap})"
    tip_key = "shop:campaign:discount" if direction == "discount" else "shop:campaign:markup"
    text += await help_text.tip_suffix(tip_key, message.from_user)
    await message.answer(text, reply_markup=shop_input_cancel_keyboard(is_fa))


@router.message(ShopStates.waiting_for_campaign_percent)
async def campaign_receive_percent(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    data = await state.get_data()
    direction = data.get("campaign_direction", "discount")
    text = (message.text or "").strip().rstrip("%")
    ceiling = 90 if direction == "discount" else 500
    if not text.isdigit() or not (1 <= int(text) <= ceiling):
        err = f"یه عدد صحیح بین ۱ تا {ceiling} وارد کن." if is_fa else f"Enter a whole number between 1 and {ceiling}."
        await message.answer(
            err,
            reply_markup=shop_input_cancel_keyboard(is_fa),
        )
        return
    await state.update_data(campaign_percent=int(text))
    await state.set_state(ShopStates.waiting_for_campaign_days)
    prompt = "چند روز اجرا بشه قبل از اینکه قیمت‌ها برگردن؟ (۱ تا ۹۰)" if is_fa else "For how many days should it run before prices revert? (1–90)"
    await message.answer(
        prompt,
        reply_markup=shop_input_cancel_keyboard(is_fa),
    )


@router.message(ShopStates.waiting_for_campaign_days, F.text.in_(SHOP_CAMPAIGN_APPLY_TEXTS))
async def campaign_apply(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    data = await state.get_data()
    bot_id = data.get("active_bot_id")
    direction = data.get("campaign_direction")
    percent = data.get("campaign_percent")
    days = data.get("campaign_days")
    await state.set_state(None)

    if not (direction and percent and days):
        text = "تنظیم کمپین منقضی شد — دوباره شروع کن." if is_fa else "Campaign setup expired — start again."
        await message.answer(text)
        await _send_menu(message, bot_id, is_fa)
        return

    campaign = await shop.start_price_campaign(bot_id, direction, percent, days)
    if campaign is None:
        text = "یه کمپین از قبل در حال اجراست — اول اونو تموم کن." if is_fa else "A campaign is already running — end it first."
        await message.answer(text)
    else:
        applied_text = "کمپین اعمال شد ✅" if is_fa else "Campaign applied ✅"
        await message.answer(applied_text)
        await message.answer(_campaign_status_text(campaign, is_fa))
    await _send_menu(message, bot_id, is_fa)


@router.message(ShopStates.waiting_for_campaign_days)
async def campaign_receive_days(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    data = await state.get_data()
    bot_id = data.get("active_bot_id")
    direction = data.get("campaign_direction", "discount")
    percent = data.get("campaign_percent")
    text = (message.text or "").strip()
    if not text.isdigit() or not (1 <= int(text) <= 90):
        err = "یه عدد صحیح بین ۱ تا ۹۰ روز وارد کن." if is_fa else "Enter a whole number of days between 1 and 90."
        await message.answer(
            err,
            reply_markup=shop_input_cancel_keyboard(is_fa),
        )
        return

    days = int(text)
    await state.update_data(campaign_days=days)
    n_products = len(await shop.get_products(bot_id))
    reverts_on = (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%d %H:%M")

    if is_fa:
        verb = "تخفیف" if direction == "discount" else "افزایش قیمت"
        text = (
            f"آماده: **{percent}٪ {verb}** روی همه‌ی قیمت‌ها ({n_products} محصول/پلن + همه‌ی "
            f"قیمت‌های رفع قفل تک‌آیتمی) برای **{days} روز**.\n"
            f"به‌صورت خودکار در {reverts_on} UTC برمی‌گرده.\n\n"
            "قیمت‌ها به نزدیک‌ترین ۱٬۰۰۰ تومان گرد می‌شن. اعمال بشه؟"
        )
    else:
        verb = "off" if direction == "discount" else "up"
        text = (
            f"Ready: **{percent}% {verb}** on every price ({n_products} product/plan(s) + all "
            f"single-item unlock prices) for **{days} day(s)**.\n"
            f"Auto-reverts on {reverts_on} UTC.\n\n"
            "Prices round to the nearest 1,000 Toman. Apply?"
        )
    await message.answer(text, reply_markup=shop_campaign_confirm_keyboard(is_fa))


@router.message(F.text.in_(_MENU_STATIC_TEXTS["orders"]))
async def recent_orders(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    data = await state.get_data()
    bot_id = data.get("active_bot_id")

    orders = await shop.list_recent_orders(bot_id)
    if not orders:
        text = "هنوز سفارشی وجود نداره." if is_fa else "No orders yet."
        await message.answer(text)
        return

    lines = ["سفارش‌های اخیر:\n" if is_fa else "Recent orders:\n"]
    for order in orders:
        product = await shop.get_product(order.product_id)
        product_name = product.name if product else "?"
        cart_note = " (سبد خرید)" if is_fa and order.checkout_id else (" (cart)" if order.checkout_id else "")
        lines.append(
            f"#{order.id} — {product_name} — {order.price:,} تومان — {order.status}{cart_note}"
        )
    text = "\n".join(lines)
    text += await help_text.tip_suffix("shop:orders", message.from_user)
    await message.answer(text)
