from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy import select

from bot import help_text
from bot.db.base import async_session_maker
from bot.db.models import Command
from bot.guide import owner_prefers_persian
from bot.keyboards import cancel_reply_keyboard, show_commands_button, tool_button_texts, tools_reply_keyboard
from bot.runtime import sync_bot_commands
from bot.states import MessageToAllStates

router = Router(name="message_to_all")


@router.message(F.text.in_(tool_button_texts("message_to_all")))
async def start_message_to_all(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    data = await state.get_data()
    bot_id = data.get("active_bot_id")

    if bot_id is None:
        text = 'اول از «ربات‌های من» یه ربات انتخاب کن.' if is_fa else 'First select a bot from "My Bots".'
        await message.answer(text)
        return

    await state.set_state(MessageToAllStates.waiting_for_command_name)
    if is_fa:
        text = (
            "نام دستوری که پیام‌رسانی گروهی رو فعال می‌کنه بنویس، با / شروع کن.\n"
            "بعد از ذخیره، هر پیامی که با این دستور روی رباتت بفرستی، به تمام کاربرهای اون ربات ارسال می‌شه."
        )
    else:
        text = (
            "Write the command name that will trigger group messaging, starting with /.\n"
            "Once saved, sending a message on your bot with this command will deliver it "
            "to every user of that bot."
        )
    text += await help_text.tip_suffix("tool:message_to_all", message.from_user)
    await message.answer(text, reply_markup=show_commands_button(is_fa))


@router.message(MessageToAllStates.waiting_for_command_name)
async def receive_broadcast_command_name(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    name = message.text.strip()

    if not name.startswith("/"):
        text = "دستور باید با / شروع بشه. دوباره امتحان کن." if is_fa else "The command must start with /. Try again."
        await message.answer(
            text, reply_markup=cancel_reply_keyboard(is_fa)
        )
        return

    data = await state.get_data()
    bot_id = data.get("active_bot_id")

    async with async_session_maker() as session:
        result = await session.execute(
            select(Command).where(Command.bot_id == bot_id, Command.name == name)
        )
        existing = result.scalar_one_or_none()
        if existing is None:
            session.add(Command(bot_id=bot_id, name=name, command_type="broadcast"))
        else:
            existing.command_type = "broadcast"
        await session.commit()

    await sync_bot_commands(bot_id)

    await state.clear()
    if is_fa:
        text = (
            f'دستور «{name}» برای پیام‌رسانی گروهی ثبت شد 📢✅\n'
            "از این به بعد، هر وقت این دستور رو روی رباتت همراه یه پیام بفرستی، "
            "به تمام کاربرهای اون ربات ارسال می‌شه."
        )
    else:
        text = (
            f'Command "{name}" registered for group messaging 📢✅\n'
            "From now on, whenever you send this command on your bot followed by a message, "
            "it will be delivered to every user of that bot."
        )
    await message.answer(text, reply_markup=tools_reply_keyboard(is_fa))
