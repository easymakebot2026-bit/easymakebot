import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.db.base import Base
from bot.db.encrypted_types import EncryptedJSON, EncryptedString


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)

    # Shared with the platform on /start to localize the how-to-use guide
    # (country guessed from the calling code — see bot/guide.py).
    phone_number: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)

    # "iran" | "international" — which /live payment methods this bot creator
    # sees (bot/platform_billing.py). Auto-derived from phone_number when
    # possible (bot.guide.is_iran_phone), else asked once and remembered here.
    region: Mapped[str | None] = mapped_column(String(20), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    bots: Mapped[list["BuiltBot"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )


class PlatformSettings(Base):
    """Single-row table (id is always 1 — see bot/platform_settings.py) for
    switches that apply to every built bot at once, as opposed to
    BuiltBot.suspended which is per-bot. Read from each built bot's own
    dispatcher (bot/runtime.py:handle_start); written from /easybotadmin
    (bot/handlers/easybotadmin.py, via bot/admin_panel.py)."""

    __tablename__ = "platform_settings"

    id: Mapped[int] = mapped_column(primary_key=True)

    # False = every built bot's /start replies with a localized "under
    # maintenance" message instead of running its normal flow — the process
    # itself keeps running/polling, unlike a per-bot suspend. Meant for a
    # brief, deliberate pause (e.g. a platform deploy), not moderation.
    bots_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class BuiltBot(Base):
    """A bot that a user has built with easymakebot."""

    __tablename__ = "built_bots"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    # The token is the most sensitive data, stored encrypted
    token: Mapped[str] = mapped_column(EncryptedString)

    bot_username: Mapped[str] = mapped_column(String(64))
    display_name: Mapped[str] = mapped_column(String(128))

    # Force-join gate: when enabled, users must join every listed JoinChannel
    # before the built bot will respond to /start (see bot/runtime.py).
    force_join_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )

    # Visual flow builder (Mini App) output: {"nodes": [...], "edges": [...]}.
    # For /start specifically, whichever of this and the legacy Command(name="/start")
    # row was edited more recently wins — see bot/runtime.py:_should_use_flow_for_start.
    # Non-/start trigger commands have no legacy equivalent, so the flow always
    # drives those (see bot/runtime.py:_has_flow_trigger).
    flow_definition: Mapped[dict[str, Any] | None] = mapped_column(EncryptedJSON, nullable=True)
    flow_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # "Go live" gate (bot/live.py): NULL means never activated — still fully
    # editable, just not polling Telegram yet. A future timestamp means
    # currently live (trial or a paid plan). A past timestamp means the live
    # window expired — bot/runtime.py stops its polling task and its
    # owner-side editing tools get gated until a new plan is purchased.
    live_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Platform-admin kill switch (bot/admin_panel.py), deliberately separate
    # from live_until — a suspended bot must stay dead even if its trial/plan
    # is still technically valid, and a future plan purchase must NOT
    # silently revive it; only an explicit admin unsuspend can. Checked
    # ahead of the live/expired check at every gating touchpoint.
    suspended: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    suspension_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)

    # "shop" | "subscription" | None (not chosen yet) — bot/commerce_mode.py.
    # A bot commits to exactly one business model: selling individual
    # products (Shop) or a subscription-gated content archive (Subscription)
    # — never both. Asked once, the first time the owner opens either the
    # Shop or Content List tool, then remembered.
    commerce_mode: Mapped[str | None] = mapped_column(String(20), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    owner: Mapped["User"] = relationship(back_populates="bots")
    commands: Mapped[list["Command"]] = relationship(
        back_populates="bot", cascade="all, delete-orphan"
    )
    join_channels: Mapped[list["JoinChannel"]] = relationship(
        back_populates="bot", cascade="all, delete-orphan"
    )
    content_items: Mapped[list["ContentItem"]] = relationship(
        back_populates="bot", cascade="all, delete-orphan"
    )
    posts: Mapped[list["BotPost"]] = relationship(
        back_populates="bot", cascade="all, delete-orphan"
    )
    products: Mapped[list["Product"]] = relationship(
        back_populates="bot", cascade="all, delete-orphan"
    )
    shop_settings: Mapped["ShopSettings | None"] = relationship(
        back_populates="bot", cascade="all, delete-orphan", uselist=False
    )
    orders: Mapped[list["Order"]] = relationship(
        back_populates="bot", cascade="all, delete-orphan"
    )


class Command(Base):
    """A command (like /start) defined for a built bot."""

    __tablename__ = "commands"

    id: Mapped[int] = mapped_column(primary_key=True)
    bot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("built_bots.id"))
    name: Mapped[str] = mapped_column(String(64))

    # "start" | "custom" | "broadcast" — determines runtime behavior in bot/runtime.py.
    # For "custom", payload["action"] picks what it actually does when triggered
    # (see bot/flow_engine.py:_execute_node) — "message", "content_list", "shop",
    # "order_status", "force_join_gate", or "guide_video". Defined via the chat
    # "Define Command" tool (bot/handlers/tools/define_command.py); a command with
    # the same name can also be defined as a Visual Builder trigger node — see
    # bot/runtime.py:_has_legacy_action for the "whichever was edited more
    # recently wins" tie-break, same idea as _should_use_flow_for_start.
    command_type: Mapped[str] = mapped_column(String(32), default="custom", server_default="custom")

    # "everyone" (default) | "admin" — an "admin" command never appears on
    # Telegram's command menu for regular users and silently refuses to run
    # for anyone but the bot owner (bot/runtime.py:sync_bot_commands /
    # handle_legacy_command), so management-only commands stay invisible and
    # inert for buyers.
    visibility: Mapped[str] = mapped_column(String(10), default="everyone", server_default="everyone")

    # Structured content collected for the command (e.g. the /start wizard answers,
    # or {"action": ..., "text": ...} for a "custom" command's chosen behavior)
    payload: Mapped[dict[str, Any] | None] = mapped_column(EncryptedJSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    bot: Mapped["BuiltBot"] = relationship(back_populates="commands")


class JoinChannel(Base):
    """A channel a built bot's users must join before the bot responds to /start."""

    __tablename__ = "join_channels"

    id: Mapped[int] = mapped_column(primary_key=True)
    bot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("built_bots.id"))
    username: Mapped[str] = mapped_column(String(64))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    bot: Mapped["BuiltBot"] = relationship(back_populates="join_channels")


