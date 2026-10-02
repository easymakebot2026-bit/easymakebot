"""Entry point: `python -m hamdam.main` (one process per node)."""

import asyncio
import logging

from aiogram import BaseMiddleware, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from hamdam.config import load_config
from hamdam.handlers import router
from hamdam.messaging import BotMessenger, SmsMessenger
from hamdam.node import Node
from hamdam.peer import run_link_loops
from hamdam.scheduler import run_scheduler
from hamdam.web import start_web

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ChannelMiddleware(BaseMiddleware):
    """Tells handlers which messenger an update came from — the same router
    serves the Telegram and the Bale bot."""

    def __init__(self, channel_by_bot: dict[int, str]):
        self.channel_by_bot = channel_by_bot

    async def __call__(self, handler, event, data):
        data["channel"] = self.channel_by_bot[id(data["bot"])]
        return await handler(event, data)


async def main() -> None:
    config = load_config()
    node = Node(config)
    await node.init_db()

    bots = []
    if config.telegram_token:
        node.messengers["telegram"] = BotMessenger("telegram", config.telegram_token)
    if config.bale_token:
        node.messengers["bale"] = BotMessenger("bale", config.bale_token, api_base=config.bale_api_base)
    for messenger in node.messengers.values():
        await messenger.resolve_username()
        bots.append(messenger.bot)
    if config.sms_api_key:
        node.messengers["sms"] = SmsMessenger(config.sms_api_key, config.sms_sender)

    dp = Dispatcher(storage=MemoryStorage())
    dp["node"] = node
    dp.update.outer_middleware(ChannelMiddleware(
        {id(m.bot): name for name, m in node.messengers.items() if isinstance(m, BotMessenger)}
    ))
    dp.include_router(router)

    await start_web(node)
    logger.info("node %s up: channels=%s peers=%s", node.id, list(node.messengers), list(config.peers))
    await asyncio.gather(run_scheduler(node), run_link_loops(node), dp.start_polling(*bots))


if __name__ == "__main__":
    asyncio.run(main())
