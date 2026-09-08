"""Thin client for the easymakebot marketing website's plan
activation-code API (web/wordpress/wp-content/mu-plugins/emb-activation-codes.php).

A user buys a plan on the website, gets a one-time code (EMB-XXXX-XXXX), then
redeems it here in /live to set the currently selected bot's live_until.

No Telegram-handler code here — used by bot/handlers/live.py.
"""

import asyncio
import logging

import aiohttp

from bot.config import load_config

logger = logging.getLogger(__name__)

_config = load_config()

_TIMEOUT = aiohttp.ClientTimeout(total=15)
# The bot (in Germany) and the website (in Iran) are on different hosts and
# the call crosses a border via Cloudflare — a transient failure is normal,
# so retry a few times before giving up.
_RETRIES = 3
_RETRY_BACKOFF = 2.0  # seconds: 2, 4, 8


def is_configured() -> bool:
    return bool(_config.website_url and _config.website_activation_key)


async def _post(path: str, payload: dict) -> dict:
    if not is_configured():
        return {"ok": False, "error": "not_configured"}
    url = f"{_config.website_url}{path}"
    headers = {"X-EMB-Key": _config.website_activation_key}

    last_error = "network"
    for attempt in range(1, _RETRIES + 1):
        try:
            async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
                async with session.post(url, json=payload, headers=headers) as resp:
                    if resp.status == 403:
                        # Bad key — retrying won't help.
                        return {"ok": False, "error": "http_403"}
                    if resp.status in (429, 502, 503, 504):
                        last_error = f"http_{resp.status}"
                    else:
                        data = await resp.json(content_type=None)
                        if isinstance(data, dict):
                            return data
                        last_error = "bad_response"
        except Exception:  # noqa: BLE001 — any transport failure is "network" to the caller
            last_error = "network"

        if attempt < _RETRIES:
            await asyncio.sleep(_RETRY_BACKOFF * attempt)
    logger.warning("website %s failed after %d attempts: %s", path, _RETRIES, last_error)
    return {"ok": False, "error": last_error}


async def redeem_activation_code(
    code: str,
    bot_id: str,
    telegram_id: int,
    *,
    username: str | None = None,
    first_name: str | None = None,
    phone: str | None = None,
) -> dict:
    """POST /wp-json/emb/v1/redeem.

    Forwards the redeemer's Telegram identity (id, @username, first name) and the
    Telegram-verified phone number so the website can bind the paid bot to a real
    person for abuse/fraud accountability.

    Success: {"ok": True, "days": 90, "months": 3, "code": "EMB-…"}
    Failure: {"ok": False, "error": "already_used" | "not_found" | "malformed_code"
              | "void" | "not_configured" | "network" | "http_403" | ...}
    """
    payload: dict = {
        "code": code,
        "bot_id": str(bot_id),
        "telegram_id": int(telegram_id),
    }
    if username:
        payload["telegram_username"] = str(username)
    if first_name:
        payload["telegram_first_name"] = str(first_name)
    if phone:
        payload["phone"] = str(phone)
    return await _post("/wp-json/emb/v1/redeem", payload)
