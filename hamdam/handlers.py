"""Chat handlers — one router serves every channel on the node (Telegram,
Bale). The `channel` and `node` arguments are injected by main.py.

Who is talking decides the flow:
  1. a linked elder          -> the gentle elder flow (buttons, free text, voice)
  2. the payment admin       -> approve/reject buttons
  3. everyone else           -> the family menu
"""

import logging

from aiogram import F, Router
from aiogram.filters import BaseFilter, Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy import delete, select

from hamdam import billing, logic, services
from hamdam.messaging import Button, to_markup
from hamdam.models import Membership, Person
from hamdam.peer import PeerUnavailable, ServiceError
from hamdam.texts import STATUS_ICON, t

logger = logging.getLogger(__name__)
router = Router()


class AddFlow(StatesGroup):
    elder_name = State()
    elder_title = State()
    tz = State()
    time = State()


class MedFlow(StatesGroup):
    name = State()
    time = State()


class LocalFlow(StatesGroup):
    name = State()
    phone = State()


class SetFlow(StatesGroup):
    value = State()


class JoinFlow(StatesGroup):
    code = State()


class TonFlow(StatesGroup):
    tx = State()


# --- helpers -------------------------------------------------------------------


def _me(node, channel: str, chat_id) -> dict:
    return {"node": node.id, "channel": channel, "chat_id": str(chat_id)}


def _kb(rows):
    return to_markup([[Button(text, data) for text, data in row] for row in rows])


async def _person(node, channel: str, chat_id: str) -> Person | None:
    async with node.session() as s:
        return (await s.execute(select(Person).where(Person.channel == channel, Person.chat_id == chat_id))
                ).scalar_one_or_none()


async def _lang(node, channel: str, chat_id) -> str:
    return await services.person_lang(node, channel, str(chat_id)) or "fa"


async def _home_of(node, channel: str, chat_id: str, circle_id: str) -> str | None:
    async with node.session() as s:
        m = (await s.execute(select(Membership).where(
            Membership.channel == channel, Membership.chat_id == chat_id, Membership.circle_id == circle_id))
        ).scalar_one_or_none()
        return m.home_node if m else None


async def _remember(node, channel: str, chat_id: str, circle_id: str, home: str, elder_name: str) -> None:
    async with node.session() as s:
        exists = (await s.execute(select(Membership).where(
            Membership.channel == channel, Membership.chat_id == chat_id, Membership.circle_id == circle_id))
        ).scalar_one_or_none()
        if exists is None:
            s.add(Membership(channel=channel, chat_id=chat_id, circle_id=circle_id, home_node=home,
                             elder_name=elder_name))
            await s.commit()


async def _safe(lang: str, target: Message, coro) -> tuple[bool, object]:
    """Runs a (possibly cross-node) call. Returns (ok, result); on failure the
    person has already been told why — e.g. that the other side of a cut
    link can't be reached right now."""
    try:
        return True, await coro
    except PeerUnavailable:
        await target.answer(t(lang, "err_peer_down"))
    except ServiceError as exc:
        await target.answer(t(lang, f"err_{exc.code}") or t(lang, "err_failed"))
    return False, None


async def show_menu(message: Message, lang: str) -> None:
    await message.answer(t(lang, "menu"), reply_markup=_kb([
        [(t(lang, "btn_add"), "menu:add")],
        [(t(lang, "btn_list"), "menu:list")],
        [(t(lang, "btn_join"), "menu:join")],
        [(t(lang, "btn_lang"), "menu:lang")],
    ]))


# --- filters ----------------------------------------------------------------------


class IsElder(BaseFilter):
    async def __call__(self, event, node, channel) -> bool | dict:
        chat = event.message.chat if isinstance(event, CallbackQuery) else event.chat
        circle = await services.elder_circle(node, channel, str(chat.id))
        return {"circle": circle} if circle else False


class IsAdmin(BaseFilter):
    async def __call__(self, event: CallbackQuery, node, channel) -> bool:
        return channel == node.config.admin_channel and str(event.from_user.id) == str(node.config.admin_chat_id)


# --- elder ------------------------------------------------------------------------


