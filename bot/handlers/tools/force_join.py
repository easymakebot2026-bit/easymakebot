import re

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from bot import help_text
from bot.db.base import async_session_maker
from bot.db.models import BuiltBot, JoinChannel
from bot.guide import owner_prefers_persian
from bot.keyboards import (
    FORCE_JOIN_BACK_BUTTON_TEXTS,
    FORCE_JOIN_CONFIRM_BUTTON_TEXTS,
    FORCE_JOIN_LIST_BUTTON_TEXTS,
    FORCE_JOIN_NEW_BUTTON_TEXTS,
    FORCE_JOIN_TOGGLE_TEXTS,
    force_join_channels_keyboard,
    force_join_confirm_keyboard,
    force_join_input_cancel_keyboard,
    force_join_menu_keyboard,
    tool_button_texts,
)
from bot.states import ForceJoinStates

router = Router(name="force_join")

CHANNEL_USERNAME_RE = re.compile(r"^@[A-Za-z0-9_]{5,32}$")


async def _send_menu(message: Message, bot_id: str, is_fa: bool, *, extra: str = "") -> None:
    async with async_session_maker() as session:
        result = await session.execute(select(BuiltBot).where(BuiltBot.id == bot_id))
        built_bot = result.scalar_one_or_none()

    enabled = bool(built_bot and built_bot.force_join_enabled)
    if is_fa:
        status = "🔒 در حال حاضر روشنه" if enabled else "🔓 در حال حاضر خاموشه"
        text = (
            f'از «لیست کانال‌ها» برای دیدن کانال‌هایی که کاربران باید عضو بشن استفاده کن، '
            f"یا یه کانال جدید تعریف کن. عضویت اجباری {status}."
        ) + extra
    else:
        status = "🔒 currently ON" if enabled else "🔓 currently OFF"
        text = (
            f'Use "List Channels" to see the channels users must join, or define a new one. '
            f"Force Join is {status}."
        ) + extra
    await message.answer(text, reply_markup=force_join_menu_keyboard(enabled, is_fa))


