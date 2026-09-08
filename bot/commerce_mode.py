"""Whether a built bot sells individual products/services (Shop) or is a
subscription-gated content archive (Subscription) — chosen once, mutually
exclusive; a bot never mixes the two. See bot/shop.py (Product/Order) and
bot/premium_content.py (the subscription/free-preview gating).

No Telegram-handler code here — reused by bot/handlers/tools/shop.py and
bot/handlers/tools/content_list.py, same split as every other shared
module this session.
"""

import uuid

from sqlalchemy import select

from bot.db.base import async_session_maker
from bot.db.models import BuiltBot

MODE_SHOP = "shop"
MODE_SUBSCRIPTION = "subscription"


async def get_commerce_mode(bot_id: uuid.UUID | str) -> str | None:
    async with async_session_maker() as session:
        result = await session.execute(select(BuiltBot.commerce_mode).where(BuiltBot.id == bot_id))
        return result.scalar_one_or_none()


async def set_commerce_mode(bot_id: uuid.UUID | str, mode: str) -> None:
    async with async_session_maker() as session:
        result = await session.execute(select(BuiltBot).where(BuiltBot.id == bot_id))
        built_bot = result.scalar_one_or_none()
        if built_bot is not None:
            built_bot.commerce_mode = mode
            await session.commit()