@router.callback_query(F.data.regexp(r"^(ok|bad|took):\d+$"), IsElder())
async def elder_button(cb: CallbackQuery, node, circle) -> None:
    action, event_id = cb.data.split(":")
    status = "concern" if action == "bad" else "ok"
    event = await services.answer_event(node, circle, int(event_id), status)
    await cb.answer()
    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    if event is None:
        return
    if action == "bad":
        await cb.message.answer(t(circle.lang, "elder_sorry", title=circle.elder_title))
        await services.notify(node, circle, "alert_said_unwell")
    else:
        await cb.message.answer(t(circle.lang, "elder_thanks" if action == "ok" else "elder_med_ok",
                                  title=circle.elder_title))


@router.message(IsElder(), F.voice | F.audio)
async def elder_voice(message: Message, node, channel, circle) -> None:
    media = message.voice or message.audio
    data = await node.messengers[channel].download(media.file_id)
    await services.elder_said(node, circle, voice=data or None, text=None if data else "🎙 (voice)")
    await message.answer(t(circle.lang, "elder_got_it", title=circle.elder_title))


@router.message(IsElder(), F.text)
async def elder_text(message: Message, node, circle) -> None:
    if message.text.startswith("/"):
        await message.answer(t(circle.lang, "elder_welcome", title=circle.elder_title))
        return
    level = await services.elder_said(node, circle, text=message.text)
    key = {"urgent": "elder_got_urgent", "concern": "elder_got_concern"}.get(level, "elder_got_it")
    await message.answer(t(circle.lang, key, title=circle.elder_title))


# --- admin --------------------------------------------------------------------------


@router.callback_query(F.data.regexp(r"^adm_(ok|no):\d+$"), IsAdmin())
async def admin_review(cb: CallbackQuery, node) -> None:
    action, pid = cb.data.split(":")
    done = await (billing.approve_ton if action == "adm_ok" else billing.reject_ton)(node, int(pid))
    await cb.answer("done" if done else "already handled")
    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass


# --- start / language / linking -------------------------------------------------------


async def _try_link_elder(message: Message, node, channel: str, code: str) -> bool:
    if channel != node.config.elder_channel:
        return False
    circle = await services.link_elder(node, channel, str(message.chat.id), code)
    if circle is None:
        return False
    await message.answer(t(circle.lang, "elder_welcome", title=circle.elder_title))
    return True


@router.message(CommandStart())
async def start(message: Message, command: CommandObject, state: FSMContext, node, channel) -> None:
    await state.clear()
    payload = (command.args or "").strip()
    if payload.startswith("e") and logic.looks_like_elder_code(payload[1:]):
        if await _try_link_elder(message, node, channel, payload[1:]):
            return
        await message.answer(t("fa", "err_bad_code"))
        return
    person = await _person(node, channel, str(message.chat.id))
    if person is None:
        await message.answer(t("fa", "choose_lang") + "\n" + t("en", "choose_lang"),
                             reply_markup=_kb([[("فارسی", "lang:fa"), ("English", "lang:en")]]))
        return
    await show_menu(message, person.lang)


@router.callback_query(F.data == "menu:lang")
async def ask_lang(cb: CallbackQuery) -> None:
    await cb.answer()
    await cb.message.answer(t("fa", "choose_lang") + "\n" + t("en", "choose_lang"),
                            reply_markup=_kb([[("فارسی", "lang:fa"), ("English", "lang:en")]]))


@router.callback_query(F.data.in_({"lang:fa", "lang:en"}))
async def set_lang(cb: CallbackQuery, node, channel) -> None:
    lang = cb.data.split(":")[1]
    chat_id = str(cb.message.chat.id)
    async with node.session() as s:
        person = (await s.execute(select(Person).where(Person.channel == channel, Person.chat_id == chat_id))
                  ).scalar_one_or_none()
        if person is None:
            s.add(Person(channel=channel, chat_id=chat_id, name=cb.from_user.full_name[:100], lang=lang))
        else:
            person.lang = lang
        await s.commit()
    await cb.answer()
    await cb.message.answer(t(lang, "welcome"))
    await show_menu(cb.message, lang)


@router.message(Command("menu"))
@router.message(Command("cancel"))
async def menu_cmd(message: Message, state: FSMContext, node, channel) -> None:
    await state.clear()
    await show_menu(message, await _lang(node, channel, message.chat.id))


# --- add a parent ------------------------------------------------------------------------


@router.callback_query(F.data == "menu:add")
async def add_start(cb: CallbackQuery, node, channel) -> None:
    lang = await _lang(node, channel, cb.message.chat.id)
    await cb.answer()
    rows = [[(node.config.label(n, lang), f"where:{n}")] for n in node.config.all_nodes]
    await cb.message.answer(t(lang, "ask_where"), reply_markup=_kb(rows))


