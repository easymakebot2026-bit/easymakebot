"""Operations on care circles. Everything in RPC runs on the circle's HOME
node and may be called from any node (see Node.call); everything else here
is used locally by the home node's own handlers and scheduler.

Authorization: every RPC carries `requester` = {node, channel, chat_id}. The
peer link is authenticated per node (HMAC), so a node can only speak for its
own chats — `requester["node"]` must equal the calling node.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select

from hamdam import logic
from hamdam.models import Circle, Event, Medication, Member, Person, aware, utcnow
from hamdam.peer import ServiceError, is_peer_down
from hamdam.texts import t

logger = logging.getLogger(__name__)


def _check_requester(origin: str, requester: dict) -> None:
    if not requester or requester.get("node") != origin:
        raise ServiceError("forbidden")


async def _family_circle(s, circle_id: str, requester: dict) -> Circle:
    circle = await s.get(Circle, circle_id)
    if circle is None:
        raise ServiceError("not_found")
    member = (
        await s.execute(
            select(Member).where(
                Member.circle_id == circle_id, Member.role == "family", Member.node == requester["node"],
                Member.channel == requester["channel"], Member.chat_id == str(requester["chat_id"]),
            )
        )
    ).scalar_one_or_none()
    if member is None:
        raise ServiceError("forbidden")
    return circle


async def _unique_elder_code(s) -> str:
    for _ in range(10):
        code = logic.new_elder_code()
        if (await s.execute(select(Circle.id).where(Circle.elder_code == code))).first() is None:
            return code
    raise ServiceError("failed")


def _elder_link(node, code: str | None) -> str | None:
    messenger = node.messengers.get(node.config.elder_channel)
    return messenger.start_link(f"e{code}") if (messenger and code) else None


async def notify(node, circle: Circle, key: str, *, roles=("family",), voice: bytes | None = None,
                 exclude: tuple | None = None, **kw) -> None:
    async with node.session() as s:
        members = (
            await s.execute(select(Member).where(Member.circle_id == circle.id, Member.role.in_(roles)))
        ).scalars().all()
    for m in members:
        if exclude and (m.node, m.channel, m.chat_id) == exclude:
            continue
        # A neighbour doesn't know her as "Mum" — use the polite form instead.
        elder = circle.elder_title if m.role == "local" else circle.elder_name
        text = t(m.lang, key, elder=elder, **kw)
        await node.deliver(m.node, m.channel, m.chat_id, text, voice=voice if m.role == "family" else None)


async def family_unreachable(node, circle: Circle) -> bool:
    """True when every family member's node is currently cut off from us —
    the moment a local contact has to step in."""
    async with node.session() as s:
        nodes = set(
            (await s.execute(
                select(Member.node).where(Member.circle_id == circle.id, Member.role == "family")
            )).scalars().all()
        )
    for n in nodes:
        if not await is_peer_down(node, n):
            return False
    return True


# --- RPC: family-facing operations ---------------------------------------------


async def create_circle(node, origin, requester, name, lang, elder_name, elder_title, elder_lang,
                        tz, checkin_time) -> dict:
    _check_requester(origin, requester)
    if not logic.valid_tz(tz) or logic.parse_hhmm(checkin_time) is None:
        raise ServiceError("invalid")
    async with node.session() as s:
        circle = Circle(
            id=uuid.uuid4().hex, elder_name=elder_name[:100], elder_title=elder_title[:100],
            lang=elder_lang, tz=tz, checkin_time=logic.parse_hhmm(checkin_time),
            elder_code=await _unique_elder_code(s), family_code=logic.new_family_code(node.id),
            paid_until=utcnow() + timedelta(days=node.config.trial_days),
        )
        s.add(circle)
        s.add(Member(circle_id=circle.id, role="family", name=name[:100], node=requester["node"],
                     channel=requester["channel"], chat_id=str(requester["chat_id"]), lang=lang))
        await s.commit()
    return {
        "circle_id": circle.id, "elder_name": circle.elder_name, "elder_code": circle.elder_code,
        "family_code": circle.family_code, "elder_link": _elder_link(node, circle.elder_code),
        "elder_channel": node.config.elder_channel, "trial_days": node.config.trial_days,
    }


async def join_circle(node, origin, requester, name, lang, family_code) -> dict:
    _check_requester(origin, requester)
    async with node.session() as s:
        circle = (await s.execute(select(Circle).where(Circle.family_code == family_code))).scalar_one_or_none()
        if circle is None:
            raise ServiceError("bad_code")
        exists = (
            await s.execute(
                select(Member.id).where(
                    Member.circle_id == circle.id, Member.node == requester["node"],
                    Member.channel == requester["channel"], Member.chat_id == str(requester["chat_id"]),
                )
            )
        ).first()
        if exists is None:
            s.add(Member(circle_id=circle.id, role="family", name=name[:100], node=requester["node"],
                         channel=requester["channel"], chat_id=str(requester["chat_id"]), lang=lang))
            await s.commit()
    if exists is None:
        await notify(node, circle, "family_joined", name=name,
                     exclude=(requester["node"], requester["channel"], str(requester["chat_id"])))
    return {"circle_id": circle.id, "elder_name": circle.elder_name}


async def circle_view(node, origin, requester, circle_id) -> dict:
    _check_requester(origin, requester)
    async with node.session() as s:
        circle = await _family_circle(s, circle_id, requester)
        meds = (await s.execute(select(Medication).where(Medication.circle_id == circle_id)
                                .order_by(Medication.time))).scalars().all()
        members = (await s.execute(select(Member).where(Member.circle_id == circle_id))).scalars().all()
        today = logic.today_in(circle.tz, utcnow()).isoformat()
        events = (await s.execute(select(Event).where(Event.circle_id == circle_id, Event.local_date == today)
                                  .order_by(Event.sent_at))).scalars().all()
    return {
        "id": circle.id, "elder_name": circle.elder_name, "elder_title": circle.elder_title,
        "tz": circle.tz, "checkin_time": circle.checkin_time, "summary_time": circle.summary_time,
        "paused": circle.paused, "linked": circle.elder_chat_id is not None,
        "elder_code": circle.elder_code, "elder_link": _elder_link(node, circle.elder_code),
        "family_code": circle.family_code, "elder_phone": circle.elder_phone,
        "days_left": logic.days_left(aware(circle.paid_until), utcnow()),
        "meds": [{"id": m.id, "name": m.name, "time": m.time} for m in meds],
        "family": [m.name for m in members if m.role == "family"],
        "locals": [{"id": m.id, "name": m.name, "phone": m.chat_id} for m in members if m.role == "local"],
        "today": [{"label": e.label, "status": e.status} for e in events],
        "sms": "sms" in node.messengers,
    }


async def update_circle(node, origin, requester, circle_id, field, value) -> None:
    _check_requester(origin, requester)
    async with node.session() as s:
        circle = await _family_circle(s, circle_id, requester)
        if field in ("checkin_time", "summary_time"):
            value = logic.parse_hhmm(str(value))
            if value is None:
                raise ServiceError("invalid")
        elif field == "tz":
            if not logic.valid_tz(str(value)):
                raise ServiceError("invalid")
        elif field == "paused":
            value = bool(value)
        elif field == "elder_phone":
            value = logic.to_ascii_digits(str(value)).replace(" ", "") or None
        elif field == "elder_title":
            value = str(value)[:100]
        else:
            raise ServiceError("invalid")
        setattr(circle, field, value)
        await s.commit()


async def add_med(node, origin, requester, circle_id, name, time) -> None:
    _check_requester(origin, requester)
    hhmm = logic.parse_hhmm(time)
    if hhmm is None or not name.strip():
        raise ServiceError("invalid")
    async with node.session() as s:
        await _family_circle(s, circle_id, requester)
        s.add(Medication(circle_id=circle_id, name=name.strip()[:100], time=hhmm))
        await s.commit()


async def del_med(node, origin, requester, circle_id, med_id) -> None:
    _check_requester(origin, requester)
    async with node.session() as s:
        await _family_circle(s, circle_id, requester)
        med = await s.get(Medication, int(med_id))
        if med is not None and med.circle_id == circle_id:
            await s.delete(med)
            await s.commit()


async def add_local_contact(node, origin, requester, circle_id, name, phone) -> None:
    """A neighbour or relative near the elder, reached by SMS from the home
    node — the one alert path that doesn't cross a border."""
    _check_requester(origin, requester)
    if "sms" not in node.messengers:
        raise ServiceError("sms_unavailable")
    phone = logic.to_ascii_digits(phone or "").replace(" ", "").replace("-", "")
    if not phone.lstrip("+").isdigit() or len(phone.lstrip("+")) < 8:
        raise ServiceError("invalid")
    async with node.session() as s:
        circle = await _family_circle(s, circle_id, requester)
        s.add(Member(circle_id=circle_id, role="local", name=name.strip()[:100], node=node.id,
                     channel="sms", chat_id=phone, lang=circle.lang))
        await s.commit()


