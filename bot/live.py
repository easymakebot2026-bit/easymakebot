"""Shared logic for a built bot's "go live" lifecycle: a one-time free
trial, or a paid plan (LIVE_PLANS — one placeholder plan for now, real
pricing TBD, see bot/platform_billing.py for the actual payment wiring),
after which the bot's Telegram polling is stopped (bot/runtime.py) and its
owner-side editing tools are gated until a plan is purchased. Also carries
the platform-admin suspension kill switch (bot/admin_panel.py) — a separate,
higher-priority gate that no plan purchase can undo (see is_bot_suspended).

No Telegram-handler code here — reused by bot/handlers/live.py (the /live
command), bot/handlers/my_bots.py (the lock icon + post-expiry gate on
"My Bots"), bot/handlers/tools_menu.py (gating the tools grid), and
bot/handlers/easybotadmin.py, same split as bot/content_nav.py / bot/shop.py.

LIVE_PLANS lives HERE rather than in bot/platform_billing.py (which does the
actual payment processing) specifically to avoid a circular import:
platform_billing.py already needs set_live_until from this module, so this
module can't import back from platform_billing.py — it just imports
LIVE_PLANS from here instead.
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from bot.db.base import async_session_maker
from bot.db.models import BuiltBot, User

TRIAL_HOURS = 72

# Real plans/pricing TBD — one clearly-placeholder plan so the whole payment
# path (bot/platform_billing.py, bot/handlers/live.py) is wired end to end;
# swapping in real plans later is a data-only edit to this list. Rendered as
# buttons by bot/keyboards.py:live_plans_keyboard.
LIVE_PLANS: list[dict] = [
    {
        "key": "monthly",
        "label": "Monthly — 30 days",
        "label_fa": "ماهانه — ۳۰ روز",
        "days": 30,
        "price_toman": 490_000,
        "price_usd": 10,
    },
]


def is_bot_live(built_bot: BuiltBot) -> bool:
    return built_bot.live_until is not None and built_bot.live_until > datetime.now(timezone.utc)


def is_bot_expired(built_bot: BuiltBot) -> bool:
    """True only for a bot that WAS live at least once (trial or a plan) and
    whose window has since passed — never true for a bot that simply hasn't
    gone live yet, which stays fully editable while its owner builds it."""
    return built_bot.live_until is not None and built_bot.live_until <= datetime.now(timezone.utc)


def is_bot_suspended(built_bot: BuiltBot) -> bool:
    """Platform-admin kill switch (bot/admin_panel.py) — deliberately
    independent of live_until, so a fresh plan purchase can never silently
    undo a suspension. Callers must check this BEFORE is_bot_expired at
    every gating touchpoint (see module docstring)."""
    return bool(built_bot.suspended)


async def get_built_bot(bot_id: uuid.UUID | str) -> BuiltBot | None:
    async with async_session_maker() as session:
        result = await session.execute(select(BuiltBot).where(BuiltBot.id == bot_id))
        return result.scalar_one_or_none()


async def get_owned_built_bot(bot_id: uuid.UUID | str, telegram_id: int) -> BuiltBot | None:
    """Same lookup as get_built_bot, but only returns the bot if `telegram_id`
    actually owns it — same ownership join bot/webapp_server.py:_authenticated_bot
    uses for the Mini App API.

    Use this (never get_built_bot) at any entry point where bot_id comes from
    something an end user can supply directly — e.g. callback_data on a
    button tap — rather than from already-verified FSM state
    (active_bot_id, set only after this check has already passed once, by
    bot/handlers/my_bots.py:select_bot or bot/handlers/create_bot.py). Every
    other get_built_bot call in this codebase reads bot_id from that trusted
    state (or from a payment/order record it's already tied to), so it's
    fine as is — this is specifically for the untrusted entry point."""
    async with async_session_maker() as session:
        result = await session.execute(
            select(BuiltBot)
            .join(User, User.id == BuiltBot.owner_id)
            .where(BuiltBot.id == bot_id, User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()


async def set_live_until(bot_id: uuid.UUID | str, until: datetime | None) -> BuiltBot | None:
    async with async_session_maker() as session:
        result = await session.execute(select(BuiltBot).where(BuiltBot.id == bot_id))
        built_bot = result.scalar_one_or_none()
        if built_bot is None:
            return None
        built_bot.live_until = until
        await session.commit()
        await session.refresh(built_bot)
        return built_bot


def trial_until() -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=TRIAL_HOURS)


def suspension_status_text(built_bot: BuiltBot, is_fa: bool = False) -> str:
    reason = built_bot.suspension_reason or ("دلیلی ذکر نشده" if is_fa else "no reason given")
    if is_fa:
        return (
            f"🚫 این ربات توسط ادمین پلتفرم مسدود شده.\n\nدلیل: {reason}\n\n"
            "ربات روی تلگرام خاموشه و ابزارهای ساخت‌وسازش قفل شده تا ادمین این مسدودیت رو بردار — "
            "هیچ پلن پرداختی نمی‌تونه این مسدودیت رو خودش لغو کنه. با ادمین پلتفرم تماس بگیر."
        )
    return (
        f"🚫 This bot has been suspended by the platform admin.\n\nReason: {reason}\n\n"
        "It's offline on Telegram and its build/edit tools are locked until the admin lifts "
        "this — no payment plan can undo a suspension. Contact the platform admin."
    )


def status_text(built_bot: BuiltBot, is_fa: bool = False) -> str:
    if is_bot_live(built_bot):
        if is_fa:
            return (
                f"✅ این ربات تا {built_bot.live_until:%Y-%m-%d %H:%M} UTC روی تلگرام فعاله.\n\n"
                "برای فعال نگه‌داشتنش بعد از این تاریخ، یکی از پلن‌های پایین رو انتخاب کن."
            )
        return (
            f"✅ This bot is live on Telegram until {built_bot.live_until:%Y-%m-%d %H:%M} UTC.\n\n"
            "To keep it live after that, choose a payment plan below."
        )
    if is_bot_expired(built_bot):
        if is_fa:
            return (
                "🔒 مدت فعال بودن این ربات تموم شده — الان روی تلگرام خاموشه و ابزارهای "
                "ساخت‌وسازش قفل شدن.\n\n"
                "برای فعال کردن دوباره‌ش، یکی از پلن‌های پایین رو انتخاب کن. همه‌ی ویژگی‌های "
                "طراحی‌شدش به‌محض موفقیت پرداخت خودکار برمی‌گردن."
            )
        return (
            "🔒 This bot's live period has ended — it's currently offline on Telegram and its "
            "build/edit tools are locked.\n\n"
            "Choose a payment plan below to make it live again. All its designed features turn "
            "back on automatically as soon as payment succeeds."
        )
    if is_fa:
        return (
            f"⚠️ فعال‌سازی آزمایشی رباتت رو {TRIAL_HOURS} ساعت روی تلگرام فعال می‌کنه، "
            "تا خودت تستش کنی و نتیجه رو نشون بدی.\n\n"
            "برای فعال نگه‌داشتنش برای همیشه، یکی از پلن‌های پرداختی پایین رو انتخاب کن."
        )
    return (
        f"⚠️ Going live on a trial basis makes your bot live on Telegram for {TRIAL_HOURS} hours, "
        "so you can test it yourself and show the result.\n\n"
        "To keep it live permanently, choose one of the payment plans below."
    )
