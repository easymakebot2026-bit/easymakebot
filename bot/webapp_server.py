"""aiohttp server for the visual flow builder Mini App: serves the built
frontend (webapp/dist/) and a small JSON API to read/save a bot's
flow_definition, authenticated via Telegram initData (bot/webapp_auth.py)."""

import hmac
import logging
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from aiohttp import web
from sqlalchemy import func, select

from bot.config import load_config
from bot.content_nav import delete_item_rows, get_item, reparent_item, upsert_item
from bot.db.base import async_session_maker
from bot.db.models import BuiltBot, ContentItem, LivePayment, Order, User
from bot.platform_billing import verify_stripe_live_payment, verify_zarinpal_live_payment
from bot.message_buttons import (
    MAX_BUTTONS,
    is_valid_button_url,
    is_valid_command_name,
    validate_buttons,
)
from bot.runtime import sync_bot_commands
from bot.shop import (
    verify_stripe_checkout,
    verify_stripe_payment,
    verify_zarinpal_checkout,
    verify_zarinpal_payment,
)
from bot.webapp_auth import validate_init_data

logger = logging.getLogger(__name__)

# Commands the bot already handles itself ahead of any owner-defined one — a
# trigger with one of these names could never run (/cancel is handled first
# everywhere) or would silently shadow a built-in.
RESERVED_TRIGGER_COMMANDS = frozenset({"/cancel"})

MAX_MESSAGE_TEXT = 4096  # Telegram text message limit
MAX_MEDIA_CAPTION = 1024  # Telegram caption limit when media is attached
MAX_MESSAGES_PER_NODE = 10


def _message_node_error(data: dict) -> str | None:
    """Same checks the chat wizard (bot/handlers/tools/define_command.py)
    applies at input time, run on what the Visual Builder saves — otherwise a
    too-long text or one bad button URL makes Telegram reject the whole
    message at delivery time, with nobody told why."""
    messages = data.get("messages")
    if messages is None:
        return None  # legacy {"text": ...} shape — nothing new to validate
    if not isinstance(messages, list):
        return "Send Message: messages must be a list"
    if len(messages) > MAX_MESSAGES_PER_NODE:
        return f"Send Message: at most {MAX_MESSAGES_PER_NODE} messages per block"
    for index, block in enumerate(messages, start=1):
        if not isinstance(block, dict):
            return f"Send Message #{index}: invalid message"
        has_media = bool(block.get("media_url") or block.get("media_file_id"))
        text = str(block.get("text") or "")
        limit = MAX_MEDIA_CAPTION if has_media else MAX_MESSAGE_TEXT
        if len(text) > limit:
            return f"Send Message #{index}: text is {len(text)} characters, the limit is {limit}"
        media_url = str(block.get("media_url") or "").strip()
        if media_url and not is_valid_button_url(media_url):
            return f"Send Message #{index}: media link must be an http:// or https:// URL without spaces"
        if block.get("media_type") not in (None, "", "photo", "video", "document"):
            return f"Send Message #{index}: unknown media type"
        buttons = block.get("buttons")
        if buttons is not None and not isinstance(buttons, list):
            return f"Send Message #{index}: buttons must be a list"
        error = validate_buttons(buttons)
        if error:
            return f"Send Message #{index}: {error}"
    return None



STATIC_DIR = Path(__file__).resolve().parent.parent / "webapp" / "dist"

# Module-level singleton, same pattern as bot/website_client.py — cheap to
# load once, read only for the static PLATFORM_STATS_API_KEY below.
_config = load_config()


