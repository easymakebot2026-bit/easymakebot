import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command as CommandFilter
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    BotCommand,
    BotCommandScopeChat,
    BotCommandScopeDefault,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    LinkPreviewOptions,
    Message,
    ReplyKeyboardRemove,
)
from sqlalchemy import select

from bot import premium_content, pricing, shop
from bot.config import load_config
from bot.content_nav import (
    folder_ids_among,
    get_children,
    get_item,
    get_item_by_code,
    has_any_content,
)
from bot.keyboards import content_menu_keyboard, post_engagement_keyboard
from bot.list_render import send_item_list
from bot.db.base import async_session_maker
from bot.db.models import BotPost, BotSubscriber, BroadcastLog, BuiltBot, Command, PostComment, PostLike, User
from bot.flow_engine import _execute_node, find_trigger_node, run_flow
from bot.force_join_gate import force_join_keyboard, missing_join_channels
from bot.guide import SKIP_BUTTON_TEXT, TYPED_PHONE_INVALID, normalize_typed_phone, phone_share_keyboard
from bot.session import make_session
from bot.states import (
    BuiltBotBroadcastStates,
    PostCommentStates,
    ShopOrderStates,
    SubscriberOnboardingStates,
)

logger = logging.getLogger(__name__)

_config = load_config()
_running_bots: dict[str, asyncio.Task] = {}

# easymakebot is a neutral platform, not the seller in a built bot's shop. Every
# payment-instruction message in a built bot carries this so the buyer knows the
# transaction — and any dispute — is with the bot's owner, not easymakebot.
_EMB_LINK = '<b><a href="https://t.me/easymakebot">easymakebot</a></b>'
_PAY_DISCLAIMER_IRREVERSIBLE = (
    "⚠️ این پرداخت مستقیم به صاحب این ربات است و قابل بازگشت نیست. قبل از واریز، "
    "از فروشنده و مبلغ مطمئن شوید. " + _EMB_LINK + " مسئول کالا یا خدمات این ربات نیست.\n\n"
    "This payment goes straight to this bot's owner and cannot be reversed. Make "
    "sure of the seller and the amount first. " + _EMB_LINK + " is not responsible "
    "for this bot's goods or services."
)
_PAY_DISCLAIMER_GATEWAY = (
    "پرداخت با فروشندهٔ این ربات است؛ " + _EMB_LINK + " مسئول کالا/خدمات نیست.\n\n"
    "Payment is with this bot's seller; " + _EMB_LINK + " is not responsible for "
    "the goods/services."
)