class ContentItem(Base):
    """One item in a built bot's "Content List" — a generic content primitive
    (title/body/image/link) reusable for news posts, products, lessons, FAQ
    entries, etc. Populated via chat, Excel upload, or (future) a live feed.
    Not encrypted — this is content meant to be shown to end users."""

    __tablename__ = "content_items"
    __table_args__ = (UniqueConstraint("bot_id", "code", name="uq_content_item_bot_code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    bot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("built_bots.id"))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    link_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    # Self-referencing tree for nested grouping. An item with children is
    # shown as a folder (tapping lists the children); one with none is a
    # leaf (tapping shows its own detail) — no separate "is category" flag
    # needed, it's inferred from whether children exist.
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("content_items.id"), nullable=True
    )

    # Set when this item was created as "for sale" from the Content List
    # wizard — the item is still browsed/displayed as normal content, but
    # also shows a price + Buy button wired into the same order/payment
    # pipeline as a standalone Product (bot/shop.py). SET NULL on delete so
    # removing the Product doesn't block deleting/keeping this content item.
    product_id: Mapped[int | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"), nullable=True
    )

    # Optional owner-chosen shortcut (e.g. "101" or "buy") — a subscriber can
    # type this directly (no menu navigation) to jump straight to this item,
    # for the common case of an Instagram post saying "send CODE to our bot".
    # Unique per bot (bot_id, code) — NOT globally, so two different owners'
    # bots can freely reuse the same code with zero risk of collision, since
    # every lookup is already scoped to bot_id like everything else here.
    code: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Requires an active subscription (BotSubscriber.subscription_until) or a
    # spent free-preview slot (ContentUnlock) to view — see bot/premium_content.py.
    # Independent of product_id above: an item can be individually purchasable,
    # subscription-gated, both, or neither.
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    # Subscription-mode à-la-carte: a non-subscriber who's out of free previews
    # can pay this (Toman) to unlock just this one item forever. None = fall
    # back to ShopSettings.default_unlock_price; if that's also None, no
    # single-item purchase is offered. Backed by a hidden Product
    # (product_type="content_unlock") created on demand — see bot/shop.py.
    unlock_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Set only while a price campaign is running (bot/db/models.py:PriceCampaign):
    # the pre-campaign unlock_price, restored verbatim when the campaign ends.
    original_unlock_price: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    bot: Mapped["BuiltBot"] = relationship(back_populates="content_items")


class ContentUnlock(Base):
    """One row = this subscriber permanently unlocked this specific premium
    ContentItem via their free-preview quota (bot/premium_content.py).
    Active-subscription access is NOT tracked here — it's always re-checked
    live against BotSubscriber.subscription_until, so it can lapse; a
    free-quota unlock never does (re-opening an already-unlocked item must
    never re-spend a quota slot)."""

    __tablename__ = "content_unlocks"
    __table_args__ = (
        UniqueConstraint("bot_id", "subscriber_telegram_id", "content_item_id", name="uq_content_unlock"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    bot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("built_bots.id"))
    subscriber_telegram_id: Mapped[int] = mapped_column(BigInteger)
    content_item_id: Mapped[int] = mapped_column(ForeignKey("content_items.id"))

    # "quota" = spent a free-preview slot; "purchase" = paid the à-la-carte
    # unlock price. Only "quota" rows count against ShopSettings.free_preview_limit
    # (bot/premium_content.py); both grant permanent access to their item.
    source: Mapped[str] = mapped_column(String(20), default="quota", server_default="quota")

    unlocked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class BotSubscriber(Base):
    """A Telegram user who has started a specific built bot (used as the audience for broadcasts)."""

    __tablename__ = "bot_subscribers"
    __table_args__ = (UniqueConstraint("bot_id", "telegram_id", name="uq_bot_subscriber"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    bot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("built_bots.id"))
    telegram_id: Mapped[int] = mapped_column(BigInteger)

    # Shared on request from within the "Guide & Video" flow block, to
    # localize that guide the same way as the platform's own onboarding.
    phone_number: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)

    # Set by an "access"-type Product purchase (see Product.product_type in
    # bot/shop.py) — e.g. "VIP". Not otherwise gated on by this codebase yet;
    # future flow blocks can branch on it.
    access_level: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Set/extended by a "subscription"-type Product purchase — unlike
    # access_level above, this is TIME-LIMITED and always re-checked live
    # (bot/premium_content.py:has_active_subscription) rather than a
    # permanent grant. None = never subscribed / subscription lapsed.
    subscription_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class BotPost(Base):
    """A social-media-style post (photo/video + caption) added from the
    Content List tool's "Add Post" option, for owners who'd rather post
    updates through the bot than run a separate Telegram channel. Pushed to
    every current BotSubscriber at creation time (bot/handlers/tools/content_list.py);
    liked/commented on by end users at runtime (bot/runtime.py). Not
    encrypted — this is content meant to be shown to end users.

    media_file_id is valid for THIS bot's own token, not the builder bot's —
    it's captured from the first send made *through* the owner's built bot
    (a temp Bot(token=built_bot.token) instance), not from the file_id the
    owner's upload arrived with in the builder chat (Telegram file_ids don't
    carry across bots)."""

    __tablename__ = "bot_posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    bot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("built_bots.id"))
    media_type: Mapped[str] = mapped_column(String(10))  # "photo" | "video"
    media_file_id: Mapped[str] = mapped_column(String(300))
    caption: Mapped[str] = mapped_column(Text)

    # Denormalized so rendering the Like/Comment buttons never needs a COUNT
    # query — kept in sync in the same transaction as each PostLike/PostComment insert/delete.
    like_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    comment_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    bot: Mapped["BuiltBot"] = relationship(back_populates="posts")
    likes: Mapped[list["PostLike"]] = relationship(back_populates="post", cascade="all, delete-orphan")
    comments: Mapped[list["PostComment"]] = relationship(back_populates="post", cascade="all, delete-orphan")


class PostLike(Base):
    """One row = this Telegram user liked this post. Unique per (post, user)
    so tapping 👍 again toggles the like off instead of double-counting."""

    __tablename__ = "post_likes"
    __table_args__ = (UniqueConstraint("post_id", "liker_telegram_id", name="uq_post_like"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("bot_posts.id"))
    liker_telegram_id: Mapped[int] = mapped_column(BigInteger)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    post: Mapped["BotPost"] = relationship(back_populates="likes")


class PostComment(Base):
    """A text comment left on a post. Many per user is fine — no uniqueness
    constraint. The bot owner is notified live when one comes in (bot/runtime.py)."""

    __tablename__ = "post_comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("bot_posts.id"))
    commenter_telegram_id: Mapped[int] = mapped_column(BigInteger)
    text: Mapped[str] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    post: Mapped["BotPost"] = relationship(back_populates="comments")


class Product(Base):
    """Something a built bot's owner sells through the "Shop" tool/flow block."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    bot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("built_bots.id"))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    price: Mapped[int] = mapped_column(Integer)  # Toman
    # Set only while a price campaign is running (PriceCampaign below): the
    # pre-campaign price, restored verbatim when the campaign ends. NULL the
    # rest of the time. Customer-facing views show it struck-through next to
    # the discounted price (bot/pricing.py).
    original_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # "physical" (ships — collects shipping info after payment),
    # "digital" (delivers delivery_text/delivery_file_url after payment), or
    # "access" (sets BotSubscriber.access_level to access_level_name), or
    # "subscription" (extends BotSubscriber.subscription_until by
    # subscription_days), or
    # "content_unlock" (hidden — grants permanent access to one premium
    # ContentItem; delivery_file_url mirrors that item's link_url; never
    # shown in the owner's product list — see bot/shop.py:fulfill_order /
    # ensure_unlock_product).
    product_type: Mapped[str] = mapped_column(String(20), default="digital", server_default="digital")

    delivery_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivery_file_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    access_level_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    subscription_days: Mapped[int | None] = mapped_column(Integer, nullable=True)  # required for "subscription"

    # Inventory (bot/inventory.py). NULL = not tracked (unlimited, e.g. most
    # digital/access/subscription products) — same graceful-omit pattern as
    # everything else here. Only meaningful for product_type in practice
    # ("physical" mainly), but not enforced at the DB level so an owner can
    # track stock on any type. Decremented atomically on each paid order;
    # a row at 0 is skipped in the buyer-facing list ("out of stock").
    stock_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Owner's own cost per unit (Toman), for profit reporting only
    # (bot/inventory.py) — never shown to buyers. NULL = unknown, in which
    # case profit just isn't computed for this product.
    cost_price: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Set when this row was upserted by the bulk "Import as Products" tool
    # (bot/shop_import.py) via a spreadsheet's Code column — lets re-uploading
    # the same file update these rows in place instead of duplicating them.
    # NULL for products created by hand or by the old Content List importer.
    import_code: Mapped[str | None] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    bot: Mapped["BuiltBot"] = relationship(back_populates="products")


class ShopSettings(Base):
    """One row per bot: how buyers can pay. Either/both may be unset, in
    which case that payment method simply isn't offered (see bot/shop.py)."""

    __tablename__ = "shop_settings"

    bot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("built_bots.id"), primary_key=True)
    zarinpal_merchant_id: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    card_number: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    card_holder_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # International equivalent of Zarinpal — Stripe Checkout, priced in USD
    # (Product.price is treated as whole US dollars on this path, vs Toman on
    # the Zarinpal path). Same graceful-omit pattern: unset = not offered.
    stripe_secret_key: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)

    # Crypto/TON: same manual "buyer sends, submits a tx ref, owner approves"
    # flow as card_number above (bot/shop.py:submit_manual_payment) — no
    # on-chain verification, deliberately, since a wrong automatic check
    # risks real money either way (falsely confirming or blocking a payment).
    crypto_wallet_address: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    crypto_network_label: Mapped[str | None] = mapped_column(String(100), nullable=True)  # e.g. "USDT (TRC20)"
    ton_wallet_address: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)

    # How many premium content items (bot/premium_content.py) a subscriber
    # can unlock for free before a subscription is required.
    free_preview_limit: Mapped[int] = mapped_column(Integer, default=1, server_default="1")

    # Default à-la-carte price (Toman) for a single premium item, used when
    # ContentItem.unlock_price is NULL. NULL here too = no single-item
    # purchase offered anywhere. See bot/premium_content.py:effective_unlock_price.
    default_unlock_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Pre-campaign value, restored when a price campaign ends (PriceCampaign).
    original_default_unlock_price: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Invoice branding (bot/shop.py:generate_invoice) — all optional, graceful
    # fallback to the plain "easymakebot" default when unset. Not encrypted:
    # this is meant to be printed on a document handed to the buyer.
    invoice_business_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    invoice_logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    invoice_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    invoice_footer_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Business phone, printed in the invoice footer alongside the address.
    invoice_business_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # Shop stamp/signature image, drawn inside the signature box at the
    # bottom of the invoice (bot/shop.py:_render_invoice_pdf) — same
    # best-effort fetch-by-URL as invoice_logo_url above.
    invoice_signature_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # 10% Iranian VAT (مالیات بر ارزش‌افزوده) — off by default. When on,
    # every new Order/Checkout snapshots the computed amount onto its own
    # tax_amount column at creation time (see bot/shop.py:_compute_tax), so
    # flipping this later never changes an invoice already issued or a
    # payment already in flight.
    tax_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    bot: Mapped["BuiltBot"] = relationship(back_populates="shop_settings")


