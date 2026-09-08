import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy import select

from bot.config import load_config
from bot.db.base import async_session_maker
from bot.db.models import BuiltBot, User
from bot.filters.admin import IsPlatformAdmin
from bot.keyboards import cancel_inline_keyboard
from bot.states import AdminBroadcastStates

router = Router(name="admin_broadcast")
logger = logging.getLogger(__name__)

_config = load_config()
_is_platform_admin = IsPlatformAdmin(_config.platform_admin_id)


@router.message(Command("send_to_all"), _is_platform_admin)
async def ask_broadcast_message(message: Message, state: FSMContext) -> None:
    await state.set_state(AdminBroadcastStates.waiting_for_message)
    await message.answer(
        "Send the message you want to deliver to every bot creator.",
        reply_markup=cancel_inline_keyboard(),
    )


@router.message(AdminBroadcastStates.waiting_for_message, _is_platform_admin)
async def send_broadcast(message: Message, state: FSMContext) -> None:
    async with async_session_maker() as session:
        result = await session.execute(
            select(User).join(BuiltBot, BuiltBot.owner_id == User.id).distinct()
        )
        owners = list(result.scalars())

    sent = 0
    for owner in owners:
        try:
            await message.copy_to(owner.telegram_id)
            sent += 1
        except Exception:
            logger.warning("Failed to deliver /send_to_all message to user %s", owner.telegram_id)

    await state.clear()
    await message.answer(f"Message sent to {sent} bot creator(s) ✅")
