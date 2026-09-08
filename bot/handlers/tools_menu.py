from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot import live
from bot.guide import owner_prefers_persian
from bot.keyboards import TOOLS_MENU_BUTTON_TEXTS, tools_menu_keyboard

router = Router(name="tools_menu")


@router.message(F.text.in_(TOOLS_MENU_BUTTON_TEXTS))
async def show_tools(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    data = await state.get_data()
    bot_id = data.get("active_bot_id")

    if bot_id:
        built_bot = await live.get_built_bot(bot_id)
        if built_bot and live.is_bot_suspended(built_bot):
            # Platform-admin kill switch (bot/admin_panel.py) — takes
            # priority over the live/expired check; no plan can undo this.
            await message.answer(live.suspension_status_text(built_bot, is_fa))
            return
        if built_bot and live.is_bot_expired(built_bot):
            # Live window expired (bot/live.py) — every tool is gated behind
            # going live again instead of showing the tools grid. The actual
            # region-aware plan/payment-method picker lives in /live
            # (bot/handlers/live.py) — this just points there rather than
            # duplicating that resolution logic here too.
            extra = "\n\n/live رو بفرست تا پلن‌های پرداخت رو ببینی." if is_fa else "\n\nSend /live to see payment plans."
            await message.answer(f"{live.status_text(built_bot, is_fa)}{extra}")
            return

    text = "یکی از ابزارهای زیر رو انتخاب کن:" if is_fa else "Choose one of the tools below:"
    await message.answer(text, reply_markup=tools_menu_keyboard(is_fa))