@router.message(F.text.in_(tool_button_texts("force_join")))
async def open_force_join(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    data = await state.get_data()
    bot_id = data.get("active_bot_id")

    if bot_id is None:
        text = 'اول از «ربات‌های من» یه ربات انتخاب کن.' if is_fa else 'First select a bot from "My Bots".'
        await message.answer(text)
        return

    await state.set_state(None)
    tip = await help_text.tip_suffix("tool:force_join", message.from_user)
    await _send_menu(message, bot_id, is_fa, extra=tip)


@router.callback_query(F.data == "force_join:menu")
async def back_to_menu(callback: CallbackQuery, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(callback.from_user)
    data = await state.get_data()
    bot_id = data.get("active_bot_id")
    await state.update_data(editing_channel_id=None, pending_channel_name=None)
    await state.set_state(None)
    await _send_menu(callback.message, bot_id, is_fa)
    await callback.answer()


@router.message(F.text.in_(FORCE_JOIN_LIST_BUTTON_TEXTS))
async def list_channels(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    data = await state.get_data()
    bot_id = data.get("active_bot_id")

    async with async_session_maker() as session:
        result = await session.execute(
            select(JoinChannel).where(JoinChannel.bot_id == bot_id).order_by(JoinChannel.created_at)
        )
        channels = list(result.scalars())

    if not channels:
        text = "هنوز کانالی تعریف نشده." if is_fa else "No channels have been defined yet."
        await message.answer(text)
        return

    text = "یه کانال برای ویرایش انتخاب کن:" if is_fa else "Select a channel to edit:"
    text += await help_text.tip_suffix("force_join:list", message.from_user)
    await message.answer(text, reply_markup=force_join_channels_keyboard(channels, is_fa))


@router.message(F.text.in_(FORCE_JOIN_NEW_BUTTON_TEXTS))
async def new_channel(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    await state.update_data(editing_channel_id=None)
    await state.set_state(ForceJoinStates.waiting_for_channel_name)
    text = (
        "یوزرنیم کانال رو با @ در ابتدا بفرست (مثلاً @mychannel)."
        if is_fa
        else "Send the channel's username, starting with @ (e.g. @mychannel)."
    )
    text += await help_text.tip_suffix("force_join:new", message.from_user)
    await message.answer(text, reply_markup=force_join_input_cancel_keyboard(is_fa))


@router.callback_query(F.data.startswith("force_join:select:"))
async def select_channel(callback: CallbackQuery, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(callback.from_user)
    channel_id = int(callback.data.split(":")[-1])
    await state.update_data(editing_channel_id=channel_id)
    await state.set_state(ForceJoinStates.waiting_for_channel_name)
    text = (
        "لطفاً نام درست رو وارد کن. یوزرنیم کانال باید با @ شروع بشه."
        if is_fa
        else "Please enter the correct name. The channel username must start with @."
    )
    await callback.message.answer(
        text,
        reply_markup=force_join_input_cancel_keyboard(is_fa),
    )
    await callback.answer()


@router.message(ForceJoinStates.waiting_for_channel_name, F.text.in_(FORCE_JOIN_BACK_BUTTON_TEXTS))
async def cancel_edit(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    data = await state.get_data()
    bot_id = data.get("active_bot_id")
    await state.update_data(editing_channel_id=None, pending_channel_name=None)
    await state.set_state(None)
    text = "لغو شد ❌" if is_fa else "Cancelled ❌"
    await message.answer(text)
    await _send_menu(message, bot_id, is_fa)


@router.message(ForceJoinStates.waiting_for_channel_name, F.text.in_(FORCE_JOIN_CONFIRM_BUTTON_TEXTS))
async def confirm_channel(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    data = await state.get_data()
    bot_id = data.get("active_bot_id")
    editing_channel_id = data.get("editing_channel_id")
    username = data.get("pending_channel_name")

    if not username:
        text = "چیزی برای ذخیره وجود نداره." if is_fa else "Nothing to save."
        await message.answer(text)
        return

    async with async_session_maker() as session:
        if editing_channel_id:
            result = await session.execute(
                select(JoinChannel).where(JoinChannel.id == editing_channel_id)
            )
            channel = result.scalar_one_or_none()
            if channel is not None:
                channel.username = username
        else:
            session.add(JoinChannel(bot_id=bot_id, username=username))
        await session.commit()

    await state.update_data(editing_channel_id=None, pending_channel_name=None)
    await state.set_state(None)

    text = "با موفقیت ذخیره شد ✅" if is_fa else "Saved successfully ✅"
    await message.answer(text)
    await _send_menu(message, bot_id, is_fa)


@router.message(ForceJoinStates.waiting_for_channel_name)
async def receive_channel_name(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    username = (message.text or "").strip()

    if not CHANNEL_USERNAME_RE.match(username):
        text = (
            "یوزرنیم کانال نامعتبره. باید با @ شروع بشه و ۵ تا ۳۲ کاراکتر باشه "
            "(حروف، عدد، آندرلاین). دوباره امتحان کن."
            if is_fa
            else "Invalid channel username. It must start with @ and be 5-32 characters "
            "(letters, digits, underscore). Try again."
        )
        await message.answer(
            text,
            reply_markup=force_join_input_cancel_keyboard(is_fa),
        )
        return

    data = await state.get_data()
    editing_channel_id = data.get("editing_channel_id")
    await state.update_data(pending_channel_name=username)

    if is_fa:
        if editing_channel_id:
            text = f'کانال به «{username}» به‌روزرسانی بشه؟'
        else:
            text = f'«{username}» به لیست اضافه بشه؟'
    else:
        if editing_channel_id:
            text = f'Update the channel to "{username}"?'
        else:
            text = f'Add "{username}" to the list?'

    await message.answer(text, reply_markup=force_join_confirm_keyboard(is_fa))


@router.message(F.text.in_(FORCE_JOIN_TOGGLE_TEXTS))
async def toggle_force_join(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    data = await state.get_data()
    bot_id = data.get("active_bot_id")

    async with async_session_maker() as session:
        result = await session.execute(select(BuiltBot).where(BuiltBot.id == bot_id))
        built_bot = result.scalar_one_or_none()

        if built_bot is None:
            text = "ربات پیدا نشد." if is_fa else "Bot not found."
            await message.answer(text)
            return

        if not built_bot.force_join_enabled:
            channels_result = await session.execute(
                select(JoinChannel).where(JoinChannel.bot_id == bot_id)
            )
            if not list(channels_result.scalars()):
                text = (
                    "قبل از فعال کردن عضویت اجباری، حداقل یه کانال تعریف کن."
                    if is_fa
                    else "Define at least one channel before enabling Force Join."
                )
                await message.answer(text)
                return

        built_bot.force_join_enabled = not built_bot.force_join_enabled
        enabled = built_bot.force_join_enabled
        await session.commit()

    if is_fa:
        text = "عضویت اجباری فعال شد ✅" if enabled else "عضویت اجباری غیرفعال شد"
    else:
        text = "Force Join enabled ✅" if enabled else "Force Join disabled"
    await message.answer(text)
    await _send_menu(message, bot_id, is_fa)
