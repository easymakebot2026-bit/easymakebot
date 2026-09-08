from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy import select

from bot import help_text
from bot.config import load_config
from bot.db.base import async_session_maker
from bot.db.models import BuiltBot, User
from bot.guide import owner_prefers_persian
from bot.keyboards import CREATE_BOT_BUTTON_TEXTS, cancel_reply_keyboard, tools_reply_keyboard, webapp_keyboard
from bot.session import make_session
from bot.states import CreateBotStates

router = Router(name="create_bot")
_config = load_config()


async def _ask_for_token(message: Message, state: FSMContext, tip_key: str | None, is_fa: bool) -> None:
    await state.set_state(CreateBotStates.waiting_for_token)
    text = "توکنی که از @BotFather گرفتی رو برام بفرست." if is_fa else "Send me the token you got from @BotFather."
    if tip_key:
        text += await help_text.tip_suffix(tip_key, message.from_user)
    await message.answer(text, reply_markup=cancel_reply_keyboard(is_fa))


@router.message(F.text.in_(CREATE_BOT_BUTTON_TEXTS))
async def ask_for_token(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    await _ask_for_token(message, state, "create_bot", is_fa)


@router.message(Command("newbot"))
async def cmd_new_bot(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    await _ask_for_token(message, state, None, is_fa)


@router.message(CreateBotStates.waiting_for_token)
async def receive_token(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    token = message.text.strip()

    temp_bot = None
    try:
        temp_bot = Bot(token=token, session=make_session())
        bot_info = await temp_bot.get_me()
    except Exception:
        text = (
            "این توکن معتبر نیست. یه توکن جدید از @BotFather بگیر و دوباره بفرست."
            if is_fa
            else "This token is not valid. Please get a new token from @BotFather and send it again."
        )
        await message.answer(text, reply_markup=cancel_reply_keyboard(is_fa))
        return
    finally:
        if temp_bot is not None:
            await temp_bot.session.close()

    async with async_session_maker() as session:
        user_result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = user_result.scalar_one_or_none()
        if user is None:
            user = User(telegram_id=message.from_user.id)
            session.add(user)
            await session.flush()

        built_bot = BuiltBot(
            owner_id=user.id,
            token=token,
            bot_username=bot_info.username or "",
            display_name=bot_info.full_name or bot_info.username or "Unnamed",
        )
        session.add(built_bot)
        await session.commit()
        await session.refresh(built_bot)

    await state.clear()
    await state.update_data(active_bot_id=str(built_bot.id))

    if is_fa:
        text = (
            f"ربات «{built_bot.display_name}» با موفقیت ثبت شد ✅\n\n"
            f"وارد محیط ساخت‌وساز ربات «{built_bot.display_name}» شدی.\n"
            "از ابزار زیر برای توسعه‌ی رباتت استفاده کن. هنوز روی تلگرام جواب نمی‌ده — "
            "وقتی تنظیماتش تموم شد، /live رو بفرست تا فعالش کنی."
        )
    else:
        text = (
            f"Bot \"{built_bot.display_name}\" registered successfully ✅\n\n"
            f"You are now in the build/edit environment for bot \"{built_bot.display_name}\".\n"
            "Please use the tool below to develop your bot. It won't respond on Telegram yet — "
            "once you're done setting it up, send /live to go live."
        )
    await message.answer(text, reply_markup=tools_reply_keyboard(is_fa))

    webapp_kb = webapp_keyboard(_config.webapp_url, built_bot.id, is_fa)
    if webapp_kb is not None:
        text2 = "دوست داری از بوم بصری استفاده کنی؟ سازنده‌ی درگ‌اند‌دراپ رو باز کن:" if is_fa else (
            "Prefer a visual canvas? Open the drag-and-drop builder:"
        )
        await message.answer(text2, reply_markup=webapp_kb)
