from datetime import datetime, timezone

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    WebAppInfo,
)

# --- Bilingual reply-keyboard buttons -------------------------------------
#
# Reply-keyboard buttons (KeyboardButton) carry no hidden payload the way an
# inline button's callback_data does — the text Telegram sends back on tap
# IS the dispatch key. So every button translated here has TWO things that
# must move together: what's displayed (picked by is_fa where the keyboard
# is built) and what a handler's `F.text == ...` / `F.text.in_(...)` filter
# matches (which must accept BOTH language variants, since a keyboard shown
# in one language must still work if the user's language later changes, or
# if a stale keyboard from before a phone number was on file is still
# on-screen). The `*_text(is_fa)` functions below produce the display string;
# the paired `*_TEXTS` frozensets are for filters and always contain both.
#
# Every is_fa param defaults to False (English) so any call site not yet
# updated keeps behaving exactly as before.


def cancel_button_text(is_fa: bool = False) -> str:
    return "❌ لغو" if is_fa else "❌ Cancel"


CANCEL_BUTTON_TEXTS = frozenset({cancel_button_text(False), cancel_button_text(True)})
# Back-compat default (English) for any code that still imports the bare
# constant directly rather than calling cancel_button_text().
CANCEL_BUTTON_TEXT = cancel_button_text(False)


def skip_button_text(is_fa: bool = False) -> str:
    return "⏭ رد کردن" if is_fa else "⏭ Skip"


SKIP_BUTTON_TEXTS = frozenset({skip_button_text(False), skip_button_text(True)})
SKIP_BUTTON_TEXT = skip_button_text(False)


# List of bot build/edit tools — deliberately a simple list separate from handler
# logic so adding/removing a tool in the future only needs to happen here.
TOOLS = [
    {"key": "define_command", "en": "1️⃣ Define Command", "fa": "1️⃣ تعریف دستور"},
    {"key": "force_join", "en": "2️⃣ Force Join", "fa": "2️⃣ عضویت اجباری"},
    {"key": "message_to_all", "en": "3️⃣ Broadcast", "fa": "3️⃣ پیام‌رسانی گروهی"},
    {"key": "content_list", "en": "4️⃣ Content List", "fa": "4️⃣ لیست محتوا"},
    {"key": "shop", "en": "5️⃣ Shop", "fa": "5️⃣ فروشگاه"},
]


def tool_button_text(key: str, is_fa: bool = False) -> str:
    for t in TOOLS:
        if t["key"] == key:
            return t["fa"] if is_fa else t["en"]
    return key


def tool_button_texts(key: str) -> frozenset[str]:
    """Both language variants of one tool's button — for a router filter."""
    return frozenset({tool_button_text(key, False), tool_button_text(key, True)})


def tools_menu_button_text(is_fa: bool = False) -> str:
    return "🛠 ابزارهای ساخت‌وساز" if is_fa else "🛠 Build & Edit Tools"


TOOLS_MENU_BUTTON_TEXTS = frozenset(
    {tools_menu_button_text(False), tools_menu_button_text(True)}
)
TOOLS_MENU_BUTTON_TEXT = tools_menu_button_text(False)


def my_bots_button_text(is_fa: bool = False) -> str:
    return "🤖 ربات‌های من" if is_fa else "🤖 My Bots"


MY_BOTS_BUTTON_TEXTS = frozenset({my_bots_button_text(False), my_bots_button_text(True)})
MY_BOTS_BUTTON_TEXT = my_bots_button_text(False)


def create_bot_button_text(is_fa: bool = False) -> str:
    return "➕ ساخت ربات جدید" if is_fa else "➕ Create New Bot"


CREATE_BOT_BUTTON_TEXTS = frozenset(
    {create_bot_button_text(False), create_bot_button_text(True)}
)
CREATE_BOT_BUTTON_TEXT = create_bot_button_text(False)


def welcome_keyboard(is_fa: bool = False) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=my_bots_button_text(is_fa)),
                KeyboardButton(text=create_bot_button_text(is_fa)),
            ]
        ],
        resize_keyboard=True,
    )


def my_bots_keyboard(bots, is_fa: bool = False) -> InlineKeyboardMarkup:
    now = datetime.now(timezone.utc)
    rows = []
    for b in bots:
        # 🚫 = suspended by the platform admin (bot/admin_panel.py) — takes
        # priority over 🔒, which marks a bot whose live period (trial or
        # paid plan — bot/live.py) has expired; neither is shown for one
        # that simply hasn't gone live yet.
        expired = b.live_until is not None and b.live_until <= now
        icon = "🚫" if getattr(b, "suspended", False) else ("🔒" if expired else "🤖")
        rows.append([InlineKeyboardButton(text=f"{icon} {b.display_name}", callback_data=f"select_bot:{b.id}")])
    rows.append(
        [
            InlineKeyboardButton(
                text=("➕ ساخت ربات جدید" if is_fa else "➕ Create New Bot"),
                callback_data="create_bot",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def tools_reply_keyboard(is_fa: bool = False) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=tools_menu_button_text(is_fa))]],
        resize_keyboard=True,
    )


def show_commands_button_text(is_fa: bool = False) -> str:
    return "📋 نمایش دستورها" if is_fa else "📋 Show Commands"


SHOW_COMMANDS_BUTTON_TEXTS = frozenset(
    {show_commands_button_text(False), show_commands_button_text(True)}
)
SHOW_COMMANDS_BUTTON_TEXT = show_commands_button_text(False)


def tools_menu_keyboard(is_fa: bool = False) -> ReplyKeyboardMarkup:
    """The 5-tool grid, shown after tapping tools_reply_keyboard()'s single
    entry button. Force Join's enabled/disabled status used to be baked into
    this button's label — moved into that tool's own menu text instead, since
    a reply-keyboard button's text must stay fixed for exact-match dispatch."""
    buttons = [KeyboardButton(text=t["fa"] if is_fa else t["en"]) for t in TOOLS]
    # BotFather-style dense grid (2 per row) instead of one button per row.
    rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def show_commands_button(is_fa: bool = False) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=show_commands_button_text(is_fa)),
                KeyboardButton(text=cancel_button_text(is_fa)),
            ]
        ],
        resize_keyboard=True,
    )



# --- Command action wizard (bot/handlers/tools/define_command.py) --------
#
# Once a command's name is registered, the owner picks who can see/run it
# (visibility) and what it actually does (action) — the action list mirrors
# the node types bot/flow_engine.py:_execute_node knows how to run, so a
# chat-defined command and a Visual Builder flow block offer exactly the
# same behaviors.

COMMAND_ACTION_TYPES = [
    ("message", "💬 پیام متنی", "💬 Text message"),
    ("content_list", "📚 لیست محتوا", "📚 Content list"),
    ("shop", "🛍 فروشگاه", "🛍 Shop"),
    ("order_status", "📦 وضعیت سفارش", "📦 Order status"),
    ("force_join_gate", "🔒 عضویت اجباری", "🔒 Force-join gate"),
    ("guide_video", "🎬 راهنما و ویدیو", "🎬 Guide & video"),
]