async def _send_pay_disclaimer(message: Message, *, irreversible: bool) -> None:
    text = _PAY_DISCLAIMER_IRREVERSIBLE if irreversible else _PAY_DISCLAIMER_GATEWAY
    try:
        await message.answer(
            text,
            parse_mode="HTML",
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
    except Exception:  # noqa: BLE001 — a disclaimer must never break the payment flow
        logger.warning("Failed to send payment disclaimer", exc_info=True)


def _format_start_message(payload: dict[str, Any]) -> str:
    lines = [(payload.get("welcome_text") or "Welcome!").strip(), ""]

    contact = []
    if payload.get("admin_telegram_id"):
        contact.append(f"Contact: {payload['admin_telegram_id']}")
    if payload.get("admin_phone"):
        contact.append(f"Phone: {payload['admin_phone']}")
    if payload.get("website"):
        contact.append(f"Website: {payload['website']}")
    if payload.get("instagram"):
        contact.append(f"Instagram: {payload['instagram']}")
    if payload.get("youtube"):
        contact.append(f"YouTube: {payload['youtube']}")
    if payload.get("facebook"):
        contact.append(f"Facebook: {payload['facebook']}")
    if payload.get("x"):
        contact.append(f"X: {payload['x']}")

    lines.extend(contact)
    return "\n".join(line for line in lines if line != "")


async def _should_use_flow_for_start(bot_id: uuid.UUID, built_bot: BuiltBot | None) -> bool:
    """For /start specifically, both the visual flow builder and the legacy
    chat-based "Define Command" wizard can define its behavior — whichever
    was saved more recently wins, so either path stays fully usable. Every
    other command gets the same "newest edit wins" treatment via
    _has_legacy_action below, which concedes to handle_flow_command when a
    flow trigger for that command is newer than the Command row."""
    if not built_bot or not built_bot.flow_definition:
        return False
    if find_trigger_node(built_bot.flow_definition, "/start") is None:
        return False

    async with async_session_maker() as session:
        result = await session.execute(
            select(Command).where(Command.bot_id == bot_id, Command.name == "/start")
        )
        legacy = result.scalar_one_or_none()

    if legacy is None:
        return True

    if built_bot.flow_updated_at is None:
        # Flow predates flow_updated_at tracking — trust the wizard's
        # timestamp instead of assuming the (untimed) flow edit was newer.
        return False

    return built_bot.flow_updated_at > legacy.updated_at


async def _get_owner_telegram_id(bot_id: uuid.UUID) -> int | None:
    async with async_session_maker() as session:
        result = await session.execute(
            select(User.telegram_id)
            .join(BuiltBot, BuiltBot.owner_id == User.id)
            .where(BuiltBot.id == bot_id)
        )
        return result.scalar_one_or_none()


async def _broadcast_to_subscribers(
    bot_id: uuid.UUID, command_name: str, message: Message
) -> int:
    async with async_session_maker() as session:
        result = await session.execute(
            select(BotSubscriber).where(BotSubscriber.bot_id == bot_id)
        )
        subscribers = list(result.scalars())

    sent = 0
    for subscriber in subscribers:
        try:
            await message.copy_to(subscriber.telegram_id)
            sent += 1
        except Exception:
            logger.warning(
                "Failed to deliver broadcast (bot %s) to %s", bot_id, subscriber.telegram_id
            )

    async with async_session_maker() as session:
        session.add(
            BroadcastLog(
                bot_id=bot_id,
                command_name=command_name,
                text=message.text or message.caption or "[non-text message]",
                recipient_count=sent,
            )
        )
        await session.commit()

    return sent


_COMMAND_DESCRIPTIONS = {
    "start": "Start the bot",
    "broadcast": "Owner: broadcast a message to all users",
    "flow": "Defined in the visual builder",
    "custom": "Custom command",
    "content": "Browse content",
    "cart": "View your cart",
}


async def sync_bot_commands(bot_id: uuid.UUID) -> None:
    """Registers this built bot's own commands on Telegram's native "/" menu
    (BotFather-style), built fresh from whatever THIS bot's owner has
    actually defined (Command rows + flow trigger nodes) — a brand-new bot
    starts with an empty menu instead of inheriting another bot's shape.
    An "admin"-visibility command (bot/db/models.py: Command.visibility) is
    registered ONLY on the owner's own chat-scoped menu (BotCommandScopeChat)
    — everyone else's default menu never lists it. A menu is just a
    suggestion though, so the command is also rejected at the handler level
    for anyone but the owner — see handle_legacy_command below. Called
    whenever a bot's commands or flow change, and once at startup."""
    async with async_session_maker() as session:
        result = await session.execute(select(BuiltBot).where(BuiltBot.id == bot_id))
        built_bot = result.scalar_one_or_none()
        if built_bot is None:
            return
        token = built_bot.token
        flow = built_bot.flow_definition or {}

        result = await session.execute(select(Command).where(Command.bot_id == bot_id))
        commands = list(result.scalars())

    kinds: dict[str, str] = {}
    admin_only: set[str] = set()
    for c in commands:
        if c.name.startswith("/"):
            kinds[c.name] = c.command_type
            if c.visibility == "admin":
                admin_only.add(c.name)
    for node in flow.get("nodes", []):
        if node.get("type") == "trigger":
            name = node.get("data", {}).get("command")
            if name and name.startswith("/"):
                kinds.setdefault(name, "flow")

    # Built-in browse-content command, only offered once there's something to browse.
    if await has_any_content(bot_id):
        kinds.setdefault("/content", "content")

    # Built-in cart command, only offered once there's something sellable to add to it.
    if await shop.get_products(bot_id):
        kinds.setdefault("/cart", "cart")

    def _describe(name: str, kind: str) -> str:
        # /start has dedicated runtime handling regardless of its stored
        # command_type (which can be stale/incidental — e.g. legacy rows
        # saved as "broadcast"), so its description is never data-driven.
        if name == "/start":
            return "Start the bot"
        return _COMMAND_DESCRIPTIONS.get(kind, "Command")

    def _build(entries) -> list[BotCommand]:
        return [
            BotCommand(command=name.lstrip("/"), description=_describe(name, kind))
            for name, kind in sorted(entries)
        ][:100]  # Telegram's own cap on the command list

    everyone_commands = _build((n, k) for n, k in kinds.items() if n not in admin_only)
    all_commands = _build(kinds.items())

    temp_bot = Bot(token=token, session=make_session())
    try:
        await temp_bot.set_my_commands(everyone_commands, scope=BotCommandScopeDefault())
        owner_telegram_id = await _get_owner_telegram_id(bot_id)
        if owner_telegram_id is not None and admin_only:
            await temp_bot.set_my_commands(
                all_commands, scope=BotCommandScopeChat(chat_id=owner_telegram_id)
            )
    except Exception:
        logger.warning("Failed to sync command menu for bot %s", bot_id)
    finally:
        await temp_bot.session.close()


async def _run_bot(bot_id: uuid.UUID, token: str) -> None:
    bot = Bot(token=token, session=make_session())
    dp = Dispatcher()
    owner_telegram_id = await _get_owner_telegram_id(bot_id)

    async def _register_subscriber(user_id: int) -> None:
        async with async_session_maker() as session:
            result = await session.execute(
                select(BotSubscriber).where(
                    BotSubscriber.bot_id == bot_id,
                    BotSubscriber.telegram_id == user_id,
                )
            )
            if result.scalar_one_or_none() is None:
                session.add(BotSubscriber(bot_id=bot_id, telegram_id=user_id))
                await session.commit()

    async def _complete_start(message: Message, user_id: int) -> None:
        await _register_subscriber(user_id)

        async with async_session_maker() as session:
            result = await session.execute(
                select(Command).where(Command.bot_id == bot_id, Command.name == "/start")
            )
            command = result.scalar_one_or_none()

        payload = command.payload if command and command.payload else {}
        await message.answer(_format_start_message(payload))

    @dp.message(CommandStart())
    async def handle_start(message: Message, state: FSMContext) -> None:
        async with async_session_maker() as session:
            result = await session.execute(select(BuiltBot).where(BuiltBot.id == bot_id))
            built_bot = result.scalar_one_or_none()

        # Whichever of the flow builder and the legacy wizard was saved more
        # recently drives /start (see _should_use_flow_for_start); otherwise
        # fall back to the legacy hardcoded handling below.
        if await _should_use_flow_for_start(bot_id, built_bot):
            await _register_subscriber(message.from_user.id)
            handled = await run_flow(
                bot, bot_id, built_bot.flow_definition, "/start", message, state
            )
            if handled:
                return

        if built_bot and built_bot.force_join_enabled:
            missing = await missing_join_channels(bot, bot_id, message.from_user.id)
            if missing:
                await message.answer(
                    "Please join the channel(s) below to use this bot, then tap "
                    "\"I've Joined\".",
                    reply_markup=force_join_keyboard(missing),
                )
                return

        await _complete_start(message, message.from_user.id)

    @dp.callback_query(F.data == "force_join_check")
    async def handle_force_join_check(callback: CallbackQuery, state: FSMContext) -> None:
        async with async_session_maker() as session:
            result = await session.execute(select(BuiltBot).where(BuiltBot.id == bot_id))
            built_bot = result.scalar_one_or_none()

        missing = await missing_join_channels(bot, bot_id, callback.from_user.id)
        if missing:
            await callback.answer(
                "You haven't joined all the channels yet.", show_alert=True
            )
            return

        await callback.answer("Thanks for joining! ✅")
        await callback.message.delete()

        if await _should_use_flow_for_start(bot_id, built_bot):
            await _register_subscriber(callback.from_user.id)
            await run_flow(
                bot, bot_id, built_bot.flow_definition, "/start", callback.message, state
            )
            return

        await _complete_start(callback.message, callback.from_user.id)

    def _content_keyboard(
        items, back_to_id: int | None, at_root: bool, folder_ids: set[int]
    ) -> InlineKeyboardMarkup:
        # Compact button index — 📂 folder / 🔒 premium markers via
        # bot/keyboards.py. Tapping a leaf opens it as a "post" (see
        # _send_content_post); tapping a folder drills in.
        back_button = None
        if not at_root:
            back_target = "root" if back_to_id is None else str(back_to_id)
            back_button = InlineKeyboardButton(
                text="🔙 Back", callback_data=f"content_nav:{back_target}"
            )
        return content_menu_keyboard(
            items, folder_ids, select_prefix="content_item:", back_button=back_button
        )

    async def _send_content_children(
        message: Message, parent_id: int | None, grandparent_id: int | None, heading: str
    ) -> bool:
        items = await get_children(bot_id, parent_id)
        if not items:
            return False
        folder_ids = await folder_ids_among(bot_id, [i.id for i in items])
        await message.answer(
            heading,
            reply_markup=_content_keyboard(
                items, grandparent_id, parent_id is None, folder_ids
            ),
        )
        return True

    async def _shop_product_for(item):
        """The real shop Product a content item is 'for sale' as (shop mode),
        or None. The hidden per-item unlock Product (subscription mode) is
        NOT a shop product — it must never show Buy/Cart on an item the
        viewer has already unlocked to be reading."""
        if not item.product_id:
            return None
        product = await shop.get_product(item.product_id)
        if product is None or product.product_type == shop.CONTENT_UNLOCK_TYPE:
            return None
        return product

    async def _content_post_markup(item, back_target: str) -> InlineKeyboardMarkup:
        """Buttons under a content "post": optional Open link, Buy / Add-to-
        cart if it's for sale, a ◀️ i/n ▶️ carousel row across its siblings,
        and Back to the list."""
        rows: list[list[InlineKeyboardButton]] = []
        if item.link_url:
            rows.append([InlineKeyboardButton(text="🔗 Open", url=item.link_url)])

        product = await _shop_product_for(item)
        if product:
            rows.append(
                [
                    InlineKeyboardButton(text="🛒 Buy Now", callback_data=f"shop_buy:{product.id}"),
                    InlineKeyboardButton(
                        text="➕ Add to Cart", callback_data=f"cart_add:{product.id}"
                    ),
                ]
            )

        siblings = await get_children(bot_id, item.parent_id)
        sibling_ids = [s.id for s in siblings]
        if item.id in sibling_ids and len(sibling_ids) > 1:
            idx = sibling_ids.index(item.id)
            nav = []
            if idx > 0:
                nav.append(
                    InlineKeyboardButton(
                        text="◀️", callback_data=f"content_post:{sibling_ids[idx - 1]}"
                    )
                )
            nav.append(
                InlineKeyboardButton(text=f"{idx + 1} / {len(sibling_ids)}", callback_data="noop")
            )
            if idx < len(sibling_ids) - 1:
                nav.append(
                    InlineKeyboardButton(
                        text="▶️", callback_data=f"content_post:{sibling_ids[idx + 1]}"
                    )
                )
            rows.append(nav)

        rows.append(
            [InlineKeyboardButton(text="🔙 Back to list", callback_data=f"content_nav:{back_target}")]
        )
        return InlineKeyboardMarkup(inline_keyboard=rows)

    async def _send_content_post(target: Message, item, *, edit: bool) -> None:
        """Renders one content item as a "post" — a photo (or plain text if
        it has no image) with its title/body/price and the _content_post_markup
        buttons. `edit=True` rewrites `target` in place (carousel ◀️/▶️);
        `edit=False` sends a new message (opening from the list, or a
        shortcut-code jump). The single premium gate (bot/premium_content.py)
        for both entry paths."""
        back_target = "root" if item.parent_id is None else str(item.parent_id)

        if item.is_premium:
            allowed = await premium_content.check_and_record_access(
                bot_id, target.chat.id, item
            )
            if not allowed:
                plans = await premium_content.get_subscription_plans(bot_id)
                rows = []

                # À-la-carte: unlock just this one item (subscription mode).
                unlock_base = await premium_content.effective_unlock_price(bot_id, item)
                unlock_line = None
                if unlock_base:
                    unlock_product = await shop.ensure_unlock_product(bot_id, item, unlock_base)
                    rows.append(
                        [
                            InlineKeyboardButton(
                                text=f"🔓 Unlock just this — {unlock_product.price:,} Toman",
                                callback_data=f"shop_buy:{unlock_product.id}",
                            )
                        ]
                    )
                    unlock_line = pricing.savings_line(
                        unlock_product.price, unlock_product.original_price
                    )

                rows += [
                    [
                        InlineKeyboardButton(
                            text=f"{p.name} — {pricing.format_price(p.price, p.original_price)}",
                            callback_data=f"shop_buy:{p.id}",
                        )
                    ]
                    for p in plans
                ]
                rows.append(
                    [InlineKeyboardButton(text="🔙 Back", callback_data=f"content_nav:{back_target}")]
                )
                if plans or unlock_base:
                    text = (
                        "🔒 Premium content. Your free previews are used up — "
                        "subscribe for the whole archive"
                    )
                    text += ", or unlock just this one:" if unlock_base else ":"
                else:
                    text = (
                        "🔒 This is premium content, and no subscription plan is set up yet. "
                        "Please contact the bot owner."
                    )
                if unlock_line:
                    text += f"\n\n{unlock_line}"
                await _render_post(
                    target, text, None, InlineKeyboardMarkup(inline_keyboard=rows), edit=edit
                )
                return

        caption = f"📌 {item.title}\n\n{item.body}"
        product = await _shop_product_for(item)
        if product:
            caption += f"\n\n💰 {pricing.format_price(product.price, product.original_price)}"
            note = pricing.savings_line(product.price, product.original_price)
            if note:
                caption += f"\n{note}"

        markup = await _content_post_markup(item, back_target)
        await _render_post(target, caption, item.image_url or None, markup, edit=edit)

    async def _render_post(
        target: Message, text: str, image_url: str | None, markup: InlineKeyboardMarkup, *, edit: bool
    ) -> None:
        """Low-level: put (text | photo+caption) on `target`, editing it in
        place when possible and otherwise deleting + re-sending (needed when
        switching a photo message to text or vice-versa, which Telegram
        can't edit across)."""
        if image_url:
            media = InputMediaPhoto(media=image_url, caption=text)
            if edit:
                try:
                    await target.edit_media(media, reply_markup=markup)
                    return
                except Exception:
                    try:
                        await target.delete()
                    except Exception:
                        pass
            try:
                await target.answer_photo(image_url, caption=text, reply_markup=markup)
                return
            except Exception:
                logger.warning("content post image failed, falling back to text")

        if edit:
            try:
                await target.edit_text(text, reply_markup=markup)
                return
            except Exception:
                try:
                    await target.delete()
                except Exception:
                    pass
        await target.answer(text, reply_markup=markup)

    @dp.callback_query(F.data.startswith("content_item:"))
    async def handle_content_item(callback: CallbackQuery) -> None:
        item_id = int(callback.data.split(":")[-1])
        item = await get_item(item_id)

        if item is None or item.bot_id != bot_id:
            await callback.answer("This item is no longer available.", show_alert=True)
            return

        await callback.answer()

        # A "folder" (has children) drills in; a leaf opens as a post.
        drilled_in = await _send_content_children(
            callback.message, item.id, item.parent_id, f"📁 {item.title}"
        )
        if drilled_in:
            return

        await _send_content_post(callback.message, item, edit=False)

    @dp.callback_query(F.data.startswith("content_post:"))
    async def handle_content_post(callback: CallbackQuery) -> None:
        """◀️ / ▶️ on a content post — rewrites the current message to the
        sibling item, so paging a catalogue never stacks up new messages."""
        item_id = int(callback.data.split(":")[-1])
        item = await get_item(item_id)
        if item is None or item.bot_id != bot_id:
            await callback.answer("This item is no longer available.", show_alert=True)
            return
        await callback.answer()
        await _send_content_post(callback.message, item, edit=True)

    @dp.callback_query(F.data == "noop")
    async def handle_noop(callback: CallbackQuery) -> None:
        await callback.answer()

    @dp.callback_query(F.data.startswith("content_nav:"))
    async def handle_content_nav(callback: CallbackQuery) -> None:
        target = callback.data.split(":", 1)[1]

        if target == "root":
            parent_id: int | None = None
            grandparent_id: int | None = None
        else:
            parent_id = int(target)
            folder = await get_item(parent_id)
            if folder is None or folder.bot_id != bot_id:
                await callback.answer("Not available.", show_alert=True)
                return
            grandparent_id = folder.parent_id

        await callback.answer()
        sent = await _send_content_children(
            callback.message, parent_id, grandparent_id, "📚 Choose an item:"
        )
        if not sent:
            await callback.message.answer("No items here.")

    @dp.message(CommandFilter("content"))
    async def handle_content_command(message: Message) -> None:
        sent = await _send_content_children(message, None, None, "📚 Choose an item:")
        if not sent:
            await message.answer("No content yet.")

    # --- Posts: "Add Post" broadcasts (bot/handlers/tools/content_list.py) ---
    # land here as normal messages; Like toggles per-viewer, Comment opens a
    # one-shot free-text capture and notifies the owner live. ---

    @dp.callback_query(F.data.startswith("post_like:"))
    async def handle_post_like(callback: CallbackQuery) -> None:
        post_id = int(callback.data.split(":")[-1])
        liker_id = callback.from_user.id

        async with async_session_maker() as session:
            result = await session.execute(select(BotPost).where(BotPost.id == post_id))
            post = result.scalar_one_or_none()
            if post is None or post.bot_id != bot_id:
                await callback.answer("This post is no longer available.", show_alert=True)
                return

            existing = await session.execute(
                select(PostLike).where(
                    PostLike.post_id == post_id, PostLike.liker_telegram_id == liker_id
                )
            )
            like_row = existing.scalar_one_or_none()
            if like_row is not None:
                await session.delete(like_row)
                post.like_count = max(0, post.like_count - 1)
                liked_now = False
            else:
                session.add(PostLike(post_id=post_id, liker_telegram_id=liker_id))
                post.like_count += 1
                liked_now = True
            await session.commit()
            like_count, comment_count = post.like_count, post.comment_count

        await callback.answer("👍 Liked!" if liked_now else "Like removed.")
        try:
            await callback.message.edit_reply_markup(
                reply_markup=post_engagement_keyboard(post_id, like_count, comment_count)
            )
        except Exception:
            pass  # markup already matches, or the message is otherwise stale

    @dp.callback_query(F.data.startswith("post_comment:"))
    async def handle_post_comment_button(callback: CallbackQuery, state: FSMContext) -> None:
        post_id = int(callback.data.split(":")[-1])
        async with async_session_maker() as session:
            result = await session.execute(select(BotPost).where(BotPost.id == post_id))
            post = result.scalar_one_or_none()
        if post is None or post.bot_id != bot_id:
            await callback.answer("This post is no longer available.", show_alert=True)
            return

        await state.update_data(
            comment_post_id=post_id,
            comment_chat_id=callback.message.chat.id,
            comment_message_id=callback.message.message_id,
        )
        await state.set_state(PostCommentStates.waiting_for_comment)
        await callback.answer()
        await callback.message.answer("Send your comment as a text message.")

    @dp.message(PostCommentStates.waiting_for_comment)
    async def handle_post_comment_text(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        post_id = data.get("comment_post_id")
        chat_id = data.get("comment_chat_id")
        orig_message_id = data.get("comment_message_id")
        text = (message.text or "").strip()

        await state.set_state(None)
        if post_id is None:
            return
        if not text:
            await message.answer("Empty comment — nothing was posted.")
            return

        async with async_session_maker() as session:
            result = await session.execute(select(BotPost).where(BotPost.id == post_id))
            post = result.scalar_one_or_none()
            if post is None:
                await message.answer("This post is no longer available.")
                return
            session.add(
                PostComment(post_id=post_id, commenter_telegram_id=message.from_user.id, text=text)
            )
            post.comment_count += 1
            await session.commit()
            like_count, comment_count = post.like_count, post.comment_count

        await message.answer("💬 Comment added — thanks!")

        if chat_id is not None and orig_message_id is not None:
            try:
                await bot.edit_message_reply_markup(
                    chat_id=chat_id,
                    message_id=orig_message_id,
                    reply_markup=post_engagement_keyboard(post_id, like_count, comment_count),
                )
            except Exception:
                pass

        if owner_telegram_id:
            commenter = message.from_user
            who = f"@{commenter.username}" if commenter.username else commenter.full_name
            try:
                await bot.send_message(owner_telegram_id, f"💬 New comment on your post:\n\n{who}: {text}")
            except Exception:
                logger.warning("Failed to notify owner of bot %s about a new comment", bot_id)

    # --- Shop: product detail -> buy -> pay (Zarinpal or card-to-card) -> ---
    # --- fulfillment (bot/shop.py) -> optional shipping wizard -> invoice ---

    @dp.callback_query(F.data.startswith("shop_product:"))
    async def handle_shop_product(callback: CallbackQuery) -> None:
        product_id = int(callback.data.split(":")[-1])
        product = await shop.get_product(product_id)

        if product is None or product.bot_id != bot_id:
            await callback.answer("Product not found.", show_alert=True)
            return

        await callback.answer()

        text = (
            f"📦 {product.name}\n\n{product.description}\n\n"
            f"💰 {pricing.format_price(product.price, product.original_price)}"
        )
        note = pricing.savings_line(product.price, product.original_price)
        if note:
            text += f"\n{note}"
        reply_markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🛒 Buy Now", callback_data=f"shop_buy:{product.id}")],
                [InlineKeyboardButton(text="➕ Add to Cart", callback_data=f"cart_add:{product.id}")],
            ]
        )

        if product.image_url:
            try:
                await callback.message.answer_photo(
                    product.image_url, caption=text, reply_markup=reply_markup
                )
                return
            except Exception:
                logger.warning("Failed to send product %s image, falling back to text", product.id)

        await callback.message.answer(text, reply_markup=reply_markup)

    @dp.callback_query(F.data.startswith("shop_buy:"))
    async def handle_shop_buy(callback: CallbackQuery) -> None:
        product_id = int(callback.data.split(":")[-1])
        order = await shop.create_order(bot_id, product_id, callback.from_user.id)

        if order is None:
            await callback.answer("Not available — it may be sold out.", show_alert=True)
            return

        settings = await shop.get_shop_settings(bot_id)
        buttons = []
        if settings and settings.zarinpal_merchant_id:
            buttons.append(
                InlineKeyboardButton(text="💳 Zarinpal", callback_data=f"shop_pay:zarinpal:{order.id}")
            )
        if settings and settings.card_number:
            buttons.append(
                InlineKeyboardButton(text="🏦 Card to Card", callback_data=f"shop_pay:card:{order.id}")
            )
        if settings and settings.stripe_secret_key:
            buttons.append(
                InlineKeyboardButton(text="🌍 Stripe (USD)", callback_data=f"shop_pay:stripe:{order.id}")
            )
        if settings and settings.crypto_wallet_address:
            buttons.append(
                InlineKeyboardButton(text="🪙 Crypto", callback_data=f"shop_pay:crypto:{order.id}")
            )
        if settings and settings.ton_wallet_address:
            buttons.append(
                InlineKeyboardButton(text="💎 TON", callback_data=f"shop_pay:ton:{order.id}")
            )

        await callback.answer()
        if not buttons:
            await callback.message.answer(
                "Payment isn't set up for this bot yet. Please contact the bot owner."
            )
            return

        await callback.message.answer(
            f"💰 Total: {shop.order_total(order):,} Toman\n\nChoose a payment method:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[b] for b in buttons]),
        )

    @dp.callback_query(F.data.startswith("shop_pay:zarinpal:"))
    async def handle_pay_zarinpal(callback: CallbackQuery) -> None:
        order_id = int(callback.data.split(":")[-1])
        order = await shop.get_order(order_id)
        if order is None or order.bot_id != bot_id:
            await callback.answer("Order not found.", show_alert=True)
            return

        pay_url = await shop.start_zarinpal_payment(order, _config.webapp_url)
        await callback.answer()
        if pay_url is None:
            await callback.message.answer("Couldn't start the payment. Please try again later.")
            return

        await callback.message.answer(
            "Tap below to pay:",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="🔗 Pay Now", url=pay_url)]]
            ),
        )
        await _send_pay_disclaimer(callback.message, irreversible=False)

    @dp.callback_query(F.data.startswith("shop_pay:stripe:"))
    async def handle_pay_stripe(callback: CallbackQuery) -> None:
        order_id = int(callback.data.split(":")[-1])
        order = await shop.get_order(order_id)
        if order is None or order.bot_id != bot_id:
            await callback.answer("Order not found.", show_alert=True)
            return

        pay_url = await shop.start_stripe_payment(order, _config.webapp_url)
        await callback.answer()
        if pay_url is None:
            await callback.message.answer("Couldn't start the payment. Please try again later.")
            return

        await callback.message.answer(
            "Tap below to pay:",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="🔗 Pay Now", url=pay_url)]]
            ),
        )
        await _send_pay_disclaimer(callback.message, irreversible=False)

    # Card-to-card, crypto, and TON all share one "buyer submits a tx ref,
    # owner approves/rejects" review flow (bot/shop.py:submit_manual_payment)
    # — only the info message shown to the buyer differs per method.
    _manual_payment_method_labels = {"card_to_card": "Card to Card", "crypto": "Crypto", "ton": "TON"}

    async def _start_manual_payment(
        callback: CallbackQuery, state: FSMContext, order_id: int, method: str, info_text: str
    ) -> None:
        order = await shop.get_order(order_id)
        if order is None or order.bot_id != bot_id:
            await callback.answer("Order not found.", show_alert=True)
            return

        await state.update_data(card_order_id=order_id, card_payment_method=method)
        await state.set_state(ShopOrderStates.waiting_for_transaction_ref)
        await callback.answer()
        await callback.message.answer(
            f"{info_text}\n\n"
            f"💰 Amount: {shop.order_total(order):,} Toman\n\n"
            "After paying, send the transaction reference number (or hash)."
        )
        await _send_pay_disclaimer(callback.message, irreversible=True)

    @dp.callback_query(F.data.startswith("shop_pay:card:"))
    async def handle_pay_card(callback: CallbackQuery, state: FSMContext) -> None:
        order_id = int(callback.data.split(":")[-1])
        settings = await shop.get_shop_settings(bot_id)
        if settings is None or not settings.card_number:
            await callback.answer("Card-to-card isn't set up for this bot.", show_alert=True)
            return

        await _start_manual_payment(
            callback, state, order_id, "card_to_card",
            f"💳 Card number: {settings.card_number}\n👤 {settings.card_holder_name or ''}",
        )

    @dp.callback_query(F.data.startswith("shop_pay:crypto:"))
    async def handle_pay_crypto(callback: CallbackQuery, state: FSMContext) -> None:
        order_id = int(callback.data.split(":")[-1])
        settings = await shop.get_shop_settings(bot_id)
        if settings is None or not settings.crypto_wallet_address:
            await callback.answer("Crypto payment isn't set up for this bot.", show_alert=True)
            return

        label = settings.crypto_network_label or "Crypto"
        await _start_manual_payment(
            callback, state, order_id, "crypto",
            f"🪙 {label} wallet address:\n{settings.crypto_wallet_address}",
        )

    @dp.callback_query(F.data.startswith("shop_pay:ton:"))
    async def handle_pay_ton(callback: CallbackQuery, state: FSMContext) -> None:
        order_id = int(callback.data.split(":")[-1])
        settings = await shop.get_shop_settings(bot_id)
        if settings is None or not settings.ton_wallet_address:
            await callback.answer("TON payment isn't set up for this bot.", show_alert=True)
            return

        await _start_manual_payment(
            callback, state, order_id, "ton", f"💎 TON wallet address:\n{settings.ton_wallet_address}"
        )

    @dp.message(ShopOrderStates.waiting_for_transaction_ref)
    async def receive_transaction_ref(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        order_id = data.get("card_order_id")
        method = data.get("card_payment_method", "card_to_card")
        order = await shop.get_order(order_id) if order_id else None
        if order is None:
            await state.clear()
            return

        ref = (message.text or "").strip()
        if not ref:
            await message.answer("Please send the transaction reference number, or /cancel to abort.")
            return

        order = await shop.submit_manual_payment(order_id, method, ref)
        await state.clear()
        await message.answer("Thanks! Your payment is pending review by the bot owner.")

        if owner_telegram_id is not None:
            product = await shop.get_product(order.product_id)
            try:
                await bot.send_message(
                    owner_telegram_id,
                    f"🧾 New order #{order.id}\n"
                    f"Product: {product.name if product else '?'}\n"
                    f"Price: {shop.order_total(order):,} Toman\n"
                    f"Payment method: {_manual_payment_method_labels.get(method, method)}\n"
                    f"Buyer: {order.buyer_telegram_id}\n"
                    f"Order date: {order.created_at:%Y-%m-%d %H:%M}\n"
                    f"Transaction ref: {ref}",
                    reply_markup=InlineKeyboardMarkup(
                        inline_keyboard=[
                            [
                                InlineKeyboardButton(
                                    text="✅ Confirm", callback_data=f"order_approve:{order.id}"
                                ),
                                InlineKeyboardButton(
                                    text="❌ Reject", callback_data=f"order_reject:{order.id}"
                                ),
                            ]
                        ]
                    ),
                )
            except Exception:
                logger.warning("Failed to notify owner about order %s", order.id)

    @dp.callback_query(F.data.startswith("order_approve:"), F.from_user.id == owner_telegram_id)
    async def handle_order_approve(callback: CallbackQuery) -> None:
        order_id = int(callback.data.split(":")[-1])
        order = await shop.approve_manual_payment(bot, order_id)
        await callback.answer("Approved ✅")
        if order is not None:
            await callback.message.edit_reply_markup(reply_markup=None)

    @dp.callback_query(F.data.startswith("order_reject:"), F.from_user.id == owner_telegram_id)
    async def handle_order_reject(callback: CallbackQuery) -> None:
        order_id = int(callback.data.split(":")[-1])
        await shop.reject_manual_payment(order_id)
        await callback.answer("Rejected")
        await callback.message.edit_reply_markup(reply_markup=None)

        order = await shop.get_order(order_id)
        if order is not None:
            try:
                await bot.send_message(
                    order.buyer_telegram_id, "❌ Your payment was rejected by the bot owner."
                )
            except Exception:
                logger.warning("Failed to notify buyer about rejected order %s", order_id)

    @dp.callback_query(F.data.startswith("ship_info:"))
    async def start_shipping_wizard(callback: CallbackQuery, state: FSMContext) -> None:
        order_id = int(callback.data.split(":")[-1])
        await state.update_data(shipping_order_id=order_id)
        await state.set_state(ShopOrderStates.shipping_wizard)
        method_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=m, callback_data=f"ship_method:{order_id}:{m}")]
                for m in shop.SHIPPING_METHODS
            ]
        )
        await callback.message.answer("Choose a shipping method:", reply_markup=method_keyboard)
        await callback.answer()

    # Checkout-scoped mirror of the wizard above — collects shipping info
    # ONCE for every physical item in a cart checkout (instead of once per
    # item), so shop.fulfill_checkout can issue one combined invoice. Shares
    # the same ShopOrderStates.shipping_wizard state and step machinery;
    # _send_shipping_step below tells the two apart by which id ended up in
    # FSM data (shipping_order_id vs shipping_checkout_id).
    @dp.callback_query(F.data.startswith("shipc_info:"))
    async def start_checkout_shipping_wizard(callback: CallbackQuery, state: FSMContext) -> None:
        checkout_id = int(callback.data.split(":")[-1])
        await state.update_data(shipping_checkout_id=checkout_id)
        await state.set_state(ShopOrderStates.shipping_wizard)
        method_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=m, callback_data=f"shipc_method:{checkout_id}:{m}")]
                for m in shop.SHIPPING_METHODS
            ]
        )
        await callback.message.answer("Choose a shipping method:", reply_markup=method_keyboard)
        await callback.answer()

    _shipping_step_prompts = {
        "name": "Recipient's full name?",
        "phone": "Phone number?",
        "address": "Full shipping address?",
        "postal_code": "Postal code?",
    }
    _shipping_steps = list(_shipping_step_prompts)

    async def _send_shipping_step(message: Message, state: FSMContext, index: int) -> None:
        if index >= len(_shipping_steps):
            data = await state.get_data()
            if "shipping_order_id" in data:
                order = await shop.save_shipping_info(
                    data["shipping_order_id"],
                    data["shipping_method"],
                    data.get("shipping_name", ""),
                    data.get("shipping_phone", ""),
                    data.get("shipping_address", ""),
                    data.get("shipping_postal_code", ""),
                )
                await state.clear()
                await message.answer("Thanks! Your order will ship soon.")
                await shop.fulfill_order(bot, order)
            else:
                checkout = await shop.save_checkout_shipping_info(
                    data["shipping_checkout_id"],
                    data["shipping_method"],
                    data.get("shipping_name", ""),
                    data.get("shipping_phone", ""),
                    data.get("shipping_address", ""),
                    data.get("shipping_postal_code", ""),
                )
                await state.clear()
                await message.answer("Thanks! Your order will ship soon.")
                await shop.fulfill_checkout(bot, checkout)
            return

        await state.update_data(shipping_step=index)
        await message.answer(_shipping_step_prompts[_shipping_steps[index]])

    @dp.callback_query(
        F.data.startswith(("ship_method:", "shipc_method:")), ShopOrderStates.shipping_wizard
    )
    async def pick_shipping_method(callback: CallbackQuery, state: FSMContext) -> None:
        method = callback.data.split(":", 2)[2]
        await state.update_data(shipping_method=method)
        await callback.answer()
        await _send_shipping_step(callback.message, state, 0)

    @dp.message(ShopOrderStates.shipping_wizard)
    async def shipping_wizard_receive(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        if "shipping_method" not in data:
            return  # still waiting for the method button tap
        index = data.get("shipping_step", 0)
        key = f"shipping_{_shipping_steps[index]}"
        await state.update_data(**{key: (message.text or "").strip()})
        await _send_shipping_step(message, state, index + 1)

    # --- Cart: "➕ Add to Cart" alongside the direct "🛒 Buy Now" flow above.
    # Checking out pays for every cart item at once via any configured
    # payment method, reusing the exact same gateways (bot/shop.py's
    # Checkout-scoped mirrors of the Order-scoped functions above). ---

    @dp.callback_query(F.data.startswith("cart_add:"))
    async def handle_cart_add(callback: CallbackQuery) -> None:
        product_id = int(callback.data.split(":")[-1])
        added = await shop.add_to_cart(bot_id, callback.from_user.id, product_id)
        await callback.answer("Added to cart ✅" if added else "Already in your cart")
        await callback.message.answer(
            "🧺 Your cart:",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="🧺 View Cart", callback_data="cart_view")]]
            ),
        )

    async def _send_cart(message: Message, buyer_telegram_id: int) -> None:
        items = await shop.get_cart_items(bot_id, buyer_telegram_id)
        if not items:
            await message.answer("🧺 Your cart is empty.")
            return

        total = sum(product.price for _cart_item, product in items)
        original_total = sum(
            (product.original_price or product.price) for _cart_item, product in items
        )
        entries = [
            {
                # A cart line with a product picture is shown as a photo; the
                # "❌ Remove" button sits under it. Lines without a picture
                # stay as plain remove-buttons in the summary below.
                "image_url": product.image_url,
                "label": f"❌ Remove {product.name}",
                "callback_data": f"cart_remove:{cart_item.id}",
                "caption": f"{product.name} — {pricing.format_price(product.price, product.original_price)}",
            }
            for cart_item, product in items
        ]
        summary = (
            "🧺 Your cart:\n"
            + "\n".join(
                f"• {p.name} — {pricing.format_price(p.price, p.original_price)}" for _c, p in items
            )
            + f"\n\n💰 Total: {pricing.format_price(total, original_total)}"
        )
        footer_rows = [[InlineKeyboardButton(text="💳 Checkout", callback_data="cart_checkout")]]
        await send_item_list(message, entries, trailing_text=summary, footer_rows=footer_rows)

    @dp.callback_query(F.data == "cart_view")
    async def handle_cart_view(callback: CallbackQuery) -> None:
        await _send_cart(callback.message, callback.from_user.id)
        await callback.answer()

    @dp.message(CommandFilter("cart"))
    async def handle_cart_command(message: Message) -> None:
        await _send_cart(message, message.from_user.id)

    @dp.callback_query(F.data.startswith("cart_remove:"))
    async def handle_cart_remove(callback: CallbackQuery) -> None:
        cart_item_id = int(callback.data.split(":")[-1])
        await shop.remove_from_cart(cart_item_id, bot_id, callback.from_user.id)
        await callback.answer("Removed")
        await _send_cart(callback.message, callback.from_user.id)

    @dp.callback_query(F.data == "cart_checkout")
    async def handle_cart_checkout(callback: CallbackQuery) -> None:
        checkout = await shop.create_checkout(bot_id, callback.from_user.id)
        if checkout is None:
            await callback.answer("Your cart is empty.", show_alert=True)
            return

        settings = await shop.get_shop_settings(bot_id)
        buttons = []
        if settings and settings.zarinpal_merchant_id:
            buttons.append(
                InlineKeyboardButton(text="💳 Zarinpal", callback_data=f"cart_pay:zarinpal:{checkout.id}")
            )
        if settings and settings.card_number:
            buttons.append(
                InlineKeyboardButton(text="🏦 Card to Card", callback_data=f"cart_pay:card:{checkout.id}")
            )
        if settings and settings.stripe_secret_key:
            buttons.append(
                InlineKeyboardButton(text="🌍 Stripe (USD)", callback_data=f"cart_pay:stripe:{checkout.id}")
            )
        if settings and settings.crypto_wallet_address:
            buttons.append(
                InlineKeyboardButton(text="🪙 Crypto", callback_data=f"cart_pay:crypto:{checkout.id}")
            )
        if settings and settings.ton_wallet_address:
            buttons.append(
                InlineKeyboardButton(text="💎 TON", callback_data=f"cart_pay:ton:{checkout.id}")
            )

        await callback.answer()
        if not buttons:
            await callback.message.answer(
                "Payment isn't set up for this bot yet. Please contact the bot owner."
            )
            return

        await callback.message.answer(
            f"💰 Total: {shop.checkout_total(checkout):,} Toman\n\nChoose a payment method:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[b] for b in buttons]),
        )

    @dp.callback_query(F.data.startswith("cart_pay:zarinpal:"))
    async def handle_cart_pay_zarinpal(callback: CallbackQuery) -> None:
        checkout_id = int(callback.data.split(":")[-1])
        checkout = await shop.get_checkout(checkout_id)
        if checkout is None or checkout.bot_id != bot_id:
            await callback.answer("Checkout not found.", show_alert=True)
            return

        pay_url = await shop.start_zarinpal_checkout(checkout, _config.webapp_url)
        await callback.answer()
        if pay_url is None:
            await callback.message.answer("Couldn't start the payment. Please try again later.")
            return

        await callback.message.answer(
            "Tap below to pay:",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="🔗 Pay Now", url=pay_url)]]
            ),
        )
        await _send_pay_disclaimer(callback.message, irreversible=False)

    @dp.callback_query(F.data.startswith("cart_pay:stripe:"))
    async def handle_cart_pay_stripe(callback: CallbackQuery) -> None:
        checkout_id = int(callback.data.split(":")[-1])
        checkout = await shop.get_checkout(checkout_id)
        if checkout is None or checkout.bot_id != bot_id:
            await callback.answer("Checkout not found.", show_alert=True)
            return

        pay_url = await shop.start_stripe_checkout(checkout, _config.webapp_url)
        await callback.answer()
        if pay_url is None:
            await callback.message.answer("Couldn't start the payment. Please try again later.")
            return

        await callback.message.answer(
            "Tap below to pay:",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="🔗 Pay Now", url=pay_url)]]
            ),
        )
        await _send_pay_disclaimer(callback.message, irreversible=False)

    async def _start_manual_checkout_payment(
        callback: CallbackQuery, state: FSMContext, checkout_id: int, method: str, info_text: str
    ) -> None:
        checkout = await shop.get_checkout(checkout_id)
        if checkout is None or checkout.bot_id != bot_id:
            await callback.answer("Checkout not found.", show_alert=True)
            return

        await state.update_data(cart_checkout_id=checkout_id, cart_payment_method=method)
        await state.set_state(ShopOrderStates.waiting_for_checkout_transaction_ref)
        await callback.answer()
        await callback.message.answer(
            f"{info_text}\n\n"
            f"💰 Amount: {shop.checkout_total(checkout):,} Toman\n\n"
            "After paying, send the transaction reference number (or hash)."
        )
        await _send_pay_disclaimer(callback.message, irreversible=True)

    @dp.callback_query(F.data.startswith("cart_pay:card:"))
    async def handle_cart_pay_card(callback: CallbackQuery, state: FSMContext) -> None:
        checkout_id = int(callback.data.split(":")[-1])
        settings = await shop.get_shop_settings(bot_id)
        if settings is None or not settings.card_number:
            await callback.answer("Card-to-card isn't set up for this bot.", show_alert=True)
            return

        await _start_manual_checkout_payment(
            callback, state, checkout_id, "card_to_card",
            f"💳 Card number: {settings.card_number}\n👤 {settings.card_holder_name or ''}",
        )

    @dp.callback_query(F.data.startswith("cart_pay:crypto:"))
    async def handle_cart_pay_crypto(callback: CallbackQuery, state: FSMContext) -> None:
        checkout_id = int(callback.data.split(":")[-1])
        settings = await shop.get_shop_settings(bot_id)
        if settings is None or not settings.crypto_wallet_address:
            await callback.answer("Crypto payment isn't set up for this bot.", show_alert=True)
            return

        label = settings.crypto_network_label or "Crypto"
        await _start_manual_checkout_payment(
            callback, state, checkout_id, "crypto",
            f"🪙 {label} wallet address:\n{settings.crypto_wallet_address}",
        )

    @dp.callback_query(F.data.startswith("cart_pay:ton:"))
    async def handle_cart_pay_ton(callback: CallbackQuery, state: FSMContext) -> None:
        checkout_id = int(callback.data.split(":")[-1])
        settings = await shop.get_shop_settings(bot_id)
        if settings is None or not settings.ton_wallet_address:
            await callback.answer("TON payment isn't set up for this bot.", show_alert=True)
            return

        await _start_manual_checkout_payment(
            callback, state, checkout_id, "ton", f"💎 TON wallet address:\n{settings.ton_wallet_address}"
        )

    @dp.message(ShopOrderStates.waiting_for_checkout_transaction_ref)
    async def receive_checkout_transaction_ref(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        checkout_id = data.get("cart_checkout_id")
        method = data.get("cart_payment_method", "card_to_card")
        checkout = await shop.get_checkout(checkout_id) if checkout_id else None
        if checkout is None:
            await state.clear()
            return

        ref = (message.text or "").strip()
        if not ref:
            await message.answer("Please send the transaction reference number, or /cancel to abort.")
            return

        checkout = await shop.submit_manual_checkout_payment(checkout_id, method, ref)
        await state.clear()
        await message.answer("Thanks! Your payment is pending review by the bot owner.")

        if owner_telegram_id is not None:
            try:
                await bot.send_message(
                    owner_telegram_id,
                    f"🧾 New cart checkout #{checkout.id}\n"
                    f"Total: {shop.checkout_total(checkout):,} Toman\n"
                    f"Payment method: {_manual_payment_method_labels.get(method, method)}\n"
                    f"Buyer: {checkout.buyer_telegram_id}\n"
                    f"Order date: {checkout.created_at:%Y-%m-%d %H:%M}\n"
                    f"Transaction ref: {ref}",
                    reply_markup=InlineKeyboardMarkup(
                        inline_keyboard=[
                            [
                                InlineKeyboardButton(
                                    text="✅ Confirm", callback_data=f"cart_approve:{checkout.id}"
                                ),
                                InlineKeyboardButton(
                                    text="❌ Reject", callback_data=f"cart_reject:{checkout.id}"
                                ),
                            ]
                        ]
                    ),
                )
            except Exception:
                logger.warning("Failed to notify owner about checkout %s", checkout.id)

    @dp.callback_query(F.data.startswith("cart_approve:"), F.from_user.id == owner_telegram_id)
    async def handle_cart_approve(callback: CallbackQuery) -> None:
        checkout_id = int(callback.data.split(":")[-1])
        checkout = await shop.approve_manual_checkout(bot, checkout_id)
        await callback.answer("Approved ✅")
        if checkout is not None:
            await callback.message.edit_reply_markup(reply_markup=None)

    @dp.callback_query(F.data.startswith("cart_reject:"), F.from_user.id == owner_telegram_id)
    async def handle_cart_reject(callback: CallbackQuery) -> None:
        checkout_id = int(callback.data.split(":")[-1])
        await shop.reject_manual_checkout(checkout_id)
        await callback.answer("Rejected")
        await callback.message.edit_reply_markup(reply_markup=None)

        checkout = await shop.get_checkout(checkout_id)
        if checkout is not None:
            try:
                await bot.send_message(
                    checkout.buyer_telegram_id, "❌ Your payment was rejected by the bot owner."
                )
            except Exception:
                logger.warning("Failed to notify buyer about rejected checkout %s", checkout_id)

    async def _save_subscriber_phone_and_resume(
        message: Message, state: FSMContext, phone: str, thanks_text: str
    ) -> None:
        async with async_session_maker() as session:
            result = await session.execute(
                select(BotSubscriber).where(
                    BotSubscriber.bot_id == bot_id,
                    BotSubscriber.telegram_id == message.from_user.id,
                )
            )
            subscriber = result.scalar_one_or_none()
            if subscriber is not None:
                subscriber.phone_number = phone
                await session.commit()

        data = await state.get_data()
        legacy_command_id = data.get("resume_legacy_command_id")
        command = data.get("resume_flow_command", "/start")
        await state.clear()
        await message.answer(thanks_text, reply_markup=ReplyKeyboardRemove())

        if legacy_command_id is not None:
            # Paused mid guide_video action from handle_legacy_command
            # (chat-defined command, not a Visual Builder flow) — resume
            # that single action now that we have a phone number/skip.
            async with async_session_maker() as session:
                result = await session.execute(select(Command).where(Command.id == legacy_command_id))
                legacy_command = result.scalar_one_or_none()
            if legacy_command is not None and legacy_command.payload:
                await _execute_node(
                    bot, bot_id, legacy_command.payload.get("action"), legacy_command.payload,
                    message, state, {"resume_legacy_command_id": legacy_command.id},
                )
            return

        async with async_session_maker() as session:
            result = await session.execute(select(BuiltBot).where(BuiltBot.id == bot_id))
            built_bot = result.scalar_one_or_none()
        if built_bot and built_bot.flow_definition:
            await run_flow(bot, bot_id, built_bot.flow_definition, command, message, state)

    @dp.message(SubscriberOnboardingStates.waiting_for_phone, F.contact)
    async def receive_subscriber_phone(message: Message, state: FSMContext) -> None:
        phone = message.contact.phone_number
        if not phone.startswith("+"):
            phone = f"+{phone}"
        await _save_subscriber_phone_and_resume(message, state, phone, "Thanks! 🙌")

    @dp.message(SubscriberOnboardingStates.waiting_for_phone, F.text == SKIP_BUTTON_TEXT)
    async def skip_subscriber_phone(message: Message, state: FSMContext) -> None:
        # "" (not None) marks this as already asked-and-skipped — see
        # bot/flow_engine.py's guide_video node.
        await _save_subscriber_phone_and_resume(message, state, "", "Okay ✅")

    @dp.message(SubscriberOnboardingStates.waiting_for_phone, F.text)
    async def receive_typed_subscriber_phone(message: Message, state: FSMContext) -> None:
        phone = normalize_typed_phone(message.text)
        if phone is None:
            await message.answer(TYPED_PHONE_INVALID, reply_markup=phone_share_keyboard())
            return
        await _save_subscriber_phone_and_resume(message, state, phone, "Thanks! 🙌")

    async def _find_legacy_command(command_token: str) -> Command | None:
        async with async_session_maker() as session:
            result = await session.execute(
                select(Command).where(
                    Command.bot_id == bot_id,
                    Command.name == command_token,
                    Command.command_type == "custom",
                )
            )
            return result.scalar_one_or_none()

    async def _has_legacy_action(message: Message) -> bool:
        """Filter for a command defined via the chat-based "Define Command"
        tool with a real action attached (bot/db/models.py: Command.payload
        ["action"] — see bot/handlers/tools/define_command.py). Same
        "newest edit wins" tie-break as _should_use_flow_for_start, but
        generalized to every command name: if a Visual Builder flow trigger
        for this same command exists and was edited more recently, this
        returns False so the message falls through to handle_flow_command
        instead."""
        if not message.text or not message.text.startswith("/") or message.text == "/start":
            return False
        command_token = message.text.split()[0].split("@")[0]

        command = await _find_legacy_command(command_token)
        if command is None or not command.payload or not command.payload.get("action"):
            return False

        async with async_session_maker() as session:
            result = await session.execute(select(BuiltBot).where(BuiltBot.id == bot_id))
            built_bot = result.scalar_one_or_none()
        if built_bot and built_bot.flow_definition:
            if find_trigger_node(built_bot.flow_definition, command_token) is not None:
                if built_bot.flow_updated_at and built_bot.flow_updated_at > command.updated_at:
                    return False

        return True

    @dp.message(_has_legacy_action)
    async def handle_legacy_command(message: Message, state: FSMContext) -> None:
        """Runs the action attached to a command defined via the chat-based
        "Define Command" tool — the non-Visual-Builder half of the same
        capability handle_flow_command gives builder users. Shares
        _execute_node with run_flow so gates (force_join_gate, guide_video)
        pause/resume identically either way — see flow_engine.py module
        docstring."""
        command_token = message.text.split()[0].split("@")[0]
        command = await _find_legacy_command(command_token)
        if command is None or not command.payload:
            return

        if command.visibility == "admin" and message.from_user.id != owner_telegram_id:
            # Admin-only command — invisible on everyone else's command menu
            # (sync_bot_commands) and inert here too, in case someone types
            # it out by hand instead of tapping the menu.
            return

        await _register_subscriber(message.from_user.id)
        await _execute_node(
            bot, bot_id, command.payload.get("action"), command.payload, message, state,
            {"resume_legacy_command_id": command.id},
        )

    async def _has_flow_trigger(message: Message) -> bool:
        """Filter (not just a handler check) so an unmatched command falls
        through to the next handler (e.g. handle_owner_command) instead of
        being silently swallowed — see module notes on aiogram dispatch."""
        if not message.text or not message.text.startswith("/") or message.text == "/start":
            return False
        command_token = message.text.split()[0].split("@")[0]

        async with async_session_maker() as session:
            result = await session.execute(select(BuiltBot).where(BuiltBot.id == bot_id))
            built_bot = result.scalar_one_or_none()

        if not built_bot or not built_bot.flow_definition:
            return False

        return find_trigger_node(built_bot.flow_definition, command_token) is not None

    @dp.message(_has_flow_trigger)
    async def handle_flow_command(message: Message, state: FSMContext) -> None:
        """Runs a flow defined for any command besides /start (which
        handle_start already covers) — lets the visual builder define
        arbitrary commands, the same capability "Define Command" gives the
        chat-based tools."""
        command_token = message.text.split()[0].split("@")[0]

        async with async_session_maker() as session:
            result = await session.execute(select(BuiltBot).where(BuiltBot.id == bot_id))
            built_bot = result.scalar_one_or_none()

        await _register_subscriber(message.from_user.id)
        await run_flow(bot, bot_id, built_bot.flow_definition, command_token, message, state)

    @dp.message(
        BuiltBotBroadcastStates.waiting_for_message,
        CommandFilter("cancel"),
        F.from_user.id == owner_telegram_id,
    )
    async def cancel_broadcast(message: Message, state: FSMContext) -> None:
        await state.clear()
        await message.answer("Broadcast cancelled ❌")

    @dp.message(BuiltBotBroadcastStates.waiting_for_message, F.from_user.id == owner_telegram_id)
    async def handle_broadcast_message(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        command_name = data.get("broadcast_command", "")
        await state.clear()

        sent = await _broadcast_to_subscribers(bot_id, command_name, message)
        await message.answer(f"Message sent to {sent} user(s) ✅")

    @dp.message(F.text.startswith("/"), F.from_user.id == owner_telegram_id)
    async def handle_owner_command(message: Message, state: FSMContext) -> None:
        command_token = message.text.split()[0].split("@")[0]

        async with async_session_maker() as session:
            result = await session.execute(
                select(Command).where(
                    Command.bot_id == bot_id,
                    Command.name == command_token,
                    Command.command_type == "broadcast",
                )
            )
            command = result.scalar_one_or_none()

        if command is None:
            return

        await state.update_data(broadcast_command=command_token)
        await state.set_state(BuiltBotBroadcastStates.waiting_for_message)
        await message.answer(
            "Send the message you want to deliver to all users of this bot.\n\n"
            "Or send /cancel to abort."
        )

    @dp.message(F.text, ~F.text.startswith("/"))
    async def handle_possible_content_code(message: Message) -> None:
        """Falls through here only once nothing else matched (state-scoped
        and command handlers above all take priority) — checks the plain
        text against this bot's content-item shortcut codes (bot/db/models.py:
        ContentItem.code) and, if it matches, jumps straight to that item.
        Silently ignored if it's not a recognized code."""
        item = await get_item_by_code(bot_id, message.text or "")
        if item is None:
            return

        await _register_subscriber(message.from_user.id)

        drilled_in = await _send_content_children(message, item.id, item.parent_id, f"📁 {item.title}")
        if drilled_in:
            return

        await _send_content_post(message, item, edit=False)

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await sync_bot_commands(bot_id)
        await dp.start_polling(bot)
    except Exception:
        logger.exception("Built bot %s crashed", bot_id)
    finally:
        await bot.session.close()


def start_built_bot(bot_id: uuid.UUID, token: str) -> None:
    """Starts (or restarts) the live polling task for one built bot."""
    key = str(bot_id)
    existing = _running_bots.get(key)
    if existing is not None and not existing.done():
        return

    task = asyncio.create_task(_run_bot(bot_id, token))
    _running_bots[key] = task


def stop_built_bot(bot_id: uuid.UUID) -> None:
    """Cancels a running built bot's polling task — its live window expired
    (bot/live.py). Idempotent: a no-op if it isn't currently running."""
    task = _running_bots.pop(str(bot_id), None)
    if task is not None and not task.done():
        task.cancel()


async def start_all_built_bots() -> None:
    """Starts polling only for bots currently within their live window
    (bot/live.py) AND not suspended by the platform admin (bot/admin_panel.py)
    — a bot that's never gone live, whose trial/plan has expired, or that's
    been suspended, stays registered but silent on Telegram."""
    async with async_session_maker() as session:
        result = await session.execute(select(BuiltBot))
        built_bots = list(result.scalars())

    now = datetime.now(timezone.utc)
    live_bots = [
        b for b in built_bots
        if b.live_until is not None and b.live_until > now and not b.suspended
    ]
    for built_bot in live_bots:
        start_built_bot(built_bot.id, built_bot.token)

    if live_bots:
        logger.info("Started %d built bot(s)", len(live_bots))


async def run_live_expiry_loop(interval_seconds: int = 300) -> None:
    """Background loop (started once from bot/main.py) that stops any
    currently-running built bot whose live_until has passed OR that's been
    suspended by the platform admin since it started. Activation (trial
    start / a plan purchase / an admin unsuspend) starts a bot immediately
    via start_built_bot elsewhere, so this loop only ever needs to handle
    the other direction: expiry or suspension."""
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            running_ids = [uuid.UUID(k) for k in _running_bots]
            if not running_ids:
                continue
            async with async_session_maker() as session:
                result = await session.execute(select(BuiltBot).where(BuiltBot.id.in_(running_ids)))
                bots = list(result.scalars())

            now = datetime.now(timezone.utc)
            for b in bots:
                if b.suspended:
                    stop_built_bot(b.id)
                    logger.info("Bot %s was suspended, stopped polling", b.id)
                elif b.live_until is not None and b.live_until <= now:
                    stop_built_bot(b.id)
                    logger.info("Bot %s's live window expired, stopped polling", b.id)
        except Exception:
            logger.exception("Live-expiry check failed")


async def run_campaign_expiry_loop(interval_seconds: int = 300) -> None:
    """Background loop (started once from bot/main.py) that reverts every
    price campaign (bot/shop.py) past its ends_at back to the pre-campaign
    prices. Runs for all bots, live or not, so the data is always correct."""
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            reverted = await shop.expire_due_campaigns()
            for bot_id in reverted:
                logger.info("Price campaign for bot %s ended, prices reverted", bot_id)
        except Exception:
            logger.exception("Price-campaign expiry check failed")
