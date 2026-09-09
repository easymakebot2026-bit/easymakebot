import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramNetworkError
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from bot import help_text
from bot.config import load_config
from bot.db.base import init_db
from bot.guide import owner_prefers_persian
from bot.handlers.admin_broadcast import router as admin_broadcast_router
from bot.handlers.cancel import router as cancel_router
from bot.handlers.create_bot import router as create_bot_router
from bot.handlers.easybotadmin import router as easybotadmin_router
from bot.handlers.live import router as live_router
from bot.handlers.my_bots import router as my_bots_router
from bot.handlers.start import router as start_router
from bot.handlers.tools.content_list import router as content_list_router
from bot.handlers.tools.define_command import router as define_command_router
from bot.handlers.tools.force_join import router as force_join_router
from bot.handlers.tools.message_to_all import router as message_to_all_router
from bot.handlers.tools.shop import router as shop_router
from bot.handlers.tools_menu import router as tools_menu_router
from bot.platform_settings import (
    MAINTENANCE_TEXT_EN,
    MAINTENANCE_TEXT_FA,
    bots_enabled,
    platform_user_prefers_persian,
)
from bot.runtime import run_campaign_expiry_loop, run_live_expiry_loop, start_all_built_bots
from bot.session import make_session
from bot.webapp_server import start_webapp_server

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def _retry_on_network_error(coro_factory, *, attempts: int = 5, base_delay: float = 2.0):
    """Retries a one-off Telegram API call with exponential backoff.

    The network this runs on has proven flaky (a working connection that
    occasionally refuses a single request) — without this, one bad request
    during startup (set_my_commands, delete_webhook) took down the whole
    process, including every already-running built bot. dp.start_polling
    already retries transient errors internally once polling begins; this
    covers the one-off calls made before that point.
    """
    for attempt in range(1, attempts + 1):
        try:
            return await coro_factory()
        except TelegramNetworkError as exc:
            if attempt == attempts:
                raise
            delay = base_delay * (2 ** (attempt - 1))
            logger.warning(
                "Network error on startup call (attempt %d/%d): %s — retrying in %.0fs",
                attempt, attempts, exc, delay,
            )
            await asyncio.sleep(delay)


async def main() -> None:
    config = load_config()

    bot = Bot(
        token=config.bot_token,
        session=make_session(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # After an owner taps a builder option, drop a one- or two-line fa/en tip
    # under it (bot/help_text.py). Runs around every callback handler but only
    # sends when that callback_data has a registered tip.
    @dp.callback_query.outer_middleware
    async def _help_tip(handler, event, data):
        result = await handler(event, data)
        try:
            key = getattr(event, "data", "") or ""
            if event.message is not None and help_text.has_tip(key):
                is_fa = await owner_prefers_persian(event.from_user)
                line = help_text.tip(key, is_fa)
                if line:
                    await event.message.answer(line)
        except Exception:
            logger.exception("help tip failed for %s", getattr(event, "data", None))
        return result

    # Platform-wide maintenance switch (bot/platform_settings.py, toggled from
    # /easybotadmin) — an outer middleware runs before every handler below, on
    # every message AND every button tap, across every router registered on
    # this dp (nothing can bypass it by matching some handler these two don't
    # know about). Unlike the built-bot version in bot/runtime.py, the
    # platform admin is exempted so they can still reach /easybotadmin (and
    # everything else) to toggle bots back on while paused.
    @dp.message.outer_middleware
    async def _maintenance_gate_message(handler, message, data):
        if message.from_user is not None and message.from_user.id == config.platform_admin_id:
            return await handler(message, data)
        if await bots_enabled():
            return await handler(message, data)
        is_fa = await platform_user_prefers_persian(message.from_user)
        await message.answer(MAINTENANCE_TEXT_FA if is_fa else MAINTENANCE_TEXT_EN)
        return None

    @dp.callback_query.outer_middleware
    async def _maintenance_gate_callback(handler, callback, data):
        if callback.from_user is not None and callback.from_user.id == config.platform_admin_id:
            return await handler(callback, data)
        if await bots_enabled():
            return await handler(callback, data)
        is_fa = await platform_user_prefers_persian(callback.from_user)
        await callback.answer(MAINTENANCE_TEXT_FA if is_fa else MAINTENANCE_TEXT_EN, show_alert=True)
        return None

    # /cancel must win over every state-scoped catch-all handler below, so it can
    # always break out of a stuck multi-step flow regardless of the current state.
    dp.include_router(cancel_router)

    # State-scoped routers (waiting for free-text input, e.g. a command name that
    # may literally be "/start") must be checked before start_router's generic
    # CommandStart() filter, so mid-flow input always wins over the global command.
    dp.include_router(create_bot_router)
    dp.include_router(define_command_router)
    dp.include_router(message_to_all_router)
    dp.include_router(force_join_router)
    dp.include_router(content_list_router)
    dp.include_router(shop_router)
    dp.include_router(admin_broadcast_router)
    dp.include_router(easybotadmin_router)
    dp.include_router(live_router)
    dp.include_router(start_router)
    dp.include_router(my_bots_router)
    dp.include_router(tools_menu_router)

    await init_db()
    await start_all_built_bots()
    asyncio.create_task(run_live_expiry_loop())
    asyncio.create_task(run_campaign_expiry_loop())

    # Serves the visual flow builder Mini App (webapp/dist/) + its /api/flow
    # endpoints, signed with this (easymakebot's own) token — see bot/webapp_server.py.
    await start_webapp_server(config.bot_token, config.webapp_port)

    # BotFather-style native "/" command menu, instead of relying only on
    # inline buttons for top-level navigation.
    await _retry_on_network_error(
        lambda: bot.set_my_commands(
            [
                BotCommand(command="start", description="Show the welcome menu"),
                BotCommand(command="mybots", description="List and select your bots"),
                BotCommand(command="newbot", description="Create a new bot"),
                BotCommand(command="live", description="Go live on Telegram (trial or a paid plan)"),
                BotCommand(command="help", description="Show help"),
            ]
        )
    )

    logger.info("Bot is running...")
    await _retry_on_network_error(lambda: bot.delete_webhook(drop_pending_updates=True))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())