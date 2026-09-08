import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, KeyboardButton, Message, ReplyKeyboardMarkup
from sqlalchemy import select

from bot import commerce_mode, help_text, shop
from bot.content_import import SAMPLE_LANGUAGES, generate_sample_excel, parse_content_excel
from bot.content_nav import (
    folder_ids_among,
    get_all_items,
    get_children,
    get_item,
    get_item_by_code,
    reparent_item,
    upsert_item,
    would_cycle,
)
from bot.db.base import async_session_maker
from bot.db.models import BotPost, BotSubscriber, BuiltBot, ContentItem, Product, User
from bot.guide import owner_prefers_persian
from bot.keyboards import (
    CONTENT_ADD_BUTTON_TEXTS,
    CONTENT_ADD_POST_BUTTON_TEXTS,
    CONTENT_BACK_BUTTON_TEXTS,
    CONTENT_BROWSE_BUTTON_TEXTS,
    CONTENT_DELETE_BUTTON_TEXTS,
    CONTENT_EDIT_BUTTON_TEXTS,
    CONTENT_FOR_SALE_YES_TEXTS,
    CONTENT_GROUP_BUTTON_TEXTS,
    CONTENT_MENU_HEADING,
    CONTENT_NO_FREE_TEXTS,
    CONTENT_NO_TEXTS,
    CONTENT_PREMIUM_YES_TEXTS,
    CONTENT_SAMPLE_BUTTON_TEXTS,
    CONTENT_UPLOAD_BUTTON_TEXTS,
    CONTENT_VIEW_BUTTON_TEXTS,
    COMMERCE_MODE_SHOP_TEXTS,
    COMMERCE_MODE_SUBSCRIPTION_TEXTS,
    SKIP_BUTTON_TEXTS,
    commerce_mode_keyboard,
    content_category_picker_keyboard,
    content_delete_confirm_keyboard,
    content_for_sale_keyboard,
    content_group_target_keyboard,
    content_input_cancel_keyboard,
    content_item_detail_keyboard,
    content_items_keyboard,
    content_list_menu_keyboard,
    content_lookup_keyboard,
    content_premium_keyboard,
    content_product_type_keyboard,
    content_sample_lang_keyboard,
    content_skip_keyboard,
    post_engagement_keyboard,
    post_preview_keyboard,
    POST_PUBLISH_BUTTON_TEXTS,
    product_type_button_to_key,
    tool_button_texts,
)
from bot.runtime import sync_bot_commands
from bot.session import make_session
from bot.shop import TYPE_FIELDS, type_field_prompt
from bot.states import ContentListStates

logger = logging.getLogger(__name__)

router = Router(name="content_list")

# Steps asked, in order, when adding a content item manually. The "which
# category" step is a separate button-based step after these — see
# _send_step and the content:parent:* handler. Bilingual: prompt_en/prompt_fa
# picked per-owner by is_fa — this whole wizard is owner-only.
ADD_ITEM_FIELDS = [
    {"key": "title", "prompt_en": "Enter the item's title.", "prompt_fa": "عنوان آیتم رو وارد کن."},
    {"key": "body", "prompt_en": "Enter the item's body text.", "prompt_fa": "متن اصلی آیتم رو وارد کن."},
    {
        "key": "image_url",
        "prompt_en": "Enter an image URL (optional).",
        "prompt_fa": "آدرس تصویر رو وارد کن (اختیاری).",
        "optional": True,
    },
    {
        "key": "link_url",
        "prompt_en": "Enter a link URL (optional).",
        "prompt_fa": "آدرس لینک رو وارد کن (اختیاری).",
        "optional": True,
    },
    {
        "key": "code",
        "prompt_en": "Set a shortcut code for this item, e.g. 101 or buy (optional). Anyone who "
        "types this to your bot jumps straight to this item — handy for an Instagram post "
        "saying \"send CODE to our bot\". Must be unique within this bot.",
        "prompt_fa": "یه کد میان‌بر برای این آیتم تنظیم کن، مثلاً 101 یا buy (اختیاری). هر کسی این "
        "کد رو به رباتت بفرسته مستقیم به این آیتم می‌ره — برای پستی مثل «کد رو به ربات ما بفرست» "
        "تو اینستاگرام مفیده. باید توی این ربات یکتا باشه.",
        "optional": True,
    },
]


def _field_prompt(field: dict, is_fa: bool) -> str:
    return field["prompt_fa"] if is_fa else field["prompt_en"]


# Same fields as Add, minus "code" — editing never changes an item's code
# (or its parent — see the dedicated Group flow for that).
EDIT_ITEM_FIELDS = [f for f in ADD_ITEM_FIELDS if f["key"] != "code"]

PRODUCT_TYPE_BUTTON_TO_KEY = product_type_button_to_key()


async def _send_menu(message: Message, is_fa: bool) -> None:
    text = (
        "مدیریت آیتم‌های محتوای این ربات — استفاده‌شده توسط بلوک «لیست محتوا» تو سازنده‌ی بصری."
        if is_fa
        else "Manage this bot's content items — used by the \"Content List\" block "
        "in the visual builder."
    )
    await message.answer(text, reply_markup=content_list_menu_keyboard(is_fa))


async def _send_step(message: Message, state: FSMContext, index: int, is_fa: bool) -> None:
    if index >= len(ADD_ITEM_FIELDS):
        await state.update_data(wizard_index=None, wizard_phase="content_done")
        data = await state.get_data()
        bot_id = data.get("active_bot_id")
        mode = await commerce_mode.get_commerce_mode(bot_id)
        if mode == commerce_mode.MODE_SUBSCRIPTION:
            # A subscription-mode bot never sells individual items — every
            # item is either free-preview or premium-gated, never "for
            # sale" (see bot/commerce_mode.py).
            await state.update_data(is_product=False)
            await _maybe_send_premium_step(message, state, _send_category_step, is_fa)
            return
        text = (
            "این آیتم برای فروشه؟ (خریدارها روش قیمت و دکمه‌ی خرید می‌بینن.)"
            if is_fa
            else "Is this item for sale? (Buyers will see a price and Buy button on it.)"
        )
        await message.answer(text, reply_markup=content_for_sale_keyboard(is_fa))
        return

    await state.update_data(wizard_index=index, wizard_phase="content")
    field = ADD_ITEM_FIELDS[index]
    keyboard = content_skip_keyboard(is_fa) if field.get("optional") else content_input_cancel_keyboard(is_fa)
    await message.answer(_field_prompt(field, is_fa), reply_markup=keyboard)


