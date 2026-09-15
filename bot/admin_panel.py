"""Platform-wide queries and mutations for /easybotadmin (bot/handlers/
easybotadmin.py) — the platform owner's (PLATFORM_ADMIN_ID) view across
every user and every built bot, for support, fraud prevention, and
reporting. No Telegram-handler code here, same split as bot/shop.py /
bot/live.py / bot/content_nav.py.

Every function here is reachable only through handlers gated by
bot/filters/admin.py:IsPlatformAdmin — this module itself does no
authorization, callers must.
"""

import io
import uuid
from datetime import datetime, timedelta, timezone

from openpyxl import Workbook
from sqlalchemy import func, select

from bot.db.base import async_session_maker
from bot.db.models import BotSubscriber, BuiltBot, LivePayment, Order, Product, User
from bot.platform_settings import bots_enabled as _bots_enabled
from bot.platform_settings import set_bots_enabled as _set_bots_enabled
from bot.runtime import start_built_bot, stop_built_bot

PAID_STATUSES = ("paid", "fulfilled")  # money has actually changed hands


async def get_platform_stats() -> dict:
    now = datetime.now(timezone.utc)
    async with async_session_maker() as session:
        user_count = (await session.execute(select(func.count(User.id)))).scalar_one()
        bot_count = (await session.execute(select(func.count(BuiltBot.id)))).scalar_one()

        result = await session.execute(select(BuiltBot.live_until, BuiltBot.suspended))
        rows = result.all()
        live = sum(1 for lu, sus in rows if not sus and lu is not None and lu > now)
        expired = sum(1 for lu, sus in rows if not sus and lu is not None and lu <= now)
        never_activated = sum(1 for lu, sus in rows if not sus and lu is None)
        suspended = sum(1 for _, sus in rows if sus)

        subscriber_count = (await session.execute(select(func.count(BotSubscriber.id)))).scalar_one()
        product_count = (await session.execute(select(func.count(Product.id)))).scalar_one()

        order_count = (await session.execute(select(func.count(Order.id)))).scalar_one()
        result = await session.execute(
            select(func.count(Order.id), func.coalesce(func.sum(Order.price), 0)).where(
                Order.status.in_(PAID_STATUSES)
            )
        )
        paid_order_count, revenue = result.one()

        live_result = await session.execute(
            select(
                LivePayment.payment_method,
                func.count(LivePayment.id),
                func.coalesce(func.sum(LivePayment.price), 0),
            )
            .where(LivePayment.status == "paid")
            .group_by(LivePayment.payment_method)
        )
        platform_revenue_toman = 0
        platform_revenue_usd = 0
        platform_revenue_ton_usd = 0
        platform_paid_count_toman = 0
        platform_paid_count_usd = 0
        platform_paid_count_ton = 0
        for method, count, total in live_result.all():
            if method == "zarinpal":
                platform_revenue_toman = int(total)
                platform_paid_count_toman = count
            elif method == "stripe":
                platform_revenue_usd = int(total)
                platform_paid_count_usd = count
            elif method == "ton":
                platform_revenue_ton_usd = int(total)
                platform_paid_count_ton = count
        platform_paid_count = (
            platform_paid_count_toman + platform_paid_count_usd + platform_paid_count_ton
        )

    return {
        "user_count": user_count,
        "bot_count": bot_count,
        "bots_live": live,
        "bots_expired": expired,
        "bots_never_activated": never_activated,
        "bots_suspended": suspended,
        "subscriber_count": subscriber_count,
        "product_count": product_count,
        "order_count": order_count,
        "paid_order_count": paid_order_count,
        "revenue_toman": int(revenue),
        "platform_revenue_toman": platform_revenue_toman,
        "platform_revenue_usd": platform_revenue_usd,
        "platform_revenue_ton_usd": platform_revenue_ton_usd,
        "platform_paid_count": platform_paid_count,
        "platform_paid_count_toman": platform_paid_count_toman,
        "platform_paid_count_usd": platform_paid_count_usd,
        "platform_paid_count_ton": platform_paid_count_ton,
    }


async def list_users_page(offset: int = 0, limit: int = 20) -> tuple[list[User], bool]:
    async with async_session_maker() as session:
        result = await session.execute(
            select(User).order_by(User.created_at).offset(offset).limit(limit + 1)
        )
        rows = list(result.scalars())
    return rows[:limit], len(rows) > limit


async def get_user_detail(user_id: int) -> dict | None:
    async with async_session_maker() as session:
        user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        if user is None:
            return None
        result = await session.execute(
            select(BuiltBot).where(BuiltBot.owner_id == user_id).order_by(BuiltBot.created_at)
        )
        bots = list(result.scalars())
    return {"user": user, "bots": bots}


async def list_bots_page(offset: int = 0, limit: int = 20) -> tuple[list[BuiltBot], bool]:
    async with async_session_maker() as session:
        result = await session.execute(
            select(BuiltBot).order_by(BuiltBot.created_at).offset(offset).limit(limit + 1)
        )
        rows = list(result.scalars())
    return rows[:limit], len(rows) > limit


