"""Order-processing logic for the "Shop" tool/flow block: creating orders,
Zarinpal payment (request + verify), card-to-card submission/approval,
fulfillment per Product.product_type, and PDF invoices.

No Telegram-handler code here — reused by bot/runtime.py (chat-side
handlers, buyer/owner interactions) and bot/webapp_server.py (Zarinpal's
HTTP redirect callback), same split as bot/content_nav.py / bot/flow_engine.py.
"""

import io
import logging
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import aiohttp
from aiogram import Bot
from aiogram.types import BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from arabic_reshaper import reshape
from bidi.algorithm import get_display
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from sqlalchemy import select, update

from bot import pricing
from bot.db.base import async_session_maker
from bot.db.models import (
    BotSubscriber,
    BuiltBot,
    CartItem,
    Checkout,
    ContentItem,
    ContentUnlock,
    Order,
    PriceCampaign,
    Product,
    ShopSettings,
)
from bot.session import make_session

CONTENT_UNLOCK_TYPE = "content_unlock"

logger = logging.getLogger(__name__)

# Zarinpal's v4 REST API. Amounts are Rial (Product.price is stored in Toman,
# so every amount sent to Zarinpal is multiplied by 10) — this is the
# long-standing contract for this endpoint, but hasn't been exercised against
# a real merchant account here; verify with a real purchase before relying on it.
ZARINPAL_REQUEST_URL = "https://api.zarinpal.com/pg/v4/payment/request.json"
ZARINPAL_VERIFY_URL = "https://api.zarinpal.com/pg/v4/payment/verify.json"
ZARINPAL_STARTPAY_URL = "https://www.zarinpal.com/pg/StartPay/{authority}"

# Stripe's REST API — plain aiohttp calls (no stripe SDK), same approach as
# Zarinpal above. Checkout Session amounts are USD cents; unlike the Zarinpal
# path (Toman), Product.price on this path is treated as whole US dollars —
# a deliberate v1 simplification (no per-bot currency setting yet) for
# sellers outside Iran, who configure Stripe instead of Zarinpal/card-to-card.
STRIPE_CHECKOUT_URL = "https://api.stripe.com/v1/checkout/sessions"
STRIPE_SESSION_URL = "https://api.stripe.com/v1/checkout/sessions/{session_id}"

# Extra product-add-wizard steps depending on the chosen product type, keyed
# by Product.product_type. Shared by the standalone product wizard
# (bot/handlers/tools/shop.py) and the "mark this content item for sale"
# branch of the Content List wizard (bot/handlers/tools/content_list.py).
# Bilingual: each field carries prompt_en/prompt_fa. Owner-only wizard data
# (bot/handlers/tools/shop.py, bot/handlers/tools/content_list.py) — never
# reused by the buyer-facing runtime, so both languages are safe here.
TYPE_FIELDS = {
    "digital": [
        {
            "key": "delivery_text",
            "prompt_en": "Enter the message to send after payment (instructions, unlock code, etc.).",
            "prompt_fa": "پیامی که بعد از پرداخت ارسال بشه رو وارد کن (راهنما، کد رفع قفل و غیره).",
        },
        {
            "key": "delivery_file_url",
            "prompt_en": "Enter a download link (optional).",
            "prompt_fa": "لینک دانلود رو وارد کن (اختیاری).",
            "optional": True,
        },
    ],
    "access": [
        {
            "key": "access_level_name",
            "prompt_en": "Enter the access level name (e.g. VIP).",
            "prompt_fa": "نام سطح دسترسی رو وارد کن (مثلاً VIP).",
        },
    ],
    "subscription": [
        {
            "key": "subscription_days",
            "prompt_en": "How many days does this plan grant access for? (e.g. 30)",
            "prompt_fa": "این پلن چند روز دسترسی می‌ده؟ (مثلاً ۳۰)",
        },
    ],
    "physical": [],
}


def type_field_prompt(field: dict, is_fa: bool = False) -> str:
    """`field` is one entry from TYPE_FIELDS[product_type] — returns the
    language-appropriate prompt, falling back to the legacy single "prompt"
    key if a caller still has an old-shaped dict lying around."""
    if is_fa:
        return field.get("prompt_fa") or field.get("prompt", "")
    return field.get("prompt_en") or field.get("prompt", "")

SHIPPING_METHODS = ["📮 پست", "🚚 ماهکس", "📦 تیپاکس", "🛵 پیک اسنپ"]

# Shipping cost is deliberately never calculated or collected here — an
# admin-quote-before-payment step would break the fully-automatic Zarinpal
# flow, so it's simply stated as the buyer's responsibility on the invoice
# (see _render_invoice_pdf's disclaimer line below).
SHIPPING_COST_DISCLAIMER_FA = "هزینه ارسال به عهده خریدار می‌باشد."
SHIPPING_COST_DISCLAIMER_EN = "Shipping cost is the buyer's responsibility."

VAT_RATE_PERCENT = 10

_FONT_NAME = "Vazirmatn"
_FONT_PATH = Path(__file__).resolve().parent / "assets" / "Vazirmatn-Regular.ttf"
pdfmetrics.registerFont(TTFont(_FONT_NAME, str(_FONT_PATH)))


def _fa(text: str) -> str:
    """Reshapes + bidi-reorders Persian text — reportlab draws glyph runs
    left-to-right with no script awareness, so RTL text needs this first."""
    return get_display(reshape(text))


async def get_products(bot_id: uuid.UUID) -> list[Product]:
    """The bot's real products — hidden per-item unlock products
    (product_type="content_unlock") are never included anywhere the owner or
    a cart sees them."""
    async with async_session_maker() as session:
        result = await session.execute(
            select(Product)
            .where(Product.bot_id == bot_id, Product.product_type != CONTENT_UNLOCK_TYPE)
            .order_by(Product.id)
        )
        return list(result.scalars())


async def get_products_page(
    bot_id: uuid.UUID, offset: int = 0, limit: int = 30
) -> tuple[list[Product], bool]:
    """Returns (page, has_more) — a bounded page of this bot's products,
    ordered by id. Used by the Shop tool's "📦 Products" list, which builds
    an inline keyboard Telegram rejects outright once a bot has more than a
    couple dozen products (see bot/keyboards.py:shop_products_keyboard) —
    get_products above stays unbounded for callers that just need the full
    list (e.g. counting/existence checks) or an already-small set."""
    async with async_session_maker() as session:
        result = await session.execute(
            select(Product)
            .where(Product.bot_id == bot_id, Product.product_type != CONTENT_UNLOCK_TYPE)
            .order_by(Product.id)
            .offset(offset)
            .limit(limit + 1)
        )
        rows = list(result.scalars())
    has_more = len(rows) > limit
    return rows[:limit], has_more


async def get_standalone_products(bot_id: uuid.UUID) -> list[Product]:
    """Products NOT linked to a Content List item — used by the "shop" flow
    block/command so it doesn't duplicate items already browsable (with a Buy
    button) through the "content_list" block. Content-linked products are
    still fully manageable from the Shop chat tool's Products list."""
    async with async_session_maker() as session:
        linked_ids = select(ContentItem.product_id).where(ContentItem.product_id.isnot(None))
        result = await session.execute(
            select(Product)
            .where(Product.bot_id == bot_id, Product.id.not_in(linked_ids))
            .order_by(Product.id)
        )
        return list(result.scalars())


