"""aiohttp server for the visual flow builder Mini App: serves the built
frontend (webapp/dist/) and a small JSON API to read/save a bot's
flow_definition, authenticated via Telegram initData (bot/webapp_auth.py)."""

import logging
from datetime import datetime, timezone
from pathlib import Path

from aiohttp import web
from sqlalchemy import func, select

from bot.content_nav import get_item, reparent_item, upsert_item
from bot.db.base import async_session_maker
from bot.db.models import BuiltBot, ContentItem, User
from bot.platform_billing import verify_stripe_live_payment, verify_zarinpal_live_payment
from bot.runtime import sync_bot_commands
from bot.shop import (
    verify_stripe_checkout,
    verify_stripe_payment,
    verify_zarinpal_checkout,
    verify_zarinpal_payment,
)
from bot.webapp_auth import validate_init_data

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent.parent / "webapp" / "dist"


async def _authenticated_bot(request: web.Request, bot_token: str) -> BuiltBot | None:
    """Validates the request's Telegram initData and returns the BuiltBot for
    ?bot_id=, but only if the requesting Telegram user actually owns it."""
    init_data = request.headers.get("X-Telegram-Init-Data")
    if not init_data:
        return None

    user = validate_init_data(init_data, bot_token)
    if user is None:
        return None

    bot_id = request.query.get("bot_id")
    if not bot_id:
        return None

    async with async_session_maker() as session:
        result = await session.execute(
            select(BuiltBot)
            .join(User, User.id == BuiltBot.owner_id)
            .where(BuiltBot.id == bot_id, User.telegram_id == user["id"])
        )
        return result.scalar_one_or_none()


def _payment_page(heading: str, detail: str) -> web.Response:
    html = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<style>body{font-family:sans-serif;text-align:center;padding:60px 20px;}"
        "h2{margin-bottom:8px}p{color:#666}</style></head><body>"
        f"<h2>{heading}</h2><p>{detail}</p></body></html>"
    )
    return web.Response(text=html, content_type="text/html")


