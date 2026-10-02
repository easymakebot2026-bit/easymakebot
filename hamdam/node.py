"""The Node object ties one deployment together: its database, the channels
it can send through, and its link to the other nodes. Handlers, the
scheduler and the web server all receive it instead of reaching for module
globals, which is also what lets the tests run two nodes in one process."""

import base64
import json
import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from hamdam.config import NodeConfig
from hamdam.messaging import Button, Buttons, Messenger
from hamdam.models import Base, InboxSeen, Outbox
from hamdam.peer import HttpTransport, PeerUnavailable, ServiceError

logger = logging.getLogger(__name__)


def _buttons_to_json(buttons: Buttons) -> list | None:
    return [[[b.text, b.data] for b in row] for row in buttons] if buttons else None


def _buttons_from_json(raw: list | None) -> Buttons:
    return [[Button(text, data) for text, data in row] for row in raw] if raw else None


class Node:
    def __init__(self, config: NodeConfig, transport=None):
        self.config = config
        self.engine = create_async_engine(config.database_url, echo=False)
        self.session = async_sessionmaker(self.engine, expire_on_commit=False, class_=AsyncSession)
        self.messengers: dict[str, Messenger] = {}
        self.transport = transport or HttpTransport(config)

    @property
    def id(self) -> str:
        return self.config.node_id

    async def init_db(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    # --- Calling the node that owns a circle -------------------------------

    async def call(self, home: str, method: str, **params):
        """Runs a service method on the circle's home node — directly when
        that's us, otherwise as a signed RPC. Raises ServiceError for a
        refusal and PeerUnavailable when the other node can't be reached."""
        from hamdam import services

        if home == self.id:
            return await services.RPC[method](self, origin=self.id, **params)
        resp = await self.transport.send(home, {"kind": "rpc", "method": method, "params": params})
        if not resp.get("ok"):
            raise ServiceError(resp.get("error") or "failed")
        return resp.get("result")

    async def command(self, target: str, name: str, **params) -> None:
        """Like call(), but queued and guaranteed: used for things that must
        happen eventually even across an outage (a paid extension)."""
        from hamdam import services

        if target == self.id:
            await services.COMMANDS[name](self, **params)
        else:
            await self.enqueue(target, "command", {"name": name, "params": params})

    # --- Reaching a person, wherever their chat lives ------------------------

    async def deliver(
        self, target_node: str, channel: str, chat_id: str, text: str,
        buttons: Buttons = None, voice: bytes | None = None,
    ) -> bool | None:
        """True/False = sent/failed right now; None = queued for another node."""
        if target_node != self.id:
            payload = {"channel": channel, "chat_id": chat_id, "text": text, "buttons": _buttons_to_json(buttons)}
            if voice:
                payload["voice"] = base64.b64encode(voice).decode()
            await self.enqueue(target_node, "deliver", payload)
            return None
        messenger = self.messengers.get(channel)
        if messenger is None:
            logger.warning("no %s channel on node %s; dropping message to %s", channel, self.id, chat_id)
            return False
        if voice:
            return await messenger.send_voice(chat_id, voice, text)
        return await messenger.send_text(chat_id, text, buttons)

    async def enqueue(self, peer: str, kind: str, payload: dict) -> None:
        async with self.session() as s:
            s.add(Outbox(msg_id=uuid.uuid4().hex, peer=peer, kind=kind, payload=json.dumps(payload)))
            await s.commit()

    # --- Incoming from another node ------------------------------------------

    async def handle_peer(self, sender: str, message: dict) -> dict:
        from hamdam import services

        kind = message.get("kind")
        if kind == "ping":
            return {"ok": True}
        if kind == "rpc":
            method = services.RPC.get(message.get("method") or "")
            if method is None:
                return {"ok": False, "error": "unknown_method"}
            try:
                result = await method(self, origin=sender, **(message.get("params") or {}))
                return {"ok": True, "result": result}
            except ServiceError as exc:
                return {"ok": False, "error": exc.code}
            except PeerUnavailable:
                return {"ok": False, "error": "peer_unavailable"}

        msg_id = message.get("msg_id")
        if not msg_id:
            return {"ok": False, "error": "missing_msg_id"}
        async with self.session() as s:
            if await s.get(InboxSeen, msg_id):
                return {"ok": True, "duplicate": True}

        if kind == "deliver":
            voice = base64.b64decode(message["voice"]) if message.get("voice") else None
            await self.deliver(
                self.id, message["channel"], message["chat_id"], message["text"],
                _buttons_from_json(message.get("buttons")), voice,
            )
        elif kind == "command":
            handler = services.COMMANDS.get(message.get("name") or "")
            if handler is None:
                return {"ok": False, "error": "unknown_command"}
            await handler(self, **(message.get("params") or {}))
        else:
            return {"ok": False, "error": "unknown_kind"}

        async with self.session() as s:
            s.add(InboxSeen(msg_id=msg_id))
            await s.commit()
        return {"ok": True}
