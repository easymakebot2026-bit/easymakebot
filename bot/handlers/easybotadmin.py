"""/easybotadmin — the platform owner's (PLATFORM_ADMIN_ID) view across
every user and every built bot. Every single handler below is gated by
_is_platform_admin (bot/filters/admin.py:IsPlatformAdmin), the exact same
filter already protecting /send_to_all (bot/handlers/admin_broadcast.py) —
nothing here is reachable by anyone else. Query/mutation logic itself lives
in bot/admin_panel.py; this file is Telegram-handler wiring only."""

from aiogram import Bot, F, Router
from aiogram.filters import Command as CommandFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from bot import admin_panel, live
from bot.config import load_config
from bot.filters.admin import IsPlatformAdmin
from bot.keyboards import (
    admin_bot_cancel_keyboard,
    admin_bot_detail_keyboard,
    admin_bots_keyboard,
    admin_grant_access_keyboard,
    admin_panel_menu_keyboard,
    admin_stats_keyboard,
    admin_user_detail_keyboard,
    admin_users_keyboard,
    cancel_inline_keyboard,
)
from bot.states import AdminBroadcastStates, AdminPanelStates

router = Router(name="easybotadmin")

_config = load_config()
_is_platform_admin = IsPlatformAdmin(_config.platform_admin_id)

PAGE_SIZE = 20


def _bot_status_line(built_bot) -> str:
    if live.is_bot_suspended(built_bot):
        return f"🚫 Suspended ({built_bot.suspension_reason or 'no reason given'})"
    if live.is_bot_live(built_bot):
        return f"🔓 Live until {built_bot.live_until:%Y-%m-%d %H:%M} UTC"
    if live.is_bot_expired(built_bot):
        return "🔒 Expired"
    return "⏸ Never activated"


async def _send_menu(message: Message) -> None:
    enabled = await admin_panel.get_bots_enabled()
    await message.answer(
        "🛡 easymakebot Platform Admin Panel", reply_markup=admin_panel_menu_keyboard(enabled)
    )


async def _send_bot_detail(message: Message, bot_id: str) -> bool:
    detail = await admin_panel.get_bot_detail(bot_id)
    if detail is None:
        return False

    built_bot, owner = detail["bot"], detail["owner"]
    lines = [
        f"🤖 {built_bot.display_name} (@{built_bot.bot_username})",
        f"Owner: {owner.telegram_id}",
        f"Status: {_bot_status_line(built_bot)}",
        f"Subscribers: {detail['subscriber_count']}",
        f"Paid orders: {detail['paid_order_count']} — revenue: {detail['revenue_toman']:,} Toman",
        f"Created: {built_bot.created_at:%Y-%m-%d}",
    ]
    await message.answer("\n".join(lines), reply_markup=admin_bot_detail_keyboard(built_bot))
    return True


@router.message(CommandFilter("easybotadmin"), _is_platform_admin)
async def open_admin_panel(message: Message) -> None:
    await _send_menu(message)


@router.callback_query(F.data == "admin:menu", _is_platform_admin)
async def back_to_admin_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(None)
    await _send_menu(callback.message)
    await callback.answer()


# --- Stats & activity --------------------------------------------------