class PriceCampaign(Base):
    """A time-boxed, bot-wide price change (a sale, or a temporary markup).
    While one is `active`, every Product.price / ContentItem.unlock_price /
    ShopSettings.default_unlock_price for the bot is overwritten with the
    adjusted value, and the pre-campaign value is stashed in the matching
    `original_*` column. When `ends_at` passes (checked by
    bot/runtime.py:run_campaign_expiry_loop) — or the owner ends it early —
    every `original_*` is restored verbatim and status becomes `ended`.
    At most one `active` row per bot (enforced in code by
    bot/shop.py:start_price_campaign, plus a partial unique index added in
    bot/db/base.py)."""

    __tablename__ = "price_campaigns"

    id: Mapped[int] = mapped_column(primary_key=True)
    bot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("built_bots.id"))
    direction: Mapped[str] = mapped_column(String(10))  # "discount" | "markup"
    percent: Mapped[int] = mapped_column(Integer)  # 1..90 for discount, 1..500 for markup
    status: Mapped[str] = mapped_column(String(10), default="active", server_default="active")  # "active" | "ended"

    starts_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Order(Base):
    """One purchase attempt — pending until payment is confirmed (Zarinpal
    verify, or the owner approving a card-to-card submission), then
    fulfilled per Product.product_type (see bot/shop.py:fulfill_order)."""

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    bot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("built_bots.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    buyer_telegram_id: Mapped[int] = mapped_column(BigInteger)

    price: Mapped[int] = mapped_column(Integer)  # snapshot of Product.price at purchase time
    # 10% VAT snapshot (bot/shop.py:_compute_tax), 0/NULL when the bot's tax
    # isn't enabled. The amount actually charged/shown to the buyer is always
    # price + tax_amount — see bot/shop.py:order_total.
    tax_amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payment_method: Mapped[str | None] = mapped_column(String(20), nullable=True)  # "zarinpal" | "card_to_card" | "stripe"

    # "pending" -> "paid" -> "fulfilled", or "rejected" (card-to-card only)
    status: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending")

    zarinpal_authority: Mapped[str | None] = mapped_column(String(64), nullable=True)
    zarinpal_ref_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    transaction_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)
    stripe_session_id: Mapped[str | None] = mapped_column(String(200), nullable=True)

    shipping_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    shipping_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    shipping_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    shipping_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    shipping_postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)

    invoice_number: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # Set only for an order created via the cart's "Checkout" step (bot/shop.py:
    # create_checkout) — None for every direct "🛒 Buy" purchase. Several
    # orders sharing one checkout_id were paid for together in one payment,
    # but each still fulfills independently per its own product_type.
    checkout_id: Mapped[int | None] = mapped_column(ForeignKey("checkouts.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    bot: Mapped["BuiltBot"] = relationship(back_populates="orders")
    product: Mapped["Product"] = relationship()


class CartItem(Base):
    """One product a buyer has added to their (per-bot) cart, before
    checking out — see bot/shop.py: add_to_cart/create_checkout."""

    __tablename__ = "cart_items"
    __table_args__ = (
        UniqueConstraint("bot_id", "buyer_telegram_id", "product_id", name="uq_cart_item"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    bot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("built_bots.id"))
    buyer_telegram_id: Mapped[int] = mapped_column(BigInteger)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Checkout(Base):
    """One payment covering several Orders at once (the cart's "pay for
    everything" step) — mirrors Order's own payment-tracking fields above.
    No "fulfilled" status here: once paid, each linked Order fulfills
    independently per its own product_type, exactly like a direct purchase."""

    __tablename__ = "checkouts"

    id: Mapped[int] = mapped_column(primary_key=True)
    bot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("built_bots.id"))
    buyer_telegram_id: Mapped[int] = mapped_column(BigInteger)
    total_price: Mapped[int] = mapped_column(Integer)  # sum of the snapshotted Order prices
    # 10% VAT snapshot on the checkout's subtotal (bot/shop.py:_compute_tax) —
    # see Order.tax_amount above for why this is snapshotted, not recomputed.
    tax_amount: Mapped[int | None] = mapped_column(Integer, nullable=True)

    payment_method: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending")

    zarinpal_authority: Mapped[str | None] = mapped_column(String(64), nullable=True)
    zarinpal_ref_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    stripe_session_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    transaction_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Collected once for the whole checkout (bot/runtime.py's shipc_info:
    # wizard) so a multi-item physical order gets ONE combined invoice
    # instead of one per item — copied onto each linked physical Order too
    # (bot/shop.py:fulfill_checkout) so existing per-order reads keep working.
    shipping_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    shipping_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    shipping_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    shipping_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    shipping_postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)

    invoice_number: Mapped[str | None] = mapped_column(String(30), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class LivePayment(Base):
    """A bot owner paying THE PLATFORM to activate/extend their bot's live
    window (bot/platform_billing.py) — deliberately separate from Order/
    Checkout above, which track a bot's OWN customers buying from its shop.
    Same payment-tracking shape as those, different money flow entirely."""

    __tablename__ = "live_payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    bot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("built_bots.id"))
    plan_key: Mapped[str] = mapped_column(String(50))
    days: Mapped[int | None] = mapped_column(Integer, nullable=True)  # None = permanent
    price: Mapped[int] = mapped_column(Integer)  # snapshot at purchase time
    currency: Mapped[str] = mapped_column(String(10))  # "toman" | "usd"

    payment_method: Mapped[str] = mapped_column(String(20))  # "zarinpal" | "stripe" | "ton"
    status: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending")

    zarinpal_authority: Mapped[str | None] = mapped_column(String(64), nullable=True)
    zarinpal_ref_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    stripe_session_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    transaction_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class BroadcastLog(Base):
    """A record of a group message sent from a built bot's owner to that bot's subscribers."""

    __tablename__ = "broadcast_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    bot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("built_bots.id"))
    command_name: Mapped[str] = mapped_column(String(64))
    text: Mapped[str] = mapped_column(EncryptedString)
    recipient_count: Mapped[int] = mapped_column(Integer, default=0)

    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
