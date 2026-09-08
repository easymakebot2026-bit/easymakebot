"""Interpreter for graphs saved by the visual flow builder Mini App
(bot/db/models.py: BuiltBot.flow_definition).

v1 scope: linear chains only, one per trigger command — no branching yet.
Graph shape (produced by webapp/):

    {
      "nodes": [
        {"id": "n1", "type": "trigger", "data": {"command": "/start"}},
        {"id": "n2", "type": "send_message", "data": {"text": "..."}},
        {"id": "n3", "type": "force_join_gate", "data": {}}
      ],
      "edges": [{"source": "n1", "target": "n2"}, {"source": "n2", "target": "n3"}]
    }

Node types:
- trigger: entry point, matched by command (e.g. "/start"). Never executed itself.
- send_message: sends data["text"] to the user.
- force_join_gate: reuses bot/force_join_gate.py; if the user is missing any
  required channel, sends the join prompt and stops the walk here (returning
  from run_flow). Re-running the flow (e.g. after "I've Joined") will pass
  through once they've joined — harmless if it re-sends earlier messages.
- guide_video: reuses bot/guide.py; if this subscriber's phone isn't on file
  yet, asks for it (same optional share-or-skip pattern as easymakebot's own
  onboarding) and stops the walk here. Re-running the flow (e.g. after they
  share/skip) sends the localized guide and continues.
- content_list: sends the bot's top-level content items (bot/db/models.py:
  ContentItem, managed via the "Content List" chat tool or Excel upload,
  possibly nested) as a list of buttons; tapping one either drills into a
  sub-list (if it has children) or shows the item (if it's a leaf) — see
  bot/content_nav.py and the content_item:*/content_nav:* handlers in
  bot/runtime.py. A leaf item created "for sale" (ContentItem.product_id set)
  also shows its price and a Buy button there, reusing the same purchase
  pipeline as the "shop" node below. Silently skipped if there's no content yet.
- shop: sends the bot's *standalone* products (bot/db/models.py: Product, not
  linked to any ContentItem, managed via the "Shop" chat tool) as a list of
  buttons with their price; tapping one starts the purchase flow (bot/shop.py
  + the shop_product:*/shop_buy:*/shop_pay:* handlers in bot/runtime.py).
  Content-linked products are deliberately excluded here — they're already
  browsable via content_list — so use both blocks together without items
  being listed twice. Silently skipped if there are no standalone products yet.
- order_status: sends the requesting buyer their own recent orders/checkouts
  (bot/shop.py:list_buyer_orders) — status, items, total, invoice number.
- broadcast: a no-op placeholder in the flow itself. The actual broadcast is
  triggered by the owner sending a message after this command, which is
  still handled by the existing BuiltBotBroadcastStates flow in runtime.py.

_execute_node below runs exactly one block and is shared by two callers:
run_flow (walks a whole trigger's chain, one node after another) and
bot/runtime.py's handle_legacy_command (runs a single action chosen via the
chat-based "Define Command" tool — bot/db/models.py: Command.payload["action"]
— for a bot owner who never opens the Visual Builder at all). Both represent
a paused gate (force_join_gate waiting on a join, guide_video waiting on a
phone number) the same way: set SubscriberOnboardingStates.waiting_for_phone
(or just return True) and stash whatever the caller needs to resume
afterwards in `resume_state_data` — see bot/runtime.py:
_save_subscriber_phone_and_resume, which branches on which resume marker it
finds.
"""

import uuid
from typing import Any

from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select

from bot import shop
from bot.content_nav import folder_ids_among, get_children
from bot.db.base import async_session_maker
from bot.db.models import BotSubscriber
from bot.force_join_gate import force_join_keyboard, missing_join_channels
from bot.guide import phone_share_keyboard, send_built_bot_guide
from bot.keyboards import CONTENT_MENU_HEADING, content_menu_keyboard
from bot.states import SubscriberOnboardingStates


def _normalize_command(raw: str) -> str:
    """A trigger's command is free text in the builder — tolerate a missing
    leading slash, surrounding spaces and case so "menu", "/Menu " and
    "/menu" all match the same incoming command."""
    cmd = (raw or "").strip().lower()
    if cmd and not cmd.startswith("/"):
        cmd = "/" + cmd
    return cmd


def find_trigger_node(flow: dict[str, Any], command: str) -> dict[str, Any] | None:
    want = _normalize_command(command)
    for node in flow.get("nodes", []):
        if node.get("type") == "trigger" and _normalize_command(
            node.get("data", {}).get("command", "")
        ) == want:
            return node
    return None


def _next_node(flow: dict[str, Any], node_id: str) -> dict[str, Any] | None:
    for edge in flow.get("edges", []):
        if edge.get("source") == node_id:
            target_id = edge.get("target")
            for node in flow.get("nodes", []):
                if node.get("id") == target_id:
                    return node
    return None


async def _subscriber_phone(bot_id: uuid.UUID, user_id: int) -> str | None:
    async with async_session_maker() as session:
        result = await session.execute(
            select(BotSubscriber).where(
                BotSubscriber.bot_id == bot_id, BotSubscriber.telegram_id == user_id
            )
        )
        subscriber = result.scalar_one_or_none()
        return subscriber.phone_number if subscriber else None


