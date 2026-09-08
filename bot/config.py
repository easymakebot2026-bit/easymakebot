import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    bot_token: str
    database_url: str
    platform_admin_id: int
    webapp_url: str
    webapp_port: int
    video_url_fa: str
    video_url_en: str
    # The platform's OWN payment credentials for /live plans (bot/platform_billing.py)
    # — one of each for the whole platform, unlike bot/shop.py's per-bot ShopSettings.
    # Optional/graceful-omit: a path with no credential set here just isn't offered.
    platform_zarinpal_merchant_id: str | None
    platform_stripe_secret_key: str | None
    platform_ton_wallet_address: str | None
    # easymakebot marketing website (web/) — used to redeem plan activation
    # codes a user bought there. Both must be set for the "Activate with code"
    # option in /live to appear; otherwise it's silently hidden.
    website_url: str | None
    website_activation_key: str | None
    # Where an Iran-region owner is sent to BUY a plan (in their browser, so
    # the payment runs on the Iranian site with a native Iran IP — a Telegram
    # VPN would break the gateway). Defaults to "{website_url}/plans/".
    website_plans_url: str | None
    # When the website is in Iran and the bot abroad, the bot must NOT start
    # its own Zarinpal payment for Iran owners (foreign server IP + the buyer's
    # Telegram VPN both fight the gateway) — they buy on the website and redeem
    # a code instead. Set true only if the bot itself is also on an Iran IP.
    platform_onbot_zarinpal: bool


def load_config() -> Config:
    bot_token = os.getenv("BOT_TOKEN")
    database_url = os.getenv("DATABASE_URL", "")
    platform_admin_id_raw = os.getenv("PLATFORM_ADMIN_ID")
    webapp_url = os.getenv("WEBAPP_URL", "")
    webapp_port = int(os.getenv("WEBAPP_PORT", "8080"))
    video_url_fa = os.getenv("VIDEO_URL_FA", "")
    video_url_en = os.getenv("VIDEO_URL_EN", "")
    platform_zarinpal_merchant_id = os.getenv("PLATFORM_ZARINPAL_MERCHANT_ID") or None
    platform_stripe_secret_key = os.getenv("PLATFORM_STRIPE_SECRET_KEY") or None
    platform_ton_wallet_address = os.getenv("PLATFORM_TON_WALLET_ADDRESS") or None
    website_url = (os.getenv("WEBSITE_URL") or "").rstrip("/") or None
    website_activation_key = os.getenv("WEBSITE_ACTIVATION_KEY") or None
    website_plans_url = (os.getenv("WEBSITE_PLANS_URL") or "").rstrip("/") or None
    if website_plans_url is None and website_url is not None:
        website_plans_url = f"{website_url}/plans/"
    platform_onbot_zarinpal = (os.getenv("PLATFORM_ONBOT_ZARINPAL") or "").strip().lower() in (
        "1", "true", "yes", "on"
    )

    if not bot_token:
        raise ValueError(
            "BOT_TOKEN is not set in the .env file. "
            "Copy .env.example to .env and put your bot token in it."
        )

    if not platform_admin_id_raw:
        raise ValueError(
            "PLATFORM_ADMIN_ID is not set in .env. "
            "Get your numeric Telegram ID from @userinfobot and put it in .env."
        )

    return Config(
        bot_token=bot_token,
        database_url=database_url,
        platform_admin_id=int(platform_admin_id_raw),
        webapp_url=webapp_url.rstrip("/"),
        webapp_port=webapp_port,
        video_url_fa=video_url_fa,
        video_url_en=video_url_en,
        platform_zarinpal_merchant_id=platform_zarinpal_merchant_id,
        platform_stripe_secret_key=platform_stripe_secret_key,
        platform_ton_wallet_address=platform_ton_wallet_address,
        website_url=website_url,
        website_activation_key=website_activation_key,
        website_plans_url=website_plans_url,
        platform_onbot_zarinpal=platform_onbot_zarinpal,
    )
