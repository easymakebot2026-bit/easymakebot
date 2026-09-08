"""Validates Telegram Mini App `initData`, per Telegram's documented algorithm:
https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

# Reject initData older than this. Telegram's docs recommend checking
# auth_date to bound how long a captured initData string stays replayable;
# a builder session realistically never needs a day-old signature.
MAX_AGE_SECONDS = 24 * 60 * 60


def validate_init_data(
    init_data: str, bot_token: str, *, max_age_seconds: int = MAX_AGE_SECONDS
) -> dict | None:
    """Returns the parsed `user` dict from initData if the HMAC signature is
    valid and (when max_age_seconds > 0) auth_date is recent, otherwise None."""
    try:
        pairs = parse_qsl(init_data, strict_parsing=True)
    except ValueError:
        return None

    data = dict(pairs)
    received_hash = data.pop("hash", None)
    if not received_hash:
        return None

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        return None

    if max_age_seconds > 0:
        try:
            auth_date = int(data.get("auth_date", "0"))
        except (TypeError, ValueError):
            return None
        if auth_date <= 0 or time.time() - auth_date > max_age_seconds:
            return None

    user_raw = data.get("user")
    if not user_raw:
        return None

    try:
        return json.loads(user_raw)
    except (TypeError, ValueError):
        return None