@router.callback_query(F.data == "admin:stats", _is_platform_admin)
async def show_stats(callback: CallbackQuery) -> None:
    stats = await admin_panel.get_platform_stats()
    activity = await admin_panel.list_recent_activity(5)

    lines = [
        "📊 Platform Stats\n",
        f"Users: {stats['user_count']}",
        f"Bots: {stats['bot_count']} (live: {stats['bots_live']}, expired: {stats['bots_expired']}, "
        f"never activated: {stats['bots_never_activated']}, suspended: {stats['bots_suspended']})",
        f"Subscribers (all bots): {stats['subscriber_count']}",
        f"Products: {stats['product_count']}",
        f"Orders: {stats['order_count']} ({stats['paid_order_count']} paid)",
        f"Revenue: {stats['revenue_toman']:,} Toman",
        "",
        "📰 Recent activity:",
    ]
    for b in activity["bots"]:
        lines.append(f"  🤖 new bot: {b.display_name} (@{b.bot_username})")
    for order, bot_username in activity["orders"]:
        lines.append(f"  🧾 order #{order.id} on @{bot_username} — {order.price:,} Toman ({order.status})")
    for u in activity["users"]:
        lines.append(f"  👤 new user: {u.telegram_id}")

    await callback.message.answer("\n".join(lines), reply_markup=admin_stats_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin:export", _is_platform_admin)
async def export_report(callback: CallbackQuery, bot: Bot) -> None:
    await callback.answer("Generating…")
    data = await admin_panel.generate_report_excel()
    file = BufferedInputFile(data, filename="easymakebot_platform_report.xlsx")
    await callback.message.answer_document(file, caption="📊 Full platform report")


# --- Users ---------------------------------------------------------------


async def _send_users_page(message: Message, offset: int) -> None:
    users, has_more = await admin_panel.list_users_page(offset, PAGE_SIZE)
    if not users:
        await message.answer("No users yet.")
        return
    await message.answer(
        f"👥 Users (showing {offset + 1}-{offset + len(users)}):",
        reply_markup=admin_users_keyboard(users, offset, has_more, PAGE_SIZE),
    )


@router.callback_query(F.data == "admin:users", _is_platform_admin)
async def show_users(callback: CallbackQuery) -> None:
    await _send_users_page(callback.message, 0)
    await callback.answer()


@router.callback_query(F.data.startswith("admin:users_page:"), _is_platform_admin)
async def show_users_page(callback: CallbackQuery) -> None:
    offset = int(callback.data.split(":")[-1])
    await _send_users_page(callback.message, offset)
    await callback.answer()


@router.callback_query(F.data.startswith("admin:user:"), _is_platform_admin)
async def show_user_detail(callback: CallbackQuery) -> None:
    user_id = int(callback.data.split(":")[-1])
    detail = await admin_panel.get_user_detail(user_id)
    if detail is None:
        await callback.answer("User not found.", show_alert=True)
        return

    user, bots = detail["user"], detail["bots"]
    lines = [
        f"👤 User #{user.id}",
        f"Telegram ID: {user.telegram_id}",
        f"Joined: {user.created_at:%Y-%m-%d}",
    ]
    if user.phone_number:
        lines.append(f"Phone: {user.phone_number}")
    lines.append(f"\nBots ({len(bots)}):")
    for b in bots:
        lines.append(f"  • {b.display_name} (@{b.bot_username}) — {_bot_status_line(b)}")
    if not bots:
        lines.append("  (none yet)")

    await callback.message.answer("\n".join(lines), reply_markup=admin_user_detail_keyboard(bots))
    await callback.answer()


# --- Bots ------------------------------------------------------------------


async def _send_bots_page(message: Message, offset: int) -> None:
    bots, has_more = await admin_panel.list_bots_page(offset, PAGE_SIZE)
    if not bots:
        await message.answer("No bots yet.")
        return
    await message.answer(
        f"🤖 All Bots (showing {offset + 1}-{offset + len(bots)}):",
        reply_markup=admin_bots_keyboard(bots, offset, has_more, PAGE_SIZE),
    )


@router.callback_query(F.data == "admin:bots", _is_platform_admin)
async def show_bots(callback: CallbackQuery) -> None:
    await _send_bots_page(callback.message, 0)
    await callback.answer()


@router.callback_query(F.data.startswith("admin:bots_page:"), _is_platform_admin)
async def show_bots_page(callback: CallbackQuery) -> None:
    offset = int(callback.data.split(":")[-1])
    await _send_bots_page(callback.message, offset)
    await callback.answer()


@router.callback_query(F.data.startswith("admin:bot:"), _is_platform_admin)
async def show_bot_detail(callback: CallbackQuery) -> None:
    bot_id = callback.data.split(":")[-1]
    sent = await _send_bot_detail(callback.message, bot_id)
    if not sent:
        await callback.answer("Bot not found.", show_alert=True)
        return
    await callback.answer()


# --- Suspend / unsuspend (fraud kill switch) --------------------------------


@router.callback_query(F.data.startswith("admin:suspend:"), _is_platform_admin)
async def start_suspend(callback: CallbackQuery, state: FSMContext) -> None:
    bot_id = callback.data.split(":")[-1]
    await state.update_data(admin_target_bot_id=bot_id)
    await state.set_state(AdminPanelStates.waiting_for_suspend_reason)
    await callback.message.answer(
        "Send the reason for suspending this bot (shown to its owner). No plan purchase will "
        "undo this — only an explicit unsuspend from here can.",
        reply_markup=admin_bot_cancel_keyboard(bot_id),
    )
    await callback.answer()


@router.message(AdminPanelStates.waiting_for_suspend_reason, _is_platform_admin)
async def receive_suspend_reason(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    bot_id = data.get("admin_target_bot_id")
    reason = (message.text or "").strip()
    if not reason:
        await message.answer("Reason can't be empty.", reply_markup=admin_bot_cancel_keyboard(bot_id))
        return

    built_bot = await admin_panel.suspend_bot(bot_id, reason)
    await state.set_state(None)
    if built_bot is None:
        await message.answer("Bot not found.")
        return
    await message.answer(f"🚫 Suspended @{built_bot.bot_username} — it's offline on Telegram now.")
    await _send_bot_detail(message, bot_id)


@router.callback_query(F.data.startswith("admin:unsuspend:"), _is_platform_admin)
async def do_unsuspend(callback: CallbackQuery) -> None:
    bot_id = callback.data.split(":")[-1]
    built_bot = await admin_panel.unsuspend_bot(bot_id)
    if built_bot is None:
        await callback.answer("Bot not found.", show_alert=True)
        return
    await callback.answer("Unsuspended ✅")
    await _send_bot_detail(callback.message, bot_id)


# --- Grant access ("ایجاد دسترسی") -----------------------------------------


@router.callback_query(F.data.startswith("admin:grant:"), _is_platform_admin)
async def show_grant_menu(callback: CallbackQuery) -> None:
    bot_id = callback.data.split(":")[-1]
    await callback.message.answer(
        "Grant how much live time? (bypasses trial/payment)",
        reply_markup=admin_grant_access_keyboard(bot_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:grantdays:"), _is_platform_admin)
async def do_grant_access(callback: CallbackQuery) -> None:
    _, _, bot_id, days_raw = callback.data.split(":")
    days = None if days_raw == "permanent" else int(days_raw)

    built_bot = await admin_panel.grant_bot_access(bot_id, days)
    if built_bot is None:
        await callback.answer("Bot not found.", show_alert=True)
        return

    label = "permanently" if days is None else f"for {days} more days"
    await callback.answer("Granted ✅")
    note = "" if not built_bot.suspended else " (still suspended — unsuspend to actually go live)"
    await callback.message.answer(f"🎁 @{built_bot.bot_username} is now live {label}.{note}")
    await _send_bot_detail(callback.message, bot_id)


# --- Rename ------------------------------------------------------------


@router.callback_query(F.data.startswith("admin:rename:"), _is_platform_admin)
async def start_rename(callback: CallbackQuery, state: FSMContext) -> None:
    bot_id = callback.data.split(":")[-1]
    await state.update_data(admin_target_bot_id=bot_id)
    await state.set_state(AdminPanelStates.waiting_for_rename)
    await callback.message.answer(
        "Send the new display name.", reply_markup=admin_bot_cancel_keyboard(bot_id)
    )
    await callback.answer()


@router.message(AdminPanelStates.waiting_for_rename, _is_platform_admin)
async def receive_rename(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    bot_id = data.get("admin_target_bot_id")
    new_name = (message.text or "").strip()
    if not new_name:
        await message.answer("Name can't be empty.", reply_markup=admin_bot_cancel_keyboard(bot_id))
        return

    built_bot = await admin_panel.rename_bot(bot_id, new_name)
    await state.set_state(None)
    if built_bot is None:
        await message.answer("Bot not found.")
        return
    await message.answer(f'✏️ Renamed to "{new_name}" ✅')
    await _send_bot_detail(message, bot_id)


# --- Delete (type-to-confirm, given the cascade) ----------------------------


@router.callback_query(F.data.startswith("admin:delete:"), _is_platform_admin)
async def start_delete(callback: CallbackQuery, state: FSMContext) -> None:
    bot_id = callback.data.split(":")[-1]
    detail = await admin_panel.get_bot_detail(bot_id)
    if detail is None:
        await callback.answer("Bot not found.", show_alert=True)
        return

    built_bot = detail["bot"]
    await state.update_data(admin_target_bot_id=bot_id, admin_delete_username=built_bot.bot_username)
    await state.set_state(AdminPanelStates.waiting_for_delete_confirmation)
    await callback.message.answer(
        f"⚠️ This permanently deletes @{built_bot.bot_username} and EVERYTHING under it "
        "(commands, content, products, orders, subscribers, shop settings — no undo).\n\n"
        f"To confirm, type exactly: {built_bot.bot_username}",
        reply_markup=admin_bot_cancel_keyboard(bot_id),
    )
    await callback.answer()


@router.message(AdminPanelStates.waiting_for_delete_confirmation, _is_platform_admin)
async def receive_delete_confirmation(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    bot_id = data.get("admin_target_bot_id")
    expected = data.get("admin_delete_username")
    typed = (message.text or "").strip()

    if typed != expected:
        await message.answer(
            f'Doesn\'t match. Type exactly "{expected}" to confirm, or /cancel to abort.',
            reply_markup=admin_bot_cancel_keyboard(bot_id),
        )
        return

    ok = await admin_panel.delete_bot(bot_id)
    await state.set_state(None)
    if ok:
        await message.answer(f"🗑 Deleted @{expected} and everything under it.")
    else:
        await message.answer("Bot not found (already deleted?).")
    await _send_menu(message)


# --- Broadcast — reuses bot/handlers/admin_broadcast.py's own send logic, ---
# --- just entering the same FSM state from this menu too. ---


@router.callback_query(F.data == "admin:broadcast", _is_platform_admin)
async def start_broadcast_from_panel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminBroadcastStates.waiting_for_message)
    await callback.message.answer(
        "Send the message you want to deliver to every bot creator.",
        reply_markup=cancel_inline_keyboard(),
    )
    await callback.answer()


# --- Global maintenance switch (all built bots at once) ---------------------


@router.callback_query(F.data == "admin:toggle_bots", _is_platform_admin)
async def toggle_bots_enabled(callback: CallbackQuery) -> None:
    currently_enabled = await admin_panel.get_bots_enabled()
    now_enabled = not currently_enabled
    await admin_panel.set_bots_enabled(now_enabled)

    await callback.answer("Bots resumed ✅" if now_enabled else "Bots paused — /start now shows the maintenance message ⏸")
    await callback.message.edit_reply_markup(reply_markup=admin_panel_menu_keyboard(now_enabled))