async def upsert_products_from_import(bot_id: uuid.UUID, items: list[dict]) -> dict:
    """Applies parsed rows (bot/shop_import.py:parse_products_workbook) to the
    Product table: a row with a Code matching an existing product (created by
    an EARLIER import, i.e. Product.import_code) updates it in place, one
    with a new/no Code always creates a new row, and a "delete" row removes
    the product matching its Code. Mirrors bot/content_nav.py:upsert_item's
    add-vs-edit rule, scoped to import_code instead of a resolved item_id.

    Imported products default to product_type="physical" (ships, collects
    shipping info at checkout) since the importer has no field for choosing
    a delivery mechanism — an owner who wants digital/access/subscription
    products with per-item delivery still uses the manual "Add Product" wizard.

    Returns {"created": n, "updated": n, "deleted": n, "skipped": n}."""
    created = updated = deleted = 0

    async with async_session_maker() as session:
        result = await session.execute(
            select(Product).where(Product.bot_id == bot_id, Product.import_code.isnot(None))
        )
        code_to_product = {p.import_code: p for p in result.scalars()}

        for item in items:
            if item["action"] == "delete":
                target = code_to_product.get(item["code"])
                if target is not None:
                    await session.delete(target)
                    deleted += 1
                continue

            existing = code_to_product.get(item["code"]) if item["code"] else None
            if existing is not None:
                existing.name = item["name"]
                existing.description = item["description"]
                existing.price = item["price"]
                existing.cost_price = item["cost_price"]
                existing.stock_quantity = item["stock_quantity"]
                existing.image_url = item["image_url"]
                updated += 1
            else:
                product = Product(
                    bot_id=bot_id,
                    name=item["name"],
                    description=item["description"],
                    price=item["price"],
                    cost_price=item["cost_price"],
                    stock_quantity=item["stock_quantity"],
                    image_url=item["image_url"],
                    product_type="physical",
                    import_code=item["code"],
                )
                session.add(product)
                if item["code"]:
                    code_to_product[item["code"]] = product
                created += 1

        await session.commit()

    return {"created": created, "updated": updated, "deleted": deleted}


async def get_product(product_id: int) -> Product | None:
    async with async_session_maker() as session:
        result = await session.execute(select(Product).where(Product.id == product_id))
        return result.scalar_one_or_none()


async def get_order(order_id: int) -> Order | None:
    async with async_session_maker() as session:
        result = await session.execute(select(Order).where(Order.id == order_id))
        return result.scalar_one_or_none()


