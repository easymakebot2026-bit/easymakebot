"""Platform-wide toggles — currently just whether built bots are open for
business (bot/db/models.py: PlatformSettings, a single row with id=1).

Deliberately its own module rather than living in bot/admin_panel.py (which
writes it, via /easybotadmin) or bot/runtime.py (which reads it, on every
built bot's /start): admin_panel.py already imports from runtime.py, so
either of those importing this the other way round would be circular.
"""

from sqlalchemy import select

from bot.db.base import async_session_maker
from bot.db.models import PlatformSettings, User
from bot.guide import is_iran_phone

_SETTINGS_ROW_ID = 1

# Shown instead of a normal /start — by both the platform's own bot
# (bot/handlers/start.py) and every built bot (bot/runtime.py) — while
# bots_enabled() is False. Lives here, not either of those two call sites,
# for the same reason the functions below do: avoids start.py/runtime.py
# needing to import from each other.
MAINTENANCE_TEXT_FA = "ربات در حال به‌روزرسانی است. به زودی برمی‌گردیم 🙏"
MAINTENANCE_TEXT_EN = "The bot is currently under maintenance. We'll be back soon 🙏"


async def bots_enabled() -> bool:
    """True (bots operate normally) unless an admin has explicitly flipped
    this off. No row yet (fresh install) also reads as True — same default
    as the column itself."""
    async with async_session_maker() as session:
        result = await session.execute(
            select(PlatformSettings.bots_enabled).where(PlatformSettings.id == _SETTINGS_ROW_ID)
        )
        value = result.scalar_one_or_none()
        return True if value is None else value


async def set_bots_enabled(enabled: bool) -> None:
    async with async_session_maker() as session:
        result = await session.execute(
            select(PlatformSettings).where(PlatformSettings.id == _SETTINGS_ROW_ID)
        )
        row = result.scalar_one_or_none()
        if row is None:
            session.add(PlatformSettings(id=_SETTINGS_ROW_ID, bots_enabled=enabled))
        else:
            row.bots_enabled = enabled
        await session.commit()


async def platform_user_prefers_persian(tg_user) -> bool:
    """Persian vs English for the maintenance message, for a Telegram user
    on the platform's own bot (easymakebot itself, bot/main.py) — prefers a
    phone number already on file (same is_iran_phone signal used
    everywhere), falling back to the Telegram client's language for a
    brand-new visitor who has none yet."""
    async with async_session_maker() as session:
        phone = (
            await session.execute(select(User.phone_number).where(User.telegram_id == tg_user.id))
        ).scalar_one_or_none()
    if phone is not None:
        return is_iran_phone(phone)
    return (tg_user.language_code or "").lower().startswith("fa")
