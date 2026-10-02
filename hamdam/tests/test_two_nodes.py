"""End-to-end: a mother in Iran (Bale, `ir` node) and her son abroad
(Telegram, `global` node), including an internet shutdown between them and a
TON payment made abroad. Two real nodes in one process, SQLite databases,
fake messengers; the link between them can be cut at will."""

import asyncio
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from hamdam import billing, scheduler, services
from hamdam.config import NodeConfig
from hamdam.messaging import Messenger
from hamdam.models import Circle, Membership, Person, PeerState
from hamdam.node import Node
from hamdam.peer import LocalNetwork, LocalTransport, PeerUnavailable, flush_outbox, heartbeat

TEHRAN = ZoneInfo("Asia/Tehran")


class FakeMessenger(Messenger):
    def __init__(self, name):
        self.name = name
        self.sent = []  # (chat_id, text, buttons, voice)

    async def send_text(self, chat_id, text, buttons=None):
        self.sent.append((chat_id, text, buttons, None))
        return True

    async def send_voice(self, chat_id, data, caption):
        self.sent.append((chat_id, caption, None, data))
        return True

    def to(self, chat_id):
        return [s for s in self.sent if s[0] == chat_id]


def make_node(tmp_path, network, node_id, peer_id, **extra) -> Node:
    cfg = NodeConfig(node_id=node_id, database_url=f"sqlite+aiosqlite:///{tmp_path}/{node_id}.db",
                     peers={peer_id: "http://unused"}, peer_key="k",
                     node_labels={"ir": {"en": "Iran", "fa": "ایران"}, "global": {"en": "Abroad", "fa": "خارج"}},
                     **extra)
    node = Node(cfg, transport=LocalTransport(network, node_id))
    network.nodes[node_id] = node
    return node


def tehran(day, h, m):
    return datetime(2026, 10, day, h, m, tzinfo=TEHRAN).astimezone(timezone.utc)


@pytest.fixture
def world(tmp_path):
    network = LocalNetwork()
    ir = make_node(tmp_path, network, "ir", "global", elder_channel="bale")
    glob = make_node(tmp_path, network, "global", "ir", elder_channel="telegram",
                     ton_wallet="UQ-test-wallet", admin_channel="telegram", admin_chat_id="1")
    ir.messengers = {"bale": FakeMessenger("bale"), "sms": FakeMessenger("sms")}
    glob.messengers = {"telegram": FakeMessenger("telegram")}

    async def setup():
        await ir.init_db()
        await glob.init_db()
    asyncio.run(setup())
    return network, ir, glob


SON = {"node": "global", "channel": "telegram", "chat_id": "42"}