async def list_recent_orders(bot_id: uuid.UUID, limit: int = 20) -> list[Order]:
    async with async_session_maker() as session:
        result = await session.execute(
            select(Order)
            .where(Order.bot_id == bot_id)
            .order_by(Order.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars())


async def get_shop_settings(bot_id: uuid.UUID) -> ShopSettings | None:
    async with async_session_maker() as session:
        result = await session.execute(select(ShopSettings).where(ShopSettings.bot_id == bot_id))
        return result.scalar_one_or_none()


def _compute_tax(subtotal: int, settings: ShopSettings | None) -> int:
    """10% Iranian VAT (مالیات بر ارزش‌افزوده) on `subtotal`, or 0 when the
    bot owner hasn't turned it on. Called once, at Order/Checkout creation
    time, and the result is snapshotted (Order.tax_amount / Checkout.tax_amount)
    — see those columns' docstrings for why."""
    if settings and settings.tax_enabled:
        return round(subtotal * VAT_RATE_PERCENT / 100)
    return 0


def order_total(order: Order) -> int:
    """price + VAT — the amount actually charged to / shown to the buyer,
    and the "مبلغ قابل پرداخت" grand total on the invoice."""
    return order.price + (order.tax_amount or 0)


def checkout_total(checkout: Checkout) -> int:
    return checkout.total_price + (checkout.tax_amount or 0)


async def _get_or_create_settings(session, bot_id: uuid.UUID) -> ShopSettings:
    settings = (
        await session.execute(select(ShopSettings).where(ShopSettings.bot_id == bot_id))
    ).scalar_one_or_none()
    if settings is None:
        settings = ShopSettings(bot_id=bot_id)
        session.add(settings)
        await session.flush()
    return settings


async def get_default_unlock_price(bot_id: uuid.UUID) -> int | None:
    settings = await get_shop_settings(bot_id)
    return settings.default_unlock_price if settings is not None else None


async def set_default_unlock_price(bot_id: uuid.UUID, price: int | None) -> None:
    """Owner sets the bot-wide à-la-carte price. Left as the live value even
    during a campaign only if no campaign is running; otherwise the campaign
    is adjusting it, so we set the pre-campaign baseline instead."""
    async with async_session_maker() as session:
        settings = await _get_or_create_settings(session, bot_id)
        campaign = (
            await session.execute(
                select(PriceCampaign).where(
                    PriceCampaign.bot_id == bot_id, PriceCampaign.status == "active"
                )
            )
        ).scalar_one_or_none()
        if campaign is not None and settings.original_default_unlock_price is not None:
            settings.original_default_unlock_price = price
            if price is None:
                settings.default_unlock_price = None
            else:
                settings.default_unlock_price = pricing.adjusted_price(
                    price, campaign.direction, campaign.percent
                )
        else:
            settings.default_unlock_price = price
        await session.commit()


async def ensure_unlock_product(bot_id: uuid.UUID, item: ContentItem, price: int) -> Product:
    """Get-or-create the hidden Product backing `item`'s à-la-carte unlock,
    linked via ContentItem.product_id. `price` is the pre-campaign price; if a
    discount/markup campaign is running it's applied here too (and stashed in
    original_price) so the buy button and the campaign revert both behave."""
    async with async_session_maker() as session:
        # Trust the DB, not a possibly-stale in-memory item.product_id, so
        # repeated calls reuse the same hidden product instead of piling up
        # duplicates.
        linked_product_id = (
            await session.execute(select(ContentItem.product_id).where(ContentItem.id == item.id))
        ).scalar_one_or_none()

        product = None
        if linked_product_id is not None:
            product = (
                await session.execute(
                    select(Product).where(
                        Product.id == linked_product_id,
                        Product.product_type == CONTENT_UNLOCK_TYPE,
                    )
                )
            ).scalar_one_or_none()

        campaign = (
            await session.execute(
                select(PriceCampaign).where(
                    PriceCampaign.bot_id == bot_id, PriceCampaign.status == "active"
                )
            )
        ).scalar_one_or_none()
        live_price = price
        original_price = None
        if campaign is not None:
            live_price = pricing.adjusted_price(price, campaign.direction, campaign.percent)
            original_price = price

        if product is None:
            product = Product(
                bot_id=bot_id,
                name=item.title,
                description=(item.body or item.title)[:2000] or item.title,
                price=live_price,
                original_price=original_price,
                product_type=CONTENT_UNLOCK_TYPE,
                delivery_file_url=item.link_url,
            )
            session.add(product)
            await session.flush()
            db_item = (
                await session.execute(select(ContentItem).where(ContentItem.id == item.id))
            ).scalar_one()
            db_item.product_id = product.id
        else:
            product.name = item.title
            product.description = (item.body or item.title)[:2000] or item.title
            product.delivery_file_url = item.link_url
            # Only rewrite the price when the owner's baseline actually changed,
            # so we don't clobber a campaign adjustment already in place.
            baseline = product.original_price if product.original_price is not None else product.price
            if baseline != price:
                product.price = live_price
                product.original_price = original_price
        await session.commit()
        await session.refresh(product)
        return product


# --- Time-boxed price campaigns (bot/db/models.py: PriceCampaign) ---


async def get_active_campaign(bot_id: uuid.UUID) -> PriceCampaign | None:
    async with async_session_maker() as session:
        return (
            await session.execute(
                select(PriceCampaign).where(
                    PriceCampaign.bot_id == bot_id, PriceCampaign.status == "active"
                )
            )
        ).scalar_one_or_none()


async def start_price_campaign(
    bot_id: uuid.UUID, direction: str, percent: int, days: int
) -> PriceCampaign | None:
    """Snapshot every price into its original_* column and overwrite the live
    price with the adjusted value; record the campaign. Returns None if one is
    already running (end it first)."""
    now = datetime.now(timezone.utc)
    async with async_session_maker() as session:
        existing = (
            await session.execute(
                select(PriceCampaign).where(
                    PriceCampaign.bot_id == bot_id, PriceCampaign.status == "active"
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return None

        def adj(base: int) -> int:
            return pricing.adjusted_price(base, direction, percent)

        products = list(
            (
                await session.execute(select(Product).where(Product.bot_id == bot_id))
            ).scalars()
        )
        for p in products:
            p.original_price = p.price
            p.price = adj(p.price)

        items = list(
            (
                await session.execute(
                    select(ContentItem).where(
                        ContentItem.bot_id == bot_id, ContentItem.unlock_price.isnot(None)
                    )
                )
            ).scalars()
        )
        for it in items:
            it.original_unlock_price = it.unlock_price
            it.unlock_price = adj(it.unlock_price)

        settings = (
            await session.execute(select(ShopSettings).where(ShopSettings.bot_id == bot_id))
        ).scalar_one_or_none()
        if settings is not None and settings.default_unlock_price is not None:
            settings.original_default_unlock_price = settings.default_unlock_price
            settings.default_unlock_price = adj(settings.default_unlock_price)

        campaign = PriceCampaign(
            bot_id=bot_id,
            direction=direction,
            percent=percent,
            status="active",
            starts_at=now,
            ends_at=now + timedelta(days=days),
        )
        session.add(campaign)
        await session.commit()
        await session.refresh(campaign)
        return campaign


async def _revert_campaign(session, campaign: PriceCampaign) -> None:
    await session.execute(
        update(Product)
        .where(Product.bot_id == campaign.bot_id, Product.original_price.isnot(None))
        .values(price=Product.original_price, original_price=None)
    )
    await session.execute(
        update(ContentItem)
        .where(
            ContentItem.bot_id == campaign.bot_id,
            ContentItem.original_unlock_price.isnot(None),
        )
        .values(unlock_price=ContentItem.original_unlock_price, original_unlock_price=None)
    )
    await session.execute(
        update(ShopSettings)
        .where(
            ShopSettings.bot_id == campaign.bot_id,
            ShopSettings.original_default_unlock_price.isnot(None),
        )
        .values(
            default_unlock_price=ShopSettings.original_default_unlock_price,
            original_default_unlock_price=None,
        )
    )
    campaign.status = "ended"
    campaign.ended_at = datetime.now(timezone.utc)


async def end_price_campaign(bot_id: uuid.UUID) -> bool:
    """Restore every pre-campaign price now (owner tapped "End"). False if
    nothing was running."""
    async with async_session_maker() as session:
        campaign = (
            await session.execute(
                select(PriceCampaign).where(
                    PriceCampaign.bot_id == bot_id, PriceCampaign.status == "active"
                )
            )
        ).scalar_one_or_none()
        if campaign is None:
            return False
        await _revert_campaign(session, campaign)
        await session.commit()
        return True


async def expire_due_campaigns() -> list[uuid.UUID]:
    """Revert every campaign whose ends_at has passed. Returns the affected
    bot ids (for logging). Called on a timer from bot/runtime.py."""
    now = datetime.now(timezone.utc)
    reverted: list[uuid.UUID] = []
    async with async_session_maker() as session:
        due = list(
            (
                await session.execute(
                    select(PriceCampaign).where(
                        PriceCampaign.status == "active", PriceCampaign.ends_at <= now
                    )
                )
            ).scalars()
        )
        for campaign in due:
            await _revert_campaign(session, campaign)
            reverted.append(campaign.bot_id)
        if due:
            await session.commit()
    return reverted


async def create_order(bot_id: uuid.UUID, product_id: int, buyer_telegram_id: int) -> Order | None:
    product = await get_product(product_id)
    if product is None or product.bot_id != bot_id:
        return None
    if product.stock_quantity is not None and product.stock_quantity <= 0:
        return None  # sold out — stock is only decremented at fulfillment, but never sold below 0

    settings = await get_shop_settings(bot_id)
    tax_amount = _compute_tax(product.price, settings)

    async with async_session_maker() as session:
        order = Order(
            bot_id=bot_id, product_id=product.id, buyer_telegram_id=buyer_telegram_id,
            price=product.price, tax_amount=tax_amount,
        )
        session.add(order)
        await session.commit()
        await session.refresh(order)
        return order


# --- Cart: "➕ Add to Cart" alongside the direct "🛒 Buy" flow above. Adding
# to the cart never creates an Order — that only happens at checkout, one
# Order per cart item, exactly like create_order above (see create_checkout). ---


async def get_cart_items(bot_id: uuid.UUID, buyer_telegram_id: int) -> list[tuple[CartItem, Product]]:
    async with async_session_maker() as session:
        result = await session.execute(
            select(CartItem, Product)
            .join(Product, Product.id == CartItem.product_id)
            .where(CartItem.bot_id == bot_id, CartItem.buyer_telegram_id == buyer_telegram_id)
            .order_by(CartItem.id)
        )
        return [(ci, p) for ci, p in result.all()]


async def add_to_cart(bot_id: uuid.UUID, buyer_telegram_id: int, product_id: int) -> bool:
    """Returns False (no-op) if the product doesn't belong to this bot, or
    is already in the buyer's cart."""
    product = await get_product(product_id)
    if product is None or product.bot_id != bot_id:
        return False

    async with async_session_maker() as session:
        result = await session.execute(
            select(CartItem).where(
                CartItem.bot_id == bot_id,
                CartItem.buyer_telegram_id == buyer_telegram_id,
                CartItem.product_id == product_id,
            )
        )
        if result.scalar_one_or_none() is not None:
            return False
        session.add(
            CartItem(bot_id=bot_id, buyer_telegram_id=buyer_telegram_id, product_id=product_id)
        )
        await session.commit()
        return True


async def remove_from_cart(cart_item_id: int, bot_id: uuid.UUID, buyer_telegram_id: int) -> None:
    async with async_session_maker() as session:
        result = await session.execute(
            select(CartItem).where(
                CartItem.id == cart_item_id,
                CartItem.bot_id == bot_id,
                CartItem.buyer_telegram_id == buyer_telegram_id,
            )
        )
        item = result.scalar_one_or_none()
        if item is not None:
            await session.delete(item)
            await session.commit()


async def get_checkout(checkout_id: int) -> Checkout | None:
    async with async_session_maker() as session:
        result = await session.execute(select(Checkout).where(Checkout.id == checkout_id))
        return result.scalar_one_or_none()


async def create_checkout(bot_id: uuid.UUID, buyer_telegram_id: int) -> Checkout | None:
    """Snapshots the buyer's cart into one Checkout + one Order per item
    (price snapshotted, same as create_order), then empties the cart.
    A cart item that's since sold out is dropped from the cart silently
    instead of blocking checkout for the items still available — same
    graceful-omit approach as everywhere else in this module.
    Returns None if the cart is empty (or every item in it is sold out)."""
    items = await get_cart_items(bot_id, buyer_telegram_id)
    available = [
        (cart_item, product) for cart_item, product in items
        if product.stock_quantity is None or product.stock_quantity > 0
    ]
    if not available:
        return None

    total_price = sum(product.price for _, product in available)
    settings = await get_shop_settings(bot_id)
    tax_amount = _compute_tax(total_price, settings)

    async with async_session_maker() as session:
        checkout = Checkout(
            bot_id=bot_id, buyer_telegram_id=buyer_telegram_id,
            total_price=total_price, tax_amount=tax_amount,
        )
        session.add(checkout)
        await session.flush()  # assign checkout.id before linking orders

        for cart_item, product in available:
            session.add(
                Order(
                    bot_id=bot_id,
                    product_id=product.id,
                    buyer_telegram_id=buyer_telegram_id,
                    price=product.price,
                    checkout_id=checkout.id,
                )
            )
            await session.delete(cart_item)

        # A sold-out item left in the cart (not in `available`) is dropped
        # here too, so it doesn't linger and confuse the next checkout attempt.
        for cart_item, product in items:
            if product.stock_quantity is not None and product.stock_quantity <= 0:
                await session.delete(cart_item)

        await session.commit()
        await session.refresh(checkout)
        return checkout


async def _zarinpal_request(
    merchant_id: str, amount_rial: int, description: str, callback_url: str
) -> str | None:
    """Calls Zarinpal's payment/request.json. Returns the authority, or None
    on failure (bad merchant ID, network error, etc.). Shared by the
    single-Order and Checkout payment flows below — the only place that
    actually talks to this endpoint."""
    payload = {
        "merchant_id": merchant_id,
        "amount": amount_rial,
        "callback_url": callback_url,
        "description": description,
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                ZARINPAL_REQUEST_URL, json=payload, timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                data = await resp.json()
    except Exception:
        logger.exception("Zarinpal payment request failed")
        return None

    authority = (data.get("data") or {}).get("authority")
    if not authority:
        logger.warning("Zarinpal request returned no authority: %s", data)
        return None
    return authority


async def _zarinpal_verify(merchant_id: str, amount_rial: int, authority: str) -> dict | None:
    """Calls Zarinpal's verify.json. Returns its `data` dict on a successful
    verification (code 100 = verified now, 101 = already verified), else
    None (network failure, or verification failed/pending)."""
    payload = {"merchant_id": merchant_id, "amount": amount_rial, "authority": authority}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                ZARINPAL_VERIFY_URL, json=payload, timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                data = await resp.json()
    except Exception:
        logger.exception("Zarinpal verify failed")
        return None

    result = data.get("data") or {}
    if result.get("code") not in (100, 101):
        return None
    return result


async def start_zarinpal_payment(order: Order, callback_base_url: str) -> str | None:
    """Stores the authority on `order` and returns the StartPay redirect
    URL — or None if Zarinpal isn't configured or the request failed."""
    settings = await get_shop_settings(order.bot_id)
    if settings is None or not settings.zarinpal_merchant_id:
        return None

    product = await get_product(order.product_id)
    authority = await _zarinpal_request(
        settings.zarinpal_merchant_id,
        order_total(order) * 10,  # Toman -> Rial, VAT-inclusive
        product.name if product else "Purchase",
        f"{callback_base_url}/payment/zarinpal/callback?order_id={order.id}",
    )
    if authority is None:
        return None

    async with async_session_maker() as session:
        result = await session.execute(select(Order).where(Order.id == order.id))
        row = result.scalar_one()
        row.payment_method = "zarinpal"
        row.zarinpal_authority = authority
        await session.commit()

    return ZARINPAL_STARTPAY_URL.format(authority=authority)


async def verify_zarinpal_payment(authority: str) -> Order | None:
    """Looks up the order by authority, verifies with Zarinpal, and on
    success marks it paid + fulfills it (idempotent — Zarinpal can hit the
    callback more than once). Returns the order (whatever its resulting
    status) so the callback page can say something sensible, or None if no
    order matches this authority at all."""
    async with async_session_maker() as session:
        result = await session.execute(select(Order).where(Order.zarinpal_authority == authority))
        order = result.scalar_one_or_none()
    if order is None:
        return None
    if order.status != "pending":
        return order

    settings = await get_shop_settings(order.bot_id)
    if settings is None or not settings.zarinpal_merchant_id:
        return order

    verify_data = await _zarinpal_verify(settings.zarinpal_merchant_id, order_total(order) * 10, authority)
    if verify_data is None:
        return order

    async with async_session_maker() as session:
        result = await session.execute(select(Order).where(Order.id == order.id))
        row = result.scalar_one()
        row.status = "paid"
        row.zarinpal_ref_id = str(verify_data.get("ref_id") or "")
        await session.commit()
        await session.refresh(row)
        order = row

    async with async_session_maker() as session:
        result = await session.execute(select(BuiltBot).where(BuiltBot.id == order.bot_id))
        built_bot = result.scalar_one()

    temp_bot = Bot(token=built_bot.token, session=make_session())
    try:
        await fulfill_order(temp_bot, order)
    finally:
        await temp_bot.session.close()

    # fulfill_order updates status/invoice_number on its own session, so the
    # `order` object above is stale (still "paid") — re-fetch for the caller.
    return await get_order(order.id)


async def _stripe_create_session(
    secret_key: str, amount_cents: int, description: str, success_url: str, cancel_url: str
) -> tuple[str, str] | None:
    """Creates a Stripe Checkout Session. Returns (session_id, checkout_url),
    or None on failure. Shared by the single-Order and Checkout flows."""
    payload = {
        "mode": "payment",
        "success_url": success_url,
        "cancel_url": cancel_url,
        "line_items[0][quantity]": "1",
        "line_items[0][price_data][currency]": "usd",
        "line_items[0][price_data][unit_amount]": str(amount_cents),
        "line_items[0][price_data][product_data][name]": description,
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                STRIPE_CHECKOUT_URL,
                data=payload,
                headers={"Authorization": f"Bearer {secret_key}"},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                data = await resp.json()
    except Exception:
        logger.exception("Stripe checkout session creation failed")
        return None

    session_id = data.get("id")
    checkout_url = data.get("url")
    if not session_id or not checkout_url:
        logger.warning("Stripe session creation returned no id/url: %s", data)
        return None
    return session_id, checkout_url


async def _stripe_retrieve_session(secret_key: str, session_id: str) -> dict | None:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                STRIPE_SESSION_URL.format(session_id=session_id),
                headers={"Authorization": f"Bearer {secret_key}"},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                return await resp.json()
    except Exception:
        logger.exception("Stripe session retrieve failed")
        return None


async def start_stripe_payment(order: Order, callback_base_url: str) -> str | None:
    """Creates a Stripe Checkout Session, stores its id, and returns the
    hosted checkout URL to redirect the buyer to — or None if Stripe isn't
    configured or the request failed."""
    settings = await get_shop_settings(order.bot_id)
    if settings is None or not settings.stripe_secret_key:
        return None

    product = await get_product(order.product_id)
    success_url = callback_base_url + "/payment/stripe/callback?session_id={CHECKOUT_SESSION_ID}"
    cancel_url = callback_base_url + f"/payment/stripe/callback?cancelled=1&order_id={order.id}"

    created = await _stripe_create_session(
        settings.stripe_secret_key,
        order_total(order) * 100,  # dollars -> cents, VAT-inclusive
        product.name if product else "Purchase",
        success_url,
        cancel_url,
    )
    if created is None:
        return None
    session_id, checkout_url = created

    async with async_session_maker() as session:
        result = await session.execute(select(Order).where(Order.id == order.id))
        row = result.scalar_one()
        row.payment_method = "stripe"
        row.stripe_session_id = session_id
        await session.commit()

    return checkout_url


async def verify_stripe_payment(session_id: str) -> Order | None:
    """Looks up the order by Stripe session id, checks the session's
    payment_status, and on success marks it paid + fulfills it (idempotent —
    Stripe can redirect the buyer's browser here more than once)."""
    async with async_session_maker() as session:
        result = await session.execute(select(Order).where(Order.stripe_session_id == session_id))
        order = result.scalar_one_or_none()
    if order is None:
        return None
    if order.status != "pending":
        return order

    settings = await get_shop_settings(order.bot_id)
    if settings is None or not settings.stripe_secret_key:
        return order

    data = await _stripe_retrieve_session(settings.stripe_secret_key, session_id)
    if data is None or data.get("payment_status") != "paid":
        return order

    async with async_session_maker() as session:
        result = await session.execute(select(Order).where(Order.id == order.id))
        row = result.scalar_one()
        row.status = "paid"
        await session.commit()
        await session.refresh(row)
        order = row

    async with async_session_maker() as session:
        result = await session.execute(select(BuiltBot).where(BuiltBot.id == order.bot_id))
        built_bot = result.scalar_one()

    temp_bot = Bot(token=built_bot.token, session=make_session())
    try:
        await fulfill_order(temp_bot, order)
    finally:
        await temp_bot.session.close()

    # fulfill_order updates status/invoice_number on its own session, so the
    # `order` object above is stale (still "paid") — re-fetch for the caller.
    return await get_order(order.id)


# --- Checkout-scoped mirrors of the two Order-scoped flows above — same
# gateway helpers (_zarinpal_request/_verify, _stripe_create_session/
# _retrieve_session), same shape, but pay for every Order in one Checkout
# at once instead of a single Order. See fulfill_checkout below. ---


async def start_zarinpal_checkout(checkout: Checkout, callback_base_url: str) -> str | None:
    settings = await get_shop_settings(checkout.bot_id)
    if settings is None or not settings.zarinpal_merchant_id:
        return None

    authority = await _zarinpal_request(
        settings.zarinpal_merchant_id,
        checkout_total(checkout) * 10,  # VAT-inclusive
        "Cart checkout",
        f"{callback_base_url}/payment/zarinpal/callback?checkout_id={checkout.id}",
    )
    if authority is None:
        return None

    async with async_session_maker() as session:
        result = await session.execute(select(Checkout).where(Checkout.id == checkout.id))
        row = result.scalar_one()
        row.payment_method = "zarinpal"
        row.zarinpal_authority = authority
        await session.commit()

    return ZARINPAL_STARTPAY_URL.format(authority=authority)


async def verify_zarinpal_checkout(authority: str) -> Checkout | None:
    async with async_session_maker() as session:
        result = await session.execute(select(Checkout).where(Checkout.zarinpal_authority == authority))
        checkout = result.scalar_one_or_none()
    if checkout is None:
        return None
    if checkout.status != "pending":
        return checkout

    settings = await get_shop_settings(checkout.bot_id)
    if settings is None or not settings.zarinpal_merchant_id:
        return checkout

    verify_data = await _zarinpal_verify(settings.zarinpal_merchant_id, checkout_total(checkout) * 10, authority)
    if verify_data is None:
        return checkout

    async with async_session_maker() as session:
        result = await session.execute(select(Checkout).where(Checkout.id == checkout.id))
        row = result.scalar_one()
        row.status = "paid"
        row.zarinpal_ref_id = str(verify_data.get("ref_id") or "")
        await session.commit()
        await session.refresh(row)
        checkout = row

    async with async_session_maker() as session:
        result = await session.execute(select(BuiltBot).where(BuiltBot.id == checkout.bot_id))
        built_bot = result.scalar_one()

    temp_bot = Bot(token=built_bot.token, session=make_session())
    try:
        await fulfill_checkout(temp_bot, checkout)
    finally:
        await temp_bot.session.close()

    return await get_checkout(checkout.id)


async def start_stripe_checkout(checkout: Checkout, callback_base_url: str) -> str | None:
    settings = await get_shop_settings(checkout.bot_id)
    if settings is None or not settings.stripe_secret_key:
        return None

    success_url = callback_base_url + "/payment/stripe/callback?session_id={CHECKOUT_SESSION_ID}"
    cancel_url = callback_base_url + f"/payment/stripe/callback?cancelled=1&checkout_id={checkout.id}"

    created = await _stripe_create_session(
        settings.stripe_secret_key, checkout_total(checkout) * 100, "Cart checkout", success_url, cancel_url
    )
    if created is None:
        return None
    session_id, checkout_url = created

    async with async_session_maker() as session:
        result = await session.execute(select(Checkout).where(Checkout.id == checkout.id))
        row = result.scalar_one()
        row.payment_method = "stripe"
        row.stripe_session_id = session_id
        await session.commit()

    return checkout_url


async def verify_stripe_checkout(session_id: str) -> Checkout | None:
    async with async_session_maker() as session:
        result = await session.execute(select(Checkout).where(Checkout.stripe_session_id == session_id))
        checkout = result.scalar_one_or_none()
    if checkout is None:
        return None
    if checkout.status != "pending":
        return checkout

    settings = await get_shop_settings(checkout.bot_id)
    if settings is None or not settings.stripe_secret_key:
        return checkout

    data = await _stripe_retrieve_session(settings.stripe_secret_key, session_id)
    if data is None or data.get("payment_status") != "paid":
        return checkout

    async with async_session_maker() as session:
        result = await session.execute(select(Checkout).where(Checkout.id == checkout.id))
        row = result.scalar_one()
        row.status = "paid"
        await session.commit()
        await session.refresh(row)
        checkout = row

    async with async_session_maker() as session:
        result = await session.execute(select(BuiltBot).where(BuiltBot.id == checkout.bot_id))
        built_bot = result.scalar_one()

    temp_bot = Bot(token=built_bot.token, session=make_session())
    try:
        await fulfill_checkout(temp_bot, checkout)
    finally:
        await temp_bot.session.close()

    return await get_checkout(checkout.id)


async def submit_manual_payment(order_id: int, payment_method: str, transaction_ref: str) -> Order:
    """Records a buyer-submitted payment reference for any "manual" method —
    card-to-card, crypto, or TON — all of which share the same review flow:
    the buyer sends funds off-platform, submits a reference, and the bot
    owner approves/rejects it (see approve_manual_payment/reject_manual_payment
    below). payment_method is one of "card_to_card" | "crypto" | "ton"."""
    async with async_session_maker() as session:
        result = await session.execute(select(Order).where(Order.id == order_id))
        order = result.scalar_one()
        order.payment_method = payment_method
        order.transaction_ref = transaction_ref
        await session.commit()
        await session.refresh(order)
        return order


async def approve_manual_payment(bot: Bot, order_id: int) -> Order:
    async with async_session_maker() as session:
        result = await session.execute(select(Order).where(Order.id == order_id))
        order = result.scalar_one()
        order.status = "paid"
        await session.commit()
        await session.refresh(order)
        order_snapshot = order

    await fulfill_order(bot, order_snapshot)
    # fulfill_order updates status/invoice_number on its own session, so
    # order_snapshot is stale (still "paid") — re-fetch for the caller.
    return await get_order(order_id)


async def reject_manual_payment(order_id: int) -> None:
    async with async_session_maker() as session:
        result = await session.execute(select(Order).where(Order.id == order_id))
        order = result.scalar_one_or_none()
        if order is not None:
            order.status = "rejected"
            await session.commit()


# --- Checkout-scoped mirrors of the manual-payment trio above (card-to-card/
# crypto/TON review flow) — same shape, on Checkout instead of Order. ---


async def submit_manual_checkout_payment(checkout_id: int, payment_method: str, transaction_ref: str) -> Checkout:
    async with async_session_maker() as session:
        result = await session.execute(select(Checkout).where(Checkout.id == checkout_id))
        checkout = result.scalar_one()
        checkout.payment_method = payment_method
        checkout.transaction_ref = transaction_ref
        await session.commit()
        await session.refresh(checkout)
        return checkout


async def approve_manual_checkout(bot: Bot, checkout_id: int) -> Checkout:
    async with async_session_maker() as session:
        result = await session.execute(select(Checkout).where(Checkout.id == checkout_id))
        checkout = result.scalar_one()
        checkout.status = "paid"
        await session.commit()
        await session.refresh(checkout)
        checkout_snapshot = checkout

    await fulfill_checkout(bot, checkout_snapshot)
    return await get_checkout(checkout_id)


async def reject_manual_checkout(checkout_id: int) -> None:
    async with async_session_maker() as session:
        result = await session.execute(select(Checkout).where(Checkout.id == checkout_id))
        checkout = result.scalar_one_or_none()
        if checkout is not None:
            checkout.status = "rejected"
            await session.commit()


async def save_shipping_info(
    order_id: int, method: str, name: str, phone: str, address: str, postal_code: str = ""
) -> Order:
    async with async_session_maker() as session:
        result = await session.execute(select(Order).where(Order.id == order_id))
        order = result.scalar_one()
        order.shipping_method = method
        order.shipping_name = name
        order.shipping_phone = phone
        order.shipping_address = address
        order.shipping_postal_code = postal_code
        await session.commit()
        await session.refresh(order)
        return order


async def save_checkout_shipping_info(
    checkout_id: int, method: str, name: str, phone: str, address: str, postal_code: str = ""
) -> Checkout:
    """Checkout-scoped mirror of save_shipping_info above — collected ONCE
    for every physical item in the cart (bot/runtime.py's shipc_info: wizard),
    instead of once per item, so fulfill_checkout can issue one combined
    invoice. Copied onto each linked Order by fulfill_checkout itself."""
    async with async_session_maker() as session:
        result = await session.execute(select(Checkout).where(Checkout.id == checkout_id))
        checkout = result.scalar_one()
        checkout.shipping_method = method
        checkout.shipping_name = name
        checkout.shipping_phone = phone
        checkout.shipping_address = address
        checkout.shipping_postal_code = postal_code
        await session.commit()
        await session.refresh(checkout)
        return checkout


async def get_orders_for_checkout(checkout_id: int) -> list[Order]:
    async with async_session_maker() as session:
        result = await session.execute(select(Order).where(Order.checkout_id == checkout_id))
        return list(result.scalars())


def _invoice_number(order: Order) -> str:
    return f"{order.bot_id.hex[:6].upper()}-{order.id:06d}"


def _checkout_invoice_number(checkout: Checkout) -> str:
    # "C" prefix keeps this visually distinct from a single-order invoice
    # number above — Order.id and Checkout.id are separate sequences that
    # could otherwise collide (e.g. order #5 and checkout #5 both -000005).
    return f"{checkout.bot_id.hex[:6].upper()}-C{checkout.id:06d}"


async def _decrement_stock(product_id: int) -> None:
    """Atomic conditional decrement (bot/inventory.py's enforcement point) —
    the WHERE guards against two concurrent fulfillments taking stock below
    0, and against decrementing a product whose stock isn't tracked (NULL)."""
    async with async_session_maker() as session:
        await session.execute(
            update(Product)
            .where(Product.id == product_id, Product.stock_quantity.isnot(None), Product.stock_quantity > 0)
            .values(stock_quantity=Product.stock_quantity - 1)
        )
        await session.commit()


async def fulfill_order(bot: Bot, order: Order, send_invoice: bool = True) -> None:
    """Dispatches on the product's type, then (unless send_invoice=False)
    issues an invoice. A physical order with no shipping info yet instead
    prompts the buyer to provide it (via a button that starts bot/runtime.py's
    shipping wizard) and returns — fulfillment finishes when that wizard
    calls this again, which is also why the stock decrement below sits AFTER
    that early return: it must fire exactly once, at the call that actually
    delivers.

    send_invoice=False is used only by fulfill_checkout below: a cart item
    still fulfills (delivers/ships) independently here, but the PDF itself
    is issued ONCE, combined, by fulfill_checkout — not per item."""
    product = await get_product(order.product_id)
    if product is None:
        return

    if product.product_type == "physical" and not order.shipping_address:
        await bot.send_message(
            order.buyer_telegram_id,
            f"✅ Payment confirmed for \"{product.name}\". Please provide your shipping info.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="📦 Enter Shipping Info", callback_data=f"ship_info:{order.id}"
                        )
                    ]
                ]
            ),
        )
        return

    await _decrement_stock(product.id)

    if product.product_type == "digital":
        parts = [f"✅ Payment confirmed for \"{product.name}\"."]
        if product.delivery_text:
            parts.append(product.delivery_text)
        await bot.send_message(order.buyer_telegram_id, "\n\n".join(parts))
        if product.delivery_file_url:
            await bot.send_message(order.buyer_telegram_id, f"🔗 {product.delivery_file_url}")

    elif product.product_type == CONTENT_UNLOCK_TYPE:
        # À-la-carte unlock of one premium ContentItem — record permanent
        # access (source="purchase" so it never counts against the free
        # preview quota, bot/premium_content.py) and hand over the file.
        async with async_session_maker() as session:
            item = (
                await session.execute(
                    select(ContentItem).where(ContentItem.product_id == product.id)
                )
            ).scalar_one_or_none()
            if item is not None:
                existing = (
                    await session.execute(
                        select(ContentUnlock).where(
                            ContentUnlock.bot_id == order.bot_id,
                            ContentUnlock.subscriber_telegram_id == order.buyer_telegram_id,
                            ContentUnlock.content_item_id == item.id,
                        )
                    )
                ).scalar_one_or_none()
                if existing is None:
                    session.add(
                        ContentUnlock(
                            bot_id=order.bot_id,
                            subscriber_telegram_id=order.buyer_telegram_id,
                            content_item_id=item.id,
                            source="purchase",
                        )
                    )
                    await session.commit()
        parts = [f"✅ Unlocked — \"{product.name}\" is yours."]
        if item is not None and item.body:
            parts.append(item.body)
        await bot.send_message(order.buyer_telegram_id, "\n\n".join(parts))
        link = product.delivery_file_url or (item.link_url if item is not None else None)
        if link:
            await bot.send_message(order.buyer_telegram_id, f"⬇️ {link}")

    elif product.product_type == "access":
        async with async_session_maker() as session:
            result = await session.execute(
                select(BotSubscriber).where(
                    BotSubscriber.bot_id == order.bot_id,
                    BotSubscriber.telegram_id == order.buyer_telegram_id,
                )
            )
            subscriber = result.scalar_one_or_none()
            if subscriber is not None:
                subscriber.access_level = product.access_level_name
                await session.commit()
        await bot.send_message(
            order.buyer_telegram_id,
            f"✅ Payment confirmed. Your access has changed to {product.access_level_name}.",
        )

    elif product.product_type == "physical":
        await bot.send_message(
            order.buyer_telegram_id,
            f"✅ Payment confirmed for \"{product.name}\". Your order will ship soon.",
        )

    elif product.product_type == "subscription":
        # Extends from the LATER of now or the current expiry, so renewing
        # before a subscription lapses stacks the new days on top instead of
        # discarding remaining time (see bot/premium_content.py — access is
        # always re-checked live against this timestamp, never permanent).
        new_until = None
        async with async_session_maker() as session:
            result = await session.execute(
                select(BotSubscriber).where(
                    BotSubscriber.bot_id == order.bot_id,
                    BotSubscriber.telegram_id == order.buyer_telegram_id,
                )
            )
            subscriber = result.scalar_one_or_none()
            if subscriber is not None:
                now = datetime.now(timezone.utc)
                base = subscriber.subscription_until if (subscriber.subscription_until and subscriber.subscription_until > now) else now
                new_until = base + timedelta(days=product.subscription_days or 0)
                subscriber.subscription_until = new_until
                await session.commit()
        if new_until is not None:
            await bot.send_message(
                order.buyer_telegram_id,
                f"✅ Payment confirmed. Your subscription is now active until {new_until:%Y-%m-%d}.",
            )

    async with async_session_maker() as session:
        result = await session.execute(select(Order).where(Order.id == order.id))
        row = result.scalar_one()
        row.status = "fulfilled"
        row.invoice_number = row.invoice_number or _invoice_number(row)
        await session.commit()
        await session.refresh(row)
        order = row

    if not send_invoice:
        return

    invoice_pdf = await generate_invoice(order)
    await bot.send_document(
        order.buyer_telegram_id,
        BufferedInputFile(invoice_pdf, filename=f"invoice-{order.invoice_number}.pdf"),
        caption="🧾 Invoice",
    )


async def fulfill_checkout(bot: Bot, checkout: Checkout) -> None:
    """Marks the checkout AND every linked Order paid. If any linked item is
    physical and the checkout doesn't have shipping info yet, collects it
    ONCE for the whole checkout (bot/runtime.py's shipc_info: wizard) instead
    of once per item, and returns — resuming (this function runs again) when
    that wizard finishes. Once shipping is settled (or wasn't needed), copies
    it onto every physical Order under this checkout, fulfills each Order's
    own delivery/shipping message via fulfill_order (send_invoice=False —
    each item still delivers independently, per its own product_type,
    exactly like a direct purchase), then issues ONE combined invoice PDF
    covering every item, instead of one per item."""
    async with async_session_maker() as session:
        result = await session.execute(select(Checkout).where(Checkout.id == checkout.id))
        row = result.scalar_one()
        row.status = "paid"
        await session.commit()
        await session.refresh(row)
        checkout = row

    async with async_session_maker() as session:
        result = await session.execute(select(Order).where(Order.checkout_id == checkout.id))
        orders = list(result.scalars())
        for order in orders:
            order.status = "paid"
        await session.commit()

    products = [await get_product(o.product_id) for o in orders]
    needs_shipping = any(p is not None and p.product_type == "physical" for p in products)

    if needs_shipping and not checkout.shipping_address:
        await bot.send_message(
            checkout.buyer_telegram_id,
            "✅ Payment confirmed. Please provide your shipping info for this order.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="📦 Enter Shipping Info", callback_data=f"shipc_info:{checkout.id}"
                        )
                    ]
                ]
            ),
        )
        return

    if checkout.shipping_address:
        # Copy the checkout-level shipping info onto every physical Order it
        # covers, so per-order fields (generate_invoice(order) for a
        # non-cart purchase, any admin view reading Order.shipping_*) stay
        # populated exactly as they always have.
        async with async_session_maker() as session:
            await session.execute(
                update(Order)
                .where(Order.checkout_id == checkout.id)
                .values(
                    shipping_method=checkout.shipping_method,
                    shipping_name=checkout.shipping_name,
                    shipping_phone=checkout.shipping_phone,
                    shipping_address=checkout.shipping_address,
                    shipping_postal_code=checkout.shipping_postal_code,
                )
            )
            await session.commit()
        orders = await get_orders_for_checkout(checkout.id)

    for order in orders:
        await fulfill_order(bot, order, send_invoice=False)

    async with async_session_maker() as session:
        result = await session.execute(select(Checkout).where(Checkout.id == checkout.id))
        row = result.scalar_one()
        row.invoice_number = row.invoice_number or _checkout_invoice_number(row)
        await session.commit()
        await session.refresh(row)
        checkout = row

    orders = await get_orders_for_checkout(checkout.id)
    invoice_pdf = await generate_checkout_invoice(checkout, orders)
    await bot.send_document(
        checkout.buyer_telegram_id,
        BufferedInputFile(invoice_pdf, filename=f"invoice-{checkout.invoice_number}.pdf"),
        caption="🧾 Invoice",
    )