@router.callback_query(F.data.startswith("where:"))
async def add_where(cb: CallbackQuery, state: FSMContext, node, channel) -> None:
    lang = await _lang(node, channel, cb.message.chat.id)
    home = cb.data.split(":", 1)[1]
    if home not in node.config.all_nodes:
        await cb.answer()
        return
    await state.set_state(AddFlow.elder_name)
    await state.update_data(home=home)
    await cb.answer()
    await cb.message.answer(t(lang, "ask_elder_name"))


@router.message(AddFlow.elder_name, F.text)
async def add_elder_name(message: Message, state: FSMContext, node, channel) -> None:
    lang = await _lang(node, channel, message.chat.id)
    await state.update_data(elder_name=message.text.strip()[:100])
    await state.set_state(AddFlow.elder_title)
    await message.answer(t(lang, "ask_elder_title"))


@router.message(AddFlow.elder_title, F.text)
async def add_elder_title(message: Message, state: FSMContext, node, channel) -> None:
    lang = await _lang(node, channel, message.chat.id)
    await state.update_data(elder_title=message.text.strip()[:100])
    await state.set_state(AddFlow.tz)
    await message.answer(t(lang, "ask_tz"), reply_markup=_kb(
        [[(name, f"tz:{name}")] for name in ("Asia/Tehran", "Europe/Berlin", "Europe/London",
                                              "America/Toronto", "America/Los_Angeles", "Australia/Sydney")]
    ))


async def _after_tz(target: Message, state: FSMContext, lang: str, tz: str) -> None:
    await state.update_data(tz=tz)
    await state.set_state(AddFlow.time)
    await target.answer(t(lang, "ask_checkin_time"))


@router.callback_query(AddFlow.tz, F.data.startswith("tz:"))
async def add_tz_button(cb: CallbackQuery, state: FSMContext, node, channel) -> None:
    await cb.answer()
    await _after_tz(cb.message, state, await _lang(node, channel, cb.message.chat.id), cb.data[3:])


@router.message(AddFlow.tz, F.text)
async def add_tz_text(message: Message, state: FSMContext, node, channel) -> None:
    lang = await _lang(node, channel, message.chat.id)
    tz = message.text.strip()
    if not logic.valid_tz(tz):
        await message.answer(t(lang, "err_tz"))
        return
    await _after_tz(message, state, lang, tz)


@router.message(AddFlow.time, F.text)
async def add_time(message: Message, state: FSMContext, node, channel) -> None:
    lang = await _lang(node, channel, message.chat.id)
    hhmm = logic.parse_hhmm(message.text)
    if hhmm is None:
        await message.answer(t(lang, "err_time"))
        return
    data = await state.get_data()
    await state.clear()
    person = await _person(node, channel, str(message.chat.id))
    ok, result = await _safe(lang, message, node.call(
        data["home"], "create_circle", requester=_me(node, channel, message.chat.id),
        name=person.name if person else "", lang=lang, elder_name=data["elder_name"],
        elder_title=data["elder_title"], elder_lang=lang, tz=data["tz"], checkin_time=hhmm,
    ))
    if not ok:
        return
    await _remember(node, channel, str(message.chat.id), result["circle_id"], data["home"], result["elder_name"])
    await message.answer(t(lang, "circle_created", elder=result["elder_name"], days=result["trial_days"]))
    await message.answer(_invite_text(lang, result, data["home"], node))
    await _send_circle(message, node, channel, result["circle_id"], lang)


def _invite_text(lang: str, info: dict, home: str, node) -> str:
    app = "Bale" if info.get("elder_channel") == "bale" else "Telegram"
    if lang == "fa":
        app = "بله" if app == "Bale" else "تلگرام"
    text = t(lang, "invite_elder", app=app, code=info.get("elder_code") or "—")
    if info.get("elder_link"):
        text += "\n" + info["elder_link"]
    text += "\n\n" + t(lang, "invite_family", code=info["family_code"])
    return text


# --- join with a family code -------------------------------------------------------------


@router.callback_query(F.data == "menu:join")
async def join_start(cb: CallbackQuery, state: FSMContext, node, channel) -> None:
    await cb.answer()
    await state.set_state(JoinFlow.code)
    await cb.message.answer(t(await _lang(node, channel, cb.message.chat.id), "ask_family_code"))


