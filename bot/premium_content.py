"""Subscription-gated content: a free-preview quota, then a subscription
required to keep going (bot/runtime.py:_send_content_post is the single
gating point — both the browse-drill path and the shortcut-code path funnel
through it).

A subscription is just a Product with product_type == "subscription" —
reuses bot/shop.py's create_order/Checkout/all 5 payment methods and
fulfill_order (which extends BotSubscriber.subscription_until on purchase).
This module only decides WHETHER a given (subscriber, item) pair may be
shown, and records free-preview unlocks — no Telegram-handler code here,
same split as bot/shop.py / bot/content_nav.py.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select

from bot.db.base import async_session_maker
from bot.db.models import BotSubscriber, ContentItem, ContentUnlock, Product, ShopSettings


async def get_free_preview_limit(bot_id: uuid.UUID) -> int:
    async with async_session_maker() as session:
        result = await session.execute(select(ShopSettings).where(ShopSettings.bot_id == bot_id))
        settings = result.scalar_one_or_none()
        return settings.free_preview_limit if settings is not None else 1


async def set_free_preview_limit(bot_id: uuid.UUID, limit: int) -> None:
    async with async_session_maker() as session:
        result = await session.execute(select(ShopSettings).where(ShopSettings.bot_id == bot_id))
        settings = result.scalar_one_or_none()
        if settings is None:
            settings = ShopSettings(bot_id=bot_id, free_preview_limit=limit)
            session.add(settings)
        else:
            settings.free_preview_limit = limit
        await session.commit()


async def get_subscription_plans(bot_id: uuid.UUID) -> list[Product]:
    async with async_session_maker() as session:
        result = await session.execute(
            select(Product)
            .where(Product.bot_id == bot_id, Product.product_type == "subscription")
            .order_by(Product.id)
        )
        return list(result.scalars())


async def effective_unlock_price(bot_id: uuid.UUID, item: ContentItem) -> int | None:
    """The à-la-carte price for unlocking just `item`: its own unlock_price,
    else the bot-wide ShopSettings.default_unlock_price, else None (no
    single-item purchase offered). Reflects any running price campaign,
    since those overwrite the live price columns (bot/shop.py)."""
    if item.unlock_price is not None:
        return item.unlock_price
    async with async_session_maker() as session:
        settings = (
            await session.execute(select(ShopSettings).where(ShopSettings.bot_id == bot_id))
        ).scalar_one_or_none()
    return settings.default_unlock_price if settings is not None else None


def has_active_subscription(subscriber: BotSubscriber | None) -> bool:
    return (
        subscriber is not None
        and subscriber.subscription_until is not None
        and subscriber.subscription_until > datetime.now(timezone.utc)
    )


async def _get_subscriber(bot_id: uuid.UUID, telegram_id: int) -> BotSubscriber | None:
    async with async_session_maker() as session:
        result = await session.execute(
            select(BotSubscriber).where(
                BotSubscriber.bot_id == bot_id, BotSubscriber.telegram_id == telegram_id
            )
        )
        return result.scalar_one_or_none()


async def check_and_record_access(bot_id: uuid.UUID, subscriber_telegram_id: int, item: ContentItem) -> bool:
    """The one gating function bot/runtime.py:_send_content_post calls.
    Free item -> always True. Active subscription -> True, no row written
    (this access can lapse). Already unlocked via free quota -> True (this
    access never lapses). Otherwise, if a free-quota slot remains, writes
    the unlock row and returns True; else returns False."""
    if not item.is_premium:
        return True

    subscriber = await _get_subscriber(bot_id, subscriber_telegram_id)
    if has_active_subscription(subscriber):
        return True

    async with async_session_maker() as session:
        result = await session.execute(
            select(ContentUnlock).where(
                ContentUnlock.bot_id == bot_id,
                ContentUnlock.subscriber_telegram_id == subscriber_telegram_id,
                ContentUnlock.content_item_id == item.id,
            )
        )
        if result.scalar_one_or_none() is not None:
            return True  # already spent a free slot on this exact item — permanent

        used_count = (
            await session.execute(
                select(func.count(ContentUnlock.id)).where(
                    ContentUnlock.bot_id == bot_id,
                    ContentUnlock.subscriber_telegram_id == subscriber_telegram_id,
                    ContentUnlock.source == "quota",  # paid unlocks don't spend the free quota
                )
            )
        ).scalar_one()

        settings = (
            await session.execute(select(ShopSettings).where(ShopSettings.bot_id == bot_id))
        ).scalar_one_or_none()
        limit = settings.free_preview_limit if settings is not None else 1
        if used_count >= limit:
            return False

        session.add(
            ContentUnlock(
                bot_id=bot_id, subscriber_telegram_id=subscriber_telegram_id, content_item_id=item.id
            )
        )
        await session.commit()
        return True
