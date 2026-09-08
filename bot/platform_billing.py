"""Platform billing for /live plans (bot/handlers/live.py) — a bot owner
paying THE PLATFORM to activate/extend their bot, as opposed to bot/shop.py
which is a bot owner's own storefront selling to their own end users. The
low-level gateway helpers are reused directly from bot/shop.py (intentional:
_zarinpal_request/_zarinpal_verify/_stripe_create_session/
_stripe_retrieve_session are the one place that actually talks to each
gateway's API) but records stay separate (LivePayment, not Order/Checkout)
so the two money flows can never mix.

No Telegram-handler code here — reused by bot/handlers/live.py and
bot/webapp_server.py, same split as bot/shop.py / bot/live.py.
"""

import uuid
from datetime import datetime, timedelta, timezone

from aiogram import Bot
from sqlalchemy import select

from bot.config import load_config
from bot.db.base import async_session_maker
from bot.db.models import BuiltBot, LivePayment, User
from bot.guide import is_iran_phone
from bot.live import LIVE_PLANS, set_live_until
from bot.runtime import start_built_bot
from bot.session import make_session
from bot.shop import (
    ZARINPAL_STARTPAY_URL,
    _stripe_create_session,
    _stripe_retrieve_session,
    _zarinpal_request,
    _zarinpal_verify,
)

_config = load_config()

__all__ = ["LIVE_PLANS"]  # re-exported from bot.live — see that module's docstring for why


def get_plan(plan_key: str) -> dict | None:
    return next((p for p in LIVE_PLANS if p["key"] == plan_key), None)


def available_methods_for_region(region: str | None) -> list[str]:
    """Which payment methods to actually offer, given the owner's region and
    which platform credentials are configured in .env — graceful-omit, same
    pattern as bot/shop.py's per-bot ShopSettings. Everyone international sees
    TON and/or Card (Stripe). An Iranian creator normally has NO on-bot method
    — they buy on the (Iranian) website and redeem a code, because a
    bot-initiated Zarinpal payment from a foreign server, plus the buyer's
    Telegram VPN, breaks the gateway. Set PLATFORM_ONBOT_ZARINPAL=true only
    when the bot itself runs on an Iran IP."""
    if region == "iran":
        if _config.platform_onbot_zarinpal and _config.platform_zarinpal_merchant_id:
            return ["zarinpal"]
        return []
    if region == "international":
        methods = []
        if _config.platform_ton_wallet_address:
            methods.append("ton")
        if _config.platform_stripe_secret_key:
            methods.append("stripe")
        return methods
    return []  # region unknown yet — caller must ask first


async def resolve_region(user: User) -> str | None:
    """Returns the owner's region ("iran" | "international"), always derived
    from an on-file phone number (same detection as the Guide & Video block —
    bot.guide.is_iran_phone) whenever one exists — this takes priority even
    over a previously self-reported region, so a phone shared later (e.g. for
    a paid activation) corrects an earlier guess instead of being ignored.
    Falls back to a manually self-reported region (set_region, via the
    "where are you based" picker) only for the case a phone is genuinely
    unavailable. Returns None if truly unknown yet — the caller must ask."""
    if user.phone_number:
        region = "iran" if is_iran_phone(user.phone_number) else "international"
        if user.region != region:
            await set_region(user.id, region)
        return region
    if user.region:
        return user.region
    return None


async def set_region(user_id: int, region: str) -> None:
    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is not None:
            user.region = region
            await session.commit()


async def create_live_payment(
    bot_id: uuid.UUID | str, plan_key: str, payment_method: str
) -> LivePayment | None:
    plan = get_plan(plan_key)
    if plan is None:
        return None

    currency = "toman" if payment_method == "zarinpal" else "usd"
    price = plan["price_toman"] if currency == "toman" else plan["price_usd"]

    async with async_session_maker() as session:
        payment = LivePayment(
            bot_id=bot_id, plan_key=plan_key, days=plan["days"], price=price, currency=currency,
            payment_method=payment_method,
        )
        session.add(payment)
        await session.commit()
        await session.refresh(payment)
        return payment


async def get_live_payment(payment_id: int) -> LivePayment | None:
    async with async_session_maker() as session:
        result = await session.execute(select(LivePayment).where(LivePayment.id == payment_id))
        return result.scalar_one_or_none()


async def _activate_bot(payment: LivePayment) -> None:
    """Shared activation step for every successful payment method below —
    same machinery bot/admin_panel.py:grant_bot_access already uses
    (set_live_until + start_built_bot)."""
    until = datetime.now(timezone.utc) + timedelta(
        days=payment.days if payment.days is not None else 3650
    )
    built_bot = await set_live_until(payment.bot_id, until)
    if built_bot is not None and not built_bot.suspended:
        start_built_bot(built_bot.id, built_bot.token)


async def _notify_owner(bot_id: uuid.UUID | str, text_en: str, text_fa: str | None = None) -> None:
    """`text_fa` is optional so old single-language call sites keep working
    unchanged; every call site in this file now passes both."""
    async with async_session_maker() as session:
        result = await session.execute(
            select(User).join(BuiltBot, BuiltBot.owner_id == User.id).where(BuiltBot.id == bot_id)
        )
        owner = result.scalar_one_or_none()
    if owner is None:
        return

    text = text_en
    if text_fa and is_iran_phone(owner.phone_number):
        text = text_fa

    temp_bot = Bot(token=_config.bot_token, session=make_session())
    try:
        await temp_bot.send_message(owner.telegram_id, text)
    except Exception:
        pass
    finally:
        await temp_bot.session.close()


# --- Zarinpal (Iran-only path) -------------------------------------------