async def _fetch_logo_image(url: str) -> ImageReader | None:
    """Best-effort logo download for generate_invoice — a broken/unreachable
    URL must never fail invoice generation, so any error here just means no
    logo gets drawn (same graceful-omit philosophy as everywhere else)."""
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return None
                data = await resp.read()
        return ImageReader(io.BytesIO(data))
    except Exception:
        return None


def _payment_label(method: str | None) -> str:
    return {
        "zarinpal": "زرین‌پال",
        "card_to_card": "کارت به کارت",
        "stripe": "Stripe",
        "crypto": "رمزارز",
        "ton": "TON",
    }.get(method or "", "-")


async def _render_invoice_pdf(
    *,
    bot_id: uuid.UUID,
    invoice_number: str,
    date: datetime,
    payment_label: str,
    buyer_telegram_id: int,
    items: list[tuple[str, int, int]],  # (name, qty, unit_price) — unit_price in Toman
    subtotal: int,
    tax_amount: int,
    shipping: dict | None,  # {"method","name","phone","address","postal_code"} or None
    has_physical: bool,
) -> bytes:
    """Shared renderer behind generate_invoice (one Order) and
    generate_checkout_invoice (several Orders combined into one PDF) — an
    itemized table (row-per-item, like a normal sales invoice) with the
    business's address/phone/footer note as a footer at the very bottom, and
    a signature/stamp box (with the invoice date) below that."""
    settings = await get_shop_settings(bot_id)
    logo = await _fetch_logo_image(settings.invoice_logo_url) if settings and settings.invoice_logo_url else None
    signature = (
        await _fetch_logo_image(settings.invoice_signature_url)
        if settings and settings.invoice_signature_url
        else None
    )

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    right_margin = width - 20 * mm
    left_margin = 20 * mm
    value_anchor = right_margin - 55 * mm  # value column, left of the label column

    def y_pt(y_mm: float) -> float:
        return height - y_mm * mm

    # Label + value are drawn as two SEPARATE strings/calls, each individually
    # reshaped — NOT concatenated into one string before reshaping. Reshaping
    # a combined "label: value" string and running it through python-bidi's
    # get_display() moves the (usually ASCII/numeric) value to a different
    # position in the resulting string, and reportlab+pypdf silently lose
    # that portion on draw/extract. Two anchored columns sidesteps it
    # entirely and is also just standard bilingual-invoice layout.
    def row(y_mm: float, label: str, value: object, size: int = 12) -> None:
        c.setFont(_FONT_NAME, size)

        label_shaped = _fa(label)
        label_width = c.stringWidth(label_shaped, _FONT_NAME, size)
        c.drawString(right_margin - label_width, y_pt(y_mm), label_shaped)

        value_shaped = _fa(str(value))
        value_width = c.stringWidth(value_shaped, _FONT_NAME, size)
        c.drawString(value_anchor - value_width, y_pt(y_mm), value_shaped)

    def title(y_mm: float, text: str, size: int = 18) -> None:
        shaped = _fa(text)
        c.setFont(_FONT_NAME, size)
        text_width = c.stringWidth(shaped, _FONT_NAME, size)
        c.drawString(right_margin - text_width, y_pt(y_mm), shaped)

    def cell(x_right: float, y_mm: float, text: str, size: int = 10) -> None:
        """One right-aligned table cell — same single-string-per-call
        isolation as row()/title() above, just anchored at an arbitrary x
        (a table column edge) instead of right_margin/value_anchor."""
        c.setFont(_FONT_NAME, size)
        shaped = _fa(str(text))
        c.drawRightString(x_right, y_pt(y_mm), shaped)

    def wrapped_lines(text: str, max_width_mm: float, size: int) -> list[str]:
        max_width = max_width_mm * mm
        words = text.split()
        lines: list[str] = []
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if not current or c.stringWidth(_fa(candidate), _FONT_NAME, size) <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines

    if logo is not None:
        try:
            c.drawImage(
                logo, left_margin, height - 40 * mm, width=25 * mm, height=25 * mm,
                preserveAspectRatio=True, mask="auto",
            )
        except Exception:
            pass  # a corrupt/unsupported image format must not break the invoice

    y = 20.0
    title(y, settings.invoice_business_name if settings and settings.invoice_business_name else "فاکتور فروش")
    y = 33.0
    row(y, "شماره فاکتور:", invoice_number, size=11)
    y += 7
    row(y, "تاریخ:", date.strftime("%Y-%m-%d %H:%M"), size=11)
    y += 7
    row(y, "روش پرداخت:", payment_label, size=11)
    y += 7
    row(y, "شناسه خریدار:", buyer_telegram_id, size=11)
    y += 9

    if shipping and shipping.get("address"):
        row(y, "روش ارسال:", shipping.get("method") or "", size=10)
        y += 6
        row(y, "گیرنده:", shipping.get("name") or "", size=10)
        y += 6
        row(y, "تلفن:", shipping.get("phone") or "", size=10)
        y += 6
        if shipping.get("postal_code"):
            row(y, "کدپستی:", shipping.get("postal_code"), size=10)
            y += 6
        for i, line in enumerate(wrapped_lines(shipping.get("address") or "", 90, 10)):
            row(y, "آدرس:" if i == 0 else "", line, size=10)
            y += 6
        y += 3

    if has_physical:
        title(y, SHIPPING_COST_DISCLAIMER_FA, size=9)
        y += 9

    # --- Items table (right-to-left: row# | item | qty | unit price | line total) ---
    col_row_r = right_margin
    col_desc_r = right_margin - 12 * mm
    col_qty_r = right_margin - 92 * mm
    col_unit_r = right_margin - 112 * mm
    col_total_r = right_margin - 142 * mm
    table_left = left_margin  # right_margin - 170mm, same usable width as everything else

    y += 4
    c.setLineWidth(0.6)
    c.line(table_left, y_pt(y + 3), right_margin, y_pt(y + 3))
    cell(col_row_r, y, "ردیف", size=10)
    cell(col_desc_r, y, "شرح کالا / خدمات", size=10)
    cell(col_qty_r, y, "تعداد", size=10)
    cell(col_unit_r, y, "قیمت واحد", size=10)
    cell(col_total_r, y, "جمع (تومان)", size=10)
    y += 6
    c.line(table_left, y_pt(y), right_margin, y_pt(y))
    y += 6

    # Single-page invoice, same graceful-cap approach as the footer note
    # below — a cart this large would run off the page regardless.
    for idx, (name, qty, unit_price) in enumerate(items[:12], start=1):
        line_total = qty * unit_price
        name_lines = wrapped_lines(name, 76, 10)[:2]
        cell(col_row_r, y, str(idx), size=10)
        for line_i, line in enumerate(name_lines):
            cell(col_desc_r, y + line_i * 5, line, size=10)
        cell(col_qty_r, y, str(qty), size=10)
        cell(col_unit_r, y, f"{unit_price:,}", size=10)
        cell(col_total_r, y, f"{line_total:,}", size=10)
        y += max(8, 5 * len(name_lines) + 3)

    c.line(table_left, y_pt(y), right_margin, y_pt(y))
    y += 9

    row(y, "جمع جزء:", f"{subtotal:,} تومان", size=11)
    y += 7
    if tax_amount:
        row(y, f"مالیات بر ارزش‌افزوده ({VAT_RATE_PERCENT}%):", f"{tax_amount:,} تومان", size=11)
        y += 7
    row(y, "مبلغ قابل پرداخت:", f"{subtotal + tax_amount:,} تومان", size=13)
    y += 9

    # --- Footer: business address/phone/note at the very bottom of the page ---
    footer_y = max(y + 8, 255.0)
    if settings and (settings.invoice_address or settings.invoice_business_phone or settings.invoice_footer_note):
        c.setLineWidth(0.3)
        c.line(table_left, y_pt(footer_y - 4), right_margin, y_pt(footer_y - 4))
        if settings.invoice_address:
            for line in wrapped_lines(settings.invoice_address, 170, 9)[:2]:
                title(footer_y, line, size=9)
                footer_y += 5
        if settings.invoice_business_phone:
            row(footer_y, "تلفن:", settings.invoice_business_phone, size=9)
            footer_y += 5
        if settings.invoice_footer_note:
            for line in wrapped_lines(settings.invoice_footer_note, 170, 9)[:3]:
                title(footer_y, line, size=9)
                footer_y += 5

    # --- Signature / stamp box, bottom-right, with the invoice date --------
    box_w = 45 * mm
    box_h = 22 * mm
    box_top_mm = max(footer_y + 10, 268.0)
    c.setLineWidth(0.5)
    c.rect(right_margin - box_w, y_pt(box_top_mm) - box_h, box_w, box_h)
    if signature is not None:
        try:
            c.drawImage(
                signature, right_margin - box_w + 2, y_pt(box_top_mm) - box_h + 2,
                width=box_w - 4, height=box_h - 4,
                preserveAspectRatio=True, mask="auto",
            )
        except Exception:
            pass  # a corrupt/unsupported image format must not break the invoice
    title(box_top_mm - 4, "امضا و مهر فروشگاه", size=9)
    title(box_top_mm + (box_h / mm) + 6, f"تاریخ: {date.strftime('%Y-%m-%d')}", size=9)

    c.showPage()
    c.save()
    return buffer.getvalue()