_ORDER_STATUS_LABELS = {
    "pending": "⏳ Pending payment",
    "paid": "✅ Paid — preparing",
    "fulfilled": "📦 Fulfilled",
    "rejected": "❌ Rejected",
}


async def _send_order_status(bot_id: uuid.UUID, message: Message) -> None:
    orders = await shop.list_buyer_orders(bot_id, message.from_user.id)
    if not orders:
        await message.answer("You don't have any orders yet.")
        return

    lines = ["📦 Your recent orders:"]
    for o in orders:
        status = _ORDER_STATUS_LABELS.get(o["status"], o["status"])
        items = ", ".join(o["items"])
        line = f"\n{o['date']:%Y-%m-%d %H:%M} — {items}\n{status} — {o['total']:,} Toman"
        if o["invoice_number"]:
            line += f"\nInvoice: {o['invoice_number']}"
        lines.append(line)
    await message.answer("\n".join(lines))


async def _execute_node(
    bot: Bot,
    bot_id: uuid.UUID,
    node_type: str,
    data: dict[str, Any],
    message: Message,
    state: FSMContext,
    resume_state_data: dict[str, Any],
) -> bool:
    """Runs exactly one block. Returns True if the walk should stop here — a
    gate that's paused waiting on the user (force_join_gate, guide_video) —
    or False to let the caller continue to whatever comes next. See the
    module docstring for the two callers and how a pause gets resumed."""
    if node_type == "send_message":
        await message.answer(data.get("text") or "")
    elif node_type == "force_join_gate":
        missing = await missing_join_channels(bot, bot_id, message.from_user.id)
        if missing:
            await message.answer(
                "Please join the channel(s) below to use this bot, then tap "
                "\"I've Joined\".",
                reply_markup=force_join_keyboard(missing),
            )
            return True
    elif node_type == "guide_video":
        phone = await _subscriber_phone(bot_id, message.from_user.id)
        if phone is None:
            await state.set_state(SubscriberOnboardingStates.waiting_for_phone)
            await state.update_data(**resume_state_data)
            await message.answer(
                "To get the guide and video tutorial in your language, share "
                "your phone number below (optional).",
                reply_markup=phone_share_keyboard(),
            )
            return True
        await send_built_bot_guide(message, phone)
    elif node_type == "content_list":
        items = await get_children(bot_id, None)

        if items:
            # Compact button index (📂 folder / 🔒 premium markers).
            # Tapping is handled by runtime.py's content_item:* handler,
            # which drills into a folder or opens a leaf as a post.
            folder_ids = await folder_ids_among(bot_id, [i.id for i in items])
            await message.answer(
                CONTENT_MENU_HEADING,
                reply_markup=content_menu_keyboard(
                    items, folder_ids, select_prefix="content_item:"
                ),
            )
    elif node_type == "shop":
        # Content-linked products (bot/db/models.py: ContentItem.product_id)
        # are already browsable — with a Buy button — through the
        # content_list block, so this only lists standalone products to
        # avoid showing the same item twice across two blocks.
        products = await shop.get_standalone_products(bot_id)
        # Out-of-stock items are hidden from buyers entirely — same
        # graceful-omit approach as "no products yet" (bot/inventory.py's
        # stock enforcement point is bot/shop.py:create_order/fulfill_order;
        # this is just the buyer-facing display side of it). Still fully
        # visible to the owner in the "📦 Products" management list.
        products = [p for p in products if p.stock_quantity is None or p.stock_quantity > 0]
        if products:
            # Telegram rejects a reply_markup above a certain size ("Bad
            # Request: reply markup is too long") — same cap as
            # bot/content_nav.py's LIST_LIMIT for content browsing. This
            # flow node has no pagination state to page through further
            # ones with, unlike the owner's "📦 Products" tool list.
            products = products[:40]
            rows = [
                [
                    InlineKeyboardButton(
                        text=f"{p.name} — {p.price:,} Toman",
                        callback_data=f"shop_product:{p.id}",
                    )
                ]
                for p in products
            ]
            rows.append([InlineKeyboardButton(text="🧺 View Cart", callback_data="cart_view")])
            await message.answer(
                "🛍 Choose a product:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)
            )
    elif node_type == "order_status":
        await _send_order_status(bot_id, message)
    # "broadcast" nodes are a marker only — see module docstring.

    return False


async def run_flow(
    bot: Bot,
    bot_id: uuid.UUID,
    flow: dict[str, Any],
    command: str,
    message: Message,
    state: FSMContext,
) -> bool:
    """Runs the flow starting at the trigger node matching `command`.
    Returns False if there's no such trigger (caller should fall back to
    legacy handling); True once the walk has run (whether it completed or
    paused at a gate)."""
    node = find_trigger_node(flow, command)
    if node is None:
        return False

    # The builder doesn't stop someone drawing a loop (n3 -> n2), which would
    # otherwise spin here forever spamming the user. Stop the walk the moment
    # a node repeats, and cap total steps as a belt-and-braces guard.
    visited: set[str] = set()
    node = _next_node(flow, node["id"])
    while node is not None and len(visited) < 100:
        node_id = node.get("id")
        if node_id in visited:
            break
        visited.add(node_id)

        stop = await _execute_node(
            bot, bot_id, node.get("type"), node.get("data", {}), message, state,
            {"resume_flow_command": command},
        )
        if stop:
            return True

        node = _next_node(flow, node["id"])

    return True