def command_action_button_texts(is_fa: bool = False) -> dict[str, str]:
    return {key: (fa if is_fa else en) for key, fa, en in COMMAND_ACTION_TYPES}


def command_action_button_to_key() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for key, fa, en in COMMAND_ACTION_TYPES:
        mapping[fa] = key
        mapping[en] = key
    return mapping


def command_action_label(action: str, is_fa: bool = False) -> str:
    return command_action_button_texts(is_fa).get(action, action)


def command_action_keyboard(is_fa: bool = False) -> ReplyKeyboardMarkup:
    labels = list(command_action_button_texts(is_fa).values())
    rows = [labels[i : i + 2] for i in range(0, len(labels), 2)]
    keyboard = [[KeyboardButton(text=t) for t in row] for row in rows]
    keyboard.append([KeyboardButton(text=cancel_button_text(is_fa))])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def command_visibility_admin_text(is_fa: bool = False) -> str:
    return "👤 فقط خودم (ادمین)" if is_fa else "👤 Admin only (just me)"


def command_visibility_everyone_text(is_fa: bool = False) -> str:
    return "👥 همه (کاربرا هم ببینن)" if is_fa else "👥 Everyone (users too)"


COMMAND_VISIBILITY_BUTTON_TO_KEY = {
    command_visibility_admin_text(False): "admin",
    command_visibility_admin_text(True): "admin",
    command_visibility_everyone_text(False): "everyone",
    command_visibility_everyone_text(True): "everyone",
}


def command_visibility_keyboard(is_fa: bool = False) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=command_visibility_everyone_text(is_fa))],
            [KeyboardButton(text=command_visibility_admin_text(is_fa))],
            [KeyboardButton(text=cancel_button_text(is_fa))],
        ],
        resize_keyboard=True,
    )


def command_list_keyboard(commands, is_fa: bool = False) -> InlineKeyboardMarkup | None:
    """One 🗑 row per deletable command. /start is excluded — it's redefined
    by re-running the wizard, not deleted, since a bot always needs one."""
    rows = [
        [InlineKeyboardButton(text=f"🗑 {c.name}", callback_data=f"cmd:delete_confirm:{c.id}")]
        for c in commands
        if c.name != "/start"
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None


def command_delete_confirm_keyboard(command_id: int, is_fa: bool = False) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=("✅ بله، حذف کن" if is_fa else "✅ Yes, delete"),
                    callback_data=f"cmd:delete:{command_id}",
                )
            ],
            [InlineKeyboardButton(text=cancel_button_text(is_fa), callback_data="cmd:delete_cancel")],
        ]
    )


def cancel_inline_keyboard(is_fa: bool = False) -> InlineKeyboardMarkup:
    """Inline cancel — kept for the surfaces that still mix cancel with other
    inline buttons or run outside the builder-nav conversion: /live
    (bot/handlers/live.py), /easybotadmin (platform-admin-only), and
    admin_broadcast.py. Builder-nav screens use cancel_reply_keyboard() instead."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=cancel_button_text(is_fa), callback_data="cancel_flow")]
        ]
    )


def cancel_reply_keyboard(is_fa: bool = False) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=cancel_button_text(is_fa))]], resize_keyboard=True
    )


def force_join_toggle_label(enabled: bool, is_fa: bool = False) -> str:
    if is_fa:
        return "🔓 غیرفعال کردن عضویت اجباری" if enabled else "🔒 فعال کردن عضویت اجباری"
    return "🔓 Disable Force Join" if enabled else "🔒 Enable Force Join"


FORCE_JOIN_TOGGLE_TEXTS = frozenset(
    {
        force_join_toggle_label(True, False),
        force_join_toggle_label(False, False),
        force_join_toggle_label(True, True),
        force_join_toggle_label(False, True),
    }
)


def force_join_list_button_text(is_fa: bool = False) -> str:
    return "📋 لیست کانال‌ها" if is_fa else "📋 List Channels"


FORCE_JOIN_LIST_BUTTON_TEXTS = frozenset(
    {force_join_list_button_text(False), force_join_list_button_text(True)}
)


def force_join_new_button_text(is_fa: bool = False) -> str:
    return "➕ تعریف کانال جدید" if is_fa else "➕ Define New Channel"


FORCE_JOIN_NEW_BUTTON_TEXTS = frozenset(
    {force_join_new_button_text(False), force_join_new_button_text(True)}
)


def force_join_menu_keyboard(enabled: bool, is_fa: bool = False) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=force_join_list_button_text(is_fa)),
                KeyboardButton(text=force_join_new_button_text(is_fa)),
            ],
            [KeyboardButton(text=force_join_toggle_label(enabled, is_fa))],
            [KeyboardButton(text=cancel_button_text(is_fa))],
        ],
        resize_keyboard=True,
    )


def force_join_channels_keyboard(channels, is_fa: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=c.username, callback_data=f"force_join:select:{c.id}")]
        for c in channels
    ]
    rows.append(
        [InlineKeyboardButton(text=cancel_button_text(is_fa), callback_data="force_join:menu")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


# Distinct from cancel_button_text on purpose: this returns to Force Join's
# own menu (force_join:cancel_edit), not the global tools-menu reset — a reply
# button's text is the only dispatch signal now, so the two must read differently.
def force_join_back_button_text(is_fa: bool = False) -> str:
    return "🔙 بازگشت به منوی عضویت اجباری" if is_fa else "🔙 Back to Force Join Menu"


FORCE_JOIN_BACK_BUTTON_TEXTS = frozenset(
    {force_join_back_button_text(False), force_join_back_button_text(True)}
)
FORCE_JOIN_BACK_BUTTON_TEXT = force_join_back_button_text(False)


def force_join_confirm_button_text(is_fa: bool = False) -> str:
    return "✅ تأیید" if is_fa else "✅ Confirm"


FORCE_JOIN_CONFIRM_BUTTON_TEXTS = frozenset(
    {force_join_confirm_button_text(False), force_join_confirm_button_text(True)}
)


def force_join_confirm_keyboard(is_fa: bool = False) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=force_join_confirm_button_text(is_fa)),
                KeyboardButton(text=force_join_back_button_text(is_fa)),
            ]
        ],
        resize_keyboard=True,
    )


def force_join_input_cancel_keyboard(is_fa: bool = False) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=force_join_back_button_text(is_fa))]], resize_keyboard=True
    )


# --- Content List tool (owner-facing) --------------------------------------

_CONTENT_LIST_MENU_BUTTONS_EN = [
    ("📋 View", "➕ Add"),
    ("✏️ Edit", "🗑 Delete"),
    ("📢 Add Post",),
    ("🔀 Group (parent/child)",),
    ("📥 Download Sample Excel", "📤 Upload Excel"),
]
_CONTENT_LIST_MENU_BUTTONS_FA = [
    ("📋 نمایش", "➕ افزودن"),
    ("✏️ ویرایش", "🗑 حذف"),
    ("📢 افزودن پست",),
    ("🔀 دسته‌بندی (زیرمجموعه/والد)",),
    ("📥 دانلود نمونه اکسل", "📤 آپلود اکسل"),
]

CONTENT_VIEW_BUTTON_TEXTS = frozenset({"📋 View", "📋 نمایش"})
CONTENT_ADD_BUTTON_TEXTS = frozenset({"➕ Add", "➕ افزودن"})
CONTENT_EDIT_BUTTON_TEXTS = frozenset({"✏️ Edit", "✏️ ویرایش"})
CONTENT_DELETE_BUTTON_TEXTS = frozenset({"🗑 Delete", "🗑 حذف"})
CONTENT_ADD_POST_BUTTON_TEXTS = frozenset({"📢 Add Post", "📢 افزودن پست"})
CONTENT_GROUP_BUTTON_TEXTS = frozenset({"🔀 Group (parent/child)", "🔀 دسته‌بندی (زیرمجموعه/والد)"})
CONTENT_SAMPLE_BUTTON_TEXTS = frozenset({"📥 Download Sample Excel", "📥 دانلود نمونه اکسل"})
CONTENT_UPLOAD_BUTTON_TEXTS = frozenset({"📤 Upload Excel", "📤 آپلود اکسل"})


def content_list_menu_keyboard(is_fa: bool = False) -> ReplyKeyboardMarkup:
    rows_src = _CONTENT_LIST_MENU_BUTTONS_FA if is_fa else _CONTENT_LIST_MENU_BUTTONS_EN
    rows = [[KeyboardButton(text=t) for t in row] for row in rows_src]
    rows.append([KeyboardButton(text=cancel_button_text(is_fa))])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def post_engagement_keyboard(post_id: int, like_count: int, comment_count: int) -> InlineKeyboardMarkup:
    """Under a broadcast Post (bot/runtime.py) — Like toggles per-viewer,
    Comment opens a one-shot text-comment capture. Rebuilt with fresh counts
    on every like/comment so it always reflects that viewer's own message.
    Shared with the buyer-facing runtime — left English-only (see
    CONTENT_MENU_HEADING below for why)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=f"👍 {like_count}", callback_data=f"post_like:{post_id}"),
                InlineKeyboardButton(text=f"💬 {comment_count}", callback_data=f"post_comment:{post_id}"),
            ]
        ]
    )


