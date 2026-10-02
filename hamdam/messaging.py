"""Channels a node can send through. Telegram and Bale share one class —
Bale implements the Telegram Bot API, so the same aiogram Bot works against
either, just pointed at a different API server."""

import logging
from dataclasses import dataclass

import aiohttp
from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.types import BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)


@dataclass
class Button:
    text: str
    data: str  # callback data


Buttons = list[list[Button]] | None


def to_markup(buttons: Buttons) -> InlineKeyboardMarkup | None:
    if not buttons:
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=b.text, callback_data=b.data) for b in row] for row in buttons]
    )


class Messenger:
    name: str = ""
    username: str | None = None

    async def send_text(self, chat_id: str, text: str, buttons: Buttons = None) -> bool:
        raise NotImplementedError

    async def send_voice(self, chat_id: str, data: bytes, caption: str) -> bool:
        return await self.send_text(chat_id, caption)

    def start_link(self, payload: str) -> str | None:
        return None


class BotMessenger(Messenger):
    """Telegram, or Bale when api_base is given."""

    def __init__(self, name: str, token: str, api_base: str | None = None):
        self.name = name
        session = AiohttpSession(api=TelegramAPIServer.from_base(api_base)) if api_base else AiohttpSession()
        self.bot = Bot(token=token, session=session)

    async def resolve_username(self) -> None:
        try:
            self.username = (await self.bot.get_me()).username
        except Exception:
            logger.warning("%s: get_me failed; invite links will fall back to codes", self.name)

    def start_link(self, payload: str) -> str | None:
        if not self.username:
            return None
        host = "ble.ir" if self.name == "bale" else "t.me"
        return f"https://{host}/{self.username}?start={payload}"

    async def send_text(self, chat_id: str, text: str, buttons: Buttons = None) -> bool:
        try:
            await self.bot.send_message(int(chat_id), text, reply_markup=to_markup(buttons))
            return True
        except Exception:
            logger.exception("%s: send_message to %s failed", self.name, chat_id)
            return False

    async def send_voice(self, chat_id: str, data: bytes, caption: str) -> bool:
        try:
            await self.bot.send_voice(int(chat_id), BufferedInputFile(data, "voice.ogg"), caption=caption)
            return True
        except Exception:
            logger.exception("%s: send_voice to %s failed", self.name, chat_id)
            return False

    async def download(self, file_id: str) -> bytes | None:
        try:
            buf = await self.bot.download(file_id)
            return buf.read() if buf else None
        except Exception:
            logger.exception("%s: download of %s failed", self.name, file_id)
            return None


class SmsMessenger(Messenger):
    """Kavenegar, outbound only. Domestic SMS inside Iran usually keeps working
    while the international internet is cut, which is exactly when it matters."""

    name = "sms"
    URL = "https://api.kavenegar.com/v1/{key}/sms/send.json"

    def __init__(self, api_key: str, sender: str | None):
        self.api_key = api_key
        self.sender = sender

    async def send_text(self, chat_id: str, text: str, buttons: Buttons = None) -> bool:
        params = {"receptor": chat_id, "message": text[:600]}
        if self.sender:
            params["sender"] = self.sender
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.URL.format(key=self.api_key), data=params, timeout=aiohttp.ClientTimeout(total=20)
                ) as resp:
                    data = await resp.json(content_type=None)
            ok = (data.get("return") or {}).get("status") == 200
            if not ok:
                logger.warning("SMS to %s rejected: %s", chat_id, data)
            return ok
        except Exception:
            logger.exception("SMS to %s failed", chat_id)
            return False
