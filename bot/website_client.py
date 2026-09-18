"""Thin client for the easymakebot marketing website's plan
activation-code API (web/wordpress/wp-content/mu-plugins/emb-activation-codes.php).

A user buys a plan on the website, gets a one-time code (EMB-XXXX-XXXX), then
redeems it here in /live to set the currently selected bot's live_until.

No Telegram-handler code here — used by bot/handlers/live.py.
"""

import asyncio
import logging
import re

import aiohttp

from bot.config import load_config

logger = logging.getLogger(__name__)

_config = load_config()


def normalize_code(code: str) -> str | None:
    """Mirrors emb_actcodes_normalize() in the WordPress mu-plugin so that
    "emb-abcd-1234", "ABCD1234", "abcd 1234", etc. all collapse to the same
    canonical "EMB-ABCD-1234" form — used both before calling the website
    API and as the bot-side idempotency ledger key (RedeemedActivationCode),
    so a code typed differently on a retry still dedupes correctly. Returns
    None if the code doesn't have the right shape after stripping."""
    cleaned = re.sub(r"[^A-Z0-9]", "", (code or "").strip().upper())
    if cleaned.startswith("EMB"):
        cleaned = cleaned[3:]
    if len(cleaned) != 8:
        return None
    return f"EMB-{cleaned[:4]}-{cleaned[4:]}"

_TIMEOUT = aiohttp.ClientTimeout(total=15)
# The bot (in Germany) and the website (in Iran) are on different hosts and
# the call crosses a border via Cloudflare — a transient failure is normal,
# so retry a few times before giving up.
_RETRIES = 3
_RETRY_BACKOFF = 2.0  # seconds: 2, 4, 8


def is_configured() -> bool:
    return bool(_config.website_url and _config.website_activation_key)


async def _post(path: str, payload: dict, *, key: str | None = None) -> dict:
    """`key` defaults to the activation-code bridge's key so existing call
    sites (redeem_activation_code) are unaffected; verify_* below pass
    website_verify_key instead — each bridge has its own X-EMB-Key for
    least-privilege (a leaked activation key can't call the verify bridge
    and vice versa)."""
    if key is None:
        key = _config.website_activation_key
    if not _config.website_url or not key:
        return {"ok": False, "error": "not_configured"}
    url = f"{_config.website_url}{path}"
    headers = {"X-EMB-Key": key}

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