@router.message(JoinFlow.code, F.text)
async def join_code(message: Message, state: FSMContext, node, channel) -> None:
    lang = await _lang(node, channel, message.chat.id)
    parsed = logic.split_family_code(message.text)
    if parsed is None or parsed[0] not in node.config.all_nodes:
        await message.answer(t(lang, "err_bad_code"))
        return
    await state.clear()
    home, code = parsed
    person = await _person(node, channel, str(message.chat.id))
    ok, result = await _safe(lang, message, node.call(
        home, "join_circle", requester=_me(node, channel, message.chat.id),
        name=person.name if person else "", lang=lang, family_code=code,
    ))
    if not ok:
        return
    await _remember(node, channel, str(message.chat.id), result["circle_id"], home, result["elder_name"])
    await _send_circle(message, node, channel, result["circle_id"], lang)


# --- circles ------------------------------------------------------------------------------


@router.callback_query(F.data == "menu:list")
async def list_circles(cb: CallbackQuery, node, channel) -> None:
    lang = await _lang(node, channel, cb.message.chat.id)
    await cb.answer()
    async with node.session() as s:
        rows = (await s.execute(select(Membership).where(
            Membership.channel == channel, Membership.chat_id == str(cb.message.chat.id)))).scalars().all()
    if not rows:
        await cb.message.answer(t(lang, "no_circles"))
        return
    await cb.message.answer(t(lang, "your_circles"), reply_markup=_kb(
        [[(f"👵 {m.elder_name} · {node.config.label(m.home_node, lang)}", f"c:{m.circle_id}")] for m in rows]
    ))


async def _view(node, channel: str, chat_id: str, circle_id: str, lang: str, target: Message):
    home = await _home_of(node, channel, chat_id, circle_id)
    if home is None:
        return None, None
    _, view = await _safe(lang, target, node.call(home, "circle_view", requester=_me(node, channel, chat_id),
                                                  circle_id=circle_id))
    return home, view


async def _send_circle(target: Message, node, channel: str, circle_id: str, lang: str) -> None:
    home, v = await _view(node, channel, str(target.chat.id), circle_id, lang, target)
    if v is None:
        return
    lines = [t(lang, "view_head", elder=v["elder_name"], place=node.config.label(home, lang))]
    lines.append(t(lang, "view_linked") if v["linked"] else t(lang, "view_not_linked"))
    lines.append(t(lang, "view_times", checkin=v["checkin_time"], summary=v["summary_time"], tz=v["tz"]))
    if v["meds"]:
        lines.append(t(lang, "view_meds") + " " + "، ".join(f"{m['name']} ({m['time']})" for m in v["meds"]))
    lines.append(t(lang, "view_days", days=v["days_left"]))
    if v["paused"]:
        lines.append(t(lang, "view_paused"))
    if v["today"]:
        lines.append(t(lang, "view_today") + " " + " · ".join(
            f"{STATUS_ICON.get(e['status'], '•')} {e['label']}" for e in v["today"]))
    cid = circle_id
    await target.answer("\n".join(lines), reply_markup=_kb([
        [(t(lang, "btn_meds"), f"cm:{cid}"), (t(lang, "btn_checkin_time"), f"ct:{cid}")],
        [(t(lang, "btn_summary_time"), f"cs:{cid}"), (t(lang, "btn_resume" if v["paused"] else "btn_pause"), f"cp:{cid}")],
        [(t(lang, "btn_locals"), f"cl:{cid}"), (t(lang, "btn_elder_phone"), f"ce:{cid}")],
        [(t(lang, "btn_invite"), f"ci:{cid}"), (t(lang, "btn_pay"), f"pay:{cid}")],
        [(t(lang, "btn_leave"), f"cx:{cid}")],
    ]))


@router.callback_query(F.data.startswith("c:"))
async def open_circle(cb: CallbackQuery, node, channel) -> None:
    await cb.answer()
    await _send_circle(cb.message, node, channel, cb.data[2:], await _lang(node, channel, cb.message.chat.id))


# Single-value settings share one text prompt.
_SETTINGS = {"ct": ("checkin_time", "ask_checkin_time"), "cs": ("summary_time", "ask_summary_time"),
             "ce": ("elder_phone", "ask_elder_phone")}