async def del_local_contact(node, origin, requester, circle_id, member_id) -> None:
    _check_requester(origin, requester)
    async with node.session() as s:
        await _family_circle(s, circle_id, requester)
        m = await s.get(Member, int(member_id))
        if m is not None and m.circle_id == circle_id and m.role == "local":
            await s.delete(m)
            await s.commit()


async def renew_elder_code(node, origin, requester, circle_id) -> dict:
    """New phone / new account for the elder: unlink and issue a fresh code."""
    _check_requester(origin, requester)
    async with node.session() as s:
        circle = await _family_circle(s, circle_id, requester)
        circle.elder_code = await _unique_elder_code(s)
        circle.elder_channel = None
        circle.elder_chat_id = None
        await s.commit()
    return {"elder_code": circle.elder_code, "elder_link": _elder_link(node, circle.elder_code)}


async def leave_circle(node, origin, requester, circle_id) -> None:
    _check_requester(origin, requester)
    async with node.session() as s:
        await _family_circle(s, circle_id, requester)
        member = (
            await s.execute(
                select(Member).where(
                    Member.circle_id == circle_id, Member.node == requester["node"],
                    Member.channel == requester["channel"], Member.chat_id == str(requester["chat_id"]),
                )
            )
        ).scalar_one()
        await s.delete(member)
        await s.commit()


