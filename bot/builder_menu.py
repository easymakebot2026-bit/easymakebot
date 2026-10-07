"""Per-chat "Visual Builder" menu button.

The menu button set in @BotFather has one fixed URL for every user, so it
opens the Mini App without ?bot_id= and the builder shows "Missing bot_id".
Whenever an owner enters a bot's build/edit environment we override the
menu button for *that owner's chat only* with a URL carrying the active
bot's id. webapp_server.py still checks ownership of bot_id against the
signed initData, so putting the id in the URL is safe.
"""
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import MenuButtonWebApp, WebAppInfo

logger = logging.getLogger(__name__)


async def set_builder_menu_button(bot: Bot, chat_id: int, webapp_url: str, bot_id, is_fa: bool = False) -> None:
    if not webapp_url or not webapp_url.startswith("https://"):
        return
    try:
        await bot.set_chat_menu_button(
            chat_id=chat_id,
            menu_button=MenuButtonWebApp(
                text="Visual Builder",
                web_app=WebAppInfo(url=f"{webapp_url}?bot_id={bot_id}"),
            ),
        )
    except TelegramAPIError:
        # Never block entering the environment over a cosmetic button.
        logger.warning("set_chat_menu_button failed for chat %s", chat_id, exc_info=True)