def create_app(bot_token: str) -> web.Application:
    app = web.Application()

    async def zarinpal_callback(request: web.Request) -> web.Response:
        """Zarinpal redirects the buyer's browser here after they pay or
        cancel — see bot/shop.py:start_zarinpal_payment for the callback_url
        this bot gave it. No initData auth here (Zarinpal hits this, not our
        own frontend); the Authority token is itself the unguessable
        credential tying this request to one order."""
        authority = request.query.get("Authority")
        status = request.query.get("Status")

        if not authority or status != "OK":
            return _payment_page("❌ Payment cancelled", "You can return to Telegram and try again.")

        # A single-item purchase (Order) and a cart Checkout each store their
        # own zarinpal_authority — try the Order first (the common case),
        # then fall back to Checkout. Authorities are unique per gateway, so
        # there's no ambiguity between the two lookups.
        order = await verify_zarinpal_payment(authority)
        if order is not None:
            if order.status not in ("paid", "fulfilled"):
                return _payment_page(
                    "⚠️ Payment verification failed",
                    "Please contact the bot owner if you were charged.",
                )
            return _payment_page("✅ Payment successful", "You can return to Telegram now.")

        checkout = await verify_zarinpal_checkout(authority)
        if checkout is None or checkout.status not in ("paid",):
            return _payment_page(
                "⚠️ Payment verification failed", "Please contact the bot owner if you were charged."
            )

        return _payment_page("✅ Payment successful", "You can return to Telegram now.")

    app.router.add_get("/payment/zarinpal/callback", zarinpal_callback)

    async def stripe_callback(request: web.Request) -> web.Response:
        """Stripe redirects the buyer's browser here after Checkout — either
        success_url (with a session_id Stripe substitutes for us) or
        cancel_url (?cancelled=1) — see bot/shop.py:start_stripe_payment."""
        if request.query.get("cancelled"):
            return _payment_page("❌ Payment cancelled", "You can return to Telegram and try again.")

        session_id = request.query.get("session_id")
        if not session_id:
            return _payment_page("⚠️ Payment verification failed", "Missing session id.")

        # Same Order-then-Checkout fallback as the Zarinpal callback above —
        # each stores its own stripe_session_id, unambiguous by lookup.
        order = await verify_stripe_payment(session_id)
        if order is not None:
            if order.status not in ("paid", "fulfilled"):
                return _payment_page(
                    "⚠️ Payment verification failed",
                    "Please contact the bot owner if you were charged.",
                )
            return _payment_page("✅ Payment successful", "You can return to Telegram now.")

        checkout = await verify_stripe_checkout(session_id)
        if checkout is None or checkout.status not in ("paid",):
            return _payment_page(
                "⚠️ Payment verification failed", "Please contact the bot owner if you were charged."
            )

        return _payment_page("✅ Payment successful", "You can return to Telegram now.")

    app.router.add_get("/payment/stripe/callback", stripe_callback)

    async def live_zarinpal_callback(request: web.Request) -> web.Response:
        """Zarinpal redirects here after a bot owner pays THE PLATFORM for a
        /live plan — see bot/platform_billing.py:start_zarinpal_live_payment.
        Separate route/table from the bot-shop callback above so a bot's own
        customer payments and platform billing can never be confused."""
        authority = request.query.get("Authority")
        status = request.query.get("Status")

        if not authority or status != "OK":
            return _payment_page("❌ Payment cancelled", "You can return to Telegram and try again.")

        payment = await verify_zarinpal_live_payment(authority)
        if payment is None or payment.status != "paid":
            return _payment_page(
                "⚠️ Payment verification failed", "Please contact the platform admin if you were charged."
            )

        return _payment_page("✅ Payment successful", "Your bot is now live — return to Telegram.")

    app.router.add_get("/payment/live/zarinpal/callback", live_zarinpal_callback)

    async def live_stripe_callback(request: web.Request) -> web.Response:
        """Same as live_zarinpal_callback above, for the Stripe (Visa/
        Mastercard) /live plan path."""
        if request.query.get("cancelled"):
            return _payment_page("❌ Payment cancelled", "You can return to Telegram and try again.")

        session_id = request.query.get("session_id")
        if not session_id:
            return _payment_page("⚠️ Payment verification failed", "Missing session id.")

        payment = await verify_stripe_live_payment(session_id)
        if payment is None or payment.status != "paid":
            return _payment_page(
                "⚠️ Payment verification failed", "Please contact the platform admin if you were charged."
            )

        return _payment_page("✅ Payment successful", "Your bot is now live — return to Telegram.")

    app.router.add_get("/payment/live/stripe/callback", live_stripe_callback)

    async def get_flow(request: web.Request) -> web.Response:
        built_bot = await _authenticated_bot(request, bot_token)
        if built_bot is None:
            return web.json_response({"error": "unauthorized"}, status=401)
        return web.json_response(built_bot.flow_definition or {"nodes": [], "edges": []})

    async def save_flow(request: web.Request) -> web.Response:
        built_bot = await _authenticated_bot(request, bot_token)
        if built_bot is None:
            return web.json_response({"error": "unauthorized"}, status=401)

        try:
            flow = await request.json()
        except ValueError:
            return web.json_response({"error": "invalid json"}, status=400)

        if not isinstance(flow, dict) or "nodes" not in flow or "edges" not in flow:
            return web.json_response({"error": "flow must have nodes and edges"}, status=400)

        async with async_session_maker() as session:
            result = await session.execute(select(BuiltBot).where(BuiltBot.id == built_bot.id))
            row = result.scalar_one()
            row.flow_definition = flow
            row.flow_updated_at = datetime.now(timezone.utc)
            await session.commit()

        await sync_bot_commands(built_bot.id)

        return web.json_response({"ok": True})

    def _serialize_content_item(item: ContentItem) -> dict:
        return {
            "id": item.id,
            "title": item.title,
            "body": item.body,
            "image_url": item.image_url,
            "link_url": item.link_url,
            "code": item.code,
            "parent_id": item.parent_id,
            "product_id": item.product_id,
            "is_premium": item.is_premium,
            # Subscription-mode à-la-carte price for this one item (Toman), or
            # null to fall back to ShopSettings.default_unlock_price. See
            # bot/premium_content.py.
            "unlock_price": item.unlock_price,
        }

    def _premium_fields(payload: dict) -> dict:
        """Pull is_premium / unlock_price out of a content payload, coerced."""
        out: dict = {}
        if "is_premium" in payload:
            out["is_premium"] = bool(payload["is_premium"])
        if "unlock_price" in payload:
            raw = payload["unlock_price"]
            if raw in (None, "", 0, "0"):
                out["unlock_price"] = None
            else:
                try:
                    out["unlock_price"] = max(0, int(raw)) or None
                except (TypeError, ValueError):
                    out["unlock_price"] = None
        return out

    async def list_content(request: web.Request) -> web.Response:
        built_bot = await _authenticated_bot(request, bot_token)
        if built_bot is None:
            return web.json_response({"error": "unauthorized"}, status=401)

        async with async_session_maker() as session:
            result = await session.execute(
                select(ContentItem)
                .where(ContentItem.bot_id == built_bot.id)
                .order_by(ContentItem.title)
            )
            items = list(result.scalars())

        return web.json_response([_serialize_content_item(i) for i in items])

    async def create_content(request: web.Request) -> web.Response:
        built_bot = await _authenticated_bot(request, bot_token)
        if built_bot is None:
            return web.json_response({"error": "unauthorized"}, status=401)

        try:
            payload = await request.json()
        except ValueError:
            return web.json_response({"error": "invalid json"}, status=400)

        if not isinstance(payload, dict) or not (payload.get("title") or "").strip():
            return web.json_response({"error": "title is required"}, status=400)

        code = (payload.get("code") or "").strip() or None
        if code:
            async with async_session_maker() as session:
                result = await session.execute(
                    select(ContentItem).where(
                        ContentItem.bot_id == built_bot.id,
                        func.lower(ContentItem.code) == code.lower(),
                    )
                )
                if result.scalar_one_or_none() is not None:
                    return web.json_response(
                        {"error": f'code "{code}" is already in use'}, status=409
                    )

        item = await upsert_item(
            built_bot.id,
            {
                "title": payload.get("title"),
                "body": payload.get("body") or "",
                "image_url": payload.get("image_url"),
                "link_url": payload.get("link_url"),
                **_premium_fields(payload),
            },
            code=code,
        )

        parent_id = payload.get("parent_id")
        if parent_id is not None:
            await reparent_item(built_bot.id, item.id, parent_id)
            item = await get_item(item.id)

        await sync_bot_commands(built_bot.id)
        return web.json_response(_serialize_content_item(item))

    async def update_content(request: web.Request) -> web.Response:
        built_bot = await _authenticated_bot(request, bot_token)
        if built_bot is None:
            return web.json_response({"error": "unauthorized"}, status=401)

        item_id = int(request.match_info["item_id"])

        async with async_session_maker() as session:
            result = await session.execute(
                select(ContentItem).where(
                    ContentItem.id == item_id, ContentItem.bot_id == built_bot.id
                )
            )
            item = result.scalar_one_or_none()
        if item is None:
            return web.json_response({"error": "not found"}, status=404)

        try:
            payload = await request.json()
        except ValueError:
            return web.json_response({"error": "invalid json"}, status=400)
        if not isinstance(payload, dict):
            return web.json_response({"error": "invalid body"}, status=400)

        fields = {
            key: payload[key]
            for key in ("title", "body", "image_url", "link_url")
            if key in payload
        }
        fields.update(_premium_fields(payload))
        if fields:
            item = await upsert_item(built_bot.id, fields, item_id=item_id)

        if "parent_id" in payload:
            ok = await reparent_item(built_bot.id, item_id, payload["parent_id"])
            if not ok:
                return web.json_response(
                    {"error": "invalid parent (cycle, or not in this bot)"}, status=400
                )
            item = await get_item(item_id)

        await sync_bot_commands(built_bot.id)
        return web.json_response(_serialize_content_item(item))

    async def delete_content(request: web.Request) -> web.Response:
        built_bot = await _authenticated_bot(request, bot_token)
        if built_bot is None:
            return web.json_response({"error": "unauthorized"}, status=401)

        item_id = int(request.match_info["item_id"])

        async with async_session_maker() as session:
            result = await session.execute(
                select(ContentItem).where(
                    ContentItem.id == item_id, ContentItem.bot_id == built_bot.id
                )
            )
            item = result.scalar_one_or_none()
            if item is None:
                return web.json_response({"error": "not found"}, status=404)

            children_result = await session.execute(
                select(ContentItem.id).where(ContentItem.parent_id == item_id).limit(1)
            )
            if children_result.scalar_one_or_none() is not None:
                return web.json_response(
                    {"error": "has sub-items — delete those first"}, status=409
                )

            await session.delete(item)
            await session.commit()

        await sync_bot_commands(built_bot.id)
        return web.json_response({"ok": True})

    async def index(request: web.Request) -> web.Response:
        index_path = STATIC_DIR / "index.html"
        if not index_path.exists():
            return web.Response(
                text="Mini App not built yet — run `npm install && npm run build` in webapp/.",
                status=503,
            )
        # Never let Telegram's in-app browser cache index.html: after a
        # redeploy its hashed /assets/*.js filenames change, and a stale
        # index pointing at the old ones renders a blank Mini App. The
        # hashed assets themselves are safe to cache forever.
        return web.FileResponse(
            index_path, headers={"Cache-Control": "no-store, must-revalidate"}
        )

    app.router.add_get("/api/flow", get_flow)
    app.router.add_post("/api/flow", save_flow)
    app.router.add_get("/api/content", list_content)
    app.router.add_post("/api/content", create_content)
    app.router.add_put("/api/content/{item_id}", update_content)
    app.router.add_delete("/api/content/{item_id}", delete_content)
    async def favicon(request: web.Request) -> web.Response:
        path = STATIC_DIR / "favicon.svg"
        if not path.exists():
            return web.Response(status=404)
        return web.FileResponse(path)

    app.router.add_get("/", index)
    app.router.add_get("/favicon.svg", favicon)
    if (STATIC_DIR / "assets").exists():
        app.router.add_static("/assets", STATIC_DIR / "assets")

    return app


async def start_webapp_server(bot_token: str, port: int) -> web.AppRunner:
    app = create_app(bot_token)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info("Mini App server listening on port %d", port)
    return runner