async def get_bot_detail(bot_id: uuid.UUID | str) -> dict | None:
    async with async_session_maker() as session:
        result = await session.execute(
            select(BuiltBot, User).join(User, User.id == BuiltBot.owner_id).where(BuiltBot.id == bot_id)
        )
        row = result.first()
        if row is None:
            return None
        built_bot, owner = row

        subscriber_count = (
            await session.execute(
                select(func.count(BotSubscriber.id)).where(BotSubscriber.bot_id == bot_id)
            )
        ).scalar_one()

        order_result = await session.execute(
            select(func.count(Order.id), func.coalesce(func.sum(Order.price), 0))
            .where(Order.bot_id == bot_id, Order.status.in_(PAID_STATUSES))
        )
        paid_order_count, revenue = order_result.one()

        method_result = await session.execute(
            select(
                Order.payment_method,
                func.count(Order.id),
                func.coalesce(func.sum(Order.price), 0),
            )
            .where(Order.bot_id == bot_id, Order.status.in_(PAID_STATUSES))
            .group_by(Order.payment_method)
        )
        orders_by_method = {
            (method or "unknown"): {"count": count, "revenue": int(total)}
            for method, count, total in method_result.all()
        }

    return {
        "bot": built_bot,
        "owner": owner,
        "subscriber_count": subscriber_count,
        "paid_order_count": paid_order_count,
        "revenue_toman": int(revenue),
        "orders_by_method": orders_by_method,
    }


async def suspend_bot(bot_id: uuid.UUID | str, reason: str) -> BuiltBot | None:
    async with async_session_maker() as session:
        result = await session.execute(select(BuiltBot).where(BuiltBot.id == bot_id))
        built_bot = result.scalar_one_or_none()
        if built_bot is None:
            return None
        built_bot.suspended = True
        built_bot.suspension_reason = reason
        await session.commit()
        await session.refresh(built_bot)

    stop_built_bot(built_bot.id)
    return built_bot


async def unsuspend_bot(bot_id: uuid.UUID | str) -> BuiltBot | None:
    async with async_session_maker() as session:
        result = await session.execute(select(BuiltBot).where(BuiltBot.id == bot_id))
        built_bot = result.scalar_one_or_none()
        if built_bot is None:
            return None
        built_bot.suspended = False
        built_bot.suspension_reason = None
        await session.commit()
        await session.refresh(built_bot)

    now = datetime.now(timezone.utc)
    if built_bot.live_until is not None and built_bot.live_until > now:
        start_built_bot(built_bot.id, built_bot.token)
    return built_bot


# --- Platform-wide maintenance switch (all bots at once, no process kill) --


async def get_bots_enabled() -> bool:
    return await _bots_enabled()


async def set_bots_enabled(enabled: bool) -> None:
    await _set_bots_enabled(enabled)


async def grant_bot_access(bot_id: uuid.UUID | str, days: int | None) -> BuiltBot | None:
    """days=None grants a very long ("permanent") window — same grandfathering
    approach already used once this session for pre-existing bots."""
    until = datetime.now(timezone.utc) + (timedelta(days=days) if days is not None else timedelta(days=3650))
    async with async_session_maker() as session:
        result = await session.execute(select(BuiltBot).where(BuiltBot.id == bot_id))
        built_bot = result.scalar_one_or_none()
        if built_bot is None:
            return None
        built_bot.live_until = until
        await session.commit()
        await session.refresh(built_bot)

    if not built_bot.suspended:
        start_built_bot(built_bot.id, built_bot.token)
    return built_bot


async def rename_bot(bot_id: uuid.UUID | str, new_display_name: str) -> BuiltBot | None:
    async with async_session_maker() as session:
        result = await session.execute(select(BuiltBot).where(BuiltBot.id == bot_id))
        built_bot = result.scalar_one_or_none()
        if built_bot is None:
            return None
        built_bot.display_name = new_display_name
        await session.commit()
        await session.refresh(built_bot)
        return built_bot


async def delete_bot(bot_id: uuid.UUID | str) -> bool:
    """Cascades — see bot/db/models.py: BuiltBot's relationships are all
    cascade="all, delete-orphan" (commands, content_items, products, orders,
    shop_settings, join_channels). Callers must confirm hard before this."""
    stop_built_bot(bot_id)  # accepts either a UUID or its string form
    async with async_session_maker() as session:
        result = await session.execute(select(BuiltBot).where(BuiltBot.id == bot_id))
        built_bot = result.scalar_one_or_none()
        if built_bot is None:
            return False
        await session.delete(built_bot)
        await session.commit()
        return True


async def list_recent_activity(limit: int = 10) -> dict:
    async with async_session_maker() as session:
        bots_result = await session.execute(
            select(BuiltBot).order_by(BuiltBot.created_at.desc()).limit(limit)
        )
        recent_bots = list(bots_result.scalars())

        orders_result = await session.execute(
            select(Order, BuiltBot.bot_username)
            .join(BuiltBot, BuiltBot.id == Order.bot_id)
            .order_by(Order.created_at.desc())
            .limit(limit)
        )
        recent_orders = list(orders_result.all())

        users_result = await session.execute(
            select(User).order_by(User.created_at.desc()).limit(limit)
        )
        recent_users = list(users_result.scalars())

    return {"bots": recent_bots, "orders": recent_orders, "users": recent_users}