async def _check_code(code: str) -> dict:
    """GET /wp-json/emb/v1/check — read-only, consumes nothing.

    Success: {"ok": True, "valid": bool, "status": "pending"|"redeemed"|"void",
              "months": int, "days": int,
              "redeemed_bot_id": str, "redeemed_by_tg": int}  # last two only if redeemed
    """
    if not is_configured():
        return {"ok": False, "error": "not_configured"}
    url = f"{_config.website_url}/wp-json/emb/v1/check"
    headers = {"X-EMB-Key": _config.website_activation_key}
    try:
        async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
            async with session.get(url, params={"code": code}, headers=headers) as resp:
                data = await resp.json(content_type=None)
                return data if isinstance(data, dict) else {"ok": False, "error": "bad_response"}
    except Exception:  # noqa: BLE001
        return {"ok": False, "error": "network"}


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

    Idempotency note: the bot (Germany) and the website (Iran) are on
    different hosts, and the border hop can eat a response after the
    website already committed the redemption (see _post's retry comment) —
    or the whole call can be retried later, e.g. after a bot restart. In
    both cases WordPress correctly reports "already_used" since the code is
    genuinely consumed, but that used to surface to the buyer as "your code
    didn't work" even though their bot should already be live. Before
    reporting "already_used" as a failure, we double-check with the
    non-consuming /check endpoint whether it was THIS bot/user that redeemed
    it — if so, we treat it as success instead of an error.
    """
    normalized = normalize_code(code)
    if normalized is None:
        return {"ok": False, "error": "malformed_code"}
    code = normalized

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
    result = await _post("/wp-json/emb/v1/redeem", payload)

    if result.get("ok") is False and result.get("error") == "already_used":
        check = await _check_code(code)
        if (
            check.get("ok")
            and check.get("status") == "redeemed"
            and str(check.get("redeemed_bot_id") or "") == str(bot_id)
            and int(check.get("redeemed_by_tg") or 0) == int(telegram_id)
        ):
            logger.info(
                "redeem for code already showed 'already_used' but /check confirmed "
                "this bot/user redeemed it (likely a lost response on retry) — "
                "treating as success"
            )
            return {
                "ok": True,
                "code": code,
                "months": check.get("months"),
                "days": check.get("days"),
            }

    return result


# --- Registration + OTP verification bridge -------------------------------
# (web/wordpress/wp-content/mu-plugins/emb-bot-verify.php) — lets a bot
# creator with no website account yet register (Iran: name/last/phone/
# address/email + SMS code; international: email + email code) directly
# inside the bot, so a foreign phone/PC isn't required just to buy a plan.
# Used by bot/handlers/live.py's /live payment flow, and (per bot owner's
# own choice) the flow-builder verification-gate node for a BUILT bot's own
# shop checkout — same bridge, same single `emb_verified` identity either
# way. Uses website_verify_key, a separate X-EMB-Key from the activation
# bridge above (least privilege — see _post's docstring).


def verify_is_configured() -> bool:
    return bool(_config.website_url and _config.website_verify_key)


async def _verify_post(path: str, payload: dict) -> dict:
    return await _post(path, payload, key=_config.website_verify_key)


async def check_verification_status(
    channel: str, *, phone: str | None = None, email: str | None = None
) -> dict:
    """POST /wp-json/emb/v1/bot-verify/status.

    Success: {"ok": True, "registered": bool, "verified": bool}
    """
    payload: dict = {"channel": channel}
    if phone:
        payload["phone"] = phone
    if email:
        payload["email"] = email
    return await _verify_post("/wp-json/emb/v1/bot-verify/status", payload)


async def start_verification(
    channel: str,
    *,
    phone: str | None = None,
    email: str,
    first_name: str | None = None,
    last_name: str | None = None,
    address: str | None = None,
    tos: bool = True,
    telegram_id: int | None = None,
    telegram_username: str | None = None,
    telegram_first_name: str | None = None,
) -> dict:
    """POST /wp-json/emb/v1/bot-verify/start — creates/finds the account and
    sends the first OTP. `email` is required for both channels (channel=sms
    still needs one — mirrors the website's own fa registration form, which
    is a WooCommerce account and therefore always has an email on it).

    Success: {"ok": True} or {"ok": True, "already_verified": True} (no code
    was sent — the account was already verified, e.g. a retry after a lost
    response).
    Failure: {"ok": False, "error": "tos_required" | "bad_email" |
              "bad_phone" | "missing_fields" | "phone_taken" | "email_taken"
              | "server" | "rate_limited" | "send_failed" | "too_soon" |
              "too_many_sends" | "not_configured" | "network" | ...}
    """
    payload: dict = {"channel": channel, "email": email, "tos": bool(tos)}
    if phone:
        payload["phone"] = phone
    if first_name:
        payload["first_name"] = first_name
    if last_name:
        payload["last_name"] = last_name
    if address:
        payload["address"] = address
    if telegram_id:
        payload["telegram_id"] = int(telegram_id)
    if telegram_username:
        payload["telegram_username"] = str(telegram_username)
    if telegram_first_name:
        payload["telegram_first_name"] = str(telegram_first_name)
    return await _verify_post("/wp-json/emb/v1/bot-verify/start", payload)


async def resend_verification(
    channel: str, *, phone: str | None = None, email: str | None = None
) -> dict:
    """POST /wp-json/emb/v1/bot-verify/resend — for an account that's already
    registered (on the site or via a previous start_verification call) but
    not yet verified; sends a fresh code to the destination already on file.

    Success: {"ok": True, "channel": "sms"|"email"} or
             {"ok": True, "already_verified": True}
    Failure: {"ok": False, "error": "no_target" | "rate_limited" |
              "too_soon" | "too_many_sends" | "send_failed" | ...}
    """
    payload: dict = {"channel": channel}
    if phone:
        payload["phone"] = phone
    if email:
        payload["email"] = email
    return await _verify_post("/wp-json/emb/v1/bot-verify/resend", payload)


async def confirm_verification(
    channel: str, code: str, *, phone: str | None = None, email: str | None = None
) -> dict:
    """POST /wp-json/emb/v1/bot-verify/confirm.

    Success: {"ok": True, "verified": True}
    Failure: {"ok": False, "error": "no_pending" | "expired" | "too_many" |
              "mismatch" | "rate_limited" | "network" | ...}
    """
    payload: dict = {"channel": channel, "code": code}
    if phone:
        payload["phone"] = phone
    if email:
        payload["email"] = email
    return await _verify_post("/wp-json/emb/v1/bot-verify/confirm", payload)


# Shared bilingual error text for every verify_* error code above — used by
# both bot/handlers/live.py (platform /live gate) and bot/runtime.py (the
# flow-builder verify_gate node), so the two surfaces never drift apart on
# wording for the exact same bridge/error vocabulary.
_VERIFY_ERRORS_EN = {
    "tos_required": "You need to accept the Terms of Service to continue.",
    "bad_email": "That doesn't look like a valid email address.",
    "bad_phone": "That doesn't look like a valid phone number.",
    "missing_fields": "Please send all the requested details.",
    "phone_taken": "That phone number is already verified on another account. Please contact support.",
    "email_taken": "That email is already verified on another account. Please contact support.",
    "no_target": "No pending verification found — please start again.",
    "no_pending": "No code is pending — request a new one.",
    "expired": "That code expired — request a new one.",
    "too_many": "Too many wrong attempts — request a new code.",
    "mismatch": "That code is incorrect.",
    "too_soon": "Please wait a bit before requesting another code.",
    "too_many_sends": "Too many codes requested — please try again in an hour.",
    "send_failed": "Couldn't send the code. Please try again shortly.",
    "rate_limited": "Too many attempts — please try again in a few minutes.",
    "not_configured": "Verification isn't available right now.",
    "network": "Couldn't reach the verification service. Please try again in a minute.",
    "bad_response": "The verification service returned an unexpected response.",
    "server": "Something went wrong on our end. Please try again.",
}
_VERIFY_ERRORS_FA = {
    "tos_required": "برای ادامه باید قوانین استفاده رو بپذیری.",
    "bad_email": "این یه ایمیل معتبر به نظر نمی‌رسه.",
    "bad_phone": "این یه شماره معتبر به نظر نمی‌رسه.",
    "missing_fields": "لطفاً همه‌ی موارد خواسته‌شده رو بفرست.",
    "phone_taken": "این شماره قبلاً روی یه حساب دیگه تأیید شده. با پشتیبانی تماس بگیر.",
    "email_taken": "این ایمیل قبلاً روی یه حساب دیگه تأیید شده. با پشتیبانی تماس بگیر.",
    "no_target": "تأییدی در انتظار پیدا نشد — از اول شروع کن.",
    "no_pending": "کدی در انتظار نیست — یه کد جدید بگیر.",
    "expired": "این کد منقضی شده — یه کد جدید بگیر.",
    "too_many": "تلاش نادرست زیاد بود — یه کد جدید بگیر.",
    "mismatch": "این کد درست نیست.",
    "too_soon": "یه کم صبر کن، بعد دوباره کد بگیر.",
    "too_many_sends": "درخواست کد زیاد شد — یه ساعت دیگه امتحان کن.",
    "send_failed": "ارسال کد ناموفق بود. یه کم دیگه دوباره امتحان کن.",
    "rate_limited": "تلاش زیاد بود — چند دقیقه‌ی دیگه امتحان کن.",
    "not_configured": "تأیید هویت الان در دسترس نیست.",
    "network": "اتصال به سرویس تأیید برقرار نشد. یه دقیقه دیگه دوباره امتحان کن.",
    "bad_response": "سرویس تأیید پاسخ غیرمنتظره‌ای برگردوند.",
    "server": "یه مشکلی پیش اومد. دوباره امتحان کن.",
}


def verify_error_text(is_fa: bool, err: str) -> str:
    if is_fa:
        return _VERIFY_ERRORS_FA.get(err, f"خطا ({err}). با پشتیبانی تماس بگیر.")
    return _VERIFY_ERRORS_EN.get(err, f"Error ({err}). Please contact support.")
