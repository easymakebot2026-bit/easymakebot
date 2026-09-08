"""Render a list of items where each item that has an image is shown as its
own photo (with one inline button under it), and items without an image fall
back to plain buttons in a single trailing keyboard.

Used for the built bot's content list and cart (bot/runtime.py) and the
visual flow builder's content_list node (bot/flow_engine.py). The bot owner
sets a picture per item in the "Content List" / "Shop" tools; when it's
there the customer sees the picture instead of just a text button.
"""

import logging

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

logger = logging.getLogger(__name__)

# Most photo cards we'll send for one list. Past this the rest render as
# buttons — dozens of separate photo messages would be slow and hit
# Telegram's per-chat flood limit.
PHOTO_CARD_LIMIT = 10


async def send_item_list(
    message: Message,
    entries: list[dict],
    *,
    trailing_text: str,
    footer_rows: list[list[InlineKeyboardButton]] | None = None,
) -> None:
    """entries: one dict per item — {"image_url": str|None, "label": str,
    "callback_data": str, "caption": str|None}. An entry with a usable
    "image_url" is sent as a photo captioned with "caption" (or "label")
    and a single [label] button; others are collected into the trailing
    keyboard. `trailing_text` + any leftover item buttons + `footer_rows`
    are always sent as one final message (so navigation / Checkout still
    shows even when every item became a photo)."""
    button_rows: list[list[InlineKeyboardButton]] = []
    photos_sent = 0

    for entry in entries:
        button = InlineKeyboardButton(text=entry["label"], callback_data=entry["callback_data"])
        image_url = entry.get("image_url")
        if image_url and photos_sent < PHOTO_CARD_LIMIT:
            try:
                await message.answer_photo(
                    image_url,
                    caption=entry.get("caption") or entry["label"],
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[[button]]),
                )
                photos_sent += 1
                continue
            except Exception:
                logger.warning("photo card failed for %s, using a button", entry.get("callback_data"))
        button_rows.append([button])

    if footer_rows:
        button_rows.extend(footer_rows)

    await message.answer(
        trailing_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=button_rows) if button_rows else None,
    )
