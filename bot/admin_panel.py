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
from bot.db.models import BotSubscriber, BuiltBot, Order, Product, User
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

    return {
        "bot": built_bot,
        "owner": owner,
        "subscriber_count": subscriber_count,
        "paid_order_count": paid_order_count,
        "revenue_toman": int(revenue),
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

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