# Distinct from cancel_button_text on purpose: these return to Content List's
# own menu (content:menu), not the global tools-menu reset.
def content_back_button_text(is_fa: bool = False) -> str:
    return "🔙 بازگشت به لیست محتوا" if is_fa else "🔙 Back to Content List"


CONTENT_BACK_BUTTON_TEXTS = frozenset(
    {content_back_button_text(False), content_back_button_text(True)}
)
CONTENT_BACK_BUTTON_TEXT = content_back_button_text(False)


def content_sample_lang_keyboard(languages, is_fa: bool = False) -> ReplyKeyboardMarkup:
    """`languages` is [(code, label), ...] (bot/content_import.SAMPLE_LANGUAGES).
    Two buttons per row; the label itself is what content_list.py matches on.
    The language-picker labels are each language's own name (EN/FA/AR/...) —
    that part stays as-is regardless of is_fa; only the trailing Back button
    is localized."""
    rows = []
    row: list[KeyboardButton] = []
    for _code, label in languages:
        row.append(KeyboardButton(text=label))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([KeyboardButton(text=content_back_button_text(is_fa))])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def content_browse_button_text(is_fa: bool = False) -> str:
    return "📋 مرور محتوا" if is_fa else "📋 Browse instead"


CONTENT_BROWSE_BUTTON_TEXTS = frozenset(
    {content_browse_button_text(False), content_browse_button_text(True)}
)


def content_lookup_keyboard(is_fa: bool = False) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=content_browse_button_text(is_fa))],
            [KeyboardButton(text=content_back_button_text(is_fa))],
        ],
        resize_keyboard=True,
    )


def content_delete_confirm_keyboard(item_id: int, is_fa: bool = False) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=("✅ بله، حذف کن" if is_fa else "✅ Yes, delete"),
                    callback_data=f"content:delete:{item_id}",
                )
            ],
            [InlineKeyboardButton(text=cancel_button_text(is_fa), callback_data="content:menu")],
        ]
    )


def content_group_target_keyboard(items, item_id: int, is_fa: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=item.title, callback_data=f"content:groupto:{item_id}:{item.id}")]
        for item in items
        if item.id != item_id
    ]
    rows.append(
        [
            InlineKeyboardButton(
                text=("📁 سطح بالا (بدون دسته)" if is_fa else "📁 Top Level (no category)"),
                callback_data=f"content:groupto:{item_id}:top",
            )
        ]
    )
    rows.append([InlineKeyboardButton(text=cancel_button_text(is_fa), callback_data="content:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _content_back_button(back_target: str, is_fa: bool = False) -> InlineKeyboardButton:
    """back_target: "menu" exits the tool entirely; "top" or a numeric parent
    id goes up one level within the (possibly nested) content tree."""
    if back_target == "menu":
        return InlineKeyboardButton(text=cancel_button_text(is_fa), callback_data="content:menu")
    return InlineKeyboardButton(
        text=("🔙 بازگشت" if is_fa else "🔙 Back"), callback_data=f"content:list_at:{back_target}"
    )


# Shared heading + button style for "a list of content items as a menu",
# used identically by the built bot at runtime (bot/runtime.py), the visual
# flow builder's content_list node (bot/flow_engine.py) and the owner's
# "Content List" tool (bot/handlers/tools/content_list.py) so all three read
# like the bot's own nested menus. Left English-only for now — localizing it
# would mean touching the buyer-facing runtime.py/flow_engine.py too, which
# is a separate, larger piece of work than this pass covers.
CONTENT_MENU_HEADING = "📚 Choose an item:"
_CONTENT_FOLDER_ICON = "📂"


def content_item_label(item, is_folder: bool) -> str:
    """The button text for one content item: `🔒` if premium (visible-but-
    locked — the access check happens on open), `📂` if it opens a sub-menu,
    then the title. Shared by the button menu and the photo-card fallback
    (bot/list_render.py) so both read the same. Left as-is — see
    CONTENT_MENU_HEADING."""
    label = item.title
    if is_folder:
        label = f"{_CONTENT_FOLDER_ICON} {label}"
    if getattr(item, "is_premium", False):
        label = f"🔒 {label}"
    return label


def content_menu_keyboard(
    items,
    folder_ids: set[int] | None = None,
    *,
    select_prefix: str,
    back_button: InlineKeyboardButton | None = None,
) -> InlineKeyboardMarkup:
    """One row per item (see content_item_label). `select_prefix` is the
    callback_data stem the item id is appended to (e.g. "content_item:" at
    runtime, "content:select:" in the owner tool). `back_button`, if given,
    is added as the last row."""
    folder_ids = folder_ids or set()
    rows = [
        [
            InlineKeyboardButton(
                text=content_item_label(item, item.id in folder_ids),
                callback_data=f"{select_prefix}{item.id}",
            )
        ]
        for item in items
    ]
    if back_button is not None:
        rows.append([back_button])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def content_items_keyboard(
    items, back_target: str = "menu", folder_ids: set[int] | None = None, is_fa: bool = False
) -> InlineKeyboardMarkup:
    return content_menu_keyboard(
        items,
        folder_ids,
        select_prefix="content:select:",
        back_button=_content_back_button(back_target, is_fa),
    )


def content_item_detail_keyboard(
    item_id: int, back_target: str = "menu", is_fa: bool = False
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=("🗑 حذف" if is_fa else "🗑 Delete"), callback_data=f"content:delete:{item_id}"
                )
            ],
            [_content_back_button(back_target, is_fa)],
        ]
    )


