"""The care loop, run once a minute by every node for the circles it is home
to. Because it runs next to the elder (the Iran node for an elder in Iran),
it keeps going through an international shutdown: check-ins and medicine
reminders still go out over Bale/SMS, a missed answer still reaches the local
contact by domestic SMS, and family abroad receive the queued news once the
link is back.
"""

import asyncio
import logging
from datetime import datetime

from sqlalchemy import select

from hamdam import logic
from hamdam.messaging import Button
from hamdam.models import Circle, Event, Medication, aware, utcnow
from hamdam.services import family_unreachable, notify, now_local
from hamdam.texts import t

logger = logging.getLogger(__name__)

TICK_SECONDS = 60


def elder_buttons(circle: Circle, event: Event) -> list[list[Button]]:
    if event.slot == "checkin":
        return [[Button(t(circle.lang, "btn_ok"), f"ok:{event.id}"),
                 Button(t(circle.lang, "btn_bad"), f"bad:{event.id}")]]
    return [[Button(t(circle.lang, "btn_taken"), f"took:{event.id}")]]


def _elder_text(circle: Circle, event: Event, reminder: bool = False) -> str:
    if event.slot == "checkin":
        return t(circle.lang, "elder_reminder" if reminder else "elder_checkin", title=circle.elder_title)
    return t(circle.lang, "elder_med_reminder" if reminder else "elder_med", title=circle.elder_title, med=event.label)


async def _send_to_elder(node, circle: Circle, event: Event, reminder: bool = False) -> bool:
    ok = await node.deliver(node.id, circle.elder_channel, circle.elder_chat_id,
                            _elder_text(circle, event, reminder), elder_buttons(circle, event))
    if not ok and circle.elder_phone and "sms" in node.messengers:
        # Messenger unreachable (e.g. Bale down too) — plain SMS still says hello.
        ok = await node.deliver(node.id, "sms", circle.elder_phone, _elder_text(circle, event, reminder) +
                                "\n" + t(circle.lang, "sms_no_reply"))
    return bool(ok)


async def _open_slots(node, circle: Circle, local_now: datetime, now: datetime) -> None:
    async with node.session() as s:
        meds = (await s.execute(select(Medication).where(Medication.circle_id == circle.id))).scalars().all()
        today = logic.local_date_str(local_now)
        existing = set(
            (await s.execute(select(Event.slot).where(Event.circle_id == circle.id, Event.local_date == today)))
            .scalars().all()
        )
    slots = [("checkin", circle.checkin_time, t(circle.lang, "checkin_label"))]
    slots += [(f"med:{m.id}", m.time, m.name) for m in meds]
    for slot, hhmm, label in slots:
        if slot in existing or not logic.is_due(local_now, hhmm):
            continue
        async with node.session() as s:
            event = Event(circle_id=circle.id, slot=slot, label=label, local_date=today, sent_at=now)
            s.add(event)
            await s.commit()
        if not await _send_to_elder(node, circle, event):
            async with node.session() as s:
                row = await s.get(Event, event.id)
                row.status = "undelivered"
                await s.commit()


async def _follow_up(node, circle: Circle, now: datetime) -> None:
    async with node.session() as s:
        events = (
            await s.execute(
                select(Event).where(Event.circle_id == circle.id, Event.escalated.is_(False),
                                    Event.status.in_(("pending", "undelivered")))
            )
        ).scalars().all()
    for event in events:
        age = now - aware(event.sent_at)
        if age >= logic.ESCALATE_AFTER:
            await _escalate(node, circle, event)
        elif age >= logic.REMIND_AFTER and event.reminded_at is None:
            await _send_to_elder(node, circle, event, reminder=True)
            async with node.session() as s:
                row = await s.get(Event, event.id)
                row.reminded_at = now
                await s.commit()


async def _escalate(node, circle: Circle, event: Event) -> None:
    async with node.session() as s:
        row = await s.get(Event, event.id)
        if row.escalated or row.status not in ("pending", "undelivered"):
            return
        row.escalated = True
        undelivered = row.status == "undelivered"
        if not undelivered:
            row.status = "missed"
        await s.commit()

    if undelivered:
        key = "alert_undelivered"
    elif event.slot == "checkin":
        key = "alert_missed_checkin"
    else:
        key = "alert_missed_med"
    await notify(node, circle, key, med=event.label)

    # Local contacts are only woken up for a missed check-in when the family
    # can't act themselves — i.e. every family member is behind a cut link.
    if event.slot == "checkin" and await family_unreachable(node, circle):
        await notify(node, circle, "local_alert_missed", roles=("local",))


async def _summary(node, circle: Circle, local_now: datetime) -> None:
    if logic.is_today(circle.last_summary_date, local_now) or not logic.is_due(local_now, circle.summary_time):
        return
    today = logic.local_date_str(local_now)
    async with node.session() as s:
        row = await s.get(Circle, circle.id)
        row.last_summary_date = today
        await s.commit()
        events = (await s.execute(select(Event).where(Event.circle_id == circle.id, Event.local_date == today)
                                  .order_by(Event.sent_at))).scalars().all()
    if not events:
        return
    await notify(node, circle, "summary", events=[(e.label, e.status, e.response) for e in events])


async def tick(node, now: datetime | None = None) -> None:
    now = now or utcnow()
    async with node.session() as s:
        circles = (await s.execute(select(Circle).where(Circle.elder_chat_id.is_not(None)))).scalars().all()
    for circle in circles:
        try:
            if aware(circle.paid_until) <= now:
                if not circle.expiry_notified:
                    async with node.session() as s:
                        (await s.get(Circle, circle.id)).expiry_notified = True
                        await s.commit()
                    await notify(node, circle, "sub_expired")
                continue
            if circle.paused:
                continue
            local_now = now_local(circle, now)
            await _open_slots(node, circle, local_now, now)
            await _follow_up(node, circle, now)
            await _summary(node, circle, local_now)
        except Exception:
            logger.exception("care loop failed for circle %s", circle.id)


async def run_scheduler(node) -> None:
    while True:
        try:
            await tick(node)
        except Exception:
            logger.exception("scheduler tick failed")
        await asyncio.sleep(TICK_SECONDS)