async def generate_report_excel() -> bytes:
    wb = Workbook()

    ws_users = wb.active
    ws_users.title = "Users"
    ws_users.append(["User ID", "Telegram ID", "Joined At", "Bot Count"])
    async with async_session_maker() as session:
        users = list((await session.execute(select(User).order_by(User.id))).scalars())
        for user in users:
            bot_count = (
                await session.execute(
                    select(func.count(BuiltBot.id)).where(BuiltBot.owner_id == user.id)
                )
            ).scalar_one()
            ws_users.append([user.id, user.telegram_id, str(user.created_at), bot_count])

        ws_bots = wb.create_sheet("Bots")
        ws_bots.append(
            ["Bot Username", "Display Name", "Owner Telegram ID", "Status", "Subscribers", "Created At"]
        )
        result = await session.execute(
            select(BuiltBot, User.telegram_id).join(User, User.id == BuiltBot.owner_id)
        )
        now = datetime.now(timezone.utc)
        for built_bot, owner_telegram_id in result.all():
            if built_bot.suspended:
                status = "suspended"
            elif built_bot.live_until is None:
                status = "never activated"
            elif built_bot.live_until > now:
                status = "live"
            else:
                status = "expired"
            sub_count = (
                await session.execute(
                    select(func.count(BotSubscriber.id)).where(BotSubscriber.bot_id == built_bot.id)
                )
            ).scalar_one()
            ws_bots.append(
                [
                    built_bot.bot_username, built_bot.display_name, owner_telegram_id, status,
                    sub_count, str(built_bot.created_at),
                ]
            )

        ws_orders = wb.create_sheet("Orders")
        ws_orders.append(
            ["Order ID", "Bot Username", "Product", "Price (Toman)", "Status", "Payment Method", "Created At"]
        )
        result = await session.execute(
            select(Order, BuiltBot.bot_username, Product.name)
            .join(BuiltBot, BuiltBot.id == Order.bot_id)
            .join(Product, Product.id == Order.product_id)
            .order_by(Order.created_at.desc())
        )
        for order, bot_username, product_name in result.all():
            ws_orders.append(
                [
                    order.id, bot_username, product_name, order.price, order.status,
                    order.payment_method or "-", str(order.created_at),
                ]
            )

        ws_live = wb.create_sheet("Platform Revenue (Live)")
        ws_live.append(
            ["Payment ID", "Bot Username", "Plan", "Price", "Currency", "Payment Method", "Status", "Created At"]
        )
        live_result = await session.execute(
            select(LivePayment, BuiltBot.bot_username)
            .join(BuiltBot, BuiltBot.id == LivePayment.bot_id)
            .order_by(LivePayment.created_at.desc())
        )
        for payment, bot_username in live_result.all():
            ws_live.append(
                [
                    payment.id, bot_username, payment.plan_key, payment.price, payment.currency.upper(),
                    payment.payment_method, payment.status, str(payment.created_at),
                ]
            )

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


async def generate_bot_report_excel(bot_id: uuid.UUID | str) -> bytes | None:
    """Per-bot Excel export - that bot's own shop orders only (money for the
    BOT OWNER, not the platform). Scoped Orders sheet + a payment-method
    summary sheet."""
    async with async_session_maker() as session:
        bot_result = await session.execute(select(BuiltBot).where(BuiltBot.id == bot_id))
        built_bot = bot_result.scalar_one_or_none()
        if built_bot is None:
            return None

        wb = Workbook()
        ws_orders = wb.active
        ws_orders.title = "Orders"
        ws_orders.append(
            [
                "Order ID", "Product", "Price", "Currency", "Status", "Payment Method",
                "Buyer Telegram ID", "Invoice #", "Created At",
            ]
        )
        result = await session.execute(
            select(Order, Product.name)
            .join(Product, Product.id == Order.product_id)
            .where(Order.bot_id == bot_id)
            .order_by(Order.created_at.desc())
        )
        rows = result.all()
        for order, product_name in rows:
            currency = "USD" if order.payment_method == "stripe" else "Toman"
            ws_orders.append(
                [
                    order.id, product_name, order.price, currency, order.status,
                    order.payment_method or "-", order.buyer_telegram_id,
                    order.invoice_number or "-", str(order.created_at),
                ]
            )

        ws_summary = wb.create_sheet("Summary by Method")
        ws_summary.append(["Payment Method", "Paid Orders", "Revenue"])
        by_method: dict[str, list[int]] = {}
        for order, _ in rows:
            if order.status not in PAID_STATUSES:
                continue
            key = order.payment_method or "unknown"
            entry = by_method.setdefault(key, [0, 0])
            entry[0] += 1
            entry[1] += order.price
        for method, (count, total) in by_method.items():
            ws_summary.append([method, count, total])

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
