"""Shared data helpers for browsing a built bot's (possibly nested) Content
List. An item with children is a "folder" (browsing it lists the children);
one with none is a leaf (browsing it shows its own detail) — inferred from
whether children exist, no separate flag needed.

Reused by the visual flow builder's content_list block (bot/flow_engine.py),
the built-in /content command, and item/back navigation (both in bot/runtime.py).
"""

import uuid

from sqlalchemy import func, select

from bot.db.base import async_session_maker
from bot.db.models import ContentItem

LIST_LIMIT = 40  # Telegram's practical inline-keyboard limit


async def get_children(bot_id: uuid.UUID, parent_id: int | None) -> list[ContentItem]:
    async with async_session_maker() as session:
        result = await session.execute(
            select(ContentItem)
            .where(ContentItem.bot_id == bot_id, ContentItem.parent_id == parent_id)
            .order_by(ContentItem.position, ContentItem.id)
            .limit(LIST_LIMIT)
        )
        return list(result.scalars())


async def folder_ids_among(bot_id: uuid.UUID, item_ids: list[int]) -> set[int]:
    """Of `item_ids`, the subset that have at least one child — i.e. the ones
    that behave as a "folder" (open into a sub-menu) rather than a leaf when
    rendered as a button menu. One query; used by every place that lists
    content as buttons so folders get the 📂 marker consistently
    (bot/keyboards.py: content_menu_keyboard)."""
    if not item_ids:
        return set()
    async with async_session_maker() as session:
        result = await session.execute(
            select(ContentItem.parent_id)
            .where(ContentItem.bot_id == bot_id, ContentItem.parent_id.in_(item_ids))
            .distinct()
        )
        return {row[0] for row in result.all() if row[0] is not None}


async def get_item(item_id: int) -> ContentItem | None:
    async with async_session_maker() as session:
        result = await session.execute(select(ContentItem).where(ContentItem.id == item_id))
        return result.scalar_one_or_none()


async def get_all_items(bot_id: uuid.UUID) -> list[ContentItem]:
    """Flat (non-nested) list of every item for a bot — used to let the owner
    pick a parent category by title, regardless of how deep it already is."""
    async with async_session_maker() as session:
        result = await session.execute(
            select(ContentItem)
            .where(ContentItem.bot_id == bot_id)
            .order_by(ContentItem.title)
            .limit(LIST_LIMIT)
        )
        return list(result.scalars())


async def get_item_by_code(bot_id: uuid.UUID, code: str) -> ContentItem | None:
    """Case-insensitive lookup by the owner-chosen shortcut code
    (ContentItem.code) — unique per bot, see bot/db/models.py."""
    normalized = code.strip().lower()
    if not normalized:
        return None
    async with async_session_maker() as session:
        result = await session.execute(
            select(ContentItem).where(
                ContentItem.bot_id == bot_id, func.lower(ContentItem.code) == normalized
            )
        )
        return result.scalar_one_or_none()


async def has_any_content(bot_id: uuid.UUID) -> bool:
    async with async_session_maker() as session:
        result = await session.execute(
            select(ContentItem.id).where(ContentItem.bot_id == bot_id).limit(1)
        )
        return result.scalar_one_or_none() is not None


def would_cycle(item_id: int, proposed_parent_id: int, parent_map: dict[int, int | None]) -> bool:
    """True if setting proposed_parent_id as item_id's parent would create a
    loop, walking up the (in-progress) parent chain. Shared by bulk Excel
    import and interactive re-parenting (bot/handlers/tools/content_list.py)."""
    seen = {item_id}
    current: int | None = proposed_parent_id
    for _ in range(50):
        if current is None:
            return False
        if current in seen:
            return True
        seen.add(current)
        current = parent_map.get(current)
    return True  # suspiciously deep — treat as a cycle to be safe


async def upsert_item(
    bot_id: uuid.UUID, fields: dict, *, item_id: int | None = None, code: str | None = None
) -> ContentItem | None:
    """Creates a new ContentItem, or updates one in place if `item_id` (an
    already-resolved item) or `code` (looked up here) matches an existing
    item in this bot — the shared "add vs edit" rule used by both the
    wizard's Edit flow and bulk Excel re-upload. Never touches parent_id or
    product_id — see reparent_item for moving an item. `fields` may include
    title/body/image_url/link_url/is_premium/unlock_price; missing keys
    default to "" (title/body), None (image/link/unlock_price), or False
    (is_premium) on create, and are left as given (including None/False, to
    intentionally clear a field) on update.
    Returns None only if `item_id` was given but doesn't belong to this bot."""
    resolved_id = item_id
    if resolved_id is None and code:
        existing = await get_item_by_code(bot_id, code)
        resolved_id = existing.id if existing else None

    async with async_session_maker() as session:
        item = None
        if resolved_id is not None:
            result = await session.execute(
                select(ContentItem).where(ContentItem.id == resolved_id, ContentItem.bot_id == bot_id)
            )
            item = result.scalar_one_or_none()
            if item is None and item_id is not None:
                return None  # explicit item_id that isn't actually this bot's — refuse, don't create

        if item is not None:
            for key in ("title", "body", "image_url", "link_url", "is_premium", "unlock_price"):
                if key in fields:
                    setattr(item, key, fields[key])
        else:
            item = ContentItem(
                bot_id=bot_id,
                title=fields.get("title") or "",
                body=fields.get("body") or "",
                image_url=fields.get("image_url"),
                link_url=fields.get("link_url"),
                is_premium=bool(fields.get("is_premium")),
                unlock_price=fields.get("unlock_price"),
                code=code,
            )
            session.add(item)

        await session.commit()
        await session.refresh(item)
        return item


async def reparent_item(bot_id: uuid.UUID, item_id: int, new_parent_id: int | None) -> bool:
    """Moves item_id under new_parent_id (or to top level if None). Returns
    False (no-op) if item_id or new_parent_id doesn't belong to bot_id, or
    the move would create a cycle — True on success."""
    if new_parent_id == item_id:
        return False

    async with async_session_maker() as session:
        result = await session.execute(select(ContentItem).where(ContentItem.bot_id == bot_id))
        all_items = list(result.scalars())

    by_id = {i.id: i for i in all_items}
    if item_id not in by_id:
        return False
    if new_parent_id is not None and new_parent_id not in by_id:
        return False

    parent_map = {i.id: i.parent_id for i in all_items}
    if new_parent_id is not None and would_cycle(item_id, new_parent_id, parent_map):
        return False

    async with async_session_maker() as session:
        result = await session.execute(select(ContentItem).where(ContentItem.id == item_id))
        item = result.scalar_one()
        item.parent_id = new_parent_id
        await session.commit()
    return True
