"""Force-join gate: shared between the legacy hardcoded /start handler
(bot/runtime.py) and the visual flow engine (bot/flow_engine.py) so there's
one gate implementation, not two."""

import uuid

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select

from bot.db.base import async_session_maker
from bot.db.models import JoinChannel


async def missing_join_channels(bot: Bot, bot_id: uuid.UUID, user_id: int) -> list[JoinChannel]:
    """Returns the JoinChannels (if any) the user hasn't joined yet. A channel the
    bot can't check (not an admin there, wrong username, API error) counts as missing
    so the gate fails safe rather than silently letting everyone through."""
    async with async_session_maker() as session:
        result = await session.execute(select(JoinChannel).where(JoinChannel.bot_id == bot_id))
        channels = list(result.scalars())

    missing = []
    for channel in channels:
        try:
            member = await bot.get_chat_member(chat_id=channel.username, user_id=user_id)
            if member.status in ("left", "kicked"):
                missing.append(channel)
        except Exception:
            missing.append(channel)

    return missing


def force_join_keyboard(missing: list[JoinChannel]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"📢 {c.username}", url=f"https://t.me/{c.username.lstrip('@')}"
            )
        ]
        for c in missing
    ]
    rows.append([InlineKeyboardButton(text="✅ I've Joined", callback_data="force_join_check")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
