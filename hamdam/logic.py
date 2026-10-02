"""Pure decision logic for Hamdam — no database, no network, no Telegram.

Everything here is deterministic and unit-tested (hamdam/tests/test_logic.py)
so the parts that decide "should we bother an elderly person now?" and "is
this reply worrying?" can be reasoned about without running a bot.
"""

import re
import secrets
import string
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# How long after a scheduled time a check-in/reminder may still be sent. A
# circle created at 15:00 with a 10:00 check-in waits for tomorrow instead of
# pinging immediately; a node that was down for a few minutes still catches up.
DUE_WINDOW = timedelta(hours=3)
# No answer this long after sending -> one gentle repeat.
REMIND_AFTER = timedelta(minutes=30)
# No answer this long after sending -> tell the family (and, when needed,
# the local contact).
ESCALATE_AFTER = timedelta(minutes=90)

_HHMM = re.compile(r"^\s*([01]?\d|2[0-3])\s*[:.]\s*([0-5]\d)\s*$")
_FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def to_ascii_digits(text: str) -> str:
    return text.translate(_FA_DIGITS)


def parse_hhmm(text: str) -> str | None:
    """'9:5' is rejected, '9:05' / '۰۹:۰۵' / '21.30' are accepted. Returns a
    normalized 'HH:MM' or None."""
    m = _HHMM.match(to_ascii_digits(text or ""))
    if not m:
        return None
    return f"{int(m.group(1)):02d}:{m.group(2)}"


def valid_tz(name: str) -> bool:
    try:
        ZoneInfo(name)
        return True
    except (ZoneInfoNotFoundError, ValueError):
        return False


def is_due(local_now: datetime, hhmm: str, window: timedelta = DUE_WINDOW) -> bool:
    """True when local_now is at/after today's hhmm but still inside window."""
    hour, minute = (int(x) for x in hhmm.split(":"))
    scheduled = local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return scheduled <= local_now < scheduled + window


def local_date_str(local_now: datetime) -> str:
    return local_now.date().isoformat()


def is_today(stored: str | None, local_now: datetime) -> bool:
    return stored == local_now.date().isoformat()


# --- Reply analysis ---------------------------------------------------------
#
# Deliberately simple keyword matching. A missed worry costs far more than a
# false alarm, so the lists lean wide; negation handling only removes the
# clearest false positives ("درد ندارم" = "I have no pain", "حالم بد نیست").

_URGENT = [
    "افتادم", "زمین خوردم", "نفسم", "تنگی نفس", "نفس تنگی", "قفسه سینه", "اورژانس",
    "آمبولانس", "کمک", "بیهوش", "غش", "سکته", "خونریزی",
    "fell", "fall", "can't breathe", "cant breathe", "chest pain", "emergency", "help",
    "ambulance", "stroke", "bleeding",
]
_CONCERN = [
    "درد", "سردرد", "دلدرد", "دل‌درد", "کمردرد", "پادرد", "زانودرد", "سرگیجه", "گیجم",
    "سرم گیج", "حالم بد", "حالم خوب نیست", "خوب نیستم", "مریض", "تب", "فشارم", "قندم",
    "ضعف", "بی‌حال", "بیحال", "حال ندارم", "نخوابیدم", "بی‌خوابی", "تنهام", "دلم گرفته",
    "غمگین", "حوصله ندارم", "دکتر", "بیمارستان", "استفراغ", "تهوع", "اسهال", "سرفه",
    "pain", "painful", "dizzy", "sick", "fever", "not well", "unwell", "lonely", "sad",
    "weak", "hospital", "doctor", "vomit", "vomiting", "couldn't sleep",
]
_FA_NEGATIONS = ("ندارم", "نداره", "ندارد", "نیست", "نشدم", "نمی")
_EN_NEGATIONS = ("no ", "not ", "don't ", "dont ", "never ")


def normalize(text: str) -> str:
    text = (text or "").replace("ي", "ی").replace("ك", "ک")
    return " ".join(to_ascii_digits(text).lower().split())


def _pattern(keyword: str) -> re.Pattern:
    # Word-bounded, so "تب" doesn't fire inside "کتاب" (compounds such as
    # "سردرد" are listed separately). A short suffix is allowed: "دردم",
    # "تبم", "کمکم", "fell"/"falls" ...
    return re.compile(r"(?<!\w)" + re.escape(keyword) + r"(?:م|ه|ی|ام|ش|ed|s)?(?!\w)")


_URGENT_RE = [_pattern(k) for k in _URGENT]
_CONCERN_RE = [_pattern(k) for k in _CONCERN]


def _hit(text: str, pattern: re.Pattern) -> bool:
    for m in pattern.finditer(text):
        tail = text[m.end():].lstrip()
        head = text[max(0, m.start() - 10): m.start()]
        if tail.startswith(_FA_NEGATIONS) or any(n in head for n in _EN_NEGATIONS):
            continue  # "درد ندارم", "no pain"
        return True
    return False


def detect_concern(text: str) -> str | None:
    """'urgent' | 'concern' | None."""
    t = normalize(text)
    if not t:
        return None
    if any(_hit(t, p) for p in _URGENT_RE):
        return "urgent"
    if any(_hit(t, p) for p in _CONCERN_RE):
        return "concern"
    return None


# --- Codes ------------------------------------------------------------------


def new_elder_code() -> str:
    """8 digits — easy for an elderly person to type (or for a relative to
    read out over the phone). Cleared once used, so it only protects the
    window between creation and linking."""
    return "".join(secrets.choice(string.digits) for _ in range(8))


_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no 0/O/1/I/L confusion


def new_family_code(node_id: str) -> str:
    """'<node>-XXXXXXXX'. The node prefix tells whoever types it which node
    owns the circle, so a relative on any node can join any circle."""
    token = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(8))
    return f"{node_id}-{token}"


def split_family_code(code: str) -> tuple[str, str] | None:
    code = (code or "").strip()
    if "-" not in code:
        return None
    node_id, token = code.rsplit("-", 1)
    if not node_id or len(token) != 8:
        return None
    return node_id.lower(), f"{node_id.lower()}-{token.upper()}"


def looks_like_elder_code(text: str) -> str | None:
    t = to_ascii_digits((text or "").strip()).replace(" ", "")
    return t if re.fullmatch(r"\d{8}", t) else None


def days_left(paid_until: datetime | None, now: datetime) -> int:
    if paid_until is None or paid_until <= now:
        return 0
    return (paid_until - now).days + 1


def today_in(tz: str, now_utc: datetime) -> date:
    return now_utc.astimezone(ZoneInfo(tz)).date()
