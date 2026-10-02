"""Database tables. Each node has its own database; nothing is shared.

Ownership rule: a care circle lives on its elder's *home node* (the node
whose messenger the elder uses). Circle, Member, Medication and Event rows
exist only there. Every other node only keeps a Membership row per chat, so
it can list "your parents" and route the person's actions to the home node.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def aware(dt: datetime | None) -> datetime | None:
    """SQLite hands back naive datetimes; everything here is stored as UTC."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class Base(DeclarativeBase):
    pass


# --- Home-node data ---------------------------------------------------------


class Circle(Base):
    """One elder and everyone looking after them."""

    __tablename__ = "circles"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    elder_name: Mapped[str] = mapped_column(String(100))  # what the family calls them
    elder_title: Mapped[str] = mapped_column(String(100))  # how the bot addresses them
    lang: Mapped[str] = mapped_column(String(5), default="fa")
    tz: Mapped[str] = mapped_column(String(64))
    checkin_time: Mapped[str] = mapped_column(String(5), default="10:00")
    summary_time: Mapped[str] = mapped_column(String(5), default="21:00")
    elder_code: Mapped[str | None] = mapped_column(String(16), unique=True, nullable=True)
    family_code: Mapped[str] = mapped_column(String(32), unique=True)
    elder_channel: Mapped[str | None] = mapped_column(String(16), nullable=True)
    elder_chat_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    elder_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    paid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    paused: Mapped[bool] = mapped_column(Boolean, default=False)
    expiry_notified: Mapped[bool] = mapped_column(Boolean, default=False)
    last_summary_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Member(Base):
    """Someone who receives news about a circle. `node` is where their chat
    lives — messages to a member on another node travel through the outbox.
    role: 'family' (full access) | 'local' (a neighbour/relative near the
    elder who is only alerted; always on the home node, usually by SMS)."""

    __tablename__ = "members"
    __table_args__ = (UniqueConstraint("circle_id", "node", "channel", "chat_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    circle_id: Mapped[str] = mapped_column(ForeignKey("circles.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(10), default="family")
    name: Mapped[str] = mapped_column(String(100), default="")
    node: Mapped[str] = mapped_column(String(16))
    channel: Mapped[str] = mapped_column(String(16))
    chat_id: Mapped[str] = mapped_column(String(64))
    lang: Mapped[str] = mapped_column(String(5), default="fa")


class Medication(Base):
    __tablename__ = "medications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    circle_id: Mapped[str] = mapped_column(ForeignKey("circles.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    time: Mapped[str] = mapped_column(String(5))


class Event(Base):
    """One scheduled touchpoint: the daily check-in or one medication dose.
    status: pending -> ok | concern, or missed (no answer in time) /
    undelivered (the elder's messenger couldn't be reached at all)."""

    __tablename__ = "events"
    __table_args__ = (UniqueConstraint("circle_id", "slot", "local_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    circle_id: Mapped[str] = mapped_column(ForeignKey("circles.id", ondelete="CASCADE"), index=True)
    slot: Mapped[str] = mapped_column(String(32))  # "checkin" | "med:<id>"
    label: Mapped[str] = mapped_column(String(100), default="")
    local_date: Mapped[str] = mapped_column(String(10))
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reminded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    escalated: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(12), default="pending")
    response: Mapped[str | None] = mapped_column(Text, nullable=True)


# --- Per-chat data on the person's own node ----------------------------------


class Person(Base):
    __tablename__ = "people"
    __table_args__ = (UniqueConstraint("channel", "chat_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel: Mapped[str] = mapped_column(String(16))
    chat_id: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(100), default="")
    lang: Mapped[str] = mapped_column(String(5), default="fa")


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("channel", "chat_id", "circle_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel: Mapped[str] = mapped_column(String(16))
    chat_id: Mapped[str] = mapped_column(String(64))
    circle_id: Mapped[str] = mapped_column(String(32))
    home_node: Mapped[str] = mapped_column(String(16))
    elder_name: Mapped[str] = mapped_column(String(100))


class Payment(Base):
    """Recorded on the PAYER's node (that's where the gateway is); the
    resulting subscription extension is sent to the circle's home node."""

    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    circle_id: Mapped[str] = mapped_column(String(32))
    home_node: Mapped[str] = mapped_column(String(16))
    payer_channel: Mapped[str] = mapped_column(String(16))
    payer_chat_id: Mapped[str] = mapped_column(String(64))
    method: Mapped[str] = mapped_column(String(16))  # zarinpal | ton
    days: Mapped[int] = mapped_column(Integer)
    amount: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(8))  # toman | usd
    status: Mapped[str] = mapped_column(String(12), default="pending")
    authority: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# --- Node-to-node plumbing ----------------------------------------------------


class Outbox(Base):
    """Messages for another node, kept until that node acknowledges them —
    this is what carries news across an internet shutdown: nothing is lost,
    it just arrives late."""

    __tablename__ = "outbox"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    msg_id: Mapped[str] = mapped_column(String(40), unique=True)
    peer: Mapped[str] = mapped_column(String(16), index=True)
    kind: Mapped[str] = mapped_column(String(16))  # deliver | command
    payload: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_try_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class InboxSeen(Base):
    """Idempotency: a retried outbox message is applied once."""

    __tablename__ = "inbox_seen"

    msg_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PeerState(Base):
    __tablename__ = "peer_state"

    peer: Mapped[str] = mapped_column(String(16), primary_key=True)
    last_ok_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failing_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    outage_announced: Mapped[bool] = mapped_column(Boolean, default=False)
