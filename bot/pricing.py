"""Pure helpers for time-boxed price campaigns (bot/db/models.py:PriceCampaign)
and customer-facing price formatting. No DB, no Telegram.

A campaign overwrites the live price columns and stashes the pre-campaign
value in an `original_*` column; these helpers compute the adjusted number
and render "old price struck through, new price" for buyers.
"""

# Adjusted prices are rounded to the nearest this many Toman so a sale
# doesn't produce prices like 43,200.
CAMPAIGN_ROUND = 1000


def adjusted_price(base: int, direction: str, percent: int) -> int:
    """`base` after a `percent`% discount or markup, rounded to CAMPAIGN_ROUND
    (never below 0). A tiny price that would round to 0 under a big discount
    is floored at CAMPAIGN_ROUND so it's still purchasable."""
    if direction == "discount":
        raw = base * (100 - percent) / 100
    else:  # "markup"
        raw = base * (100 + percent) / 100
    rounded = round(raw / CAMPAIGN_ROUND) * CAMPAIGN_ROUND
    if direction == "discount" and base > 0 and rounded <= 0:
        return CAMPAIGN_ROUND
    return max(0, int(rounded))


def _strike(text: str) -> str:
    """Combining-overlay strikethrough — renders struck-through in every
    Telegram client with no parse_mode / HTML escaping needed."""
    return "".join(ch + "̶" for ch in text)


def format_price(current: int, original: int | None = None, *, currency: str = "Toman") -> str:
    """"12,000 Toman", or "1̶5̶,̶0̶0̶0̶ 12,000 Toman" when `original` is a higher
    pre-campaign price (a discount). A markup shows only the current price."""
    if original is not None and original > current:
        return f"{_strike(f'{original:,}')} {current:,} {currency}"
    return f"{current:,} {currency}"


def discount_percent(current: int, original: int | None) -> int | None:
    if not original or original <= current:
        return None
    return round((original - current) / original * 100)


def savings_line(current: int, original: int | None, *, currency: str = "Toman") -> str | None:
    """A marketing one-liner for a discounted item, or None if not discounted."""
    pct = discount_percent(current, original)
    if pct is None:
        return None
    return f"🎉 {pct}% off — you save {original - current:,} {currency}"