async def start_zarinpal_live_payment(payment: LivePayment, callback_base_url: str) -> str | None:
    if not _config.platform_zarinpal_merchant_id:
        return None

    authority = await _zarinpal_request(
        _config.platform_zarinpal_merchant_id,
        payment.price * 10,  # Toman -> Rial
        f"easymakebot live plan: {payment.plan_key}",
        f"{callback_base_url}/payment/live/zarinpal/callback?payment_id={payment.id}",
    )
    if authority is None:
        return None

    async with async_session_maker() as session:
        result = await session.execute(select(LivePayment).where(LivePayment.id == payment.id))
        row = result.scalar_one()
        row.zarinpal_authority = authority
        await session.commit()

    return ZARINPAL_STARTPAY_URL.format(authority=authority)


async def verify_zarinpal_live_payment(authority: str) -> LivePayment | None:
    async with async_session_maker() as session:
        result = await session.execute(
            select(LivePayment).where(LivePayment.zarinpal_authority == authority)
        )
        payment = result.scalar_one_or_none()
    if payment is None:
        return None
    if payment.status != "pending":
        return payment
    if not _config.platform_zarinpal_merchant_id:
        return payment

    verify_data = await _zarinpal_verify(
        _config.platform_zarinpal_merchant_id, payment.price * 10, authority
    )
    if verify_data is None:
        return payment

    async with async_session_maker() as session:
        result = await session.execute(select(LivePayment).where(LivePayment.id == payment.id))
        row = result.scalar_one()
        row.status = "paid"
        row.zarinpal_ref_id = str(verify_data.get("ref_id") or "")
        await session.commit()
        await session.refresh(row)
        payment = row

    await _activate_bot(payment)
    await _notify_owner(
        payment.bot_id,
        "🎉 Payment received — your bot is now live!",
        "🎉 پرداخت دریافت شد — رباتت الان فعاله!",
    )
    return payment


# --- Stripe (international card path — Visa/Mastercard, both accepted ----
# --- directly by Stripe Checkout, no separate per-network integration) ---


async def start_stripe_live_payment(payment: LivePayment, callback_base_url: str) -> str | None:
    if not _config.platform_stripe_secret_key:
        return None

    success_url = callback_base_url + "/payment/live/stripe/callback?session_id={CHECKOUT_SESSION_ID}"
    cancel_url = callback_base_url + f"/payment/live/stripe/callback?cancelled=1&payment_id={payment.id}"

    created = await _stripe_create_session(
        _config.platform_stripe_secret_key,
        payment.price * 100,  # dollars -> cents
        f"easymakebot live plan: {payment.plan_key}",
        success_url,
        cancel_url,
    )
    if created is None:
        return None
    session_id, checkout_url = created

    async with async_session_maker() as session:
        result = await session.execute(select(LivePayment).where(LivePayment.id == payment.id))
        row = result.scalar_one()
        row.stripe_session_id = session_id
        await session.commit()

    return checkout_url


async def verify_stripe_live_payment(session_id: str) -> LivePayment | None:
    async with async_session_maker() as session:
        result = await session.execute(
            select(LivePayment).where(LivePayment.stripe_session_id == session_id)
        )
        payment = result.scalar_one_or_none()
    if payment is None:
        return None
    if payment.status != "pending":
        return payment
    if not _config.platform_stripe_secret_key:
        return payment

    data = await _stripe_retrieve_session(_config.platform_stripe_secret_key, session_id)
    if data is None or data.get("payment_status") != "paid":
        return payment

    async with async_session_maker() as session:
        result = await session.execute(select(LivePayment).where(LivePayment.id == payment.id))
        row = result.scalar_one()
        row.status = "paid"
        await session.commit()
        await session.refresh(row)
        payment = row

    await _activate_bot(payment)
    await _notify_owner(
        payment.bot_id,
        "🎉 Payment received — your bot is now live!",
        "🎉 پرداخت دریافت شد — رباتت الان فعاله!",
    )
    return payment


# --- TON (manual review, same reasoning as bot/shop.py's crypto/TON path: --
# --- no on-chain auto-verification — a wrong automatic check risks real ---
# --- money either way. Approval goes to PLATFORM_ADMIN_ID, not a bot owner. --


async def submit_ton_live_payment(payment_id: int, tx_hash: str) -> LivePayment:
    async with async_session_maker() as session:
        result = await session.execute(select(LivePayment).where(LivePayment.id == payment_id))
        payment = result.scalar_one()
        payment.transaction_ref = tx_hash
        await session.commit()
        await session.refresh(payment)
        return payment


async def approve_ton_live_payment(payment_id: int) -> LivePayment | None:
    async with async_session_maker() as session:
        result = await session.execute(select(LivePayment).where(LivePayment.id == payment_id))
        payment = result.scalar_one_or_none()
        if payment is None:
            return None
        payment.status = "paid"
        await session.commit()
        await session.refresh(payment)

    await _activate_bot(payment)
    await _notify_owner(
        payment.bot_id,
        "🎉 Your TON payment was confirmed — your bot is now live!",
        "🎉 پرداخت TON تو تأیید شد — رباتت الان فعاله!",
    )
    return payment


async def reject_ton_live_payment(payment_id: int) -> None:
    async with async_session_maker() as session:
        result = await session.execute(select(LivePayment).where(LivePayment.id == payment_id))
        payment = result.scalar_one_or_none()
        if payment is not None:
            payment.status = "rejected"
            await session.commit()

    if payment is not None:
        await _notify_owner(
            payment.bot_id,
            "❌ Your TON payment could not be confirmed. Please contact support.",
            "❌ پرداخت TON تو تأیید نشد. با پشتیبانی تماس بگیر.",
        )