def content_category_picker_keyboard(items, is_fa: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=item.title, callback_data=f"content:parent:{item.id}")]
        for item in items
    ]
    rows.append(
        [
            InlineKeyboardButton(
                text=("📁 سطح بالا (بدون دسته)" if is_fa else "📁 Top Level (no category)"),
                callback_data="content:parent:top",
            )
        ]
    )
    rows.append([InlineKeyboardButton(text=cancel_button_text(is_fa), callback_data="cancel_flow")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def content_input_cancel_keyboard(is_fa: bool = False) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=cancel_button_text(is_fa))]], resize_keyboard=True
    )


def content_skip_keyboard(is_fa: bool = False) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=skip_button_text(is_fa)),
                KeyboardButton(text=cancel_button_text(is_fa)),
            ]
        ],
        resize_keyboard=True,
    )


def content_for_sale_yes_text(is_fa: bool = False) -> str:
    return "💰 بله، برای فروشه" if is_fa else "💰 Yes, it's for sale"


def content_no_text(is_fa: bool = False) -> str:
    return "➖ نه" if is_fa else "➖ No"


CONTENT_FOR_SALE_YES_TEXTS = frozenset(
    {content_for_sale_yes_text(False), content_for_sale_yes_text(True)}
)
CONTENT_NO_TEXTS = frozenset({content_no_text(False), content_no_text(True)})


def content_for_sale_keyboard(is_fa: bool = False) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=content_for_sale_yes_text(is_fa)),
                KeyboardButton(text=content_no_text(is_fa)),
            ],
            [KeyboardButton(text=cancel_button_text(is_fa))],
        ],
        resize_keyboard=True,
    )


def content_premium_yes_text(is_fa: bool = False) -> str:
    return "🔒 بله، پرمیوم" if is_fa else "🔒 Yes, premium"


def content_no_free_text(is_fa: bool = False) -> str:
    return "➖ نه، رایگان" if is_fa else "➖ No, free"


CONTENT_PREMIUM_YES_TEXTS = frozenset(
    {content_premium_yes_text(False), content_premium_yes_text(True)}
)
CONTENT_NO_FREE_TEXTS = frozenset({content_no_free_text(False), content_no_free_text(True)})


def content_premium_keyboard(is_fa: bool = False) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=content_premium_yes_text(is_fa)),
                KeyboardButton(text=content_no_free_text(is_fa)),
            ],
            [KeyboardButton(text=cancel_button_text(is_fa))],
        ],
        resize_keyboard=True,
    )


def product_type_button_texts(is_fa: bool = False) -> dict[str, str]:
    """key -> button label, for both the Content List and Shop product-type
    pickers (same three kinds either way)."""
    if is_fa:
        return {"physical": "📦 فیزیکی", "digital": "💾 دیجیتال", "access": "🎫 دسترسی / عضویت"}
    return {"physical": "📦 Physical", "digital": "💾 Digital", "access": "🎫 Access / Membership"}


def product_type_button_to_key() -> dict[str, str]:
    """Every language's button text -> its type key, for a router filter
    that must recognize the button regardless of which language it was
    shown in."""
    mapping: dict[str, str] = {}
    for is_fa in (False, True):
        for key, label in product_type_button_texts(is_fa).items():
            mapping[label] = key
    return mapping


def content_product_type_keyboard(is_fa: bool = False) -> ReplyKeyboardMarkup:
    # Shop-mode only — a Subscription-mode bot never reaches this picker
    # (its Content List items are premium-gated, never individually "for
    # sale" — see bot/commerce_mode.py).
    labels = product_type_button_texts(is_fa)
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=labels["physical"]), KeyboardButton(text=labels["digital"])],
            [KeyboardButton(text=labels["access"])],
            [KeyboardButton(text=cancel_button_text(is_fa))],
        ],
        resize_keyboard=True,
    )


def commerce_mode_shop_text(is_fa: bool = False) -> str:
    return "🏪 فروشگاه (فروش تک‌محصولی)" if is_fa else "🏪 Shop (sell individual products)"


def commerce_mode_subscription_text(is_fa: bool = False) -> str:
    return "🔁 اشتراک (آرشیو محتوا)" if is_fa else "🔁 Subscription (content archive)"


COMMERCE_MODE_SHOP_TEXTS = frozenset(
    {commerce_mode_shop_text(False), commerce_mode_shop_text(True)}
)
COMMERCE_MODE_SUBSCRIPTION_TEXTS = frozenset(
    {commerce_mode_subscription_text(False), commerce_mode_subscription_text(True)}
)
# Back-compat bare constants (English) — see cancel_button_text's note above.
COMMERCE_MODE_SHOP_TEXT = commerce_mode_shop_text(False)
COMMERCE_MODE_SUBSCRIPTION_TEXT = commerce_mode_subscription_text(False)


def commerce_mode_keyboard(is_fa: bool = False) -> ReplyKeyboardMarkup:
    """Asked once, the first time the owner opens either the Shop or Content
    List tool on a bot with no commerce_mode set yet (bot/commerce_mode.py).
    Which tool asked is stashed in FSM data (commerce_mode_source) by the
    caller rather than encoded here, since a reply button carries no hidden
    payload — see content_list.py:choose_commerce_mode, the one shared
    handler for both tools' buttons."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=commerce_mode_shop_text(is_fa))],
            [KeyboardButton(text=commerce_mode_subscription_text(is_fa))],
        ],
        resize_keyboard=True,
    )


def post_publish_button_text(is_fa: bool = False) -> str:
    return "📢 انتشار برای مشترکین" if is_fa else "📢 Publish to subscribers"


POST_PUBLISH_BUTTON_TEXTS = frozenset(
    {post_publish_button_text(False), post_publish_button_text(True)}
)


def post_preview_keyboard(is_fa: bool = False) -> ReplyKeyboardMarkup:
    """Shown after the owner supplies a post's media + caption, right before
    publishing it to their bot's subscribers (bot/handlers/tools/content_list.py)."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=post_publish_button_text(is_fa))],
            [KeyboardButton(text=cancel_button_text(is_fa))],
        ],
        resize_keyboard=True,
    )


# --- Shop tool (owner-facing) ----------------------------------------------

# Distinct from cancel_button_text on purpose: returns to Shop's own menu
# (shop:menu), not the global tools-menu reset.
def shop_back_button_text(is_fa: bool = False) -> str:
    return "🔙 بازگشت به منوی فروشگاه" if is_fa else "🔙 Back to Shop Menu"


SHOP_BACK_BUTTON_TEXTS = frozenset({shop_back_button_text(False), shop_back_button_text(True)})
SHOP_BACK_BUTTON_TEXT = shop_back_button_text(False)


