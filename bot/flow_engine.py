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
from bot.content_nav import CONTENT_PAGE_SIZE, count_children, folder_ids_among, get_children
from bot.db.base import async_session_maker
from bot.db.models import BotSubscriber, Product
from bot.force_join_gate import force_join_keyboard, missing_join_channels
from bot.guide import end_user_prefers_persian, phone_share_keyboard, send_built_bot_guide
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


_ORDER_STATUS_LABELS_EN = {
    "pending": "⏳ Pending payment",
    "paid": "✅ Paid — preparing",
    "fulfilled": "📦 Fulfilled",
    "rejected": "❌ Rejected",
}
_ORDER_STATUS_LABELS_FA = {
    "pending": "⏳ در انتظار پرداخت",
    "paid": "✅ پرداخت‌شده — در حال آماده‌سازی",
    "fulfilled": "📦 تحویل داده شده",
    "rejected": "❌ رد شده",
}


async def send_order_status(bot_id: uuid.UUID, message: Message, is_fa: bool) -> None:
    """Renders a buyer's own recent orders/checkouts. Used by both the
    "order_status" flow node (_execute_node below) and the built-in "/orders"
    command (bot/runtime.py:sync_bot_commands + handle_orders_command) —
    kept public (no leading underscore) for that second caller."""
    orders = await shop.list_buyer_orders(bot_id, message.from_user.id)
    if not orders:
        empty_text = "📦 هنوز سفارشی ثبت نکردی." if is_fa else "You don't have any orders yet."
        await message.answer(empty_text)
        return

    labels = _ORDER_STATUS_LABELS_FA if is_fa else _ORDER_STATUS_LABELS_EN
    currency = "تومان" if is_fa else "Toman"
    lines = ["📦 سفارش‌های اخیر تو:" if is_fa else "📦 Your recent orders:"]
    for o in orders:
        status = labels.get(o["status"], o["status"])
        items = ", ".join(o["items"])
        line = f"\n{o['date']:%Y-%m-%d %H:%M} — {items}\n{status} — {o['total']:,} {currency}"
        if o["invoice_number"]:
            line += ("\nشماره فاکتور: " if is_fa else "\nInvoice: ") + o["invoice_number"]
        lines.append(line)
    await message.answer("\n".join(lines))


