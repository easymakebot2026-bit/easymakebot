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
