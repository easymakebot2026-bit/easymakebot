import re

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, KeyboardButton, Message, ReplyKeyboardMarkup
from sqlalchemy import select

from bot import help_text
from bot.db.base import async_session_maker
from bot.db.models import Command
from bot.guide import owner_prefers_persian
from bot.keyboards import (
    COMMAND_VISIBILITY_BUTTON_TO_KEY,
    cancel_button_text,
    cancel_reply_keyboard,
    command_action_button_to_key,
    command_action_keyboard,
    command_action_label,
    command_delete_confirm_keyboard,
    command_list_keyboard,
    command_visibility_keyboard,
    show_commands_button,
    tool_button_texts,
    tools_reply_keyboard,
)
from bot.runtime import sync_bot_commands
from bot.states import DefineCommandStates

router = Router(name="define_command")

TELEGRAM_ID_RE = re.compile(r"^@[A-Za-z0-9_]{5,32}$")
PHONE_RE = re.compile(r"^\+\d{6,15}$")

# Steps asked, in order, when a bot's /start command is (re)defined.
# key -> (English prompt, Persian prompt[, English error, Persian error]).
START_WIZARD_FIELDS = [
    {
        "key": "welcome_text",
        "prompt_en": "Please enter a short welcome message describing what your bot does.",
        "prompt_fa": "یه پیام خوش‌آمدگویی کوتاه بنویس که توضیح بده رباتت چیکار می‌کنه.",
    },
    {
        "key": "admin_telegram_id",
        "prompt_en": (
            "Enter the Telegram username for direct contact with the admin. "
            "It must start with @ (e.g. @username)."
        ),
        "prompt_fa": "یوزرنیم تلگرام برای تماس مستقیم با ادمین رو وارد کن. باید با @ شروع بشه (مثلاً @username).",
        "error_en": "Invalid Telegram username. It must start with @ and be 5-32 characters (letters, digits, underscore).",
        "error_fa": "یوزرنیم تلگرام نامعتبره. باید با @ شروع بشه و بین ۵ تا ۳۲ کاراکتر (حرف، عدد، آندرلاین) باشه.",
    },
    {
        "key": "admin_phone",
        "prompt_en": "Share your phone number with the button below, or type it manually including the country code (e.g. +12025550123).",
        "prompt_fa": "شماره‌ت رو با دکمه‌ی زیر به اشتراک بذار، یا با کد کشور دستی تایپ کن (مثلاً +989121234567).",
        "phone": True,
    },
    {
        "key": "website",
        "prompt_en": "Enter your website link (optional).",
        "prompt_fa": "لینک وب‌سایتت رو وارد کن (اختیاری).",
        "optional": True,
    },
    {
        "key": "instagram",
        "prompt_en": "Enter your Instagram page (optional).",
        "prompt_fa": "پیج اینستاگرامت رو وارد کن (اختیاری).",
        "optional": True,
    },
    {
        "key": "youtube",
        "prompt_en": "Enter your YouTube channel (optional).",
        "prompt_fa": "کانال یوتیوبت رو وارد کن (اختیاری).",
        "optional": True,
    },
    {
        "key": "facebook",
        "prompt_en": "Enter your Facebook page (optional).",
        "prompt_fa": "پیج فیسبوکت رو وارد کن (اختیاری).",
        "optional": True,
    },
    {
        "key": "x",
        "prompt_en": "Enter your X (Twitter) account (optional).",
        "prompt_fa": "اکانت X (توییتر) ت رو وارد کن (اختیاری).",
        "optional": True,
    },
]


def _prompt(field: dict, is_fa: bool) -> str:
    return field["prompt_fa"] if is_fa else field["prompt_en"]


def _error(field: dict, is_fa: bool) -> str:
    return field["error_fa"] if is_fa else field["error_en"]


def start_wizard_skip_text(is_fa: bool = False) -> str:
    return "⏭ رد کردن" if is_fa else "⏭ Skip"


def start_wizard_save_text(is_fa: bool = False) -> str:
    return "✅ ذخیره‌ی دستور /start" if is_fa else "✅ Save /start command"


START_WIZARD_SKIP_TEXTS = frozenset({start_wizard_skip_text(False), start_wizard_skip_text(True)})
START_WIZARD_SAVE_TEXTS = frozenset({start_wizard_save_text(False), start_wizard_save_text(True)})
# Back-compat bare constants.
START_WIZARD_SKIP_TEXT = start_wizard_skip_text(False)
START_WIZARD_SAVE_TEXT = start_wizard_save_text(False)


def _skip_keyboard(is_fa: bool = False) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=start_wizard_skip_text(is_fa)),
                KeyboardButton(text=cancel_button_text(is_fa)),
            ]
        ],
        resize_keyboard=True,
    )