@router.callback_query(F.data.regexp(r"^(ct|cs|ce):[0-9a-f]{32}$"))
async def setting_start(cb: CallbackQuery, state: FSMContext, node, channel) -> None:
    prefix, cid = cb.data.split(":")
    field, prompt = _SETTINGS[prefix]
    await cb.answer()
    await state.set_state(SetFlow.value)
    await state.update_data(circle_id=cid, field=field)
    await cb.message.answer(t(await _lang(node, channel, cb.message.chat.id), prompt))


@router.message(SetFlow.value, F.text)
async def setting_value(message: Message, state: FSMContext, node, channel) -> None:
    lang = await _lang(node, channel, message.chat.id)
    data = await state.get_data()
    await state.clear()
    await _update(message, node, channel, lang, data["circle_id"], data["field"], message.text.strip())


async def _update(target: Message, node, channel, lang, cid, field, value) -> None:
    chat_id = str(target.chat.id)
    home = await _home_of(node, channel, chat_id, cid)
    if home is None:
        return
    ok, _ = await _safe(lang, target, node.call(home, "update_circle", requester=_me(node, channel, chat_id),
                                                circle_id=cid, field=field, value=value))
    if ok:
        await _send_circle(target, node, channel, cid, lang)


@router.callback_query(F.data.startswith("cp:"))
async def toggle_pause(cb: CallbackQuery, node, channel) -> None:
    lang = await _lang(node, channel, cb.message.chat.id)
    await cb.answer()
    cid = cb.data[3:]
    _, v = await _view(node, channel, str(cb.message.chat.id), cid, lang, cb.message)
    if v is not None:
        await _update(cb.message, node, channel, lang, cid, "paused", not v["paused"])


# --- medications ---------------------------------------------------------------------------


@router.callback_query(F.data.startswith("cm:"))
async def meds(cb: CallbackQuery, node, channel) -> None:
    lang = await _lang(node, channel, cb.message.chat.id)
    await cb.answer()
    cid = cb.data[3:]
    _, v = await _view(node, channel, str(cb.message.chat.id), cid, lang, cb.message)
    if v is None:
        return
    rows = [[(f"🗑 {m['name']} ({m['time']})", f"md:{cid}:{m['id']}")] for m in v["meds"]]
    rows.append([(t(lang, "btn_add_med"), f"ma:{cid}")])
    await cb.message.answer(t(lang, "meds_head"), reply_markup=_kb(rows))


@router.callback_query(F.data.startswith("ma:"))
async def med_add(cb: CallbackQuery, state: FSMContext, node, channel) -> None:
    await cb.answer()
    await state.set_state(MedFlow.name)
    await state.update_data(circle_id=cb.data[3:])
    await cb.message.answer(t(await _lang(node, channel, cb.message.chat.id), "ask_med_name"))


@router.message(MedFlow.name, F.text)
async def med_name(message: Message, state: FSMContext, node, channel) -> None:
    await state.update_data(name=message.text.strip()[:100])
    await state.set_state(MedFlow.time)
    await message.answer(t(await _lang(node, channel, message.chat.id), "ask_med_time"))


@router.message(MedFlow.time, F.text)
async def med_time(message: Message, state: FSMContext, node, channel) -> None:
    lang = await _lang(node, channel, message.chat.id)
    if logic.parse_hhmm(message.text) is None:
        await message.answer(t(lang, "err_time"))
        return
    data = await state.get_data()
    await state.clear()
    chat_id = str(message.chat.id)
    home = await _home_of(node, channel, chat_id, data["circle_id"])
    if home is None:
        return
    ok, _ = await _safe(lang, message, node.call(
        home, "add_med", requester=_me(node, channel, chat_id), circle_id=data["circle_id"],
        name=data["name"], time=message.text))
    if ok:
        await _send_circle(message, node, channel, data["circle_id"], lang)


@router.callback_query(F.data.startswith("md:"))
async def med_delete(cb: CallbackQuery, node, channel) -> None:
    lang = await _lang(node, channel, cb.message.chat.id)
    await cb.answer()
    _, cid, med_id = cb.data.split(":")
    chat_id = str(cb.message.chat.id)
    home = await _home_of(node, channel, chat_id, cid)
    if home:
        await _safe(lang, cb.message, node.call(home, "del_med", requester=_me(node, channel, chat_id),
                                                circle_id=cid, med_id=int(med_id)))
        await _send_circle(cb.message, node, channel, cid, lang)


# --- local contacts ---------------------------------------------------------------------------


