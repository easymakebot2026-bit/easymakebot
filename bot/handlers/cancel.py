from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.guide import owner_prefers_persian
from bot.keyboards import CANCEL_BUTTON_TEXTS, tools_reply_keyboard, welcome_keyboard

router = Router(name="cancel")


async def _reset_state(state: FSMContext) -> str | None:
    """Clears whatever multi-step flow is in progress, keeping active_bot_id (if any)
    so cancelling a tool drops you back into that bot's edit environment, not the top menu."""
    data = await state.get_data()
    bot_id = data.get("active_bot_id")
    if bot_id:
        await state.set_state(None)
        await state.set_data({"active_bot_id": bot_id})
    else:
        await state.clear()
    return bot_id


async def _send_cancelled(message: Message, state: FSMContext, is_fa: bool) -> None:
    bot_id = await _reset_state(state)
    if bot_id:
        text = "لغو شد ❌ بازگشت به منوی ابزارها." if is_fa else "Cancelled ❌ Back to the tools menu."
        await message.answer(text, reply_markup=tools_reply_keyboard(is_fa))
    else:
        # Now that the whole builder nav is reply-keyboard-driven, a single
        # message with the new keyboard replaces whatever was showing —
        # no separate ReplyKeyboardRemove step needed first.
        text = "لغو شد ❌ چیکار می‌خوای بکنی؟" if is_fa else "Cancelled ❌ What would you like to do?"
        await message.answer(text, reply_markup=welcome_keyboard(is_fa))


@router.message(Command("cancel"))
async def cancel_command(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    await _send_cancelled(message, state, is_fa)


# "❌ Cancel" / "❌ لغو" is reserved app-wide for this one exit-the-current-flow
# action — every tool-local "back to my own menu" button uses different
# wording (e.g. "🔙 Back to Shop Menu") precisely so this global match never
# shadows them. This router registers first in bot/main.py, ahead of every
# state-scoped tool router, so it always wins regardless of current state.
# Matches BOTH language variants (bot/keyboards.py:CANCEL_BUTTON_TEXTS) so
# cancel always works no matter which language the button was shown in.
@router.message(F.text.in_(CANCEL_BUTTON_TEXTS))
async def cancel_text(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    await _send_cancelled(message, state, is_fa)


@router.callback_query(F.data == "cancel_flow")
async def cancel_callback(callback: CallbackQuery, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(callback.from_user)
    await _send_cancelled(callback.message, state, is_fa)
    await callback.answer()
