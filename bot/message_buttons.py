"""Validation and keyboard-building for owner-authored inline buttons attached
to a "message" command/flow-node action (see bot/flow_engine.py:_execute_node,
bot/handlers/tools/define_command.py, and webapp/src/nodes.jsx's message
composer). Two button kinds:

- "url": opens an external link, `{"type": "url", "text": ..., "url": ...}`.
- "jump": fires another command defined on this same bot, exactly as if the
  user had typed it themselves — `{"type": "jump", "text": ..., "command": "/menu"}`,
  encoded as `callback_data=f"cmdjump:{command}"` and resolved by
  bot/runtime.py's `handle_command_jump`.

Kept deliberately forgiving on the *read* side (build_inline_keyboard): an
owner can save a button through the Visual Builder, which does no validation
of its own, or old data can predate a stricter rule added later — a
malformed button is silently dropped rather than raising and breaking
delivery of the rest of the message. validate_buttons is the stricter,
owner-facing check used by the chat wizard at input time, where a clear
error is exactly what's wanted.
"""

from __future__ import annotations

import re

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

MAX_BUTTONS = 8
MAX_BUTTON_TEXT = 64
MAX_CALLBACK_DATA_BYTES = 64

# Telegram's own rule for a bot command (BotCommand.command): 1-32 of
# lowercase English letters, digits and underscores. A single name outside
# it makes setMyCommands reject the bot's ENTIRE "/" menu, and a name with
# spaces/other scripts can't be sent as a command anyway.
COMMAND_NAME_RE = re.compile(r"^/[a-z0-9_]{1,32}$")


def is_valid_command_name(name: str | None) -> bool:
    return bool(name) and COMMAND_NAME_RE.match(name) is not None


def is_valid_button_url(url: str | None) -> bool:
    """An http(s) link Telegram will accept as a URL button. One bad URL
    button makes Telegram reject the whole message it's attached to."""
    url = (url or "").strip()
    return (
        (url.startswith("http://") or url.startswith("https://"))
        and len(url) > len("https://")
        and not any(ch.isspace() for ch in url)
    )


_valid_url = is_valid_button_url


def validate_buttons(buttons: list[dict] | None, is_fa: bool = False) -> str | None:
    """Returns a bilingual, owner-facing error message if `buttons` isn't
    usable as typed, or None if it's fine to save. Called by the chat wizard
    right after the owner finishes describing one button."""
    if not buttons:
        return None
    if len(buttons) > MAX_BUTTONS:
        return (
            f"حداکثر {MAX_BUTTONS} دکمه مجازه." if is_fa else f"Maximum {MAX_BUTTONS} buttons allowed."
        )
    for b in buttons:
        text = (b.get("text") or "").strip()
        if not text or len(text) > MAX_BUTTON_TEXT:
            return (
                "متن دکمه نمی‌تونه خالی یا خیلی طولانی باشه."
                if is_fa
                else "Button text can't be empty or too long."
            )
        kind = b.get("type")
        if kind == "url":
            if not _valid_url((b.get("url") or "").strip()):
                return (
                    "لینک دکمه معتبر نیست (باید با http:// یا https:// شروع بشه)."
                    if is_fa
                    else "Button URL is invalid (must start with http:// or https://)."
                )
        elif kind == "jump":
            command = (b.get("command") or "").strip().lower()
            if not is_valid_command_name(command):
                return (
                    "اسم دستور مقصد باید با / شروع بشه و فقط حروف کوچک انگلیسی، عدد و _ داشته باشه "
                    "(حداکثر ۳۲ کاراکتر)، مثلاً /menu."
                    if is_fa
                    else "The target command must start with / and use only lowercase English letters, "
                    "digits and _ (max 32 characters), e.g. /menu."
                )
        else:
            return "نوع دکمه نامعتبره." if is_fa else "Invalid button type."
    return None


def build_inline_keyboard(buttons: list[dict] | None) -> InlineKeyboardMarkup | None:
    """Best-effort: silently drops any button that doesn't fit rather than
    raising, since this also runs against data saved through the Visual
    Builder (no validation there) or from before a rule existed."""
    if not buttons:
        return None
    if not isinstance(buttons, list):
        return None
    rows: list[list[InlineKeyboardButton]] = []
    for b in buttons[:MAX_BUTTONS]:
        if not isinstance(b, dict):
            continue
        text = (b.get("text") or "").strip()[:MAX_BUTTON_TEXT]
        if not text:
            continue
        kind = b.get("type")
        if kind == "url":
            url = (b.get("url") or "").strip()
            if not _valid_url(url):
                continue
            rows.append([InlineKeyboardButton(text=text, url=url)])
        elif kind == "jump":
            command = (b.get("command") or "").strip().lower()
            if not is_valid_command_name(command):
                continue
            callback_data = f"cmdjump:{command}"
            if len(callback_data.encode("utf-8")) > MAX_CALLBACK_DATA_BYTES:
                continue
            rows.append([InlineKeyboardButton(text=text, callback_data=callback_data)])
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None