def test_full_story(world):
    network, ir, glob = world
    tg, bale, sms = glob.messengers["telegram"], ir.messengers["bale"], ir.messengers["sms"]

    async def story():
        async with glob.session() as s:
            s.add(Person(channel="telegram", chat_id="42", name="Ali", lang="fa"))
            await s.commit()

        # Son (abroad) adds his mother, who lives in Iran -> circle is created ON THE IR NODE.
        info = await glob.call("ir", "create_circle", requester=SON, name="Ali", lang="fa",
                               elder_name="مامان", elder_title="مادر عزیز", elder_lang="fa",
                               tz="Asia/Tehran", checkin_time="10:00")
        assert info["elder_channel"] == "bale"
        async with glob.session() as s:
            s.add(Membership(channel="telegram", chat_id="42", circle_id=info["circle_id"],
                             home_node="ir", elder_name="مامان"))
            await s.commit()
        cid = info["circle_id"]

        # Mother opens Bale and sends the code.
        circle = await services.link_elder(ir, "bale", "500", info["elder_code"])
        assert circle is not None
        await flush_outbox(ir)
        assert any("وصل شد" in s[1] for s in tg.to("42"))

        await glob.call("ir", "add_med", requester=SON, circle_id=cid, name="قرص فشار", time="10:30")
        await glob.call("ir", "add_local_contact", requester=SON, circle_id=cid, name="همسایه",
                        phone="09120000000")

        # Day 1, 10:05 Tehran: check-in goes out on Bale with buttons.
        await scheduler.tick(ir, tehran(1, 10, 5))
        checkin = bale.to("500")[-1]
        assert "حالتان چطور است" in checkin[1] and checkin[2]
        # She writes back something worrying -> forwarded as a concern.
        circle = await services.elder_circle(ir, "bale", "500")
        assert await services.elder_said(ir, circle, text="امروز سرم گیج میره") == "concern"
        await flush_outbox(ir)
        assert any("⚠️" in s[1] and "سرم گیج" in s[1] for s in tg.to("42"))

        # 10:30 medicine reminder; no answer until 12:05 -> family told.
        await scheduler.tick(ir, tehran(1, 10, 31))
        assert "قرص فشار" in bale.to("500")[-1][1]
        await scheduler.tick(ir, tehran(1, 12, 5))
        await flush_outbox(ir)
        assert any("قرص فشار" in s[1] and "تأیید نکرده" in s[1] for s in tg.to("42"))
        assert sms.sent == []  # family was reachable -> neighbour not bothered

        # --- Day 2: the international link is cut. ---
        network.down.add("ir")
        with pytest.raises(PeerUnavailable):
            await glob.call("ir", "circle_view", requester=SON, circle_id=cid)

        await scheduler.tick(ir, tehran(2, 10, 5))  # check-in still goes out domestically
        assert "حالتان چطور است" in bale.to("500")[-1][1]
        await heartbeat(ir)  # fails -> ir marks global as unreachable
        await scheduler.tick(ir, tehran(2, 11, 40))  # 95 min, no answer
        # Family is behind the cut link -> the neighbour gets an SMS inside Iran.
        assert len(sms.to("09120000000")) == 1
        assert "مادر عزیز" in sms.to("09120000000")[0][1]

        # Abroad, the son gets ONE calm outage notice, not an alarm.
        await heartbeat(glob)
        async with glob.session() as s:
            (await s.get(PeerState, "ir")).failing_since = datetime.now(timezone.utc) - timedelta(minutes=10)
            await s.commit()
        before = len(tg.to("42"))
        await heartbeat(glob)
        await heartbeat(glob)
        notices = tg.to("42")[before:]
        assert len(notices) == 1 and "قطع شده" in notices[0][1]

        # Link back: queued news arrives, plus an "all clear".
        network.down.clear()
        await heartbeat(glob)
        await flush_outbox(ir)
        texts = [s[1] for s in tg.to("42")]
        assert any("برقرار شد" in x for x in texts)
        assert any("جواب نداده" in x for x in texts)  # the missed check-in, delivered late

        # --- Son pays with TON abroad; the extension lands on the ir node. ---
        async with ir.session() as s:
            before_until = (await s.get(Circle, cid)).paid_until
        payment = await billing.create_payment(glob, cid, "ir", "telegram", "42", "m1", "ton")
        assert payment.amount == 12 and payment.currency == "usd"
        await billing.submit_ton(glob, payment.id, "txhash123")
        assert "TON payment" in tg.to("1")[-1][1]  # admin review request
        assert await billing.approve_ton(glob, payment.id)
        assert not await billing.approve_ton(glob, payment.id)  # double tap is harmless
        await flush_outbox(glob)
        async with ir.session() as s:
            after_until = (await s.get(Circle, cid)).paid_until
        assert after_until - before_until == timedelta(days=30)
        await flush_outbox(ir)
        assert any("تمدید شد" in s[1] for s in tg.to("42"))

        # A stranger can't read the circle.
        stranger = {"node": "global", "channel": "telegram", "chat_id": "999"}
        with pytest.raises(Exception):
            await glob.call("ir", "circle_view", requester=stranger, circle_id=cid)
        # ...and a node can't speak for another node's chats.
        resp = await ir.handle_peer("global", {"kind": "rpc", "method": "circle_view",
                                               "params": {"requester": {**SON, "node": "ir"}, "circle_id": cid}})
        assert resp == {"ok": False, "error": "forbidden"}

    asyncio.run(story())


def test_sibling_in_iran_joins(world):
    """Mixed family: mother abroad (global home), one child abroad, one in Iran on Bale."""
    network, ir, glob = world

    async def story():
        info = await glob.call("global", "create_circle", requester=SON, name="Ali", lang="fa",
                               elder_name="مامان", elder_title="مادر عزیز", elder_lang="fa",
                               tz="Europe/Berlin", checkin_time="09:00")
        sister = {"node": "ir", "channel": "bale", "chat_id": "77"}
        joined = await ir.call("global", "join_circle", requester=sister, name="Sara", lang="fa",
                               family_code=info["family_code"])
        assert joined["circle_id"] == info["circle_id"]
        await flush_outbox(glob)  # nothing for ir yet; Ali (local) was told directly
        assert any("Sara" in s[1] for s in glob.messengers["telegram"].to("42"))

        await services.link_elder(glob, "telegram", "600", info["elder_code"])
        await flush_outbox(glob)
        assert any("وصل شد" in s[1] for s in ir.messengers["bale"].to("77"))

    asyncio.run(story())