def _phone_keyboard(is_fa: bool = False) -> ReplyKeyboardMarkup:
    # Now that Cancel is a reply button everywhere, it can share this
    # keyboard with the contact-share button — no more "can't mix inline
    # Cancel with a reply keyboard" workaround.
    share_text = "📱 اشتراک‌گذاری شماره" if is_fa else "📱 Share Phone Number"
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=share_text, request_contact=True)],
            [KeyboardButton(text=cancel_button_text(is_fa))],
        ],
        resize_keyboard=True,
    )


def _save_keyboard(is_fa: bool = False) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=start_wizard_save_text(is_fa)),
                KeyboardButton(text=cancel_button_text(is_fa)),
            ]
        ],
        resize_keyboard=True,
    )


async def _send_step(message: Message, state: FSMContext, index: int, is_fa: bool) -> None:
    if index >= len(START_WIZARD_FIELDS):
        await state.set_state(DefineCommandStates.confirm_start_wizard)
        text = "همه چی آماده‌ست. این مقادیر برای دستور /start ذخیره بشن؟" if is_fa else "All set. Save these values for the /start command?"
        await message.answer(text, reply_markup=_save_keyboard(is_fa))
        return

    await state.update_data(wizard_index=index)
    field = START_WIZARD_FIELDS[index]

    if field.get("phone"):
        await message.answer(_prompt(field, is_fa), reply_markup=_phone_keyboard(is_fa))
    elif field.get("optional"):
        await message.answer(_prompt(field, is_fa), reply_markup=_skip_keyboard(is_fa))
    else:
        await message.answer(_prompt(field, is_fa), reply_markup=cancel_reply_keyboard(is_fa))


async def _open(message: Message, state: FSMContext, is_fa: bool) -> None:
    data = await state.get_data()
    bot_id = data.get("active_bot_id")

    if bot_id is None:
        text = 'اول یه ربات از «ربات‌های من» انتخاب کن.' if is_fa else 'First select a bot from "My Bots".'
        await message.answer(text)
        return

    async with async_session_maker() as session:
        result = await session.execute(
            select(Command).where(Command.bot_id == bot_id, Command.name == "/start")
        )
        has_start = result.scalar_one_or_none() is not None

    await state.set_state(DefineCommandStates.waiting_for_command_name)

    if has_start:
        text = "اسم دستور جدید رو بنویس، با / شروع بشه." if is_fa else "Please write the name of the new command starting with /."
    elif is_fa:
        text = (
            "دستورها همیشه باید با / شروع بشن.\n"
            "چون این اولین دستوریه که برای این ربات تعریف می‌کنی، پیشنهاد ما /start ئه — "
            "همه‌ی تنظیمات اولیه برای همین دستور انجام می‌شه.\n\n"
            "اسم دستور رو با / شروع کن و بنویس."
        )
    else:
        text = (
            "Commands must always start with /.\n"
            "Since this is the first command you're defining for this bot, "
            "we suggest /start — all the initial setup will be handled for this command.\n\n"
            "Please write the command name starting with /."
        )
    text += await help_text.tip_suffix("tool:define_command", message.from_user)

    await message.answer(text, reply_markup=show_commands_button(is_fa))


