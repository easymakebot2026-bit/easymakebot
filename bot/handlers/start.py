from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardRemove
from sqlalchemy import select

from bot.db.base import async_session_maker
from bot.db.models import User
from bot.guide import (
    SKIP_BUTTON_TEXT,
    TYPED_PHONE_INVALID,
    is_iran_phone,
    normalize_typed_phone,
    phone_share_keyboard,
    send_platform_guide,
)
from bot.keyboards import welcome_keyboard
from bot.states import OnboardingStates

router = Router(name="start")

BOT_DESCRIPTION_EN = (
    "easymakebot helps you build and manage your own Telegram bots — no coding "
    "required. Create a bot, configure its commands, and it goes live right away."
)
BOT_DESCRIPTION_FA = (
    "با easymakebot می‌تونی ربات‌های تلگرامی خودت رو بدون نیاز به برنامه‌نویسی بسازی و مدیریت "
    "کنی. یه ربات بساز، دستورهاش رو تنظیم کن، همون لحظه فعال می‌شه."
)
# Back-compat name (English) for any external reference.
BOT_DESCRIPTION = BOT_DESCRIPTION_EN

PHONE_PROMPT = (
    "To get the guide and video tutorial in your language, share your phone "
    "number with the button below, or type it manually with the country code "
    "(optional)."
)


async def _save_phone_and_continue(message: Message, state: FSMContext, phone: str) -> None:
    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()
        if user is not None:
            user.phone_number = phone
            await session.commit()

    is_fa = is_iran_phone(phone)
    await state.clear()
    text = "ممنون! 🙌" if is_fa else "Thanks! 🙌"
    await message.answer(text, reply_markup=ReplyKeyboardRemove())
    await send_platform_guide(message, phone)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    telegram_id = message.from_user.id

    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if user is None:
            user = User(telegram_id=telegram_id)
            session.add(user)
            await session.commit()
        phone = user.phone_number

    # A phone on file (even the "" skip-marker) already tells us the right
    # language for THIS message; a brand-new user has no signal yet, so this
    # defaults to English same as everywhere else until a phone says otherwise.
    is_fa = is_iran_phone(phone) if phone is not None else False

    # /start is always the top-level "no bot selected" screen — drop any
    # leftover build/edit context (active_bot_id). Sending welcome_keyboard()
    # here replaces whatever reply keyboard was showing (e.g. a stale "🛠
    # Build & Edit Tools" button from a previous bot selection), so a single
    # message is enough — no ReplyKeyboardRemove needed first.
    await state.clear()
    if is_fa:
        text = (
            f"به easymakebot خوش اومدی، {telegram_id}!\n\n{BOT_DESCRIPTION_FA}\n\n"
            "چیکار می‌خوای بکنی؟"
        )
    else:
        text = f"Welcome to easymakebot, {telegram_id}!\n\n{BOT_DESCRIPTION_EN}\n\nWhat would you like to do?"
    await message.answer(text, reply_markup=welcome_keyboard(is_fa))

    if phone is not None:
        # "" means they already chose "Skip" before — don't ask again.
        await send_platform_guide(message, phone)
        return

    await state.set_state(OnboardingStates.waiting_for_phone)
    await message.answer(PHONE_PROMPT, reply_markup=phone_share_keyboard())


@router.message(OnboardingStates.waiting_for_phone, F.contact)
async def receive_phone(message: Message, state: FSMContext) -> None:
    phone = message.contact.phone_number
    if not phone.startswith("+"):
        phone = f"+{phone}"
    await _save_phone_and_continue(message, state, phone)


@router.message(OnboardingStates.waiting_for_phone, F.text == SKIP_BUTTON_TEXT)
async def skip_phone(message: Message, state: FSMContext) -> None:
    # "" (not None) marks this as already asked-and-skipped, so future
    # /start calls don't prompt again — see bot/flow_engine.py's guide_video
    # node for the same convention on the built-bot side.
    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()
        if user is not None:
            user.phone_number = ""
            await session.commit()

    await state.clear()
    await message.answer("Okay ✅", reply_markup=ReplyKeyboardRemove())
    await send_platform_guide(message, None)


@router.message(OnboardingStates.waiting_for_phone, F.text)
async def receive_typed_phone(message: Message, state: FSMContext) -> None:
    phone = normalize_typed_phone(message.text)
    if phone is None:
        await message.answer(TYPED_PHONE_INVALID, reply_markup=phone_share_keyboard())
        return
    await _save_phone_and_continue(message, state, phone)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    from bot.guide import owner_prefers_persian

    is_fa = await owner_prefers_persian(message.from_user)
    if is_fa:
        text = (
            "دستورهای easymakebot:\n\n"
            "/start — نمایش منوی خوش‌آمدگویی\n"
            "/mybots — لیست و انتخاب ربات‌هات\n"
            "/newbot — ساخت ربات جدید\n"
            "/live — فعال‌سازی روی تلگرام (آزمایشی یا خرید پلن)\n"
            "/help — نمایش همین راهنما\n\n"
            "از دکمه‌ها برای دیدن یا ساختن ربات‌هات استفاده کن، بعد از منوی "
            "«🛠 ابزارهای ساخت‌وساز» برای تنظیمشون."
        )
    else:
        text = (
            "easymakebot commands:\n\n"
            "/start — show the welcome menu\n"
            "/mybots — list and select your bots\n"
            "/newbot — create a new bot\n"
            "/live — go live on Telegram (trial or a paid plan)\n"
            "/help — show this help message\n\n"
            "Use the buttons to view or create your bots, then use the "
            "\"Build & Edit Tools\" menu to configure them."
        )
    await message.answer(text)