def shop_products_button_texts(is_fa: bool = False) -> dict[str, str]:
    if is_fa:
        return {"shop": "📦 محصولات", "subscription": "📋 پلن‌ها"}
    return {"shop": "📦 Products", "subscription": "📋 Plans"}


def shop_add_button_texts(is_fa: bool = False) -> dict[str, str]:
    if is_fa:
        return {"shop": "➕ افزودن محصول", "subscription": "➕ افزودن پلن"}
    return {"shop": "➕ Add Product", "subscription": "➕ Add Plan"}


# Back-compat bare constants (English) — kept for anything reading the old
# name directly; filters should prefer the *_TEXTS_ALL sets below instead,
# which include every language's variant for every mode.
SHOP_PRODUCTS_BUTTON_TEXTS = shop_products_button_texts(False)
SHOP_ADD_BUTTON_TEXTS = shop_add_button_texts(False)
SHOP_PRODUCTS_BUTTON_TEXTS_ALL = frozenset(
    shop_products_button_texts(False).values()
) | frozenset(shop_products_button_texts(True).values())
SHOP_ADD_BUTTON_TEXTS_ALL = frozenset(shop_add_button_texts(False).values()) | frozenset(
    shop_add_button_texts(True).values()
)


_SHOP_MENU_STATIC_EN = {
    "payments": "💳 Payment Methods",
    "orders": "📋 Recent Orders",
    "import": "📥 Import Products",
    "stats": "📊 Sales & Stock",
    "invoice": "🧾 Invoice Branding",
    "free_preview": "🎁 Free Preview Limit",
    "unlock_price": "🔓 Single-item Price",
    "campaign": "🎉 Sale / Campaign",
}
_SHOP_MENU_STATIC_FA = {
    "payments": "💳 روش‌های پرداخت",
    "orders": "📋 سفارش‌های اخیر",
    "import": "📥 وارد کردن محصولات",
    "stats": "📊 فروش و موجودی",
    "invoice": "🧾 برندسازی فاکتور",
    "free_preview": "🎁 سقف پیش‌نمایش رایگان",
    "unlock_price": "🔓 قیمت تک‌آیتم",
    "campaign": "🎉 تخفیف / کمپین",
}


def shop_menu_static_texts(is_fa: bool = False) -> dict[str, str]:
    return _SHOP_MENU_STATIC_FA if is_fa else _SHOP_MENU_STATIC_EN


def shop_menu_static_texts_all() -> dict[str, frozenset[str]]:
    """key -> {both language variants} — for router filters."""
    return {
        key: frozenset({_SHOP_MENU_STATIC_EN[key], _SHOP_MENU_STATIC_FA[key]})
        for key in _SHOP_MENU_STATIC_EN
    }


def shop_menu_keyboard(mode: str = "shop", is_fa: bool = False) -> ReplyKeyboardMarkup:
    products_labels = shop_products_button_texts(is_fa)
    add_labels = shop_add_button_texts(is_fa)
    products_label = products_labels.get(mode, products_labels["shop"])
    add_label = add_labels.get(mode, add_labels["shop"])
    static = shop_menu_static_texts(is_fa)
    rows = [
        [KeyboardButton(text=products_label), KeyboardButton(text=add_label)],
        [KeyboardButton(text=static["payments"]), KeyboardButton(text=static["orders"])],
        [KeyboardButton(text=static["import"]), KeyboardButton(text=static["stats"])],
        [KeyboardButton(text=static["invoice"])],
    ]
    if mode == "subscription":
        rows.append(
            [
                KeyboardButton(text=static["free_preview"]),
                KeyboardButton(text=static["unlock_price"]),
            ]
        )
    rows.append([KeyboardButton(text=static["campaign"])])
    rows.append([KeyboardButton(text=cancel_button_text(is_fa))])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def shop_invoice_field_labels() -> dict[str, tuple[str, str]]:
    """field -> (English name, Persian name) for the invoice-branding
    buttons' base label (before the ✅/Set prefix logic)."""
    return {
        "business_name": ("Business Name", "نام کسب‌وکار"),
        "logo": ("Logo (image URL)", "لوگو (آدرس تصویر)"),
        "address": ("Address", "آدرس"),
        "business_phone": ("Business Phone", "تلفن کسب‌وکار"),
        "footer_note": ("Footer Note", "یادداشت پایانی"),
        "signature": ("Signature/Stamp (image URL)", "مهر و امضا (آدرس تصویر)"),
    }


_INVOICE_ICONS = {
    "business_name": "🏢",
    "logo": "🖼",
    "address": "📍",
    "business_phone": "☎️",
    "footer_note": "📝",
    "signature": "✍️",
}


def shop_invoice_labels(settings, is_fa: bool = False) -> dict[str, str]:
    """The invoice-branding button labels, keyed by field — mirrors
    shop_payment_labels' ✅-suffix convention."""
    names = shop_invoice_field_labels()
    is_set = {
        "business_name": bool(settings and settings.invoice_business_name),
        "logo": bool(settings and settings.invoice_logo_url),
        "address": bool(settings and settings.invoice_address),
        "business_phone": bool(settings and settings.invoice_business_phone),
        "footer_note": bool(settings and settings.invoice_footer_note),
        "signature": bool(settings and settings.invoice_signature_url),
    }
    result = {}
    for field, (en, fa) in names.items():
        icon = _INVOICE_ICONS[field]
        name = fa if is_fa else en
        if is_set[field]:
            result[field] = f"{icon} {name} ✅"
        else:
            result[field] = f"{icon} تنظیم {name}" if is_fa else f"{icon} Set {name}"
    return result


def shop_invoice_labels_all(settings) -> dict[str, frozenset[str]]:
    """field -> {both language variants, both set/unset states already fixed
    by `settings`} — for router filters, which only need to recognize
    whichever of the two states (✅-set or not-yet-set) is CURRENTLY shown,
    in either language."""
    en = shop_invoice_labels(settings, False)
    fa = shop_invoice_labels(settings, True)
    return {field: frozenset({en[field], fa[field]}) for field in en}


def shop_invoice_button_texts_all() -> dict[str, frozenset[str]]:
    """field -> {every label this button could ever show: both the ✅-set and
    not-yet-set states, in both languages} — see shop_payment_button_texts_all,
    same reasoning (a router filter registered once at import time)."""
    unset_en = shop_invoice_labels(None, False)
    unset_fa = shop_invoice_labels(None, True)
    set_en = shop_invoice_labels(_ALL_FIELDS_SET, False)
    set_fa = shop_invoice_labels(_ALL_FIELDS_SET, True)
    return {
        field: frozenset({unset_en[field], unset_fa[field], set_en[field], set_fa[field]})
        for field in unset_en
    }


def shop_import_keyboard(is_fa: bool = False) -> ReplyKeyboardMarkup:
    upload_text = "📤 آپلود فایل" if is_fa else "📤 Upload File"
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🇬🇧 Sample (EN)"), KeyboardButton(text="🇮🇷 Sample (FA)")],
            [KeyboardButton(text=upload_text)],
            [KeyboardButton(text=shop_back_button_text(is_fa))],
        ],
        resize_keyboard=True,
    )