async def generate_invoice(order: Order) -> bytes:
    product = await get_product(order.product_id)
    return await _render_invoice_pdf(
        bot_id=order.bot_id,
        invoice_number=order.invoice_number,
        date=order.updated_at,
        payment_label=_payment_label(order.payment_method),
        buyer_telegram_id=order.buyer_telegram_id,
        items=[(product.name if product else "-", 1, order.price)],
        subtotal=order.price,
        tax_amount=order.tax_amount or 0,
        shipping=(
            {
                "method": order.shipping_method,
                "name": order.shipping_name,
                "phone": order.shipping_phone,
                "address": order.shipping_address,
                "postal_code": order.shipping_postal_code,
            }
            if order.shipping_method
            else None
        ),
        has_physical=bool(product and product.product_type == "physical"),
    )


async def generate_checkout_invoice(checkout: Checkout, orders: list[Order]) -> bytes:
    """Combined invoice for every Order under one Checkout — see
    fulfill_checkout, which is the only real caller."""
    products = [await get_product(o.product_id) for o in orders]
    items = [
        (product.name if product else "-", 1, o.price) for o, product in zip(orders, products)
    ]
    return await _render_invoice_pdf(
        bot_id=checkout.bot_id,
        invoice_number=checkout.invoice_number,
        date=checkout.updated_at,
        payment_label=_payment_label(checkout.payment_method),
        buyer_telegram_id=checkout.buyer_telegram_id,
        items=items,
        subtotal=checkout.total_price,
        tax_amount=checkout.tax_amount or 0,
        shipping=(
            {
                "method": checkout.shipping_method,
                "name": checkout.shipping_name,
                "phone": checkout.shipping_phone,
                "address": checkout.shipping_address,
                "postal_code": checkout.shipping_postal_code,
            }
            if checkout.shipping_method
            else None
        ),
        has_physical=any(p is not None and p.product_type == "physical" for p in products),
    )