RPC = {
    f.__name__: f
    for f in (create_circle, join_circle, circle_view, update_circle, add_med, del_med,
              add_local_contact, del_local_contact, renew_elder_code, leave_circle)
}


# --- Commands (queued, guaranteed) ----------------------------------------------


async def extend_subscription(node, circle_id, days, payer_name="") -> None:
    async with node.session() as s:
        circle = await s.get(Circle, circle_id)
        if circle is None:
            logger.error("paid extension for unknown circle %s", circle_id)
            return
        now = utcnow()
        base = max(now, aware(circle.paid_until))
        circle.paid_until = base + timedelta(days=int(days))
        circle.expiry_notified = False
        await s.commit()
    until = circle.paid_until.astimezone(ZoneInfo(circle.tz)).date().isoformat()
    await notify(node, circle, "sub_extended", days=days, until=until, name=payer_name)


COMMANDS = {"extend_subscription": extend_subscription}


# --- Elder side (home node only) ------------------------------------------------


async def elder_circle(node, channel: str, chat_id: str) -> Circle | None:
    async with node.session() as s:
        return (
            await s.execute(select(Circle).where(Circle.elder_channel == channel, Circle.elder_chat_id == chat_id))
        ).scalars().first()


async def link_elder(node, channel: str, chat_id: str, code: str) -> Circle | None:
    async with node.session() as s:
        circle = (await s.execute(select(Circle).where(Circle.elder_code == code))).scalar_one_or_none()
        if circle is None:
            return None
        circle.elder_channel = channel
        circle.elder_chat_id = chat_id
        circle.elder_code = None
        await s.commit()
    await notify(node, circle, "elder_linked")
    return circle


async def answer_event(node, circle: Circle, event_id: int, status: str, response: str | None = None) -> Event | None:
    async with node.session() as s:
        event = await s.get(Event, event_id)
        if event is None or event.circle_id != circle.id:
            return None
        event.status = status
        event.answered_at = utcnow()
        if response:
            event.response = ((event.response or "") + "\n" + response).strip()[:2000]
        await s.commit()
    return event


async def _open_checkin(node, circle: Circle) -> Event | None:
    today = logic.today_in(circle.tz, utcnow()).isoformat()
    async with node.session() as s:
        return (
            await s.execute(
                select(Event).where(Event.circle_id == circle.id, Event.slot == "checkin",
                                    Event.local_date == today)
            )
        ).scalar_one_or_none()


async def elder_said(node, circle: Circle, text: str | None = None, voice: bytes | None = None) -> str | None:
    """Anything the elder sends outside the buttons: forwarded to the family,
    scanned for worrying words, and counted as today's check-in answer.
    Returns the concern level found (None / 'concern' / 'urgent')."""
    level = logic.detect_concern(text) if text else None
    checkin = await _open_checkin(node, circle)
    if checkin is not None:
        # A worry stays a worry even if a cheerful message follows it.
        new_status = "concern" if (level or checkin.status == "concern") else "ok"
        await answer_event(node, circle, checkin.id, new_status, text or "🎙")

    if voice is not None:
        await notify(node, circle, "voice_from_elder", voice=voice)
    if level == "urgent":
        await notify(node, circle, "urgent_from_elder", roles=("family", "local"), text=text)
    elif level == "concern":
        await notify(node, circle, "concern_from_elder", text=text)
    elif text:
        await notify(node, circle, "msg_from_elder", text=text)
    return level


async def person_lang(node, channel: str, chat_id: str) -> str | None:
    async with node.session() as s:
        p = (await s.execute(select(Person).where(Person.channel == channel, Person.chat_id == chat_id))
             ).scalar_one_or_none()
        return p.lang if p else None


def now_local(circle: Circle, now: datetime | None = None) -> datetime:
    return (now or datetime.now(timezone.utc)).astimezone(ZoneInfo(circle.tz))