SHOP_UPLOAD_BUTTON_TEXTS = frozenset({"📤 Upload File", "📤 آپلود فایل"})


def shop_tax_toggle_text(enabled: bool, is_fa: bool = False) -> str:
    if is_fa:
        return "✅ مالیات ۱۰٪ فعاله (لمس کن غیرفعال شه)" if enabled else "☑️ فعال‌سازی مالیات بر ارزش‌افزوده ۱۰٪"
    return "✅ 10% VAT is ON (tap to turn off)" if enabled else "☑️ Enable 10% VAT"


def shop_tax_toggle_texts_all() -> frozenset[str]:
    """Every label the VAT toggle button could ever show — both states, both
    languages — see shop_invoice_button_texts_all, same reasoning."""
    return frozenset(
        {
            shop_tax_toggle_text(True, False),
            shop_tax_toggle_text(False, False),
            shop_tax_toggle_text(True, True),
            shop_tax_toggle_text(False, True),
        }
    )


def shop_invoice_list_button_text(is_fa: bool = False) -> str:
    return "📋 لیست فاکتورهای صادرشده" if is_fa else "📋 Issued Invoices"


SHOP_INVOICE_LIST_BUTTON_TEXTS = frozenset(
    {shop_invoice_list_button_text(False), shop_invoice_list_button_text(True)}
)


_INVOICE_PERIOD_LABELS_FA = {"day": "روزانه", "week": "هفتگی", "month": "ماهانه", "year": "سالانه"}
_INVOICE_PERIOD_LABELS_EN = {"day": "Daily", "week": "Weekly", "month": "Monthly", "year": "Yearly"}


def invoice_period_label(period: str, is_fa: bool = False) -> str:
    labels = _INVOICE_PERIOD_LABELS_FA if is_fa else _INVOICE_PERIOD_LABELS_EN
    return labels.get(period, period)


def shop_invoice_period_keyboard(is_fa: bool = False) -> InlineKeyboardMarkup:
    labels = _INVOICE_PERIOD_LABELS_FA if is_fa else _INVOICE_PERIOD_LABELS_EN
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"📅 {labels['day']}", callback_data="shop_invlist:day")],
            [InlineKeyboardButton(text=f"📅 {labels['week']}", callback_data="shop_invlist:week")],
            [InlineKeyboardButton(text=f"📅 {labels['month']}", callback_data="shop_invlist:month")],
            [InlineKeyboardButton(text=f"📅 {labels['year']}", callback_data="shop_invlist:year")],
        ]
    )


def shop_invoice_keyboard(settings, is_fa: bool = False) -> ReplyKeyboardMarkup:
    labels = shop_invoice_labels(settings, is_fa)
    tax_enabled = bool(settings and settings.tax_enabled)
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=labels["business_name"])],
            [KeyboardButton(text=labels["logo"])],
            [KeyboardButton(text=labels["address"])],
            [KeyboardButton(text=labels["business_phone"])],
            [KeyboardButton(text=labels["footer_note"])],
            [KeyboardButton(text=labels["signature"])],
            [KeyboardButton(text=shop_tax_toggle_text(tax_enabled, is_fa))],
            [KeyboardButton(text=shop_invoice_list_button_text(is_fa))],
            [KeyboardButton(text=shop_back_button_text(is_fa))],
        ],
        resize_keyboard=True,
    )


def shop_campaign_end_text(is_fa: bool = False) -> str:
    return "🔚 پایان کمپین" if is_fa else "🔚 End Campaign Now"


def shop_campaign_discount_text(is_fa: bool = False) -> str:
    return "📉 تخفیف" if is_fa else "📉 Discount"


def shop_campaign_markup_text(is_fa: bool = False) -> str:
    return "📈 افزایش قیمت" if is_fa else "📈 Markup"


SHOP_CAMPAIGN_END_TEXTS = frozenset(
    {shop_campaign_end_text(False), shop_campaign_end_text(True)}
)
SHOP_CAMPAIGN_DISCOUNT_MARKUP_TEXTS = frozenset(
    {
        shop_campaign_discount_text(False),
        shop_campaign_markup_text(False),
        shop_campaign_discount_text(True),
        shop_campaign_markup_text(True),
    }
)


def shop_campaign_direction_from_text(text: str) -> str | None:
    if text in (shop_campaign_discount_text(False), shop_campaign_discount_text(True)):
        return "discount"
    if text in (shop_campaign_markup_text(False), shop_campaign_markup_text(True)):
        return "markup"
    return None


def shop_campaign_keyboard(has_active: bool, is_fa: bool = False) -> ReplyKeyboardMarkup:
    if has_active:
        rows = [[KeyboardButton(text=shop_campaign_end_text(is_fa))]]
    else:
        rows = [
            [
                KeyboardButton(text=shop_campaign_discount_text(is_fa)),
                KeyboardButton(text=shop_campaign_markup_text(is_fa)),
            ]
        ]
    rows.append([KeyboardButton(text=shop_back_button_text(is_fa))])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def shop_campaign_apply_text(is_fa: bool = False) -> str:
    return "✅ اعمال کن" if is_fa else "✅ Apply"


SHOP_CAMPAIGN_APPLY_TEXTS = frozenset(
    {shop_campaign_apply_text(False), shop_campaign_apply_text(True)}
)


def shop_campaign_confirm_keyboard(is_fa: bool = False) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=shop_campaign_apply_text(is_fa)),
                KeyboardButton(text=shop_back_button_text(is_fa)),
            ]
        ],
        resize_keyboard=True,
    )


def shop_products_keyboard(
    products, offset: int = 0, has_more: bool = False, page_size: int = 30, is_fa: bool = False
) -> InlineKeyboardMarkup:
    """One page of the owner's product list — Telegram flat-out rejects a
    reply_markup above a certain size ("Bad Request: reply markup is too
    long"), which an unpaginated keyboard hits once a bot has more than a
    couple dozen products (see bot/shop.py:get_products_page)."""
    currency = "تومان" if is_fa else "Toman"
    rows = [
        [
            InlineKeyboardButton(
                text=f"{p.name} — {p.price:,} {currency}", callback_data=f"shop:select:{p.id}"
            )
        ]
        for p in products
    ]
    nav = []
    prev_text = "⬅️ قبلی" if is_fa else "⬅️ Prev"
    next_text = "➡️ بعدی" if is_fa else "➡️ Next"
    back_text = "🔙 بازگشت" if is_fa else "🔙 Back"
    if offset > 0:
        nav.append(
            InlineKeyboardButton(
                text=prev_text, callback_data=f"shop:products_page:{max(0, offset - page_size)}"
            )
        )
    if has_more:
        nav.append(
            InlineKeyboardButton(text=next_text, callback_data=f"shop:products_page:{offset + page_size}")
        )
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text=back_text, callback_data="shop:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def shop_product_detail_keyboard(product_id: int, is_fa: bool = False) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=("🗑 حذف" if is_fa else "🗑 Delete"), callback_data=f"shop:delete:{product_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text=("🔙 بازگشت" if is_fa else "🔙 Back"), callback_data="shop:products"
                )
            ],
        ]
    )


