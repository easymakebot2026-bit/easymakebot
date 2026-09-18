"""The "💳 My Subscription" screen — a cross-bot summary of every bot this
owner has built, showing which are live (and whether that live window came
from a paid plan or the one-time free trial), which have expired, and which
were never activated. Read-only: all the actual activation/payment actions
still happen in /live (bot/handlers/live.py) for a specific selected bot.

"Paid" here means this bot has at least one successful platform payment on
record — either a LivePayment row with status="paid" (bot/platform_billing.py,
/live's in-bot Zarinpal/Stripe/TON flow) or a RedeemedActivationCode row
(bot/handlers/live.py's "activate with a code bought on the website" flow).
A bot whose live_until is set but has neither is on its free trial.
"""

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select

from bot import help_text, live
from bot.db.base import async_session_maker
from bot.db.models import BuiltBot, LivePayment, RedeemedActivationCode, User
from bot.guide import owner_prefers_persian
from bot.keyboards import MY_ACCOUNT_BUTTON_TEXTS

router = Router(name="my_account")


async def _paid_bot_ids(bot_ids: list) -> set:
    """Bot ids among `bot_ids` that have ever had a genuine paid activation —
    a paid LivePayment, or a redeemed website activation code. Two separate
    queries (not a join) since these are two independent tables with no FK
    to each other, both only ever pointing at built_bots.id."""
    if not bot_ids:
        return set()
    async with async_session_maker() as session:
        from_payments = await session.execute(
            select(LivePayment.bot_id)
            .where(LivePayment.bot_id.in_(bot_ids), LivePayment.status == "paid")
            .distinct()
        )
        from_codes = await session.execute(
            select(RedeemedActivationCode.bot_id).where(RedeemedActivationCode.bot_id.in_(bot_ids)).distinct()
        )
    return {row[0] for row in from_payments} | {row[0] for row in from_codes}


def _bot_status_line(built_bot: BuiltBot, is_paid: bool, is_fa: bool) -> str:
    if live.is_bot_suspended(built_bot):  # checked first — see bot/live.py module docstring
        return "🚫 مسدود توسط ادمین" if is_fa else "🚫 Suspended by admin"
    if live.is_bot_live(built_bot):
        until = f"{built_bot.live_until:%Y-%m-%d %H:%M} UTC"
        if is_paid:
            return (f"💎 فعال (اشتراک پرداختی) تا {until}" if is_fa else f"💎 Live (paid plan) until {until}")
        return (f"🎁 فعال (دوره‌ی آزمایشی) تا {until}" if is_fa else f"🎁 Live (free trial) until {until}")
    if live.is_bot_expired(built_bot):
        return "🔒 منقضی شده" if is_fa else "🔒 Expired"
    return "⚪️ هنوز فعال نشده" if is_fa else "⚪️ Never activated"


async def _render_my_account(telegram_id: int, is_fa: bool) -> str:
    async with async_session_maker() as session:
        user_result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = user_result.scalar_one_or_none()

        bots: list[BuiltBot] = []
        if user is not None:
            bots_result = await session.execute(
                select(BuiltBot).where(BuiltBot.owner_id == user.id).order_by(BuiltBot.created_at)
            )
            bots = list(bots_result.scalars())

    if not bots:
        return (
            "هنوز هیچ رباتی نساختی — از «🤖 ربات‌های من» شروع کن."
            if is_fa
            else "You haven't built any bots yet — start from \"🤖 My Bots\"."
        )

    paid_ids = await _paid_bot_ids([b.id for b in bots])

    lines = ["💳 " + ("اشتراک من" if is_fa else "My Subscription"), ""]
    for b in bots:
        lines.append(f"{b.display_name} (@{b.bot_username})")
        lines.append(_bot_status_line(b, b.id in paid_ids, is_fa))
        lines.append("")

    paid_bots = [b for b in bots if b.id in paid_ids]
    trial_bots = [b for b in bots if live.is_bot_live(b) and b.id not in paid_ids]
    if paid_bots:
        header = "— ربات‌های با اشتراک پرداختی —" if is_fa else "— Paid-subscription bots —"
        names = "، ".join(f"@{b.bot_username}" for b in paid_bots) if is_fa else ", ".join(f"@{b.bot_username}" for b in paid_bots)
        lines += [header, names, ""]

    total = len(bots)
    summary = (
        f"جمع: {total} ربات — {len(paid_bots)} پرداختی، {len(trial_bots)} آزمایشی"
        if is_fa
        else f"Total: {total} bot(s) — {len(paid_bots)} paid, {len(trial_bots)} trial"
    )
    lines.append(summary)

    return "\n".join(lines).rstrip()


@router.message(F.text.in_(MY_ACCOUNT_BUTTON_TEXTS))
async def show_my_account(message: Message) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    text = await _render_my_account(message.from_user.id, is_fa)
    text += await help_text.tip_suffix("my_account", message.from_user)
    await message.answer(text)


@router.message(Command("myaccount"))
async def cmd_my_account(message: Message) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    text = await _render_my_account(message.from_user.id, is_fa)
    await message.answer(text)