async def build_content_children_view(
    bot_id: uuid.UUID,
    parent_id: int | None,
    grandparent_id: int | None,
    heading: str,
    page: int = 0,
) -> tuple[str, InlineKeyboardMarkup] | None:
    """The (paginated) list of children under `parent_id` — root level when
    None. Shared by bot/runtime.py's /content command and its
    content_nav:*/content_page:* callbacks, and this module's own
    content_list flow node above, so all three page through content exactly
    the same way (bot/content_nav.py:CONTENT_PAGE_SIZE). Returns None when
    there's nothing under this parent — callers skip/report empty
    accordingly, same as before pagination existed."""
    total = await count_children(bot_id, parent_id)
    if total == 0:
        return None
    total_pages = max(1, (total + CONTENT_PAGE_SIZE - 1) // CONTENT_PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    items = await get_children(bot_id, parent_id, offset=page * CONTENT_PAGE_SIZE, limit=CONTENT_PAGE_SIZE)
    folder_ids = await folder_ids_among(bot_id, [i.id for i in items])

    back_button = None
    if parent_id is not None:
        back_target = "root" if grandparent_id is None else str(grandparent_id)
        back_button = InlineKeyboardButton(text="🔙 Back", callback_data=f"content_nav:{back_target}")

    parent_token = "root" if parent_id is None else str(parent_id)
    nav_row = []
    if page > 0:
        nav_row.append(
            InlineKeyboardButton(text="◀️", callback_data=f"content_page:{parent_token}:{page - 1}")
        )
    if total_pages > 1:
        nav_row.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav_row.append(
            InlineKeyboardButton(text="▶️", callback_data=f"content_page:{parent_token}:{page + 1}")
        )

    markup = content_menu_keyboard(
        items,
        folder_ids,
        select_prefix="content_item:",
        back_button=back_button,
        extra_rows=[nav_row] if nav_row else None,
    )
    return heading, markup


async def _visible_standalone_products(bot_id: uuid.UUID) -> list[Product]:
    """Standalone products (bot/shop.py:get_standalone_products), minus
    anything sold out. Shared by both shop view builders below so the
    category list and the product list are always computed from the exact
    same set."""
    products = await shop.get_standalone_products(bot_id)
    # Out-of-stock items are hidden from buyers entirely — same
    # graceful-omit approach as "no products yet" (bot/inventory.py's stock
    # enforcement point is bot/shop.py:create_order/fulfill_order; this is
    # just the buyer-facing display side of it). Still fully visible to the
    # owner in the "📦 Products" management list.
    return [p for p in products if p.stock_quantity is None or p.stock_quantity > 0]


def _shop_cat_token(category_index: int | None) -> str:
    return "all" if category_index is None else str(category_index)


def _shop_view_footer_rows(is_fa: bool, *, show_categories_button: bool) -> list[list[InlineKeyboardButton]]:
    rows = []
    if show_categories_button:
        back_text = "🔙 دسته‌بندی‌ها" if is_fa else "🔙 Categories"
        rows.append([InlineKeyboardButton(text=back_text, callback_data="shop_categories")])
    cart_text = "🧺 مشاهده سبد خرید" if is_fa else "🧺 View Cart"
    rows.append([InlineKeyboardButton(text=cart_text, callback_data="cart_view")])
    return rows


async def build_shop_categories_view(
    bot_id: uuid.UUID, is_fa: bool
) -> tuple[str, InlineKeyboardMarkup] | None:
    """The buyer's shop entry screen. Bots whose owner never set a category
    on any product (the common case, and every bot's state before this
    feature existed) skip straight to the flat, paginated product list —
    identical to the old un-categorized behavior. Returns None if there are
    no products for sale at all (caller should skip silently, as before)."""
    products = await _visible_standalone_products(bot_id)
    if not products:
        return None
    categories = shop.product_categories(products)
    if not categories:
        return await build_shop_list_view(bot_id, None, 0, is_fa)

    text = "🛍 یه دسته‌بندی رو انتخاب کن:" if is_fa else "🛍 Choose a category:"
    rows = [
        [InlineKeyboardButton(text=cat, callback_data=f"shop_cat:{idx}:0")]
        for idx, cat in enumerate(categories)
    ]
    all_text = "📋 همه محصولات" if is_fa else "📋 All products"
    rows.append([InlineKeyboardButton(text=all_text, callback_data="shop_cat:all:0")])
    rows.extend(_shop_view_footer_rows(is_fa, show_categories_button=False))
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


async def build_shop_list_view(
    bot_id: uuid.UUID, category_token: str | None, page: int, is_fa: bool
) -> tuple[str, InlineKeyboardMarkup] | None:
    """The (optionally category-filtered) paginated product list.
    category_token is None or "all" for no filter, otherwise a stringified
    index into bot.shop.product_categories(products) — kept as an index
    rather than the raw category text so callback_data (64-byte Telegram
    limit) never depends on how long an owner's category name is. Returns
    None if there are no products for sale at all."""
    products = await _visible_standalone_products(bot_id)
    if not products:
        return None
    categories = shop.product_categories(products)

    selected_category = None
    if category_token not in (None, "all"):
        try:
            idx = int(category_token)
        except ValueError:
            idx = -1
        if 0 <= idx < len(categories):
            selected_category = categories[idx]
        # An out-of-range index (categories changed since the button was
        # shown) falls back to the unfiltered list rather than erroring.

    filtered = [p for p in products if p.category == selected_category] if selected_category else products
    page_items, page, total_pages = shop.paginate_products(filtered, page)

    if selected_category:
        heading = f"🛍 {selected_category}:"
    else:
        heading = "🛍 یه محصول رو انتخاب کن:" if is_fa else "🛍 Choose a product:"

    currency = "تومان" if is_fa else "Toman"
    rows = [
        [
            InlineKeyboardButton(
                text=f"{p.name} — {p.price:,} {currency}",
                callback_data=f"shop_product:{p.id}",
            )
        ]
        for p in page_items
    ]

    token = _shop_cat_token(None if selected_category is None else categories.index(selected_category))
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="◀️", callback_data=f"shop_cat:{token}:{page - 1}"))
    if total_pages > 1:
        nav_row.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="▶️", callback_data=f"shop_cat:{token}:{page + 1}"))
    if nav_row:
        rows.append(nav_row)

    rows.extend(_shop_view_footer_rows(is_fa, show_categories_button=bool(categories)))
    return heading, InlineKeyboardMarkup(inline_keyboard=rows)


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
            # Same as the guide_video pause below — stash what the caller
            # needs to resume (which command's flow, or which legacy
            # command) so bot/runtime.py:handle_force_join_check continues
            # THIS walk instead of always restarting "/start".
            await state.update_data(**resume_state_data)
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
        # Tapping an item/folder/page button is handled by runtime.py's
        # content_item:*/content_nav:*/content_page:* handlers.
        view = await build_content_children_view(bot_id, None, None, CONTENT_MENU_HEADING)
        if view is not None:
            text, markup = view
            await message.answer(text, reply_markup=markup)
    elif node_type == "shop":
        is_fa = await end_user_prefers_persian(bot_id, message.from_user)
        view = await build_shop_categories_view(bot_id, is_fa)
        if view is not None:
            text, markup = view
            await message.answer(text, reply_markup=markup)
    elif node_type == "order_status":
        is_fa = await end_user_prefers_persian(bot_id, message.from_user)
        await send_order_status(bot_id, message, is_fa)
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