def shop_product_type_keyboard(is_fa: bool = False) -> ReplyKeyboardMarkup:
    # Shop-mode only — Subscription-mode bots skip this picker entirely
    # (every product they add *is* a subscription plan — bot/commerce_mode.py).
    # Same labels as content_product_type_keyboard() — safe, the two only ever
    # show up in their own distinct FSM states (ShopStates.add_product_wizard
    # vs ContentListStates.add_item_wizard), which is what each handler is
    # scoped on, same as today's inline callback_data + state combo.
    labels = product_type_button_texts(is_fa)
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=labels["physical"]), KeyboardButton(text=labels["digital"])],
            [KeyboardButton(text=labels["access"])],
            [KeyboardButton(text=cancel_button_text(is_fa))],
        ],
        resize_keyboard=True,
    )


def shop_payment_field_labels() -> dict[str, tuple[str, str]]:
    return {
        "zarinpal": ("Zarinpal", "زرین‌پال"),
        "card": ("Card-to-Card", "کارت به کارت"),
        "stripe": ("Stripe (USD, international)", "استرایپ (دلاری، بین‌المللی)"),
        "crypto": ("Crypto Wallet", "کیف پول ارز دیجیتال"),
        "ton": ("TON Wallet", "کیف پول TON"),
    }


_PAYMENT_ICONS = {"zarinpal": "💳", "card": "🏦", "stripe": "🌍", "crypto": "🪙", "ton": "💎"}


def shop_payment_labels(settings, is_fa: bool = False) -> dict[str, str]:
    """The 5 payment-method button labels, keyed by method — exposed so the
    handler can match either the ✅-set or the not-yet-set variant of each."""
    names = shop_payment_field_labels()
    is_set = {
        "zarinpal": bool(settings and settings.zarinpal_merchant_id),
        "card": bool(settings and settings.card_number and settings.card_holder_name),
        "stripe": bool(settings and settings.stripe_secret_key),
        "crypto": bool(settings and settings.crypto_wallet_address),
        "ton": bool(settings and settings.ton_wallet_address),
    }
    result = {}
    for field, (en, fa) in names.items():
        icon = _PAYMENT_ICONS[field]
        name = fa if is_fa else en
        if is_set[field]:
            result[field] = f"{icon} {name} ✅"
        else:
            result[field] = f"{icon} تنظیم {name}" if is_fa else f"{icon} Set {name}"
    return result


def shop_payment_labels_all(settings) -> dict[str, frozenset[str]]:
    """field -> {both language variants} — for router filters."""
    en = shop_payment_labels(settings, False)
    fa = shop_payment_labels(settings, True)
    return {field: frozenset({en[field], fa[field]}) for field in en}


class _AllFieldsSet:
    """Stub with every ShopSettings field shop_payment_labels/shop_invoice_labels
    check truthy — used only to enumerate each button's "already configured"
    (✅) text below, independent of any real bot's settings."""

    zarinpal_merchant_id = "x"
    card_number = "x"
    card_holder_name = "x"
    stripe_secret_key = "x"
    crypto_wallet_address = "x"
    ton_wallet_address = "x"
    invoice_business_name = "x"
    invoice_logo_url = "x"
    invoice_address = "x"
    invoice_business_phone = "x"
    invoice_footer_note = "x"
    invoice_signature_url = "x"


_ALL_FIELDS_SET = _AllFieldsSet()


def shop_payment_button_texts_all() -> dict[str, frozenset[str]]:
    """field -> {every label this button could ever show: both the ✅-set and
    not-yet-set states, in both languages}. A router filter is registered
    once at import time and must recognize the button no matter which state
    or language it was showing when tapped — unlike shop_payment_labels_all,
    which only covers one (settings-dependent) state."""
    unset_en = shop_payment_labels(None, False)
    unset_fa = shop_payment_labels(None, True)
    set_en = shop_payment_labels(_ALL_FIELDS_SET, False)
    set_fa = shop_payment_labels(_ALL_FIELDS_SET, True)
    return {
        field: frozenset({unset_en[field], unset_fa[field], set_en[field], set_fa[field]})
        for field in unset_en
    }


def shop_payments_keyboard(settings, is_fa: bool = False) -> ReplyKeyboardMarkup:
    labels = shop_payment_labels(settings, is_fa)
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=labels["zarinpal"])],
            [KeyboardButton(text=labels["card"])],
            [KeyboardButton(text=labels["stripe"])],
            [KeyboardButton(text=labels["crypto"])],
            [KeyboardButton(text=labels["ton"])],
            [KeyboardButton(text=shop_back_button_text(is_fa))],
        ],
        resize_keyboard=True,
    )


def shop_skip_keyboard(is_fa: bool = False) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=skip_button_text(is_fa)),
                KeyboardButton(text=cancel_button_text(is_fa)),
            ]
        ],
        resize_keyboard=True,
    )


def shop_input_cancel_keyboard(is_fa: bool = False) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=cancel_button_text(is_fa))]], resize_keyboard=True
    )


# --- /live (owner paying the platform — bot/handlers/live.py) -------------
# All inline-keyboard based (callback_data-driven), so already safe to show
# in either language without any router-filter risk; is_fa was already
# threaded through here before this pass.

_LIVE_METHOD_LABELS = {
    "zarinpal": "💳 Zarinpal",
    "stripe": "🌍 Card (Visa/Mastercard)",
    "ton": "💎 TON",
}
_LIVE_METHOD_LABELS_FA = {
    "zarinpal": "💳 زرین‌پال",
    "stripe": "🌍 کارت (ویزا/مسترکارت)",
    "ton": "💎 TON",
}


def live_plans_keyboard(
    plans: list[dict],
    methods: list[str],
    show_trial: bool,
    show_redeem: bool = False,
    plans_url: str | None = None,
    is_fa: bool = False,
) -> InlineKeyboardMarkup:
    """methods: the payment methods to offer on the bot for this owner's
    region (bot/platform_billing.py) — ["ton", "stripe"] for international,
    usually EMPTY for Iran (they buy on the website instead).

    plans_url: when set and there are no on-bot methods, a "buy on the
    website" link — the payment then runs on the Iranian site with a native
    Iran IP, unaffected by the buyer's Telegram VPN.
    show_redeem: offer "Activate with code" — only when WEBSITE_URL +
    WEBSITE_ACTIVATION_KEY are set.
    """
    method_labels = _LIVE_METHOD_LABELS_FA if is_fa else _LIVE_METHOD_LABELS
    rows = [
        [
            InlineKeyboardButton(
                text=f"{plan['label_fa'] if is_fa and plan.get('label_fa') else plan['label']} — "
                f"{method_labels.get(method, method)}",
                callback_data=f"live:pay:{plan['key']}:{method}",
            )
        ]
        for plan in plans
        for method in methods
    ]
    if not methods and plans_url:
        rows.append(
            [
                InlineKeyboardButton(
                    text="🌐 خرید پلن روی سایت" if is_fa else "🌐 Buy a plan on the website",
                    url=plans_url,
                )
            ]
        )
    if show_redeem:
        rows.append(
            [
                InlineKeyboardButton(
                    text="🎟 فعال‌سازی با کد" if is_fa else "🎟 Activate with a code",
                    callback_data="live:redeem",
                )
            ]
        )
    if show_trial:
        rows.append(
            [
                InlineKeyboardButton(
                    text=("🧪 استفاده‌ی آزمایشی (۷۲ ساعت)" if is_fa else "🧪 Go live on a trial basis (72h)"),
                    callback_data="live:trial",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text=cancel_button_text(is_fa), callback_data="cancel_flow")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def live_region_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🇮🇷 Iran", callback_data="live:region:iran"),
                InlineKeyboardButton(text="🌍 Outside Iran", callback_data="live:region:international"),
            ],
        ]
    )


