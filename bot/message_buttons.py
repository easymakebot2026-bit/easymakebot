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

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

MAX_BUTTONS = 8
MAX_BUTTON_TEXT = 64
MAX_CALLBACK_DATA_BYTES = 64


def _valid_url(url: str) -> bool:
    return bool(url) and (url.startswith("http://") or url.startswith("https://")) and " " not in url


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
            command = (b.get("command") or "").strip()
            if not command.startswith("/"):
                return (
                    "اسم دستور مقصد باید با / شروع بشه."
                    if is_fa
                    else "The target command must start with /."
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
    rows: list[list[InlineKeyboardButton]] = []
    for b in buttons[:MAX_BUTTONS]:
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
            command = (b.get("command") or "").strip()
            if not command.startswith("/"):
                continue
            callback_data = f"cmdjump:{command}"
            if len(callback_data.encode("utf-8")) > MAX_CALLBACK_DATA_BYTES:
                continue
            rows.append([InlineKeyboardButton(text=text, callback_data=callback_data)])
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None
