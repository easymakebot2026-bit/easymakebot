from aiogram.client.session.aiohttp import AiohttpSession


def make_session() -> AiohttpSession:
    return AiohttpSession()