def live_ton_admin_keyboard(payment_id: int) -> InlineKeyboardMarkup:
    """Sent to PLATFORM_ADMIN_ID (not a bot owner) to confirm/reject a
    submitted TON transaction hash for a /live plan purchase."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Confirm", callback_data=f"live:ton_approve:{payment_id}"),
                InlineKeyboardButton(text="❌ Reject", callback_data=f"live:ton_reject:{payment_id}"),
            ]
        ]
    )


def video_keyboard(video_url: str, is_fa: bool) -> InlineKeyboardMarkup | None:
    """Video tutorial link. Returns None if VIDEO_URL_FA/EN isn't configured
    yet in .env — the guide text still gets sent, just without this button."""
    if not video_url:
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎥 آموزش ویدیویی" if is_fa else "🎥 Video Tutorial", url=video_url
                )
            ]
        ]
    )


def webapp_keyboard(webapp_url: str, bot_id, is_fa: bool = False) -> InlineKeyboardMarkup | None:
    """Inline button opening the visual flow builder Mini App for `bot_id`.
    Returns None when WEBAPP_URL isn't configured (e.g. no tunnel running yet
    in local dev) — Telegram rejects a web_app button without an HTTPS URL."""
    if not webapp_url or not webapp_url.startswith("https://"):
        return None

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=("🎨 سازنده‌ی بصری" if is_fa else "🎨 Visual Builder"),
                    web_app=WebAppInfo(url=f"{webapp_url}?bot_id={bot_id}"),
                )
            ]
        ]
    )


# --- /easybotadmin (bot/handlers/easybotadmin.py) — platform-admin-only, ---
# --- gated by bot/filters/admin.py:IsPlatformAdmin on every handler.     ---
# --- Not localized: this is Siavash's own admin console, not customer-  ---
# --- facing, so it's left out of this pass.                             ---


def admin_panel_menu_keyboard(bots_enabled: bool = True) -> InlineKeyboardMarkup:
    # Global maintenance switch (bot/db/models.py: PlatformSettings) — every
    # built bot keeps running, but /start shows a "back soon" message instead
    # of its normal flow while this is off. Separate from per-bot suspend
    # (admin:suspend:*), which actually kills that one bot's process.
    toggle_text = "🟢 Bots: ON (tap to pause all)" if bots_enabled else "🔴 Bots: OFF (tap to resume all)"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 Stats & Activity", callback_data="admin:stats")],
            [
                InlineKeyboardButton(text="👥 Users", callback_data="admin:users"),
                InlineKeyboardButton(text="🤖 All Bots", callback_data="admin:bots"),
            ],
            [InlineKeyboardButton(text="📢 Broadcast to All", callback_data="admin:broadcast")],
            [InlineKeyboardButton(text=toggle_text, callback_data="admin:toggle_bots")],
        ]
    )


def admin_users_keyboard(users, offset: int, has_more: bool, page_size: int = 20) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"👤 {u.telegram_id}", callback_data=f"admin:user:{u.id}")]
        for u in users
    ]
    nav = []
    if offset > 0:
        nav.append(
            InlineKeyboardButton(text="⬅️ Prev", callback_data=f"admin:users_page:{max(0, offset - page_size)}")
        )
    if has_more:
        nav.append(InlineKeyboardButton(text="➡️ Next", callback_data=f"admin:users_page:{offset + page_size}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="🔙 Back", callback_data="admin:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_bots_keyboard(bots, offset: int, has_more: bool, page_size: int = 20) -> InlineKeyboardMarkup:
    rows = []
    for b in bots:
        icon = "🚫" if b.suspended else "🤖"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{icon} {b.display_name} (@{b.bot_username})", callback_data=f"admin:bot:{b.id}"
                )
            ]
        )
    nav = []
    if offset > 0:
        nav.append(
            InlineKeyboardButton(text="⬅️ Prev", callback_data=f"admin:bots_page:{max(0, offset - page_size)}")
        )
    if has_more:
        nav.append(InlineKeyboardButton(text="➡️ Next", callback_data=f"admin:bots_page:{offset + page_size}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="🔙 Back", callback_data="admin:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_bot_detail_keyboard(built_bot) -> InlineKeyboardMarkup:
    suspend_row = (
        [InlineKeyboardButton(text="✅ Unsuspend", callback_data=f"admin:unsuspend:{built_bot.id}")]
        if built_bot.suspended
        else [InlineKeyboardButton(text="🚫 Suspend", callback_data=f"admin:suspend:{built_bot.id}")]
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            suspend_row,
            [InlineKeyboardButton(text="🎁 Grant Access", callback_data=f"admin:grant:{built_bot.id}")],
            [InlineKeyboardButton(text="✏️ Rename", callback_data=f"admin:rename:{built_bot.id}")],
            [InlineKeyboardButton(text="🗑 Delete Bot", callback_data=f"admin:delete:{built_bot.id}")],
            [InlineKeyboardButton(text="🔙 Back to Bots", callback_data="admin:bots")],
        ]
    )


def admin_grant_access_keyboard(bot_id) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="+30 days", callback_data=f"admin:grantdays:{bot_id}:30"),
                InlineKeyboardButton(text="+90 days", callback_data=f"admin:grantdays:{bot_id}:90"),
            ],
            [
                InlineKeyboardButton(text="+365 days", callback_data=f"admin:grantdays:{bot_id}:365"),
                InlineKeyboardButton(text="♾ Permanent", callback_data=f"admin:grantdays:{bot_id}:permanent"),
            ],
            [InlineKeyboardButton(text="🔙 Cancel", callback_data=f"admin:bot:{bot_id}")],
        ]
    )


def admin_user_detail_keyboard(bots) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"🤖 {b.display_name}", callback_data=f"admin:bot:{b.id}")]
        for b in bots
    ]
    rows.append([InlineKeyboardButton(text="🔙 Back to Users", callback_data="admin:users")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_stats_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📥 Export Full Report (Excel)", callback_data="admin:export")],
            [InlineKeyboardButton(text="🔙 Back", callback_data="admin:menu")],
        ]
    )


def admin_bot_cancel_keyboard(bot_id) -> InlineKeyboardMarkup:
    """Generic "cancel back to this bot's detail view" — used by the
    suspend-reason/rename/delete-confirmation text prompts."""
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔙 Cancel", callback_data=f"admin:bot:{bot_id}")]]
    )