async def list_issued_invoices(bot_id: uuid.UUID, since: datetime) -> list[dict]:
    """Every invoice issued at/after `since` — one entry per standalone Order
    (not part of a checkout) plus one per Checkout, each already carrying its
    own invoice_number (see fulfill_order/fulfill_checkout). Used by the
    owner-facing "Issued Invoices" list (bot/handlers/tools/shop.py) so the
    shop owner can see who to contact for shipping/logistics. Sorted newest
    first."""
    entries: list[dict] = []

    async with async_session_maker() as session:
        order_rows = list(
            (
                await session.execute(
                    select(Order).where(
                        Order.bot_id == bot_id,
                        Order.checkout_id.is_(None),
                        Order.invoice_number.isnot(None),
                        Order.updated_at >= since,
                    )
                )
            ).scalars()
        )
        checkout_rows = list(
            (
                await session.execute(
                    select(Checkout).where(
                        Checkout.bot_id == bot_id,
                        Checkout.invoice_number.isnot(None),
                        Checkout.updated_at >= since,
                    )
                )
            ).scalars()
        )

    for order in order_rows:
        product = await get_product(order.product_id)
        entries.append(
            {
                "invoice_number": order.invoice_number,
                "date": order.updated_at,
                "total": order_total(order),
                "buyer_telegram_id": order.buyer_telegram_id,
                "phone": order.shipping_phone,
                "address": order.shipping_address,
                "items": [product.name if product else "-"],
            }
        )

    for checkout in checkout_rows:
        checkout_orders = await get_orders_for_checkout(checkout.id)
        names = []
        for o in checkout_orders:
            p = await get_product(o.product_id)
            names.append(p.name if p else "-")
        entries.append(
            {
                "invoice_number": checkout.invoice_number,
                "date": checkout.updated_at,
                "total": checkout_total(checkout),
                "buyer_telegram_id": checkout.buyer_telegram_id,
                "phone": checkout.shipping_phone,
                "address": checkout.shipping_address,
                "items": names,
            }
        )

    entries.sort(key=lambda e: e["date"], reverse=True)
    return entries


