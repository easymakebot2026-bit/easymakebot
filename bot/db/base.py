from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from bot.config import load_config

_config = load_config()

engine = create_async_engine(_config.database_url, echo=False)
async_session_maker = async_sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)


class Base(DeclarativeBase):
    pass


async def init_db() -> None:
    """Creates the tables if they don't exist yet (fine for now, will be replaced with alembic later)."""
    from bot.db import models  # noqa: F401  ensures models are registered on Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # create_all doesn't alter existing tables — patch in columns added after
        # a table already existed in a dev database (no alembic wired up yet).
        await conn.execute(
            text(
                "ALTER TABLE commands ADD COLUMN IF NOT EXISTS "
                "command_type VARCHAR(32) NOT NULL DEFAULT 'custom'"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE built_bots ADD COLUMN IF NOT EXISTS "
                "force_join_enabled BOOLEAN NOT NULL DEFAULT false"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE built_bots ADD COLUMN IF NOT EXISTS "
                "flow_definition BYTEA"
            )
        )
        await conn.execute(
            text("ALTER TABLE users ADD COLUMN IF NOT EXISTS phone_number BYTEA")
        )
        await conn.execute(
            text("ALTER TABLE bot_subscribers ADD COLUMN IF NOT EXISTS phone_number BYTEA")
        )
        await conn.execute(
            text(
                "ALTER TABLE built_bots ADD COLUMN IF NOT EXISTS "
                "flow_updated_at TIMESTAMPTZ"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE content_items ADD COLUMN IF NOT EXISTS "
                "parent_id INTEGER REFERENCES content_items(id)"
            )
        )
        await conn.execute(
            text("ALTER TABLE bot_subscribers ADD COLUMN IF NOT EXISTS access_level VARCHAR(100)")
        )
        await conn.execute(
            text(
                "ALTER TABLE content_items ADD COLUMN IF NOT EXISTS "
                "product_id INTEGER REFERENCES products(id) ON DELETE SET NULL"
            )
        )
        await conn.execute(
            text("ALTER TABLE shop_settings ADD COLUMN IF NOT EXISTS stripe_secret_key BYTEA")
        )
        await conn.execute(
            text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS stripe_session_id VARCHAR(200)")
        )
        await conn.execute(
            text("ALTER TABLE shop_settings ADD COLUMN IF NOT EXISTS crypto_wallet_address BYTEA")
        )
        await conn.execute(
            text(
                "ALTER TABLE shop_settings ADD COLUMN IF NOT EXISTS "
                "crypto_network_label VARCHAR(100)"
            )
        )
        await conn.execute(
            text("ALTER TABLE shop_settings ADD COLUMN IF NOT EXISTS ton_wallet_address BYTEA")
        )
        await conn.execute(
            text("ALTER TABLE built_bots ADD COLUMN IF NOT EXISTS live_until TIMESTAMPTZ")
        )
        await conn.execute(
            text("ALTER TABLE content_items ADD COLUMN IF NOT EXISTS code VARCHAR(50)")
        )
        await conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_content_item_bot_code "
                "ON content_items (bot_id, code)"
            )
        )
        # checkouts/cart_items are new tables, created by create_all above —
        # this only patches the new FK column onto the pre-existing orders table.
        await conn.execute(
            text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS checkout_id INTEGER REFERENCES checkouts(id)")
        )
        await conn.execute(
            text("ALTER TABLE built_bots ADD COLUMN IF NOT EXISTS suspended BOOLEAN NOT NULL DEFAULT false")
        )
        await conn.execute(
            text("ALTER TABLE built_bots ADD COLUMN IF NOT EXISTS suspension_reason VARCHAR(300)")
        )
        # live_payments is a new table, created by create_all above.
        await conn.execute(
            text("ALTER TABLE users ADD COLUMN IF NOT EXISTS region VARCHAR(20)")
        )
        # content_unlocks is a new table, created by create_all above — these
        # only patch new columns onto pre-existing tables.
        await conn.execute(
            text("ALTER TABLE products ADD COLUMN IF NOT EXISTS subscription_days INTEGER")
        )
        await conn.execute(
            text("ALTER TABLE bot_subscribers ADD COLUMN IF NOT EXISTS subscription_until TIMESTAMPTZ")
        )
        await conn.execute(
            text("ALTER TABLE content_items ADD COLUMN IF NOT EXISTS is_premium BOOLEAN NOT NULL DEFAULT false")
        )
        await conn.execute(
            text(
                "ALTER TABLE shop_settings ADD COLUMN IF NOT EXISTS "
                "free_preview_limit INTEGER NOT NULL DEFAULT 1"
            )
        )
        await conn.execute(
            text("ALTER TABLE built_bots ADD COLUMN IF NOT EXISTS commerce_mode VARCHAR(20)")
        )
        # À-la-carte single-item unlock (subscription mode) + time-boxed price
        # campaigns. price_campaigns is a new table (create_all above); these
        # patch new columns onto pre-existing tables.
        await conn.execute(
            text("ALTER TABLE content_items ADD COLUMN IF NOT EXISTS unlock_price INTEGER")
        )
        await conn.execute(
            text("ALTER TABLE content_items ADD COLUMN IF NOT EXISTS original_unlock_price INTEGER")
        )
        await conn.execute(
            text("ALTER TABLE content_unlocks ADD COLUMN IF NOT EXISTS "
                 "source VARCHAR(20) NOT NULL DEFAULT 'quota'")
        )
        await conn.execute(
            text("ALTER TABLE products ADD COLUMN IF NOT EXISTS original_price INTEGER")
        )
        await conn.execute(
            text("ALTER TABLE shop_settings ADD COLUMN IF NOT EXISTS default_unlock_price INTEGER")
        )
        await conn.execute(
            text("ALTER TABLE shop_settings ADD COLUMN IF NOT EXISTS "
                 "original_default_unlock_price INTEGER")
        )
        # At most one running campaign per bot.
        await conn.execute(
            text("CREATE UNIQUE INDEX IF NOT EXISTS uq_price_campaign_active "
                 "ON price_campaigns (bot_id) WHERE status = 'active'")
        )
        # Inventory (stock/cost) + bulk-import upsert key + invoice branding.
        await conn.execute(
            text("ALTER TABLE products ADD COLUMN IF NOT EXISTS stock_quantity INTEGER")
        )
        await conn.execute(
            text("ALTER TABLE products ADD COLUMN IF NOT EXISTS cost_price INTEGER")
        )
        await conn.execute(
            text("ALTER TABLE products ADD COLUMN IF NOT EXISTS import_code VARCHAR(50)")
        )
        await conn.execute(
            text("ALTER TABLE shop_settings ADD COLUMN IF NOT EXISTS invoice_business_name VARCHAR(200)")
        )
        await conn.execute(
            text("ALTER TABLE shop_settings ADD COLUMN IF NOT EXISTS invoice_logo_url VARCHAR(500)")
        )
        await conn.execute(
            text("ALTER TABLE shop_settings ADD COLUMN IF NOT EXISTS invoice_address TEXT")
        )
        await conn.execute(
            text("ALTER TABLE shop_settings ADD COLUMN IF NOT EXISTS invoice_footer_note TEXT")
        )
        # (bot_id, import_code) isn't globally unique — two owners' bots can
        # reuse the same code — same reasoning as uq_content_item_bot_code.
        await conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_product_bot_import_code "
                "ON products (bot_id, import_code) WHERE import_code IS NOT NULL"
            )
        )
        # 10% VAT + combined checkout invoices + postal code + signature/stamp
        # image (see bot/shop.py: _compute_tax, fulfill_checkout,
        # _render_invoice_pdf).
        await conn.execute(
            text("ALTER TABLE shop_settings ADD COLUMN IF NOT EXISTS "
                 "tax_enabled BOOLEAN NOT NULL DEFAULT false")
        )
        await conn.execute(
            text("ALTER TABLE shop_settings ADD COLUMN IF NOT EXISTS "
                 "invoice_business_phone VARCHAR(30)")
        )
        await conn.execute(
            text("ALTER TABLE shop_settings ADD COLUMN IF NOT EXISTS "
                 "invoice_signature_url VARCHAR(500)")
        )
        await conn.execute(
            text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS tax_amount INTEGER")
        )
        await conn.execute(
            text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS shipping_postal_code VARCHAR(20)")
        )
        await conn.execute(
            text("ALTER TABLE checkouts ADD COLUMN IF NOT EXISTS tax_amount INTEGER")
        )
        await conn.execute(
            text("ALTER TABLE checkouts ADD COLUMN IF NOT EXISTS shipping_method VARCHAR(50)")
        )
        await conn.execute(
            text("ALTER TABLE checkouts ADD COLUMN IF NOT EXISTS shipping_name VARCHAR(200)")
        )
        await conn.execute(
            text("ALTER TABLE checkouts ADD COLUMN IF NOT EXISTS shipping_phone VARCHAR(30)")
        )
        await conn.execute(
            text("ALTER TABLE checkouts ADD COLUMN IF NOT EXISTS shipping_address TEXT")
        )
        await conn.execute(
            text("ALTER TABLE checkouts ADD COLUMN IF NOT EXISTS shipping_postal_code VARCHAR(20)")
        )
        await conn.execute(
            text("ALTER TABLE checkouts ADD COLUMN IF NOT EXISTS invoice_number VARCHAR(30)")
        )
        # Command actions (bot/flow_engine.py:_execute_node) + admin-only
        # command visibility.
        await conn.execute(
            text("ALTER TABLE commands ADD COLUMN IF NOT EXISTS "
                 "visibility VARCHAR(10) NOT NULL DEFAULT 'everyone'")
        )
        # Alternate digital delivery: a pre-loaded single-use item pool, or a
        # live API call, per Product — see bot/db/models.py:Product,
        # ProductDeliveryItem and bot/shop.py:fulfill_order.
        await conn.execute(
            text("ALTER TABLE products ADD COLUMN IF NOT EXISTS "
                 "delivery_mode VARCHAR(20) NOT NULL DEFAULT 'static'")
        )
        await conn.execute(
            text("ALTER TABLE products ADD COLUMN IF NOT EXISTS delivery_api_url VARCHAR(500)")
        )
        await conn.execute(
            text("ALTER TABLE products ADD COLUMN IF NOT EXISTS delivery_api_method VARCHAR(10)")
        )
        await conn.execute(
            text("ALTER TABLE products ADD COLUMN IF NOT EXISTS delivery_api_headers BYTEA")
        )
        await conn.execute(
            text("ALTER TABLE products ADD COLUMN IF NOT EXISTS delivery_api_body_template TEXT")
        )
        await conn.execute(
            text("ALTER TABLE products ADD COLUMN IF NOT EXISTS delivery_api_response_path VARCHAR(200)")
        )
        await conn.execute(
            text("ALTER TABLE products ADD COLUMN IF NOT EXISTS delivery_api_extra_vars BYTEA")
        )
        await conn.execute(
            text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS fulfillment_error TEXT")
        )
        # product_delivery_items is a new table, created by create_all above —
        # this only adds the lookup index fulfillment queries rely on.
        await conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_product_delivery_items_product_status "
                "ON product_delivery_items (product_id, status)"
            )
        )
        # One-time-per-person free trial (bot/live.py, bot/db/models.py:User).
        await conn.execute(
            text("ALTER TABLE users ADD COLUMN IF NOT EXISTS trial_used BOOLEAN NOT NULL DEFAULT false")
        )
        # Free-trial quota (bot/live.py): per-owner trial counter and what
        # opened each bot's live window.
        await conn.execute(
            text("ALTER TABLE users ADD COLUMN IF NOT EXISTS trial_count INTEGER NOT NULL DEFAULT 0")
        )
        await conn.execute(
            text("ALTER TABLE built_bots ADD COLUMN IF NOT EXISTS live_kind VARCHAR(10)")
        )
        # Postgres doesn't auto-index foreign keys. These back the per-bot /
        # per-owner scoped queries that run on every incoming message or
        # dashboard view (bot/runtime.py's command lookup on every update is
        # the hottest of these) — added late because the tables were small
        # enough not to notice the missing index until now.
        for _index_sql in (
            "CREATE INDEX IF NOT EXISTS ix_commands_bot_id ON commands (bot_id)",
            "CREATE INDEX IF NOT EXISTS ix_join_channels_bot_id ON join_channels (bot_id)",
            "CREATE INDEX IF NOT EXISTS ix_content_items_bot_id ON content_items (bot_id)",
            "CREATE INDEX IF NOT EXISTS ix_content_unlocks_bot_id ON content_unlocks (bot_id)",
            "CREATE INDEX IF NOT EXISTS ix_bot_subscribers_bot_id ON bot_subscribers (bot_id)",
            "CREATE INDEX IF NOT EXISTS ix_bot_posts_bot_id ON bot_posts (bot_id)",
            "CREATE INDEX IF NOT EXISTS ix_products_bot_id ON products (bot_id)",
            "CREATE INDEX IF NOT EXISTS ix_price_campaigns_bot_id ON price_campaigns (bot_id)",
            "CREATE INDEX IF NOT EXISTS ix_orders_bot_id ON orders (bot_id)",
            "CREATE INDEX IF NOT EXISTS ix_orders_product_id ON orders (product_id)",
            "CREATE INDEX IF NOT EXISTS ix_orders_buyer_telegram_id ON orders (buyer_telegram_id)",
            "CREATE INDEX IF NOT EXISTS ix_cart_items_bot_id ON cart_items (bot_id)",
            "CREATE INDEX IF NOT EXISTS ix_checkouts_bot_id ON checkouts (bot_id)",
            "CREATE INDEX IF NOT EXISTS ix_live_payments_bot_id ON live_payments (bot_id)",
            "CREATE INDEX IF NOT EXISTS ix_broadcast_logs_bot_id ON broadcast_logs (bot_id)",
            "CREATE INDEX IF NOT EXISTS ix_built_bots_owner_id ON built_bots (owner_id)",
        ):
            await conn.execute(text(_index_sql))

        # UI/UX pass (bot/db/models.py: BotSubscriber.muted, Product.category,
        # CartItem.quantity) — see each column's docstring there.
        await conn.execute(
            text("ALTER TABLE bot_subscribers ADD COLUMN IF NOT EXISTS muted BOOLEAN NOT NULL DEFAULT false")
        )
        await conn.execute(
            text("ALTER TABLE products ADD COLUMN IF NOT EXISTS category VARCHAR(100)")
        )
        await conn.execute(
            text("ALTER TABLE cart_items ADD COLUMN IF NOT EXISTS quantity INTEGER NOT NULL DEFAULT 1")
        )

        # Per-bot toggle for the buyer-facing "My Account" screen (bot/shop.py:
        # get_account_summary, bot/runtime.py's /account handler) — off by
        # default, each bot owner turns it on for their own bot from the Shop
        # tool's main menu (bot/handlers/tools/shop.py:toggle_my_account).
        await conn.execute(
            text("ALTER TABLE shop_settings ADD COLUMN IF NOT EXISTS "
                 "my_account_enabled BOOLEAN NOT NULL DEFAULT false")
        )

        # Website identity verification cache (bot/db/models.py:User.site_verified/
        # site_email) — gates /live's Zarinpal/TON plan payments, see
        # bot/handlers/live.py:_ensure_site_verified.
        await conn.execute(
            text("ALTER TABLE users ADD COLUMN IF NOT EXISTS "
                 "site_verified BOOLEAN NOT NULL DEFAULT false")
        )
        await conn.execute(
            text("ALTER TABLE users ADD COLUMN IF NOT EXISTS site_email BYTEA")
        )

        # Same cache, for a BUILT bot's own end customers — flow-builder
        # "verify_gate" node (bot/flow_engine.py, bot/db/models.py:
        # BotSubscriber.site_verified/site_email).
        await conn.execute(
            text("ALTER TABLE bot_subscribers ADD COLUMN IF NOT EXISTS "
                 "site_verified BOOLEAN NOT NULL DEFAULT false")
        )
        await conn.execute(
            text("ALTER TABLE bot_subscribers ADD COLUMN IF NOT EXISTS site_email BYTEA")
        )

        # Bug-fix pass: duplicate-bot guard, archived (soft-deleted) products,
        # stock reserved at payment time, and a Toman->USD rate for Stripe —
        # see each column's docstring in bot/db/models.py.
        await conn.execute(
            text("ALTER TABLE built_bots ADD COLUMN IF NOT EXISTS telegram_bot_id BIGINT")
        )
        await conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_built_bots_telegram_bot_id ON built_bots (telegram_bot_id)")
        )
        await conn.execute(
            text("ALTER TABLE products ADD COLUMN IF NOT EXISTS archived BOOLEAN NOT NULL DEFAULT false")
        )
        await conn.execute(
            text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS stock_reserved BOOLEAN NOT NULL DEFAULT false")
        )
        await conn.execute(
            text("ALTER TABLE shop_settings ADD COLUMN IF NOT EXISTS stripe_toman_per_usd INTEGER")
        )

    await _backfill_telegram_bot_ids()


async def _backfill_telegram_bot_ids() -> None:
    """Fills built_bots.telegram_bot_id for rows created before that column
    existed. The token is encrypted (random IV), so this can't be done in
    SQL — it's decrypted row by row here. Cheap: only rows still NULL."""
    from sqlalchemy import select

    from bot.db.models import BuiltBot

    async with async_session_maker() as session:
        result = await session.execute(select(BuiltBot).where(BuiltBot.telegram_bot_id.is_(None)))
        rows = list(result.scalars())
        for row in rows:
            row.telegram_bot_id = telegram_bot_id_from_token(row.token)
        if rows:
            await session.commit()


def telegram_bot_id_from_token(token: str | None) -> int | None:
    """The numeric bot id Telegram embeds before the ":" in every bot token."""
    head = (token or "").split(":", 1)[0].strip()
    return int(head) if head.isdigit() else None