@router.message(F.text.in_(tool_button_texts("define_command")))
async def start_define_command(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    await _open(message, state, is_fa)


@router.message(DefineCommandStates.waiting_for_command_name)
async def receive_command_name(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    name = message.text.strip()

    if not name.startswith("/"):
        text = "دستور باید با / شروع بشه. دوباره امتحان کن." if is_fa else "The command must start with /. Try again."
        await message.answer(text, reply_markup=cancel_reply_keyboard(is_fa))
        return

    if name == "/start":
        await state.update_data(wizard_payload={})
        await state.set_state(DefineCommandStates.start_wizard)
        await _send_step(message, state, 0, is_fa)
        return

    await state.update_data(pending_command_name=name)
    await state.set_state(DefineCommandStates.waiting_for_command_visibility)

    if is_fa:
        text = f"دستور «{name}» — این دستور برای کی نمایش داده بشه؟"
    else:
        text = f"Command \"{name}\" — who should be able to see and use this command?"
    await message.answer(text, reply_markup=command_visibility_keyboard(is_fa))


@router.message(DefineCommandStates.waiting_for_command_visibility)
async def receive_command_visibility(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    visibility = COMMAND_VISIBILITY_BUTTON_TO_KEY.get((message.text or "").strip())

    if visibility is None:
        text = "لطفاً یکی از گزینه‌های زیر رو انتخاب کن." if is_fa else "Please choose one of the options below."
        await message.answer(text, reply_markup=command_visibility_keyboard(is_fa))
        return

    await state.update_data(pending_command_visibility=visibility)
    await state.set_state(DefineCommandStates.waiting_for_command_action)

    text = "این دستور وقتی اجرا بشه چیکار کنه؟" if is_fa else "What should this command do when it's used?"
    await message.answer(text, reply_markup=command_action_keyboard(is_fa))


@router.message(DefineCommandStates.waiting_for_command_action)
async def receive_command_action(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    action = command_action_button_to_key().get((message.text or "").strip())

    if action is None:
        text = "لطفاً یکی از گزینه‌های زیر رو انتخاب کن." if is_fa else "Please choose one of the options below."
        await message.answer(text, reply_markup=command_action_keyboard(is_fa))
        return

    if action == "message":
        await state.set_state(DefineCommandStates.waiting_for_command_message_text)
        text = "متنی که این دستور باید بفرسته رو بنویس." if is_fa else "Write the text this command should send."
        await message.answer(text, reply_markup=cancel_reply_keyboard(is_fa))
        return

    await _save_command(message, state, is_fa, action, {})


@router.message(DefineCommandStates.waiting_for_command_message_text)
async def receive_command_message_text(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    text_in = (message.text or "").strip()

    if not text_in:
        text = "این فیلد نمی‌تونه خالی باشه. دوباره امتحان کن." if is_fa else "This field can't be empty. Please try again."
        await message.answer(text, reply_markup=cancel_reply_keyboard(is_fa))
        return

    await _save_command(message, state, is_fa, "message", {"text": text_in})


async def _save_command(
    message: Message, state: FSMContext, is_fa: bool, action: str, payload_extra: dict
) -> None:
    data = await state.get_data()
    bot_id = data.get("active_bot_id")
    name = data.get("pending_command_name")
    visibility = data.get("pending_command_visibility", "everyone")
    payload = {"action": action, **payload_extra}

    async with async_session_maker() as session:
        result = await session.execute(
            select(Command).where(Command.bot_id == bot_id, Command.name == name)
        )
        existing = result.scalar_one_or_none()
        if existing is None:
            session.add(
                Command(
                    bot_id=bot_id,
                    name=name,
                    command_type="custom",
                    visibility=visibility,
                    payload=payload,
                )
            )
        else:
            existing.command_type = "custom"
            existing.visibility = visibility
            existing.payload = payload
        await session.commit()

    await sync_bot_commands(bot_id)

    await state.set_state(DefineCommandStates.waiting_for_command_name)
    if is_fa:
        text = f"دستور «{name}» ثبت شد ✅\nاسم دستور بعدی رو با / شروع کن و بنویس."
    else:
        text = f"Command \"{name}\" registered ✅\nPlease write the next command name starting with /."
    await message.answer(text, reply_markup=show_commands_button(is_fa))


@router.message(DefineCommandStates.start_wizard, F.text.in_(START_WIZARD_SKIP_TEXTS))
async def wizard_skip(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    data = await state.get_data()
    index = data.get("wizard_index", 0)
    field = START_WIZARD_FIELDS[index]

    if not field.get("optional"):
        text = "این فیلد رو نمی‌شه رد کرد." if is_fa else "This field can't be skipped."
        await message.answer(text, reply_markup=_skip_keyboard(is_fa))
        return

    payload = data.get("wizard_payload", {})
    payload[field["key"]] = None
    await state.update_data(wizard_payload=payload)
    await _send_step(message, state, index + 1, is_fa)


@router.message(DefineCommandStates.start_wizard)
async def wizard_receive(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    data = await state.get_data()
    index = data.get("wizard_index", 0)
    field = START_WIZARD_FIELDS[index]
    payload = data.get("wizard_payload", {})

    if field.get("phone"):
        if message.contact is not None:
            phone = message.contact.phone_number
            value = phone if phone.startswith("+") else f"+{phone}"
        elif message.text and PHONE_RE.match(message.text.strip()):
            value = message.text.strip()
        else:
            if is_fa:
                text = "شماره نامعتبره. با دکمه به اشتراک بذار، یا با کد کشور تایپ کن، مثلاً +989121234567."
            else:
                text = (
                    "Invalid phone number. Share it with the button, or type it with "
                    "the country code, e.g. +12025550123."
                )
            await message.answer(text, reply_markup=_phone_keyboard(is_fa))
            return
    else:
        text_in = (message.text or "").strip()
        if not text_in and not field.get("optional"):
            text = "این فیلد نمی‌تونه خالی باشه. دوباره امتحان کن." if is_fa else "This field can't be empty. Please try again."
            await message.answer(text, reply_markup=cancel_reply_keyboard(is_fa))
            return
        if field["key"] == "admin_telegram_id" and text_in and not TELEGRAM_ID_RE.match(text_in):
            await message.answer(_error(field, is_fa), reply_markup=cancel_reply_keyboard(is_fa))
            return
        value = text_in or None

    payload[field["key"]] = value
    await state.update_data(wizard_payload=payload)
    await _send_step(message, state, index + 1, is_fa)


@router.message(DefineCommandStates.confirm_start_wizard, F.text.in_(START_WIZARD_SAVE_TEXTS))
async def wizard_save(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    data = await state.get_data()
    bot_id = data.get("active_bot_id")
    payload = data.get("wizard_payload", {})

    async with async_session_maker() as session:
        result = await session.execute(
            select(Command).where(Command.bot_id == bot_id, Command.name == "/start")
        )
        existing = result.scalar_one_or_none()
        if existing is None:
            session.add(Command(bot_id=bot_id, name="/start", command_type="start", payload=payload))
        else:
            existing.payload = payload
        await session.commit()

    await sync_bot_commands(bot_id)

    await state.set_state(DefineCommandStates.waiting_for_command_name)
    saved_text = "تغییرات با موفقیت ذخیره شد ✅" if is_fa else "Changes saved successfully ✅"
    await message.answer(saved_text, reply_markup=tools_reply_keyboard(is_fa))
    next_text = "اسم دستور بعدی رو با / شروع کن و بنویس." if is_fa else "Please write the next command name starting with /."
    await message.answer(next_text, reply_markup=show_commands_button(is_fa))


async def _send_command_list(message: Message, bot_id, is_fa: bool) -> None:
    async with async_session_maker() as session:
        result = await session.execute(
            select(Command).where(Command.bot_id == bot_id).order_by(Command.created_at)
        )
        commands = list(result.scalars())

    if not commands:
        text = "هنوز هیچ دستوری برای این ربات تعریف نشده." if is_fa else "No commands have been defined for this bot yet."
        await message.answer(text)
        return

    lines = ["دستورهای ثبت‌شده برای این ربات:\n"] if is_fa else ["Commands registered for this bot:\n"]
    for c in commands:
        marker = "📢 " if c.command_type == "broadcast" else ""
        admin_marker = " 👤" if c.visibility == "admin" else ""
        action = (c.payload or {}).get("action") if c.command_type == "custom" else None
        action_label = f" — {command_action_label(action, is_fa)}" if action else ""
        if is_fa:
            lines.append(
                f"• {marker}{c.name}{action_label}{admin_marker} — آخرین ویرایش: {c.updated_at:%Y-%m-%d %H:%M}"
            )
        else:
            lines.append(
                f"• {marker}{c.name}{action_label}{admin_marker} — last edited: {c.updated_at:%Y-%m-%d %H:%M}"
            )
    text = "\n".join(lines)
    text += await help_text.tip_suffix("show_commands", message.from_user)

    await message.answer(text)

    keyboard = command_list_keyboard(commands, is_fa)
    if keyboard is not None:
        hint = "برای حذف یه دستور، روی دکمه‌ش بزن:" if is_fa else "Tap a command below to delete it:"
        await message.answer(hint, reply_markup=keyboard)


@router.message(F.text.in_(frozenset({"📋 Show Commands", "📋 نمایش دستورها"})))
async def show_commands(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    data = await state.get_data()
    bot_id = data.get("active_bot_id")
    await _send_command_list(message, bot_id, is_fa)


@router.callback_query(F.data.startswith("cmd:delete_confirm:"))
async def confirm_delete_command(callback: CallbackQuery, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(callback.from_user)
    command_id = int(callback.data.split(":")[-1])

    async with async_session_maker() as session:
        result = await session.execute(select(Command).where(Command.id == command_id))
        command = result.scalar_one_or_none()

    if command is None:
        await callback.answer()
        return

    text = (
        f"مطمئنی می‌خوای دستور «{command.name}» رو حذف کنی؟"
        if is_fa
        else f"Delete command \"{command.name}\"?"
    )
    await callback.message.answer(text, reply_markup=command_delete_confirm_keyboard(command_id, is_fa))
    await callback.answer()


@router.callback_query(F.data.startswith("cmd:delete:"))
async def delete_command(callback: CallbackQuery, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(callback.from_user)
    command_id = int(callback.data.split(":")[-1])
    data = await state.get_data()
    bot_id = data.get("active_bot_id")

    async with async_session_maker() as session:
        result = await session.execute(select(Command).where(Command.id == command_id))
        command = result.scalar_one_or_none()
        if command is not None and str(command.bot_id) == str(bot_id):
            await session.delete(command)
            await session.commit()

    await sync_bot_commands(bot_id)

    text = "دستور حذف شد ✅" if is_fa else "Command deleted ✅"
    await callback.message.answer(text)
    await callback.answer()


@router.callback_query(F.data == "cmd:delete_cancel")
async def cancel_delete_command(callback: CallbackQuery) -> None:
    text = "لغو شد." if await owner_prefers_persian(callback.from_user) else "Cancelled."
    await callback.message.answer(text)
    await callback.answer()