@router.callback_query(F.data.startswith("cl:"))
async def locals_view(cb: CallbackQuery, node, channel) -> None:
    lang = await _lang(node, channel, cb.message.chat.id)
    await cb.answer()
    cid = cb.data[3:]
    _, v = await _view(node, channel, str(cb.message.chat.id), cid, lang, cb.message)
    if v is None:
        return
    rows = [[(f"🗑 {m['name']} ({m['phone']})", f"ld:{cid}:{m['id']}")] for m in v["locals"]]
    if v["sms"]:
        rows.append([(t(lang, "btn_add_local"), f"la:{cid}")])
    await cb.message.answer(t(lang, "locals_head" if v["sms"] else "locals_no_sms"), reply_markup=_kb(rows))


@router.callback_query(F.data.startswith("la:"))
async def local_add(cb: CallbackQuery, state: FSMContext, node, channel) -> None:
    await cb.answer()
    await state.set_state(LocalFlow.name)
    await state.update_data(circle_id=cb.data[3:])
    await cb.message.answer(t(await _lang(node, channel, cb.message.chat.id), "ask_local_name"))


@router.message(LocalFlow.name, F.text)
async def local_name(message: Message, state: FSMContext, node, channel) -> None:
    await state.update_data(name=message.text.strip()[:100])
    await state.set_state(LocalFlow.phone)
    await message.answer(t(await _lang(node, channel, message.chat.id), "ask_local_phone"))


@router.message(LocalFlow.phone, F.text)
async def local_phone(message: Message, state: FSMContext, node, channel) -> None:
    lang = await _lang(node, channel, message.chat.id)
    data = await state.get_data()
    await state.clear()
    chat_id = str(message.chat.id)
    home = await _home_of(node, channel, chat_id, data["circle_id"])
    if home:
        await _safe(lang, message, node.call(home, "add_local_contact", requester=_me(node, channel, chat_id),
                                             circle_id=data["circle_id"], name=data["name"], phone=message.text))
        await _send_circle(message, node, channel, data["circle_id"], lang)


@router.callback_query(F.data.startswith("ld:"))
async def local_delete(cb: CallbackQuery, node, channel) -> None:
    lang = await _lang(node, channel, cb.message.chat.id)
    await cb.answer()
    _, cid, mid = cb.data.split(":")
    chat_id = str(cb.message.chat.id)
    home = await _home_of(node, channel, chat_id, cid)
    if home:
        await _safe(lang, cb.message, node.call(home, "del_local_contact", requester=_me(node, channel, chat_id),
                                                circle_id=cid, member_id=int(mid)))
        await _send_circle(cb.message, node, channel, cid, lang)


# --- invite / leave ----------------------------------------------------------------------------


@router.callback_query(F.data.startswith("ci:"))
async def invite(cb: CallbackQuery, node, channel) -> None:
    lang = await _lang(node, channel, cb.message.chat.id)
    await cb.answer()
    cid = cb.data[3:]
    home, v = await _view(node, channel, str(cb.message.chat.id), cid, lang, cb.message)
    if v is None:
        return
    info = {"elder_code": v["elder_code"], "elder_link": v["elder_link"], "family_code": v["family_code"],
            "elder_channel": None}
    text = _invite_text(lang, info, home, node) if not v["linked"] else t(lang, "invite_family", code=v["family_code"])
    await cb.message.answer(text, reply_markup=_kb([[(t(lang, "btn_new_elder_code"), f"cr:{cid}")]]))


@router.callback_query(F.data.startswith("cr:"))
async def renew_code(cb: CallbackQuery, node, channel) -> None:
    lang = await _lang(node, channel, cb.message.chat.id)
    await cb.answer()
    cid = cb.data[3:]
    chat_id = str(cb.message.chat.id)
    home = await _home_of(node, channel, chat_id, cid)
    if home is None:
        return
    ok, info = await _safe(lang, cb.message, node.call(home, "renew_elder_code",
                                                       requester=_me(node, channel, chat_id), circle_id=cid))
    if ok:
        text = t(lang, "new_elder_code", code=info["elder_code"])
        await cb.message.answer(text + ("\n" + info["elder_link"] if info.get("elder_link") else ""))


@router.callback_query(F.data.startswith("cx:"))
async def leave_ask(cb: CallbackQuery, node, channel) -> None:
    lang = await _lang(node, channel, cb.message.chat.id)
    await cb.answer()
    await cb.message.answer(t(lang, "leave_confirm"), reply_markup=_kb([[(t(lang, "btn_yes_leave"), f"cxy:{cb.data[3:]}")]]))


