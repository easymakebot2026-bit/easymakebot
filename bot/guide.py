"""Shared phone-share onboarding + localized guide content.

Reused by easymakebot's own /start (bot/handlers/start.py) and the visual
flow builder's "Guide & Video" block (bot/flow_engine.py) — same mechanism
(ask once for a phone number, guess the country from its calling code,
remember it), different guide text per context.
"""

import re

from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup, User as TgUser
from sqlalchemy import select

from bot.config import load_config
from bot.db.base import async_session_maker
from bot.db.models import User
from bot.keyboards import video_keyboard

_config = load_config()

SHARE_PHONE_BUTTON_TEXT = "📱 Share Phone Number"
SKIP_BUTTON_TEXT = "⏭ Skip"

PHONE_RE = re.compile(r"^\+\d{6,15}$")

TYPED_PHONE_INVALID = (
    "Please use the button to share your phone, type it with the country code "
    "(e.g. +12025550123), or tap Skip."
)


def normalize_typed_phone(text: str) -> str | None:
    """A manually typed phone number is accepted alongside the contact-share
    button — must include the leading country code (e.g. +989121234567)."""
    text = (text or "").strip()
    return text if PHONE_RE.match(text) else None

PLATFORM_GUIDE_FA = (
    "📖 راهنمای استفاده از easymakebot:\n\n"
    "۱. از دکمه «Create New Bot» توکن رباتت (از @BotFather) رو وارد کن.\n"
    "۲. وارد محیط ساخت‌وساز اون بات می‌شی — از منوی «Build & Edit Tools» ابزارها رو ببین.\n"
    "۳. با «Define Command» دستورهای رباتت رو بساز (اولین‌شون معمولاً /start).\n"
    "۴. با «Message to All» یه دستور برای پیام‌رسانی گروهی به همه‌ی کاربرای رباتت بساز.\n"
    "۵. با «Force Join» می‌تونی کاربرا رو مجبور کنی قبل از استفاده از ربات، عضو کانال‌هات بشن.\n"
    "۶. یا از دکمه‌ی «🎨 Visual Builder» استفاده کن و فلوی ربات رو با درگ‌اند‌دراپ بصری بساز.\n\n"
    "هر وقت وسط یه مرحله گیر کردی، کافیه /cancel بزنی."
)

PLATFORM_GUIDE_EN = (
    "📖 How to use easymakebot:\n\n"
    "1. Tap \"Create New Bot\" and send the token you got from @BotFather.\n"
    "2. You'll enter that bot's build/edit environment — check the \"Build & Edit Tools\" menu.\n"
    "3. Use \"Define Command\" to set up your bot's commands (the first one is usually /start).\n"
    "4. Use \"Message to All\" to create a command that broadcasts a message to every user of your bot.\n"
    "5. Use \"Force Join\" to require users to join your channel(s) before using the bot.\n"
    "6. Or tap \"🎨 Visual Builder\" to build your bot's flow visually, block by block.\n\n"
    "Stuck mid-flow at any point? Just send /cancel."
)

BUILT_BOT_GUIDE_FA = (
    "📖 راهنمای استفاده از این ربات:\n\n"
    "برای شروع کافیه /start رو بفرستی. دکمه‌ها و دستورهایی که صاحب این ربات "
    "تعریف کرده رو می‌بینی — روشون بزن یا دستور مدنظرت رو تایپ کن."
)

BUILT_BOT_GUIDE_EN = (
    "📖 How to use this bot:\n\n"
    "Just send /start to begin. You'll see the buttons and commands this "
    "bot's owner has set up — tap one, or type the command you want."
)


def is_iran_phone(phone: str | None) -> bool:
    return bool(phone) and phone.startswith("+98")


async def owner_prefers_persian(tg_user: "TgUser") -> bool:
    """Persian vs English for an easymakebot owner — driven ONLY by the phone
    number they shared during onboarding (same detection as the Guide & Video
    block, is_iran_phone), never by the Telegram client's own app language.
    No phone on file yet (or a non-Iran phone) -> English, same default used
    everywhere else in the bot until a phone says otherwise."""
    async with async_session_maker() as session:
        phone = (
            await session.execute(
                select(User.phone_number).where(User.telegram_id == tg_user.id)
            )
        ).scalar_one_or_none()
    return is_iran_phone(phone)


def phone_share_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=SHARE_PHONE_BUTTON_TEXT, request_contact=True)],
            [KeyboardButton(text=SKIP_BUTTON_TEXT)],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


async def _send(message: Message, phone: str | None, text_fa: str, text_en: str) -> None:
    is_fa = is_iran_phone(phone)
    text = text_fa if is_fa else text_en
    video_url = _config.video_url_fa if is_fa else _config.video_url_en
    await message.answer(text, reply_markup=video_keyboard(video_url, is_fa))


async def send_platform_guide(message: Message, phone: str | None) -> None:
    await _send(message, phone, PLATFORM_GUIDE_FA, PLATFORM_GUIDE_EN)


async def send_built_bot_guide(message: Message, phone: str | None) -> None:
    await _send(message, phone, BUILT_BOT_GUIDE_FA, BUILT_BOT_GUIDE_EN)
