"""Per-node settings, read from the environment (.env).

One codebase, deployed once per *node*. A node is one server + database
serving the people who live on its side of a network border:

    NODE_ID=ir      Bale bot (+ domestic SMS, + Zarinpal)  — server inside Iran
    NODE_ID=global  Telegram bot (+ TON)                    — server abroad

A single node with every channel it can reach is also a complete deployment
(families who all live outside Iran never need the `ir` node). Anything left
unset is simply not offered — same graceful-omit rule as bot/config.py.
"""

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _peers(raw: str) -> dict[str, str]:
    """'ir=https://ir.example.com,global=https://app.example.com'"""
    peers = {}
    for part in (raw or "").split(","):
        if "=" in part:
            key, url = part.split("=", 1)
            if key.strip() and url.strip():
                peers[key.strip().lower()] = url.strip().rstrip("/")
    return peers


def _labels(raw: str) -> dict[str, dict[str, str]]:
    """'ir=Iran|ایران,global=Outside Iran|خارج از ایران' -> {node: {en, fa}}"""
    labels = {}
    for part in (raw or "").split(","):
        if "=" in part:
            key, names = part.split("=", 1)
            en, _, fa = names.partition("|")
            labels[key.strip().lower()] = {"en": en.strip(), "fa": (fa or en).strip()}
    return labels


@dataclass
class NodeConfig:
    node_id: str
    database_url: str
    public_url: str = ""
    port: int = 8090
    # Other nodes and the shared HMAC secret every node signs requests with.
    peers: dict[str, str] = field(default_factory=dict)
    peer_key: str = ""
    # Human names for every node (including this one) — shown when a family
    # member says where their parent lives.
    node_labels: dict[str, dict[str, str]] = field(default_factory=dict)
    # Messaging channels this node runs. Bale speaks the Telegram Bot API, so
    # both are driven by aiogram; only the API base URL differs.
    telegram_token: str | None = None
    bale_token: str | None = None
    bale_api_base: str = "https://tapi.bale.ai"
    # Channel used to talk to elders whose home is this node.
    elder_channel: str = "telegram"
    # Kavenegar (domestic Iranian SMS) — outbound only: reminder fallback for
    # elders and alerts to local contacts, which keep working when the
    # international internet is cut.
    sms_api_key: str | None = None
    sms_sender: str | None = None
    # Admin who approves manual (TON) payments, on one of this node's channels.
    admin_channel: str = "telegram"
    admin_chat_id: str | None = None
    # Payment methods are decided by where the PAYER is, i.e. which node
    # their chat lives on: Zarinpal on the Iran node, TON abroad.
    zarinpal_merchant_id: str | None = None
    ton_wallet: str | None = None
    price_usd_month: int = 12
    price_toman_month: int = 990_000
    trial_days: int = 7
    default_tz: str = "UTC"

    def label(self, node_id: str, lang: str) -> str:
        names = self.node_labels.get(node_id) or {}
        return names.get(lang) or names.get("en") or node_id

    @property
    def all_nodes(self) -> list[str]:
        return [self.node_id] + [p for p in self.peers if p != self.node_id]


def load_config() -> NodeConfig:
    node_id = (os.getenv("NODE_ID") or "global").strip().lower()
    database_url = os.getenv("DATABASE_URL") or ""
    if not database_url:
        raise ValueError("DATABASE_URL is not set (e.g. postgresql+asyncpg://user:pass@host/hamdam).")

    cfg = NodeConfig(
        node_id=node_id,
        database_url=database_url,
        public_url=(os.getenv("PUBLIC_URL") or "").rstrip("/"),
        port=int(os.getenv("PORT", "8090")),
        peers=_peers(os.getenv("PEERS", "")),
        peer_key=os.getenv("PEER_KEY") or "",
        node_labels=_labels(os.getenv("NODE_LABELS", "")),
        telegram_token=os.getenv("TELEGRAM_BOT_TOKEN") or None,
        bale_token=os.getenv("BALE_BOT_TOKEN") or None,
        bale_api_base=(os.getenv("BALE_API_BASE") or "https://tapi.bale.ai").rstrip("/"),
        sms_api_key=os.getenv("SMS_API_KEY") or None,
        sms_sender=os.getenv("SMS_SENDER") or None,
        admin_channel=(os.getenv("ADMIN_CHANNEL") or "").strip().lower(),
        admin_chat_id=os.getenv("ADMIN_CHAT_ID") or None,
        zarinpal_merchant_id=os.getenv("ZARINPAL_MERCHANT_ID") or None,
        ton_wallet=os.getenv("TON_WALLET_ADDRESS") or None,
        price_usd_month=int(os.getenv("PRICE_USD_MONTH", "12")),
        price_toman_month=int(os.getenv("PRICE_TOMAN_MONTH", "990000")),
        trial_days=int(os.getenv("TRIAL_DAYS", "7")),
        default_tz=os.getenv("DEFAULT_TZ") or "UTC",
    )
    channels = [c for c, tok in (("telegram", cfg.telegram_token), ("bale", cfg.bale_token)) if tok]
    if not channels:
        raise ValueError("Set TELEGRAM_BOT_TOKEN and/or BALE_BOT_TOKEN.")
    cfg.elder_channel = (os.getenv("ELDER_CHANNEL") or channels[0]).strip().lower()
    if cfg.elder_channel not in channels:
        raise ValueError(f"ELDER_CHANNEL={cfg.elder_channel} but that bot token isn't set.")
    if not cfg.admin_channel:
        cfg.admin_channel = channels[0]
    if cfg.peers and not cfg.peer_key:
        raise ValueError("PEERS is set but PEER_KEY is empty — node-to-node calls must be signed.")
    return cfg