@router.callback_query(F.data.startswith("cxy:"))
async def leave(cb: CallbackQuery, node, channel) -> None:
    lang = await _lang(node, channel, cb.message.chat.id)
    await cb.answer()
    cid = cb.data[4:]
    chat_id = str(cb.message.chat.id)
    home = await _home_of(node, channel, chat_id, cid)
    if home is None:
        return
    ok, _ = await _safe(lang, cb.message, node.call(home, "leave_circle", requester=_me(node, channel, chat_id),
                                                    circle_id=cid))
    if not ok:
        return
    async with node.session() as s:
        await s.execute(delete(Membership).where(Membership.channel == channel, Membership.chat_id == chat_id,
                                                 Membership.circle_id == cid))
        await s.commit()
    await cb.message.answer(t(lang, "left"))


# --- payment ------------------------------------------------------------------------------------


@router.callback_query(F.data.startswith("pay:"))
async def pay_plans(cb: CallbackQuery, node, channel) -> None:
    lang = await _lang(node, channel, cb.message.chat.id)
    await cb.answer()
    cid = cb.data[4:]
    if not billing.methods(node):
        await cb.message.answer(t(lang, "pay_none"))
        return
    rows = [[(t(lang, f"plan_{p['key']}"), f"pp:{cid}:{p['key']}")] for p in billing.PLANS]
    await cb.message.answer(t(lang, "pay_choose_plan"), reply_markup=_kb(rows))


@router.callback_query(F.data.startswith("pp:"))
async def pay_methods(cb: CallbackQuery, node, channel) -> None:
    lang = await _lang(node, channel, cb.message.chat.id)
    await cb.answer()
    _, cid, plan_key = cb.data.split(":")
    rows = []
    for method in billing.methods(node):
        amount, currency = billing.price(node, plan_key, method)
        rows.append([(t(lang, f"method_{method}", amount=f"{amount:,}"), f"pm:{cid}:{plan_key}:{method}")])
    await cb.message.answer(t(lang, "pay_choose_method"), reply_markup=_kb(rows))


@router.callback_query(F.data.startswith("pm:"))
async def pay_start(cb: CallbackQuery, state: FSMContext, node, channel) -> None:
    lang = await _lang(node, channel, cb.message.chat.id)
    await cb.answer()
    _, cid, plan_key, method = cb.data.split(":")
    chat_id = str(cb.message.chat.id)
    home = await _home_of(node, channel, chat_id, cid)
    if home is None:
        return
    payment = await billing.create_payment(node, cid, home, channel, chat_id, plan_key, method)
    if payment is None:
        await cb.message.answer(t(lang, "err_failed"))
        return
    if method == "zarinpal":
        url = await billing.start_zarinpal(node, payment)
        if url is None:
            await cb.message.answer(t(lang, "err_failed"))
            return
        await cb.message.answer(t(lang, "pay_zarinpal", amount=f"{payment.amount:,}") + "\n" + url)
        return
    await state.set_state(TonFlow.tx)
    await state.update_data(payment_id=payment.id)
    await cb.message.answer(t(lang, "pay_ton", wallet=node.config.ton_wallet, amount=payment.amount,
                              memo=f"HMD-{payment.id}"))


@router.message(TonFlow.tx, F.text)
async def pay_ton_tx(message: Message, state: FSMContext, node, channel) -> None:
    lang = await _lang(node, channel, message.chat.id)
    data = await state.get_data()
    await state.clear()
    payment = await billing.submit_ton(node, data["payment_id"], message.text)
    await message.answer(t(lang, "pay_ton_sent" if payment else "err_failed"))


# --- fallback --------------------------------------------------------------------------------------


@router.message(F.text)
async def fallback(message: Message, state: FSMContext, node, channel) -> None:
    code = logic.looks_like_elder_code(message.text)
    if code and await _try_link_elder(message, node, channel, code):
        await state.clear()
        return
    person = await _person(node, channel, str(message.chat.id))
    if person is None:
        await message.answer(t("fa", "choose_lang") + "\n" + t("en", "choose_lang"),
                             reply_markup=_kb([[("فارسی", "lang:fa"), ("English", "lang:en")]]))
        return
    await show_menu(message, person.lang)