async def list_buyer_orders(bot_id: uuid.UUID, buyer_telegram_id: int, limit: int = 10) -> list[dict]:
    """One buyer's own recent orders/checkouts (any status, newest first) —
    used by the "order_status" command action (bot/flow_engine.py) so a
    buyer can check on their own purchase without messaging the owner."""
    entries: list[dict] = []

    async with async_session_maker() as session:
        order_rows = list(
            (
                await session.execute(
                    select(Order)
                    .where(
                        Order.bot_id == bot_id,
                        Order.buyer_telegram_id == buyer_telegram_id,
                        Order.checkout_id.is_(None),
                    )
                    .order_by(Order.created_at.desc())
                    .limit(limit)
                )
            ).scalars()
        )
        checkout_rows = list(
            (
                await session.execute(
                    select(Checkout)
                    .where(
                        Checkout.bot_id == bot_id,
                        Checkout.buyer_telegram_id == buyer_telegram_id,
                    )
                    .order_by(Checkout.created_at.desc())
                    .limit(limit)
                )
            ).scalars()
        )

    for order in order_rows:
        product = await get_product(order.product_id)
        entries.append(
            {
                "date": order.created_at,
                "status": order.status,
                "items": [product.name if product else "-"],
                "total": order_total(order),
                "invoice_number": order.invoice_number,
            }
        )

    for checkout in checkout_rows:
        checkout_orders = await get_orders_for_checkout(checkout.id)
        names = []
        for o in checkout_orders:
            p = await get_product(o.product_id)
            names.append(p.name if p else "-")
        entries.append(
            {
                "date": checkout.created_at,
                "status": checkout.status,
                "items": names,
                "total": checkout_total(checkout),
                "invoice_number": checkout.invoice_number,
            }
        )

    entries.sort(key=lambda e: e["date"], reverse=True)
    return entries[:limit]
