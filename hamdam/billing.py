"""Subscriptions. The payment method follows the PAYER, not the elder: a
payer whose chat lives on the Iran node pays in Toman through Zarinpal, a
payer abroad pays in TON. Payment rows stay on the payer's node; the
resulting extension is sent to the circle's home node as a queued command,
so a payment made during an outage is still applied once the link returns.

TON is reviewed by hand, same reasoning as bot/platform_billing.py: no
on-chain auto-verification — a wrong automatic check risks real money.
"""

import logging

import aiohttp
from sqlalchemy import select, update

from hamdam.messaging import Button
from hamdam.models import Payment
from hamdam.services import person_lang
from hamdam.texts import t

logger = logging.getLogger(__name__)

ZARINPAL_REQUEST_URL = "https://api.zarinpal.com/pg/v4/payment/request.json"
ZARINPAL_VERIFY_URL = "https://api.zarinpal.com/pg/v4/payment/verify.json"
ZARINPAL_STARTPAY_URL = "https://www.zarinpal.com/pg/StartPay/{authority}"

PLANS = [
    {"key": "m1", "days": 30, "factor": 1.0},
    {"key": "m3", "days": 90, "factor": 2.7},  # 10% off
]


def plan(key: str) -> dict | None:
    return next((p for p in PLANS if p["key"] == key), None)


def price(node, plan_key: str, method: str) -> tuple[int, str]:
    p = plan(plan_key)
    if method == "zarinpal":
        return int(round(node.config.price_toman_month * p["factor"], -3)), "toman"
    return int(round(node.config.price_usd_month * p["factor"])), "usd"


def methods(node) -> list[str]:
    found = []
    if node.config.zarinpal_merchant_id and node.config.public_url:
        found.append("zarinpal")
    if node.config.ton_wallet and node.config.admin_chat_id:
        found.append("ton")
    return found


async def create_payment(node, circle_id: str, home_node: str, channel: str, chat_id: str,
                         plan_key: str, method: str) -> Payment | None:
    p = plan(plan_key)
    if p is None or method not in methods(node):
        return None
    amount, currency = price(node, plan_key, method)
    async with node.session() as s:
        payment = Payment(circle_id=circle_id, home_node=home_node, payer_channel=channel,
                          payer_chat_id=chat_id, method=method, days=p["days"], amount=amount,
                          currency=currency)
        s.add(payment)
        await s.commit()
        return payment


async def _mark_paid(node, payment_id: int, **values) -> Payment | None:
    """Atomic pending -> paid; returns the payment only for the ONE caller
    that flipped it (gateway callbacks and double taps can repeat)."""
    async with node.session() as s:
        result = await s.execute(
            update(Payment).where(Payment.id == payment_id, Payment.status == "pending")
            .values(status="paid", **values)
        )
        await s.commit()
        if result.rowcount == 0:
            return None
        return await s.get(Payment, payment_id)


async def _apply(node, payment: Payment) -> None:
    await node.command(payment.home_node, "extend_subscription", circle_id=payment.circle_id, days=payment.days)
    lang = await person_lang(node, payment.payer_channel, payment.payer_chat_id) or "fa"
    await node.deliver(node.id, payment.payer_channel, payment.payer_chat_id,
                       t(lang, "paid_ok", days=payment.days))


# --- Zarinpal (Toman) --------------------------------------------------------


async def _zarinpal_post(url: str, payload: dict) -> dict | None:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                return await resp.json(content_type=None)
    except Exception:
        logger.exception("Zarinpal call failed")
        return None


async def start_zarinpal(node, payment: Payment) -> str | None:
    data = await _zarinpal_post(ZARINPAL_REQUEST_URL, {
        "merchant_id": node.config.zarinpal_merchant_id,
        "amount": payment.amount * 10,  # Toman -> Rial
        "callback_url": f"{node.config.public_url}/pay/zarinpal/callback?pid={payment.id}",
        "description": f"Hamdam subscription #{payment.id}",
    })
    authority = ((data or {}).get("data") or {}).get("authority")
    if not authority:
        logger.warning("Zarinpal request returned no authority: %s", data)
        return None
    async with node.session() as s:
        (await s.get(Payment, payment.id)).authority = authority
        await s.commit()
    return ZARINPAL_STARTPAY_URL.format(authority=authority)


async def verify_zarinpal(node, payment_id: int, authority: str) -> bool:
    async with node.session() as s:
        payment = await s.get(Payment, payment_id)
    if payment is None or payment.authority != authority or payment.method != "zarinpal":
        return False
    if payment.status == "paid":
        return True
    data = await _zarinpal_post(ZARINPAL_VERIFY_URL, {
        "merchant_id": node.config.zarinpal_merchant_id,
        "amount": payment.amount * 10,
        "authority": authority,
    })
    result = (data or {}).get("data") or {}
    if result.get("code") not in (100, 101):
        return False
    paid = await _mark_paid(node, payment.id, ref=str(result.get("ref_id") or ""))
    if paid is not None:
        await _apply(node, paid)
    return True


# --- TON (USD equivalent, manual review) --------------------------------------


async def submit_ton(node, payment_id: int, tx_hash: str) -> Payment | None:
    async with node.session() as s:
        payment = await s.get(Payment, payment_id)
        if payment is None or payment.status != "pending" or payment.method != "ton":
            return None
        payment.ref = tx_hash.strip()[:128]
        await s.commit()
    await node.deliver(
        node.id, node.config.admin_channel, node.config.admin_chat_id,
        f"💎 TON payment #{payment.id}\n${payment.amount} · {payment.days} days\n"
        f"circle {payment.circle_id} @ {payment.home_node}\ntx: {payment.ref}",
        [[Button("✅ Approve", f"adm_ok:{payment.id}"), Button("❌ Reject", f"adm_no:{payment.id}")]],
    )
    return payment


async def approve_ton(node, payment_id: int) -> bool:
    paid = await _mark_paid(node, payment_id)
    if paid is None:
        return False
    await _apply(node, paid)
    return True


async def reject_ton(node, payment_id: int) -> bool:
    async with node.session() as s:
        result = await s.execute(
            update(Payment).where(Payment.id == payment_id, Payment.status == "pending").values(status="rejected")
        )
        await s.commit()
        if result.rowcount == 0:
            return False
        payment = await s.get(Payment, payment_id)
    lang = await person_lang(node, payment.payer_channel, payment.payer_chat_id) or "fa"
    await node.deliver(node.id, payment.payer_channel, payment.payer_chat_id, t(lang, "paid_rejected"))
    return True


async def pending_ton_for(node, channel: str, chat_id: str) -> Payment | None:
    async with node.session() as s:
        return (
            await s.execute(
                select(Payment).where(Payment.payer_channel == channel, Payment.payer_chat_id == chat_id,
                                      Payment.method == "ton", Payment.status == "pending")
                .order_by(Payment.id.desc())
            )
        ).scalars().first()
