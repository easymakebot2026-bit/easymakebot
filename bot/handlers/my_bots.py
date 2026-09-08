from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from sqlalchemy import select

from bot import help_text, live
from bot.config import load_config
from bot.db.base import async_session_maker
from bot.db.models import BuiltBot, User
from bot.guide import owner_prefers_persian
from bot.keyboards import MY_BOTS_BUTTON_TEXTS, my_bots_keyboard, tools_reply_keyboard, webapp_keyboard

router = Router(name="my_bots")
_config = load_config()


async def _render_my_bots(telegram_id: int, is_fa: bool) -> tuple[str, InlineKeyboardMarkup]:
    async with async_session_maker() as session:
        user_result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = user_result.scalar_one_or_none()

        bots: list[BuiltBot] = []
        if user is not None:
            bots_result = await session.execute(
                select(BuiltBot).where(BuiltBot.owner_id == user.id).order_by(BuiltBot.created_at)
            )
            bots = list(bots_result.scalars())

    if is_fa:
        text = "ربات‌های تو:" if bots else "هنوز هیچ رباتی نساختی."
    else:
        text = "Your bots:" if bots else "You haven't built any bots yet."
    return text, my_bots_keyboard(bots, is_fa)


@router.message(F.text.in_(MY_BOTS_BUTTON_TEXTS))
async def show_my_bots(message: Message) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    text, keyboard = await _render_my_bots(message.from_user.id, is_fa)
    text += await help_text.tip_suffix("my_bots", message.from_user)
    await message.answer(text, reply_markup=keyboard)


@router.message(Command("mybots"))
async def cmd_my_bots(message: Message) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    text, keyboard = await _render_my_bots(message.from_user.id, is_fa)
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("select_bot:"))
async def select_bot(callback: CallbackQuery, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(callback.from_user)
    bot_id = callback.data.split(":", 1)[1]

    # get_owned_built_bot (not get_built_bot) — bot_id here comes straight
    # from callback_data, i.e. untrusted user input, so ownership must be
    # checked before this ever reaches active_bot_id in FSM state. Every
    # downstream tool trusts active_bot_id precisely because this is the
    # one gate it always passes through first.
    built_bot = await live.get_owned_built_bot(bot_id, callback.from_user.id)

    if built_bot is None:
        await callback.answer("ربات پیدا نشد." if is_fa else "Bot not found.", show_alert=True)
        return

    await state.update_data(active_bot_id=str(built_bot.id))
    await callback.answer()

    if live.is_bot_suspended(built_bot):
        # Platform-admin kill switch (bot/admin_panel.py) — takes priority
        # over the live/expired check; no plan can undo this.
        await callback.message.answer(live.suspension_status_text(built_bot, is_fa))
        return

    if live.is_bot_expired(built_bot):
        # Live window expired (bot/live.py) — skip the normal edit-mode
        # welcome entirely. The region-aware plan/payment-method picker
        # lives in /live (bot/handlers/live.py) — point there rather than
        # duplicating that resolution logic here too.
        extra = "\n\n/live رو بفرست تا پلن‌های پرداخت رو ببینی." if is_fa else "\n\nSend /live to see payment plans."
        await callback.message.answer(f"{live.status_text(built_bot, is_fa)}{extra}")
        return

    if is_fa:
        text = (
            f"وارد محیط ساخت‌وساز ربات «{built_bot.display_name}» شدی.\n"
            "از ابزار زیر برای توسعه‌ی رباتت استفاده کن."
        )
    else:
        text = (
            f"You are now in the build/edit environment for bot \"{built_bot.display_name}\".\n"
            "Please use the tool below to develop your bot."
        )
    await callback.message.answer(text, reply_markup=tools_reply_keyboard(is_fa))

    webapp_kb = webapp_keyboard(_config.webapp_url, built_bot.id, is_fa)
    if webapp_kb is not None:
        text2 = "دوست داری از بوم بصری استفاده کنی؟ سازنده‌ی درگ‌اند‌دراپ رو باز کن:" if is_fa else (
            "Prefer a visual canvas? Open the drag-and-drop builder:"
        )
        await callback.message.answer(text2, reply_markup=webapp_kb)
