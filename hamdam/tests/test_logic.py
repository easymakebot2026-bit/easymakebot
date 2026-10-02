from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from hamdam import logic
from hamdam.peer import sign, verify_signature
import time


def test_parse_hhmm():
    assert logic.parse_hhmm("9:05") == "09:05"
    assert logic.parse_hhmm("۰۸:۳۰") == "08:30"
    assert logic.parse_hhmm("21.15") == "21:15"
    assert logic.parse_hhmm("24:00") is None
    assert logic.parse_hhmm("9:5") is None
    assert logic.parse_hhmm("hello") is None


def test_is_due_window():
    tz = ZoneInfo("Asia/Tehran")
    at = lambda h, m: datetime(2026, 10, 2, h, m, tzinfo=tz)  # noqa: E731
    assert not logic.is_due(at(9, 59), "10:00")
    assert logic.is_due(at(10, 0), "10:00")
    assert logic.is_due(at(12, 59), "10:00")
    assert not logic.is_due(at(13, 0), "10:00")  # created too late in the day -> wait for tomorrow


def test_detect_concern():
    d = logic.detect_concern
    assert d("خوبم ممنون") is None
    assert d("درد ندارم") is None
    assert d("حالم بد نیست") is None
    assert d("کتاب میخونم") is None
    assert d("خونه هستم") is None
    assert d("دردم زیاده") == "concern"
    assert d("سرم گیجه") == "concern"
    assert d("حالم خوب نیست") == "concern"
    assert d("تنهام") == "concern"
    assert d("افتادم زمین") == "urgent"
    assert d("كمكم كنيد") == "urgent"  # Arabic kaf/yeh normalised
    assert d("I fell in the kitchen") == "urgent"
    assert d("no pain today") is None


def test_codes():
    assert logic.looks_like_elder_code("۱۲۳۴ ۵۶۷۸") == "12345678"
    assert logic.looks_like_elder_code("1234567") is None
    code = logic.new_family_code("ir")
    assert logic.split_family_code(code.lower()) == ("ir", code)
    assert logic.split_family_code("nope") is None


def test_days_left():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert logic.days_left(now - timedelta(seconds=1), now) == 0
    assert logic.days_left(now + timedelta(days=6, hours=1), now) == 7


def test_signature():
    ts = str(int(time.time()))
    sig = sign("k", "ir", ts, b"{}")
    assert verify_signature("k", "ir", ts, b"{}", sig)
    assert not verify_signature("k", "global", ts, b"{}", sig)  # can't speak for another node
    assert not verify_signature("other", "ir", ts, b"{}", sig)
    old = str(int(time.time()) - 3600)
    assert not verify_signature("k", "ir", old, b"{}", sign("k", "ir", old, b"{}"))
