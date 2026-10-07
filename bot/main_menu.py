"""Button menu for built bots.

Every command a built bot offers (owner-defined commands, Visual Builder
triggers, and the built-ins like /content, /cart, /orders) used to be
reachable only by typing it or via Telegram's "/" list. This module turns
the same set into a persistent reply-keyboard menu that end users get once
/start has completed (i.e. after any force-join / guide-video gate), so
nobody has to know command names.

collect_bot_commands() is the single source of truth for "which commands
does this bot offer, to whom" — runtime.sync_bot_commands (Telegram's "/"
menu) and build_main_menu (this keyboard) both read it, so the two never
disagree.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Any

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from sqlalchemy import select

from bot import premium_content, shop
from bot.content_nav import has_any_content
from bot.db.base import async_session_maker
from bot.db.models import BuiltBot, Command, Product
from bot.flow_engine import _normalize_command
from bot.message_buttons import is_valid_command_name

MENU_LABEL_MAX = 40

# Built-in commands, in the order they appear in the menu (after the
# owner's own commands). Value: (Persian label, English label).
BUILTIN_LABELS: dict[str, tuple[str, str]] = {
    "/content": ("📚 محتوا", "📚 Content"),
    "/cart": ("🛒 سبد خرید", "🛒 Cart"),
    "/orders": ("📦 سفارش‌های من", "📦 My orders"),
    "/status": ("💎 وضعیت اشتراک من", "💎 My subscription"),
    "/account": ("👤 حساب من", "👤 My account"),
    "/help": ("ℹ️ راهنما", "ℹ️ Help"),
}

# Never shown as menu buttons: /start is what shows the menu in the first
# place, /stop (mute broadcasts) and /cancel are utility commands that
# would only clutter it.
_NEVER_IN_MENU = {"/start", "/stop", "/cancel"}


@dataclass
class BotCommandEntry:
    name: str
    kind: str  # Command.command_type, "flow", or a built-in key ("content", "cart", ...)
    admin_only: bool
    label: str | None  # owner-chosen menu label, if any
    order: int


def clean_menu_label(text: str | None) -> str | None:
    """Normalises an owner-supplied label; None if unusable."""
    if not text:
        return None
    label = " ".join(str(text).split())
    if not label or label.startswith("/") or len(label) > MENU_LABEL_MAX:
        return None
    return label


async def has_subscription_offer(bot_id: uuid.UUID) -> bool:
    """True when this bot sells something time- or level-based that a
    "my subscription" status button would make sense for."""
    if await premium_content.get_subscription_plans(bot_id):
        return True
    async with async_session_maker() as session:
        result = await session.execute(
            select(Product.id)
            .where(
                Product.bot_id == bot_id,
                Product.product_type.in_(("subscription", "access")),
                Product.archived.is_(False),
            )
            .limit(1)
        )
        return result.first() is not None


# The menu-tap filter runs on every plain-text message a built bot gets, so
# the command set is cached briefly per bot. runtime.sync_bot_commands
# (called whenever an owner changes commands, flow, shop or content)
# invalidates it, so edits still show up immediately.
_CACHE_TTL = 60.0
_cache: dict[uuid.UUID, tuple[float, list["BotCommandEntry"]]] = {}


def invalidate_menu_cache(bot_id: uuid.UUID) -> None:
    _cache.pop(bot_id, None)


async def collect_bot_commands(bot_id: uuid.UUID) -> list[BotCommandEntry]:
    cached = _cache.get(bot_id)
    if cached and time.monotonic() - cached[0] < _CACHE_TTL:
        return cached[1]
    entries = await _collect_bot_commands_uncached(bot_id)
    _cache[bot_id] = (time.monotonic(), entries)
    return entries


async def _collect_bot_commands_uncached(bot_id: uuid.UUID) -> list[BotCommandEntry]:
    async with async_session_maker() as session:
        result = await session.execute(select(BuiltBot).where(BuiltBot.id == bot_id))
        built_bot = result.scalar_one_or_none()
        if built_bot is None:
            return []
        flow: dict[str, Any] = built_bot.flow_definition or {}
        result = await session.execute(
            select(Command).where(Command.bot_id == bot_id).order_by(Command.id)
        )
        commands = list(result.scalars())

    entries: dict[str, BotCommandEntry] = {}
    order = 0

    # Only names Telegram accepts: one invalid name (old data saved before
    # names were validated) would make setMyCommands reject the whole list.
    for c in commands:
        if not is_valid_command_name(c.name):
            continue
        payload = c.payload if isinstance(c.payload, dict) else {}
        entries[c.name] = BotCommandEntry(
            name=c.name,
            kind=c.command_type,
            admin_only=c.visibility == "admin",
            label=clean_menu_label(payload.get("menu_label")),
            order=order,
        )
        order += 1

    nodes = flow.get("nodes") if isinstance(flow.get("nodes"), list) else []
    for node in nodes:
        if not (isinstance(node, dict) and node.get("type") == "trigger"):
            continue
        node_data = node.get("data") or {}
        name = _normalize_command(node_data.get("command", ""))
        if not is_valid_command_name(name):
            continue
        label = clean_menu_label(node_data.get("menu_label"))
        if name in entries:
            # Same command defined both ways — keep the legacy row but let a
            # builder-supplied label fill in a missing one.
            entries[name].label = entries[name].label or label
            continue
        entries[name] = BotCommandEntry(
            name=name,
            kind="flow",
            admin_only=node_data.get("visibility") == "admin" and name != "/start",
            label=label,
            order=order,
        )
        order += 1

    builtins: list[tuple[str, str]] = []
    if await has_any_content(bot_id):
        builtins.append(("/content", "content"))
    if await shop.get_products(bot_id):
        builtins += [("/cart", "cart"), ("/orders", "orders")]
    if await has_subscription_offer(bot_id):
        builtins.append(("/status", "status"))
    settings = await shop.get_shop_settings(bot_id)
    if settings and settings.my_account_enabled:
        builtins.append(("/account", "account"))
    builtins += [("/help", "help"), ("/stop", "stop")]

    for name, kind in builtins:
        if name not in entries:  # an owner-defined command of the same name wins
            entries[name] = BotCommandEntry(name=name, kind=kind, admin_only=False, label=None, order=1000 + order)
            order += 1

    return sorted(entries.values(), key=lambda e: e.order)


def _default_label(entry: BotCommandEntry, is_fa: bool) -> str:
    if entry.name in BUILTIN_LABELS:
        fa, en = BUILTIN_LABELS[entry.name]
        return fa if is_fa else en
    return "▫️ " + entry.name.lstrip("/").replace("_", " ")


def menu_items(entries: list[BotCommandEntry], *, is_owner: bool, is_fa: bool) -> list[tuple[str, str]]:
    """[(label, command)] in display order, labels unique."""
    items: list[tuple[str, str]] = []
    seen: set[str] = set()
    for e in entries:
        if e.name in _NEVER_IN_MENU:
            continue
        if (e.admin_only or e.kind == "broadcast") and not is_owner:
            continue
        label = e.label or _default_label(e, is_fa)
        if label in seen:
            label = f"{label} ({e.name})"
        seen.add(label)
        items.append((label, e.name))
    return items


def layout_keyboard(items: list[tuple[str, str]], is_fa: bool) -> ReplyKeyboardMarkup | None:
    """Two buttons per row; a long label gets a row of its own so nothing is
    truncated on phones. Help always sits alone on the last row."""
    if not items:
        return None
    help_items = [i for i in items if i[1] == "/help"]
    main = [i for i in items if i[1] != "/help"]

    rows: list[list[KeyboardButton]] = []
    pending: list[KeyboardButton] = []
    for label, _ in main:
        if len(label) > 18:
            if pending:
                rows.append(pending)
                pending = []
            rows.append([KeyboardButton(text=label)])
            continue
        pending.append(KeyboardButton(text=label))
        if len(pending) == 2:
            rows.append(pending)
            pending = []
    if pending:
        rows.append(pending)
    for label, _ in help_items:
        rows.append([KeyboardButton(text=label)])

    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="یکی از گزینه‌ها رو انتخاب کن 👇" if is_fa else "Choose an option 👇",
    )


async def build_main_menu(bot_id: uuid.UUID, *, is_owner: bool, is_fa: bool) -> ReplyKeyboardMarkup | None:
    entries = await collect_bot_commands(bot_id)
    return layout_keyboard(menu_items(entries, is_owner=is_owner, is_fa=is_fa), is_fa)


async def command_for_label(bot_id: uuid.UUID, text: str, *, is_owner: bool) -> str | None:
    """Maps a tapped menu label back to its command. Labels of both
    languages are accepted, since the menu a user has on screen may have
    been sent before their language preference was known."""
    text = (text or "").strip()
    if not text or text.startswith("/"):
        return None
    entries = await collect_bot_commands(bot_id)
    for is_fa in (True, False):
        for label, command in menu_items(entries, is_owner=is_owner, is_fa=is_fa):
            if label == text:
                return command
    return None