async def _send_category_step(message: Message, state: FSMContext, is_fa: bool) -> None:
    data = await state.get_data()
    bot_id = data.get("active_bot_id")
    items = await get_all_items(bot_id)
    text = "این زیر کدوم دسته باشه؟ (تودرتو کردن اختیاریه.)" if is_fa else "Which category should this go under? (Nesting is optional.)"
    await message.answer(text, reply_markup=content_category_picker_keyboard(items, is_fa))


async def _send_premium_step(message: Message, state: FSMContext, is_fa: bool) -> None:
    """Asked independently of "is this for sale" — a content item can be
    premium-gated (bot/premium_content.py), individually purchasable,
    both, or neither. Subscription-mode bots always reach this; Shop-mode
    bots never do — see _maybe_send_premium_step."""
    text = (
        "🔒 این آیتم پرمیومه؟ (برای دیدنش اشتراک فعال لازمه، بعد از تموم شدن سهمیه‌ی پیش‌نمایش "
        "رایگان — به «🎁 محدودیت پیش‌نمایش رایگان» تو ابزار فروشگاه نگاه کن.)"
        if is_fa
        else "🔒 Is this a premium item? (Requires an active subscription to view, after any free "
        "preview quota is used — see the Shop tool's \"🎁 Free Preview Limit\".)"
    )
    await message.answer(text, reply_markup=content_premium_keyboard(is_fa))


async def _maybe_send_premium_step(message: Message, state: FSMContext, next_step, is_fa: bool) -> None:
    """Only actually asks in Subscription mode — a Shop-mode bot never
    gates content behind a subscription, so it saves is_premium=False
    directly and moves straight to `next_step` (bot/commerce_mode.py)."""
    data = await state.get_data()
    bot_id = data.get("active_bot_id")
    mode = await commerce_mode.get_commerce_mode(bot_id)
    if mode == commerce_mode.MODE_SUBSCRIPTION:
        await _send_premium_step(message, state, is_fa)
        return
    await state.update_data(is_premium=False)
    await next_step(message, state, is_fa)


async def _send_type_field_step(message: Message, state: FSMContext, index: int, is_fa: bool) -> None:
    data = await state.get_data()
    fields = TYPE_FIELDS.get(data.get("product_type"), [])

    if index >= len(fields):
        await _maybe_send_premium_step(message, state, _send_category_step, is_fa)
        return

    await state.update_data(wizard_index=index, wizard_phase="type_fields")
    field = fields[index]
    keyboard = content_skip_keyboard(is_fa) if field.get("optional") else content_input_cancel_keyboard(is_fa)
    await message.answer(type_field_prompt(field, is_fa), reply_markup=keyboard)


async def _send_children(
    message: Message, bot_id: str, parent_id: int | None, back_target: str, is_fa: bool
) -> bool:
    items = await get_children(bot_id, parent_id)
    if not items:
        return False
    folder_ids = await folder_ids_among(bot_id, [i.id for i in items])
    await message.answer(
        CONTENT_MENU_HEADING,
        reply_markup=content_items_keyboard(items, back_target, folder_ids, is_fa),
    )
    return True


async def _send_edit_step(message: Message, state: FSMContext, index: int, is_fa: bool) -> None:
    if index >= len(EDIT_ITEM_FIELDS):
        await _maybe_send_premium_step(message, state, _save_edit, is_fa)
        return

    data = await state.get_data()
    payload = data.get("wizard_payload", {})
    field = EDIT_ITEM_FIELDS[index]
    current = payload.get(field["key"]) or ("(هیچی)" if is_fa else "(none)")

    await state.update_data(wizard_index=index)
    keyboard = content_skip_keyboard(is_fa) if field.get("optional") else content_input_cancel_keyboard(is_fa)
    label = "مقدار فعلی" if is_fa else "Current value"
    await message.answer(f'{_field_prompt(field, is_fa)}\n\n{label}: {current}', reply_markup=keyboard)


async def _save_edit(message: Message, state: FSMContext, is_fa: bool) -> None:
    data = await state.get_data()
    payload = data.get("wizard_payload", {})
    item_id = data.get("edit_item_id")
    bot_id = data.get("active_bot_id")

    payload["is_premium"] = bool(data.get("is_premium"))
    item = await upsert_item(bot_id, payload, item_id=item_id)

    await state.set_state(None)
    if item is None:
        text = "این آیتم دیگه در دسترس نیست." if is_fa else "This item is no longer available."
        await message.answer(text)
        await _send_menu(message, is_fa)
        return

    await sync_bot_commands(bot_id)
    text = "آیتم به‌روزرسانی شد ✅" if is_fa else "Item updated ✅"
    await message.answer(text)
    await _send_menu(message, is_fa)


async def _act_on_resolved_item(
    message: Message, state: FSMContext, item: ContentItem, mode: str, is_fa: bool
) -> None:
    """Once Edit/Delete/Group has resolved a target item (by code or by
    browsing), continues into that action's next step."""
    await state.set_state(None)
    await state.update_data(action_mode=None)

    if mode == "delete":
        text = f'«{item.title}» حذف بشه؟ این کار قابل بازگشت نیست.' if is_fa else f'Delete "{item.title}"? This cannot be undone.'
        await message.answer(
            text,
            reply_markup=content_delete_confirm_keyboard(item.id, is_fa),
        )
        return

    if mode == "group":
        data = await state.get_data()
        bot_id = data.get("active_bot_id")
        items = await get_all_items(bot_id)
        text = f'یه دسته‌ی جدید برای «{item.title}» انتخاب کن:' if is_fa else f'Choose a new category for "{item.title}":'
        await message.answer(text, reply_markup=content_group_target_keyboard(items, item.id, is_fa))
        return

    if mode == "edit":
        await state.update_data(
            edit_item_id=item.id,
            is_premium=item.is_premium,
            wizard_payload={
                "title": item.title,
                "body": item.body,
                "image_url": item.image_url,
                "link_url": item.link_url,
            },
        )
        await state.set_state(ContentListStates.edit_field_wizard)
        await _send_edit_step(message, state, 0, is_fa)


