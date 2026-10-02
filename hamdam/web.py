"""HTTP side of a node: the peer endpoint other nodes call, the Zarinpal
return page, and a health check."""

import json
import logging

from aiohttp import web

from hamdam import billing
from hamdam.peer import verify_signature

logger = logging.getLogger(__name__)

_PAGE = """<!doctype html><html lang="fa" dir="rtl"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Hamdam</title>
<body style="font-family:sans-serif;text-align:center;padding:48px 16px">
<h2>{title}</h2><p>{body}</p></body></html>"""


def make_app(node) -> web.Application:
    async def health(_request):
        return web.json_response({"ok": True, "node": node.id})

    async def peer(request: web.Request):
        sender = request.headers.get("X-Hamdam-Node", "")
        body = await request.read()
        if sender not in node.config.peers or not verify_signature(
            node.config.peer_key, sender, request.headers.get("X-Hamdam-Ts", ""), body,
            request.headers.get("X-Hamdam-Sig", ""),
        ):
            return web.json_response({"ok": False, "error": "unauthorized"}, status=401)
        try:
            message = json.loads(body)
        except ValueError:
            return web.json_response({"ok": False, "error": "bad_json"}, status=400)
        try:
            return web.json_response(await node.handle_peer(sender, message))
        except Exception:
            logger.exception("peer message from %s failed", sender)
            # 500 -> the sender keeps it in its outbox and retries.
            return web.json_response({"ok": False, "error": "internal"}, status=500)

    async def zarinpal_callback(request: web.Request):
        try:
            pid = int(request.query.get("pid", ""))
        except ValueError:
            pid = 0
        authority = request.query.get("Authority", "")
        ok = request.query.get("Status") == "OK" and pid and await billing.verify_zarinpal(node, pid, authority)
        if ok:
            html = _PAGE.format(title="✅ پرداخت موفق", body="می‌توانید به ربات برگردید. / You can return to the bot.")
        else:
            html = _PAGE.format(title="❌ پرداخت انجام نشد", body="اگر مبلغی کم شده، طی ۷۲ ساعت برمی‌گردد. / Not completed.")
        return web.Response(text=html, content_type="text/html")

    app = web.Application(client_max_size=4 * 1024 * 1024)  # voice notes travel in peer messages
    app.router.add_get("/health", health)
    app.router.add_post("/peer", peer)
    app.router.add_get("/pay/zarinpal/callback", zarinpal_callback)
    return app


async def start_web(node) -> web.AppRunner:
    runner = web.AppRunner(make_app(node))
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", node.config.port).start()
    logger.info("node %s listening on :%s", node.id, node.config.port)
    return runner
