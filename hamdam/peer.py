"""Node-to-node link: signed HTTP calls, the outbox that survives outages,
and outage detection.

Two kinds of traffic:
- rpc      — synchronous request/response (a person on node A edits a circle
             that lives on node B). Fails fast during an outage; the person is
             told so and nothing half-happens.
- deliver / command — fire-and-forget, queued in the Outbox table and retried
             until the other node acknowledges. Alerts, summaries, voice notes
             and paid subscription extensions all travel this way, so an
             internet shutdown only delays them.
"""

import asyncio
import hashlib
import hmac
import json
import logging
import time
from datetime import timedelta

import aiohttp
from sqlalchemy import select

from hamdam.models import Membership, Outbox, PeerState, Person, aware, utcnow

logger = logging.getLogger(__name__)

MAX_SKEW_SECONDS = 300
# A peer unreachable this long is announced as an outage to the people it affects.
OUTAGE_AFTER = timedelta(minutes=5)
HEARTBEAT_SECONDS = 60
FLUSH_SECONDS = 10


class PeerUnavailable(Exception):
    pass


class ServiceError(Exception):
    """A refused operation (bad code, not a member, ...). `code` maps to a
    user-facing text in hamdam/texts.py."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def sign(key: str, node_id: str, ts: str, body: bytes) -> str:
    return hmac.new(key.encode(), f"{node_id}.{ts}.".encode() + body, hashlib.sha256).hexdigest()


def verify_signature(key: str, node_id: str, ts: str, body: bytes, signature: str) -> bool:
    try:
        if abs(time.time() - int(ts)) > MAX_SKEW_SECONDS:
            return False
    except ValueError:
        return False
    return hmac.compare_digest(sign(key, node_id, ts, body), signature or "")


class HttpTransport:
    def __init__(self, config):
        self.config = config

    async def send(self, peer: str, message: dict) -> dict:
        url = self.config.peers.get(peer)
        if not url:
            raise PeerUnavailable(f"unknown peer {peer}")
        body = json.dumps(message).encode()
        ts = str(int(time.time()))
        headers = {
            "Content-Type": "application/json",
            "X-Hamdam-Node": self.config.node_id,
            "X-Hamdam-Ts": ts,
            "X-Hamdam-Sig": sign(self.config.peer_key, self.config.node_id, ts, body),
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{url}/peer", data=body, headers=headers, timeout=aiohttp.ClientTimeout(total=20)
                ) as resp:
                    if resp.status != 200:
                        raise PeerUnavailable(f"{peer} answered HTTP {resp.status}")
                    return await resp.json()
        except PeerUnavailable:
            raise
        except Exception as exc:  # DNS, timeout, reset — all look the same during a shutdown
            raise PeerUnavailable(str(exc)) from exc


class LocalTransport:
    """In-process transport for tests: nodes call each other directly, and a
    test can cut the link with `network.down.add(node_id)`."""

    def __init__(self, network: "LocalNetwork", node_id: str):
        self.network = network
        self.node_id = node_id

    async def send(self, peer: str, message: dict) -> dict:
        if peer in self.network.down or self.node_id in self.network.down or peer not in self.network.nodes:
            raise PeerUnavailable(peer)
        return await self.network.nodes[peer].handle_peer(self.node_id, json.loads(json.dumps(message)))


class LocalNetwork:
    def __init__(self):
        self.nodes = {}
        self.down: set[str] = set()


# --- Outbox ------------------------------------------------------------------


async def flush_outbox(node) -> None:
    now = utcnow()
    for peer in node.config.peers:
        async with node.session() as s:
            rows = (
                await s.execute(
                    select(Outbox)
                    .where(Outbox.peer == peer, Outbox.delivered_at.is_(None), Outbox.next_try_at <= now)
                    .order_by(Outbox.id)
                    .limit(50)
                )
            ).scalars().all()
            for row in rows:
                message = {"kind": row.kind, "msg_id": row.msg_id, **json.loads(row.payload)}
                try:
                    resp = await node.transport.send(peer, message)
                    if not resp.get("ok"):
                        # The peer understood but refused (e.g. chat no longer
                        # exists). Retrying won't help; keep the row for audit.
                        logger.warning("outbox %s refused by %s: %s", row.msg_id, peer, resp)
                    row.delivered_at = utcnow()
                except PeerUnavailable:
                    row.attempts += 1
                    row.next_try_at = utcnow() + timedelta(seconds=min(300, 5 * 2 ** min(row.attempts, 6)))
                    await s.commit()
                    await peer_failed(node, peer)
                    break  # keep order; try this peer again later
                await s.commit()
            else:
                if rows:
                    await peer_ok(node, peer)


async def heartbeat(node) -> None:
    for peer in node.config.peers:
        try:
            await node.transport.send(peer, {"kind": "ping"})
            await peer_ok(node, peer)
        except PeerUnavailable:
            await peer_failed(node, peer)


async def _state(s, peer: str) -> PeerState:
    state = await s.get(PeerState, peer)
    if state is None:
        state = PeerState(peer=peer)
        s.add(state)
    return state


async def peer_ok(node, peer: str) -> None:
    async with node.session() as s:
        state = await _state(s, peer)
        was_announced = state.outage_announced
        state.last_ok_at = utcnow()
        state.failing_since = None
        state.outage_announced = False
        await s.commit()
    if was_announced:
        await _announce(node, peer, "outage_over")


async def peer_failed(node, peer: str) -> None:
    async with node.session() as s:
        state = await _state(s, peer)
        if state.failing_since is None:
            state.failing_since = utcnow()
        announce = not state.outage_announced and utcnow() - aware(state.failing_since) >= OUTAGE_AFTER
        if announce:
            state.outage_announced = True
        await s.commit()
    if announce:
        await _announce(node, peer, "outage_started")


async def is_peer_down(node, peer: str) -> bool:
    if peer == node.id:
        return False
    async with node.session() as s:
        state = await s.get(PeerState, peer)
    return bool(state and state.failing_since)


async def _announce(node, peer: str, key: str) -> None:
    """Tells the people on THIS node whose parent lives on `peer` what is
    going on — once per outage, instead of a flood of "no answer" alarms."""
    from hamdam.texts import t

    async with node.session() as s:
        rows = (
            await s.execute(
                select(Membership.channel, Membership.chat_id).where(Membership.home_node == peer).distinct()
            )
        ).all()
        langs = {
            (p.channel, p.chat_id): p.lang
            for p in (await s.execute(select(Person))).scalars().all()
        }
    for channel, chat_id in rows:
        lang = langs.get((channel, chat_id), "fa")
        await node.deliver(node.id, channel, chat_id, t(lang, key, place=node.config.label(peer, lang)))


async def run_link_loops(node) -> None:
    async def flush_loop():
        while True:
            try:
                await flush_outbox(node)
            except Exception:
                logger.exception("outbox flush failed")
            await asyncio.sleep(FLUSH_SECONDS)

    async def heartbeat_loop():
        while True:
            try:
                await heartbeat(node)
            except Exception:
                logger.exception("heartbeat failed")
            await asyncio.sleep(HEARTBEAT_SECONDS)

    if node.config.peers:
        await asyncio.gather(flush_loop(), heartbeat_loop())