@router.message(F.text.in_(tool_button_texts("content_list")))
async def open_content_list(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    data = await state.get_data()
    bot_id = data.get("active_bot_id")
    if bot_id is None:
        text = 'اول از «ربات‌های من» یه ربات انتخاب کن.' if is_fa else 'First select a bot from "My Bots".'
        await message.answer(text)
        return

    await state.update_data(action_mode=None)
    await state.set_state(None)

    mode = await commerce_mode.get_commerce_mode(bot_id)
    if mode is None:
        await state.update_data(commerce_mode_source="content_tool")
        text = (
            "قبل از مدیریت این بخش، انتخاب کن این ربات چطور کسب‌وکار می‌کنه — بعداً قابل تغییر "
            "نیست، پس با دقت انتخاب کن:"
            if is_fa
            else "Before managing this, choose how this bot does business — this can't be "
            "changed later, so pick carefully:"
        )
        await message.answer(text, reply_markup=commerce_mode_keyboard(is_fa))
        return

    tip = await help_text.tip_suffix("tool:content_list", message.from_user)
    if tip:
        await message.answer(tip.strip())
    await _send_menu(message, is_fa)


@router.message(F.text.in_(COMMERCE_MODE_SHOP_TEXTS | COMMERCE_MODE_SUBSCRIPTION_TEXTS))
async def choose_commerce_mode(message: Message, state: FSMContext) -> None:
    """Shared by both Shop's and Content List's "pick a business model" step
    (bot/handlers/tools/shop.py:open_shop sets the same commerce_mode_source
    flag before showing this keyboard) — a reply button carries no hidden
    payload, so which tool asked travels via FSM data instead of two
    separate callback_data suffixes like before."""
    is_fa = await owner_prefers_persian(message.from_user)
    mode = "shop" if message.text in COMMERCE_MODE_SHOP_TEXTS else "subscription"
    data = await state.get_data()
    bot_id = data.get("active_bot_id")
    if bot_id is None:
        text = 'اول از «ربات‌های من» یه ربات انتخاب کن.' if is_fa else 'First select a bot from "My Bots".'
        await message.answer(text)
        return

    await commerce_mode.set_commerce_mode(bot_id, mode)
    tip_key = "mode:shop:" if mode == "shop" else "mode:subscription:"
    mode_set_text = "حالت تنظیم شد ✅" if is_fa else "Mode set ✅"
    text = mode_set_text + await help_text.tip_suffix(tip_key, message.from_user)
    await message.answer(text)

    if data.get("commerce_mode_source") == "shop_tool":
        from bot.handlers.tools.shop import _send_menu as _send_shop_menu

        await _send_shop_menu(message, bot_id, is_fa)
    else:
        await _send_menu(message, is_fa)


@router.callback_query(F.data == "content:menu")
async def back_to_menu(callback: CallbackQuery, state: FSMContext) -> None:
    """Still needed as a callback handler: content_delete_confirm_keyboard
    and content_group_target_keyboard (dynamic, still inline) route their own
    Cancel here."""
    is_fa = await owner_prefers_persian(callback.from_user)
    await state.update_data(action_mode=None)
    await state.set_state(None)
    await _send_menu(callback.message, is_fa)
    await callback.answer()


@router.message(F.text.in_(CONTENT_BACK_BUTTON_TEXTS))
async def back_to_menu_text(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    await state.update_data(action_mode=None)
    await state.set_state(None)
    await _send_menu(message, is_fa)


@router.message(F.text.in_(CONTENT_VIEW_BUTTON_TEXTS))
async def list_items(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    data = await state.get_data()
    bot_id = data.get("active_bot_id")

    await state.update_data(action_mode=None)
    sent = await _send_children(message, bot_id, None, "menu", is_fa)
    if not sent:
        text = "هنوز آیتم محتوایی وجود نداره." if is_fa else "No content items yet."
        await message.answer(text)


@router.callback_query(F.data.startswith("content:list_at:"))
async def list_at(callback: CallbackQuery, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(callback.from_user)
    target = callback.data.split(":")[-1]
    data = await state.get_data()
    bot_id = data.get("active_bot_id")

    if target == "top":
        parent_id, back_target = None, "menu"
    else:
        parent_id = int(target)
        folder = await get_item(parent_id)
        if folder is None:
            text = "پیدا نشد." if is_fa else "Not found."
            await callback.answer(text, show_alert=True)
            return
        back_target = "top" if folder.parent_id is None else str(folder.parent_id)

    await callback.answer()
    sent = await _send_children(callback.message, bot_id, parent_id, back_target, is_fa)
    if not sent:
        text = "اینجا آیتمی نیست." if is_fa else "No items here."
        await callback.message.answer(text)


@router.callback_query(F.data.startswith("content:select:"))
async def select_item(callback: CallbackQuery, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(callback.from_user)
    item_id = int(callback.data.split(":")[-1])
    item = await get_item(item_id)

    data = await state.get_data()
    bot_id = data.get("active_bot_id")

    if item is None or str(item.bot_id) != str(bot_id):
        text = "آیتم پیدا نشد." if is_fa else "Item not found."
        await callback.answer(text, show_alert=True)
        return

    back_target = "top" if item.parent_id is None else str(item.parent_id)

    drilled = await _send_children(callback.message, bot_id, item.id, back_target, is_fa)
    await callback.answer()
    if drilled:
        return

    mode = data.get("action_mode")
    if mode:
        # Reached via "📋 Browse instead" from Edit/Delete/Group, not the
        # plain "View" menu option — act on this leaf instead of showing it.
        await _act_on_resolved_item(callback.message, state, item, mode, is_fa)
        return

    lines = [f"📌 {item.title}", "", item.body]
    if item.product_id:
        product = await shop.get_product(item.product_id)
        if product:
            price_line = f"\n💰 برای فروش: {product.price:,} تومان" if is_fa else f"\n💰 For sale: {product.price:,} Toman"
            lines.append(price_line)
    if item.image_url:
        lines.append(f"\n🖼 {item.image_url}")
    if item.link_url:
        lines.append(f"🔗 {item.link_url}")

    await callback.message.answer(
        "\n".join(lines), reply_markup=content_item_detail_keyboard(item.id, back_target, is_fa)
    )


@router.callback_query(F.data.startswith("content:delete:"))
async def delete_item(callback: CallbackQuery, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(callback.from_user)
    item_id = int(callback.data.split(":")[-1])
    data = await state.get_data()
    bot_id = data.get("active_bot_id")

    if await get_children(bot_id, item_id):
        text = "این آیتم زیرمجموعه داره — اول اون‌ها رو حذف کن." if is_fa else "This has sub-items — delete those first."
        await callback.answer(text, show_alert=True)
        return

    async with async_session_maker() as session:
        result = await session.execute(select(ContentItem).where(ContentItem.id == item_id))
        item = result.scalar_one_or_none()
        if item is not None and str(item.bot_id) == str(bot_id):
            await session.delete(item)
            await session.commit()

    await sync_bot_commands(bot_id)
    text = "آیتم حذف شد ✅" if is_fa else "Item deleted ✅"
    await callback.message.answer(text)
    await _send_menu(callback.message, is_fa)
    await callback.answer()


@router.message(F.text.in_(CONTENT_ADD_BUTTON_TEXTS))
async def new_item(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    await state.update_data(wizard_payload={})
    await state.set_state(ContentListStates.add_item_wizard)
    tip = await help_text.tip_suffix("content:new", message.from_user)
    if tip:
        await message.answer(tip.strip())
    await _send_step(message, state, 0, is_fa)


@router.message(ContentListStates.add_item_wizard, F.text.in_(SKIP_BUTTON_TEXTS))
async def wizard_skip(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    data = await state.get_data()
    phase = data.get("wizard_phase", "content")
    index = data.get("wizard_index", 0)
    fields = ADD_ITEM_FIELDS if phase == "content" else TYPE_FIELDS.get(data.get("product_type"), [])
    field = fields[index]

    if not field.get("optional"):
        text = "این فیلد رو نمی‌شه رد کرد." if is_fa else "This field can't be skipped."
        await message.answer(text, reply_markup=content_skip_keyboard(is_fa))
        return

    payload = data.get("wizard_payload", {})
    payload[field["key"]] = None
    await state.update_data(wizard_payload=payload)

    if phase == "content":
        await _send_step(message, state, index + 1, is_fa)
    else:
        await _send_type_field_step(message, state, index + 1, is_fa)


@router.message(ContentListStates.add_item_wizard, F.text.in_(CONTENT_FOR_SALE_YES_TEXTS))
async def for_sale_yes(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    await state.update_data(is_product=True, wizard_phase="price")
    text = "قیمت رو به تومان وارد کن (فقط عدد)." if is_fa else "Enter the price in Toman (numbers only)."
    text += await help_text.tip_suffix("content:for_sale:yes", message.from_user)
    await message.answer(text, reply_markup=content_input_cancel_keyboard(is_fa))


@router.message(ContentListStates.add_item_wizard, F.text.in_(CONTENT_NO_TEXTS))
async def for_sale_no(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    await state.update_data(is_product=False)
    tip = await help_text.tip_suffix("content:for_sale:no", message.from_user)
    if tip:
        await message.answer(tip.strip())
    await _maybe_send_premium_step(message, state, _send_category_step, is_fa)


@router.message(ContentListStates.add_item_wizard, F.text.in_(CONTENT_PREMIUM_YES_TEXTS))
async def premium_yes_add(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    await state.update_data(is_premium=True)
    tip = await help_text.tip_suffix("content:premium:yes", message.from_user)
    if tip:
        await message.answer(tip.strip())
    await _send_category_step(message, state, is_fa)


@router.message(ContentListStates.add_item_wizard, F.text.in_(CONTENT_NO_FREE_TEXTS))
async def premium_no_add(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    await state.update_data(is_premium=False)
    tip = await help_text.tip_suffix("content:premium:no", message.from_user)
    if tip:
        await message.answer(tip.strip())
    await _send_category_step(message, state, is_fa)


@router.message(ContentListStates.add_item_wizard, F.text.in_(PRODUCT_TYPE_BUTTON_TO_KEY))
async def choose_product_type(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    await state.update_data(product_type=PRODUCT_TYPE_BUTTON_TO_KEY[message.text])
    tip = await help_text.tip_suffix("content:ptype:", message.from_user)
    if tip:
        await message.answer(tip.strip())
    await _send_type_field_step(message, state, 0, is_fa)


@router.message(ContentListStates.add_item_wizard)
async def wizard_receive(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    data = await state.get_data()
    phase = data.get("wizard_phase", "content")
    payload = data.get("wizard_payload", {})
    text = (message.text or "").strip()

    if phase == "price":
        if not text.isdigit():
            err = "لطفاً فقط عدد وارد کن (بدون نماد ارز)." if is_fa else "Please enter numbers only (no currency symbols)."
            await message.answer(
                err,
                reply_markup=content_input_cancel_keyboard(is_fa),
            )
            return
        payload["price"] = text
        await state.update_data(wizard_payload=payload, wizard_phase="type_select")
        prompt = "این محصول چه نوعیه؟" if is_fa else "What type of product is this?"
        await message.answer(
            prompt, reply_markup=content_product_type_keyboard(is_fa)
        )
        return

    if phase == "type_fields":
        index = data.get("wizard_index", 0)
        field = TYPE_FIELDS.get(data.get("product_type"), [])[index]
        if not text and not field.get("optional"):
            err = "این فیلد نمی‌تونه خالی باشه. دوباره امتحان کن." if is_fa else "This field can't be empty. Please try again."
            await message.answer(
                err,
                reply_markup=content_input_cancel_keyboard(is_fa),
            )
            return
        payload[field["key"]] = text or None
        await state.update_data(wizard_payload=payload)
        await _send_type_field_step(message, state, index + 1, is_fa)
        return

    # phase == "content"
    index = data.get("wizard_index", 0)
    field = ADD_ITEM_FIELDS[index]
    if not text and not field.get("optional"):
        err = "این فیلد نمی‌تونه خالی باشه. دوباره امتحان کن." if is_fa else "This field can't be empty. Please try again."
        await message.answer(
            err,
            reply_markup=content_input_cancel_keyboard(is_fa),
        )
        return

    if field["key"] == "code" and text:
        bot_id = data.get("active_bot_id")
        existing = await get_item_by_code(bot_id, text)
        if existing is not None:
            err = (
                f'کد «{text}» قبلاً برای آیتم دیگه‌ای تو این ربات استفاده شده. '
                "یه کد دیگه انتخاب کن، یا رد کن."
                if is_fa
                else f'The code "{text}" is already used by another item in this bot. '
                "Choose a different one, or skip."
            )
            await message.answer(
                err,
                reply_markup=content_skip_keyboard(is_fa),
            )
            return

    payload[field["key"]] = text or None
    await state.update_data(wizard_payload=payload)
    await _send_step(message, state, index + 1, is_fa)


@router.callback_query(F.data.startswith("content:parent:"), ContentListStates.add_item_wizard)
async def wizard_save_with_parent(callback: CallbackQuery, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(callback.from_user)
    target = callback.data.split(":")[-1]
    parent_id = None if target == "top" else int(target)

    data = await state.get_data()
    payload = data.get("wizard_payload", {})
    bot_id = data.get("active_bot_id")

    async with async_session_maker() as session:
        product_id = None
        if data.get("is_product"):
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
            product = Product(
                bot_id=bot_id,
                name=payload.get("title") or "",
                description=payload.get("body") or "",
                price=price,
                image_url=payload.get("image_url"),
                product_type=data.get("product_type", "digital"),
                delivery_text=payload.get("delivery_text"),
                delivery_file_url=payload.get("delivery_file_url"),
                access_level_name=payload.get("access_level_name"),
                subscription_days=subscription_days,
            )
            session.add(product)
            await session.flush()  # assign product.id before linking the content item
            product_id = product.id

        session.add(
            ContentItem(
                bot_id=bot_id,
                title=payload.get("title") or "",
                body=payload.get("body") or "",
                image_url=payload.get("image_url"),
                link_url=payload.get("link_url"),
                parent_id=parent_id,
                product_id=product_id,
                code=payload.get("code"),
                is_premium=bool(data.get("is_premium")),
            )
        )
        await session.commit()

    await sync_bot_commands(bot_id)
    await state.set_state(None)
    text = "آیتم اضافه شد ✅" if is_fa else "Item added ✅"
    await callback.message.answer(text)
    await _send_menu(callback.message, is_fa)
    await callback.answer()


POST_MEDIA_PROMPT_EN = "Send a photo or video for your post."
POST_MEDIA_PROMPT_FA = "یه عکس یا ویدیو برای پستت بفرست."
POST_CAPTION_PROMPT_EN = "Now send the caption for this post — the text your subscribers will see."
POST_CAPTION_PROMPT_FA = "حالا کپشن این پست رو بفرست — متنی که مشترکینت می‌بینن."


def _post_media_prompt(is_fa: bool) -> str:
    return POST_MEDIA_PROMPT_FA if is_fa else POST_MEDIA_PROMPT_EN


def _post_caption_prompt(is_fa: bool) -> str:
    return POST_CAPTION_PROMPT_FA if is_fa else POST_CAPTION_PROMPT_EN


@router.message(F.text.in_(CONTENT_ADD_POST_BUTTON_TEXTS))
async def start_add_post(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    await state.update_data(post_phase="media")
    await state.set_state(ContentListStates.add_post_wizard)
    if is_fa:
        text = (
            "📢 افزودن پست — یه عکس/ویدیو + کپشن که مستقیم برای مشترکین رباتت ارسال می‌شه، "
            "برای وقتی که ترجیح می‌دی به‌جای یه کانال جدا، از طریق ربات خبر بدی.\n\n"
            + _post_media_prompt(is_fa)
        )
    else:
        text = (
            "📢 Add Post — a photo/video + caption pushed straight to your bot's subscribers, "
            "for when you'd rather post updates through the bot than run a separate channel.\n\n"
            + _post_media_prompt(is_fa)
        )
    text += await help_text.tip_suffix("content:add_post", message.from_user)
    await message.answer(text, reply_markup=content_input_cancel_keyboard(is_fa))


@router.message(ContentListStates.add_post_wizard, F.text.in_(POST_PUBLISH_BUTTON_TEXTS))
async def publish_post(message: Message, state: FSMContext, bot: Bot) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    data = await state.get_data()
    bot_id = data.get("active_bot_id")
    media_type = data.get("post_media_type")
    file_id = data.get("post_media_file_id")
    caption = data.get("post_caption")

    if bot_id is None or not file_id or not caption:
        text = (
            'یه چیزی اشتباه شد — با «📢 افزودن پست» دوباره شروع کن.'
            if is_fa
            else 'Something went wrong — start over with "📢 Add Post".'
        )
        await message.answer(text)
        return

    publishing_text = "در حال انتشار…" if is_fa else "Publishing…"
    await message.answer(publishing_text, reply_markup=content_list_menu_keyboard(is_fa))

    async with async_session_maker() as session:
        result = await session.execute(select(BuiltBot).where(BuiltBot.id == bot_id))
        built_bot = result.scalar_one_or_none()
    if built_bot is None:
        text = "این ربات دیگه وجود نداره." if is_fa else "This bot no longer exists."
        await message.answer(text)
        await state.set_state(None)
        return

    # The uploaded file_id is only valid on THIS (builder) bot's session —
    # download its bytes here so they can be re-uploaded through the owner's
    # own built bot below (Telegram file_ids never carry across bots).
    tg_file = await bot.get_file(file_id)
    file_bytes = await bot.download_file(tg_file.file_path)
    input_file = BufferedInputFile(
        file_bytes.read(), filename=("post.jpg" if media_type == "photo" else "post.mp4")
    )

    post = BotPost(bot_id=bot_id, media_type=media_type, media_file_id="", caption=caption)
    async with async_session_maker() as session:
        session.add(post)
        await session.commit()
        await session.refresh(post)

    async with async_session_maker() as session:
        result = await session.execute(
            select(BotSubscriber).where(BotSubscriber.bot_id == bot_id)
        )
        subscribers = list(result.scalars())
        owner_result = await session.execute(
            select(User.telegram_id).join(BuiltBot, BuiltBot.owner_id == User.id).where(BuiltBot.id == bot_id)
        )
        owner_telegram_id = owner_result.scalar_one_or_none()

    markup = post_engagement_keyboard(post.id, like_count=0, comment_count=0)
    temp_bot = Bot(token=built_bot.token, session=make_session())
    delivered_file_id: str | None = None
    sent = 0

    async def _send_via_temp_bot(chat_id: int, media):
        if media_type == "photo":
            return await temp_bot.send_photo(chat_id, photo=media, caption=caption, reply_markup=markup)
        return await temp_bot.send_video(chat_id, video=media, caption=caption, reply_markup=markup)

    try:
        # First send goes to the owner themself — doubles as a confirmation
        # copy and is where we mint a file_id valid for the owner's own bot
        # (reused for every subscriber below instead of re-uploading each time).
        if owner_telegram_id is not None:
            try:
                owner_msg = await _send_via_temp_bot(owner_telegram_id, input_file)
                delivered_file_id = (
                    owner_msg.photo[-1].file_id if media_type == "photo" else owner_msg.video.file_id
                )
            except Exception:
                logger.warning("Failed to deliver post %s preview to owner", post.id)

        for subscriber in subscribers:
            if subscriber.telegram_id == owner_telegram_id:
                continue  # already got the preview copy above
            media = delivered_file_id if delivered_file_id else input_file
            try:
                msg = await _send_via_temp_bot(subscriber.telegram_id, media)
                if delivered_file_id is None:
                    delivered_file_id = (
                        msg.photo[-1].file_id if media_type == "photo" else msg.video.file_id
                    )
                sent += 1
            except Exception:
                logger.warning("Failed to deliver post %s to %s", post.id, subscriber.telegram_id)
    finally:
        await temp_bot.session.close()

    if delivered_file_id:
        async with async_session_maker() as session:
            result = await session.execute(select(BotPost).where(BotPost.id == post.id))
            row = result.scalar_one()
            row.media_file_id = delivered_file_id
            await session.commit()

    await state.set_state(None)
    text = f"✅ منتشر شد — برای {sent} مشترک ارسال شد." if is_fa else f"✅ Published — delivered to {sent} subscriber(s)."
    await message.answer(text)
    await _send_menu(message, is_fa)


@router.message(ContentListStates.add_post_wizard)
async def post_wizard_receive(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    data = await state.get_data()
    phase = data.get("post_phase")

    if phase == "media":
        if message.photo:
            media_type, file_id = "photo", message.photo[-1].file_id
        elif message.video:
            media_type, file_id = "video", message.video.file_id
        else:
            not_media = "این عکس یا ویدیو نیست. " if is_fa else "That's not a photo or video. "
            await message.answer(
                not_media + _post_media_prompt(is_fa),
                reply_markup=content_input_cancel_keyboard(is_fa),
            )
            return

        await state.update_data(post_media_type=media_type, post_media_file_id=file_id)

        caption = (message.caption or "").strip()
        if caption:
            await state.update_data(post_caption=caption)
            await _send_post_preview(message, state, is_fa)
            return

        await state.update_data(post_phase="caption")
        await message.answer(_post_caption_prompt(is_fa), reply_markup=content_input_cancel_keyboard(is_fa))
        return

    if phase == "caption":
        caption = (message.text or "").strip()
        if not caption:
            empty = "کپشن نمی‌تونه خالی باشه. " if is_fa else "The caption can't be empty. "
            await message.answer(
                empty + _post_caption_prompt(is_fa),
                reply_markup=content_input_cancel_keyboard(is_fa),
            )
            return
        await state.update_data(post_caption=caption)
        await _send_post_preview(message, state, is_fa)
        return


async def _send_post_preview(message: Message, state: FSMContext, is_fa: bool) -> None:
    data = await state.get_data()
    media_type = data["post_media_type"]
    file_id = data["post_media_file_id"]
    caption = data["post_caption"]

    keyboard = post_preview_keyboard(is_fa)
    if media_type == "photo":
        await message.answer_photo(file_id, caption=caption, reply_markup=keyboard)
    else:
        await message.answer_video(file_id, caption=caption, reply_markup=keyboard)


@router.message(F.text.in_(CONTENT_EDIT_BUTTON_TEXTS))
async def start_edit(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    await state.update_data(action_mode="edit")
    await state.set_state(ContentListStates.lookup_wizard)
    text = "کد آیتمی که می‌خوای ویرایش کنی رو بفرست، یا روی مرور بزن." if is_fa else "Send the code of the item to edit, or tap Browse."
    text += await help_text.tip_suffix("content:edit", message.from_user)
    await message.answer(text, reply_markup=content_lookup_keyboard(is_fa))


@router.message(F.text.in_(CONTENT_DELETE_BUTTON_TEXTS))
async def start_delete(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    await state.update_data(action_mode="delete")
    await state.set_state(ContentListStates.lookup_wizard)
    text = "کد آیتمی که می‌خوای حذف کنی رو بفرست، یا روی مرور بزن." if is_fa else "Send the code of the item to delete, or tap Browse."
    text += await help_text.tip_suffix("content:delete_start", message.from_user)
    await message.answer(text, reply_markup=content_lookup_keyboard(is_fa))


@router.message(F.text.in_(CONTENT_GROUP_BUTTON_TEXTS))
async def start_group(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    await state.update_data(action_mode="group")
    await state.set_state(ContentListStates.lookup_wizard)
    text = (
        "کد آیتمی که می‌خوای به دسته‌ی دیگه‌ای منتقل کنی رو بفرست، یا روی مرور بزن."
        if is_fa
        else "Send the code of the item to move to a different category, or tap Browse."
    )
    text += await help_text.tip_suffix("content:group_start", message.from_user)
    await message.answer(text, reply_markup=content_lookup_keyboard(is_fa))


@router.message(ContentListStates.lookup_wizard, F.text.in_(CONTENT_BROWSE_BUTTON_TEXTS))
async def lookup_browse(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    data = await state.get_data()
    bot_id = data.get("active_bot_id")

    sent = await _send_children(message, bot_id, None, "menu", is_fa)
    if not sent:
        text = "هنوز آیتم محتوایی وجود نداره." if is_fa else "No content items yet."
        await message.answer(text)


@router.message(ContentListStates.lookup_wizard)
async def lookup_receive(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    data = await state.get_data()
    bot_id = data.get("active_bot_id")
    mode = data.get("action_mode")
    code = (message.text or "").strip()

    item = await get_item_by_code(bot_id, code)
    if item is None:
        text = (
            f'آیتمی با کد «{code}» پیدا نشد. دوباره امتحان کن، یا روی مرور بزن.'
            if is_fa
            else f'No item found with code "{code}". Try again, or tap Browse.'
        )
        await message.answer(
            text,
            reply_markup=content_lookup_keyboard(is_fa),
        )
        return

    await _act_on_resolved_item(message, state, item, mode, is_fa)


@router.message(ContentListStates.edit_field_wizard, F.text.in_(SKIP_BUTTON_TEXTS))
async def edit_wizard_skip(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    data = await state.get_data()
    index = data.get("wizard_index", 0)
    field = EDIT_ITEM_FIELDS[index]

    if not field.get("optional"):
        text = "این فیلد رو نمی‌شه رد کرد." if is_fa else "This field can't be skipped."
        await message.answer(text, reply_markup=content_skip_keyboard(is_fa))
        return

    payload = data.get("wizard_payload", {})
    payload[field["key"]] = None
    await state.update_data(wizard_payload=payload)
    await _send_edit_step(message, state, index + 1, is_fa)


@router.message(ContentListStates.edit_field_wizard, F.text.in_(CONTENT_PREMIUM_YES_TEXTS))
async def premium_yes_edit(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    await state.update_data(is_premium=True)
    await _save_edit(message, state, is_fa)


@router.message(ContentListStates.edit_field_wizard, F.text.in_(CONTENT_NO_FREE_TEXTS))
async def premium_no_edit(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    await state.update_data(is_premium=False)
    await _save_edit(message, state, is_fa)


@router.message(ContentListStates.edit_field_wizard)
async def edit_wizard_receive(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    data = await state.get_data()
    index = data.get("wizard_index", 0)
    field = EDIT_ITEM_FIELDS[index]
    payload = data.get("wizard_payload", {})
    text = (message.text or "").strip()

    if not text and not field.get("optional"):
        err = "این فیلد نمی‌تونه خالی باشه. دوباره امتحان کن." if is_fa else "This field can't be empty. Please try again."
        await message.answer(
            err,
            reply_markup=content_input_cancel_keyboard(is_fa),
        )
        return

    payload[field["key"]] = text or None
    await state.update_data(wizard_payload=payload)
    await _send_edit_step(message, state, index + 1, is_fa)


@router.callback_query(F.data.startswith("content:groupto:"))
async def group_to(callback: CallbackQuery, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(callback.from_user)
    _, _, item_id_str, target = callback.data.split(":")
    item_id = int(item_id_str)
    new_parent_id = None if target == "top" else int(target)

    data = await state.get_data()
    bot_id = data.get("active_bot_id")

    ok = await reparent_item(bot_id, item_id, new_parent_id)
    await callback.answer()

    if not ok:
        text = (
            "نشد این آیتم رو اونجا منتقل کرد — ممکنه یه حلقه بسازه، یا دیگه متعلق به این ربات نباشه."
            if is_fa
            else "Couldn't move this item there — it may create a loop, or no longer belong to this bot."
        )
        await callback.message.answer(text)
    else:
        await sync_bot_commands(bot_id)
        text = "آیتم منتقل شد ✅" if is_fa else "Item moved ✅"
        await callback.message.answer(text)

    await _send_menu(callback.message, is_fa)


@router.message(F.text.in_(CONTENT_SAMPLE_BUTTON_TEXTS))
async def download_sample(message: Message) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    text = (
        "زبان هدرهای ستون نمونه رو انتخاب کن. می‌تونی کاتالوگ .xlsx یا .csv *خودت* رو هم آپلود "
        "کنی — هدرها به هر کدوم از این زبان‌ها شناسایی می‌شن، و می‌تونه بالای ردیف هدر یه بلوک "
        "عنوان هم باشه."
        if is_fa
        else "Pick the language for the sample's column headers. You can also upload your "
        "*own* .xlsx or .csv catalogue — headers in any of these languages are recognized, "
        "and the header row can have a title block above it."
    )
    text += await help_text.tip_suffix("content:sample", message.from_user)
    await message.answer(text, reply_markup=content_sample_lang_keyboard(SAMPLE_LANGUAGES, is_fa))


_SAMPLE_LABEL_TO_CODE = {label: code for code, label in SAMPLE_LANGUAGES}


@router.message(F.text.in_(_SAMPLE_LABEL_TO_CODE))
async def download_sample_lang(message: Message) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    lang = _SAMPLE_LABEL_TO_CODE[message.text]
    data = generate_sample_excel(lang)
    file = BufferedInputFile(data, filename=f"content_template_{lang}.xlsx")
    caption = (
        'اینو پر کن و با «📤 آپلود اکسل» دوباره آپلودش کن.\n\n'
        '«دسته» اختیاریه — عنوان دقیق یه ردیف دیگه رو بذار تا زیرش قرار بگیره. «کد» اختیاریه — '
        'آپلود دوباره‌ی فایل با همون کد، اون آیتم رو به‌روزرسانی می‌کنه به‌جای اینکه تکرارش کنه. '
        '«اقدام» = حذف، آیتمی که با اون کد مطابقت داره رو حذف می‌کنه.'
        if is_fa
        else "Fill this in and upload it back with \"📤 Upload Excel\".\n\n"
        "\"Category\" is optional — put another row's exact Title there to nest under it. "
        "\"Code\" is optional — re-uploading a file with the same Code updates that item "
        "instead of duplicating it. \"Action\" = Delete removes the item matching that Code."
    )
    caption += await help_text.tip_suffix("content:sample:", message.from_user)
    await message.answer_document(file, caption=caption, reply_markup=content_list_menu_keyboard(is_fa))


@router.message(F.text.in_(CONTENT_UPLOAD_BUTTON_TEXTS))
async def start_upload(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    await state.set_state(ContentListStates.waiting_for_excel)
    text = (
        "فایل رو به‌صورت داکیومنت بفرست — .xlsx یا .csv. از هدرهای ستون قالب نمونه استفاده کن "
        "یا اسم‌های مطابق خودت (فارسی یا انگلیسی)؛ لازم نیست ردیف هدر اولین ردیف باشه."
        if is_fa
        else "Send me the file as a document — .xlsx or .csv. Use the sample template's "
        "column headers or your own matching names (English or Persian); the header "
        "row doesn't have to be the first row."
    )
    text += await help_text.tip_suffix("content:upload", message.from_user)
    await message.answer(text, reply_markup=content_input_cancel_keyboard(is_fa))


@router.message(ContentListStates.waiting_for_excel, F.document)
async def receive_excel(message: Message, state: FSMContext, bot: Bot) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    data = await state.get_data()
    bot_id = data.get("active_bot_id")

    file = await bot.download(message.document)
    try:
        rows = parse_content_excel(file.read(), filename=message.document.file_name)
    except ValueError as exc:
        retry = "دوباره امتحان کن، یا /cancel رو بفرست تا لغو بشه." if is_fa else "Try again, or send /cancel to abort."
        await message.answer(f"{exc}\n\n{retry}")
        return

    if not rows:
        text = (
            "هیچ ردیفی با عنوان (یا کد برای حذف) تو این فایل پیدا نشد. "
            "دوباره امتحان کن، یا /cancel رو بفرست."
            if is_fa
            else "No rows with a title (or a Code to delete) were found in that file. "
            "Try again, or send /cancel."
        )
        await message.answer(text)
        return

    async with async_session_maker() as session:
        existing_result = await session.execute(
            select(ContentItem).where(ContentItem.bot_id == bot_id)
        )
        existing_items = list(existing_result.scalars())
        title_to_id = {item.title: item.id for item in existing_items}
        parent_map: dict[int, int | None] = {item.id: item.parent_id for item in existing_items}
        code_to_id = {item.code: item.id for item in existing_items if item.code}

        touched: list[tuple[ContentItem, str | None]] = []
        deleted_count = 0

        for row in rows:
            if row["action"] == "delete":
                target_id = code_to_id.get(row["code"]) if row["code"] else None
                if target_id is None:
                    continue
                result = await session.execute(
                    select(ContentItem).where(ContentItem.id == target_id)
                )
                victim = result.scalar_one_or_none()
                if victim is not None:
                    await session.delete(victim)
                    deleted_count += 1
                continue

            existing_id = code_to_id.get(row["code"]) if row["code"] else None
            if existing_id is not None:
                result = await session.execute(
                    select(ContentItem).where(ContentItem.id == existing_id)
                )
                item = result.scalar_one()
                item.title = row["title"]
                item.body = row["body"]
                item.image_url = row["image_url"]
                item.link_url = row["link_url"]
            else:
                item = ContentItem(
                    bot_id=bot_id,
                    title=row["title"],
                    body=row["body"],
                    image_url=row["image_url"],
                    link_url=row["link_url"],
                    code=row["code"],
                )
                session.add(item)
            touched.append((item, row["category"]))

        await session.flush()  # assign primary keys before resolving categories

        for item, _category in touched:
            title_to_id[item.title] = item.id
            parent_map.setdefault(item.id, item.parent_id)

        for item, category in touched:
            if not category:
                continue
            candidate_parent_id = title_to_id.get(category)
            if candidate_parent_id is None or candidate_parent_id == item.id:
                continue
            if would_cycle(item.id, candidate_parent_id, parent_map):
                continue
            item.parent_id = candidate_parent_id
            parent_map[item.id] = candidate_parent_id

        await session.commit()

    await sync_bot_commands(bot_id)
    await state.set_state(None)
    if is_fa:
        summary = f"{len(touched)} آیتم اضافه/به‌روزرسانی شد"
        if deleted_count:
            summary += f"، {deleted_count} حذف شد"
    else:
        summary = f"{len(touched)} item(s) added/updated"
        if deleted_count:
            summary += f", {deleted_count} deleted"
    await message.answer(f"{summary} ✅")
    await _send_menu(message, is_fa)


@router.message(ContentListStates.waiting_for_excel)
async def receive_excel_invalid(message: Message) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    text = (
        "لطفاً فایل رو به‌صورت داکیومنت بفرست (.xlsx یا .csv)، یا /cancel رو بفرست تا لغو بشه."
        if is_fa
        else "Please send the file as a document (.xlsx or .csv), or send /cancel to abort."
    )
    await message.answer(text)