async def _authenticated_bot(request: web.Request, bot_token: str) -> BuiltBot | None:
    """Validates the request's Telegram initData and returns the BuiltBot for
    ?bot_id=, but only if the requesting Telegram user actually owns it."""
    init_data = request.headers.get("X-Telegram-Init-Data")
    if not init_data:
        return None

    user = validate_init_data(init_data, bot_token)
    if user is None or not isinstance(user, dict) or not isinstance(user.get("id"), int):
        return None

    try:
        bot_id = uuid.UUID(request.query.get("bot_id") or "")
    except ValueError:
        return None  # malformed id — a clean 401, not a DB error / 500

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

        if (
            not isinstance(flow, dict)
            or not isinstance(flow.get("nodes"), list)
            or not isinstance(flow.get("edges"), list)
            or not all(isinstance(n, dict) for n in flow["nodes"])
            or not all(isinstance(e, dict) for e in flow["edges"])
        ):
            return web.json_response({"error": "flow must have nodes and edges"}, status=400)

        seen_triggers: set[str] = set()
        for node in flow["nodes"]:
            data = node.get("data") if isinstance(node.get("data"), dict) else {}

            if node.get("type") == "send_message":
                error = _message_node_error(data)
                if error:
                    return web.json_response({"error": error}, status=400)
                continue

            if node.get("type") != "trigger":
                continue
            command = str(data.get("command") or "").strip().lower()
            if command and not command.startswith("/"):
                command = "/" + command
            if not is_valid_command_name(command):
                return web.json_response(
                    {
                        "error": f'invalid command "{data.get("command") or ""}" — use / plus lowercase '
                        "English letters, digits or _ (max 32)"
                    },
                    status=400,
                )
            if command in RESERVED_TRIGGER_COMMANDS:
                return web.json_response(
                    {"error": f"{command} is reserved and can't be used as a trigger"}, status=400
                )
            if command in seen_triggers:
                return web.json_response(
                    {"error": f"two Trigger blocks use {command} — each command can have only one"},
                    status=400,
                )
            seen_triggers.add(command)
            if data.get("visibility", "everyone") not in ("everyone", "admin"):
                return web.json_response(
                    {"error": f'{command}: visibility must be "everyone" or "admin"'}, status=400
                )
            if command == "/start" and data.get("visibility") == "admin":
                return web.json_response(
                    {"error": "/start can't be admin-only — everyone needs it to begin"}, status=400
                )

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

    def _link_error(payload: dict) -> str | None:
        """A link/image that isn't a plain http(s) URL makes Telegram reject
        the whole content post it's attached to, so it's refused up front."""
        for key in ("link_url", "image_url"):
            value = payload.get(key)
            if value not in (None, "") and not is_valid_button_url(str(value)):
                return f"{key} must be an http:// or https:// link without spaces"
        return None

    def _parse_item_id(request: web.Request) -> int | None:
        try:
            return int(request.match_info["item_id"])
        except (KeyError, ValueError):
            return None

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

        if not isinstance(payload, dict) or not str(payload.get("title") or "").strip():
            return web.json_response({"error": "title is required"}, status=400)
        link_error = _link_error(payload)
        if link_error:
            return web.json_response({"error": link_error}, status=400)

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
        if parent_id is not None and (not isinstance(parent_id, int) or isinstance(parent_id, bool)):
            return web.json_response({"error": "parent_id must be an integer or null"}, status=400)
        if parent_id is not None:
            ok = await reparent_item(built_bot.id, item.id, parent_id)
            if not ok:
                return web.json_response(
                    {"error": "invalid parent (cycle, or not in this bot)"}, status=400
                )
            item = await get_item(item.id)

        await sync_bot_commands(built_bot.id)
        return web.json_response(_serialize_content_item(item))

    async def update_content(request: web.Request) -> web.Response:
        built_bot = await _authenticated_bot(request, bot_token)
        if built_bot is None:
            return web.json_response({"error": "unauthorized"}, status=401)

        item_id = _parse_item_id(request)
        if item_id is None:
            return web.json_response({"error": "not found"}, status=404)

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
        link_error = _link_error(payload)
        if link_error:
            return web.json_response({"error": link_error}, status=400)

        fields = {
            key: payload[key]
            for key in ("title", "body", "image_url", "link_url")
            if key in payload
        }
        fields.update(_premium_fields(payload))
        if fields:
            item = await upsert_item(built_bot.id, fields, item_id=item_id)

        if "parent_id" in payload:
            new_parent = payload["parent_id"]
            if new_parent is not None and (not isinstance(new_parent, int) or isinstance(new_parent, bool)):
                return web.json_response({"error": "parent_id must be an integer or null"}, status=400)
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

        item_id = _parse_item_id(request)
        if item_id is None:
            return web.json_response({"error": "not found"}, status=404)

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

            await delete_item_rows(session, item)
            await session.commit()

        await sync_bot_commands(built_bot.id)
        return web.json_response({"ok": True})

    async def platform_stats(request: web.Request) -> web.Response:
        """Platform-wide aggregate stats — for the business owner's own
        dashboards/reports (e.g. the scheduled business-check-in), never
        exposed to bot owners. Not tied to any single bot, so it doesn't use
        _authenticated_bot; auth is a static key instead, same "X-EMB-Key"
        header convention bot/website_client.py already uses for the
        website<->bot API. Read-only, no writes anywhere in this handler.
        """
        if not _config.platform_stats_api_key:
            return web.json_response({"error": "stats_api_disabled"}, status=503)
        if not hmac.compare_digest(
            request.headers.get("X-EMB-Key", "").encode(), _config.platform_stats_api_key.encode()
        ):
            return web.json_response({"error": "unauthorized"}, status=401)

        now = datetime.now(timezone.utc)
        since_30d = now - timedelta(days=30)
        since_7d = now - timedelta(days=7)

        def _rev(row) -> dict[str, float]:
            return {"toman": int(row[0] or 0), "usd": float(row[1] or 0)}

        async with async_session_maker() as session:
            users_total = (
                await session.execute(select(func.count()).select_from(User))
            ).scalar_one()
            users_7d = (
                await session.execute(
                    select(func.count()).select_from(User).where(User.created_at >= since_7d)
                )
            ).scalar_one()
            users_30d = (
                await session.execute(
                    select(func.count()).select_from(User).where(User.created_at >= since_30d)
                )
            ).scalar_one()

            bots_total = (
                await session.execute(select(func.count()).select_from(BuiltBot))
            ).scalar_one()
            bots_live = (
                await session.execute(
                    select(func.count())
                    .select_from(BuiltBot)
                    .where(
                        BuiltBot.live_until.is_not(None),
                        BuiltBot.live_until > now,
                        BuiltBot.suspended.is_(False),
                    )
                )
            ).scalar_one()
            bots_suspended = (
                await session.execute(
                    select(func.count()).select_from(BuiltBot).where(BuiltBot.suspended.is_(True))
                )
            ).scalar_one()

            platform_rev_all = (
                await session.execute(
                    select(
                        func.coalesce(
                            func.sum(LivePayment.price).filter(LivePayment.currency == "toman"), 0
                        ),
                        func.coalesce(
                            func.sum(LivePayment.price).filter(LivePayment.currency == "usd"), 0
                        ),
                    ).where(LivePayment.status == "paid")
                )
            ).one()
            platform_rev_30d = (
                await session.execute(
                    select(
                        func.coalesce(
                            func.sum(LivePayment.price).filter(LivePayment.currency == "toman"), 0
                        ),
                        func.coalesce(
                            func.sum(LivePayment.price).filter(LivePayment.currency == "usd"), 0
                        ),
                    ).where(LivePayment.status == "paid", LivePayment.created_at >= since_30d)
                )
            ).one()

            paid_statuses = ("paid", "fulfilled")
            shop_orders_total = (
                await session.execute(
                    select(func.count()).select_from(Order).where(Order.status.in_(paid_statuses))
                )
            ).scalar_one()
            # All end-customer shop revenue is Toman-only (Product.price is
            # always Toman — see db/models.py) — never mix it with the
            # platform's own usd LivePayment revenue above.
            shop_revenue_all = (
                await session.execute(
                    select(
                        func.coalesce(
                            func.sum(Order.price + func.coalesce(Order.tax_amount, 0)), 0
                        )
                    ).where(Order.status.in_(paid_statuses))
                )
            ).scalar_one()
            shop_revenue_30d = (
                await session.execute(
                    select(
                        func.coalesce(
                            func.sum(Order.price + func.coalesce(Order.tax_amount, 0)), 0
                        )
                    ).where(Order.status.in_(paid_statuses), Order.created_at >= since_30d)
                )
            ).scalar_one()

        return web.json_response(
            {
                "generated_at": now.isoformat(),
                "users": {"total": users_total, "new_7d": users_7d, "new_30d": users_30d},
                "bots": {"total": bots_total, "live": bots_live, "suspended": bots_suspended},
                "platform_revenue": {
                    "all_time": _rev(platform_rev_all),
                    "last_30d": _rev(platform_rev_30d),
                },
                "end_customer_shops": {
                    "orders_total": shop_orders_total,
                    "revenue_toman_all_time": int(shop_revenue_all),
                    "revenue_toman_30d": int(shop_revenue_30d),
                },
            }
        )

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
    app.router.add_get("/api/platform/stats", platform_stats)
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
