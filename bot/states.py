from aiogram.fsm.state import State, StatesGroup


class CreateBotStates(StatesGroup):
    waiting_for_token = State()


class DefineCommandStates(StatesGroup):
    waiting_for_command_name = State()
    start_wizard = State()
    confirm_start_wizard = State()
    # Non-/start command action wizard: who sees it, then what it does (and,
    # for a "message" action, the text to send) — see
    # bot/handlers/tools/define_command.py.
    waiting_for_command_visibility = State()
    waiting_for_command_action = State()
    waiting_for_command_message_text = State()


class MessageToAllStates(StatesGroup):
    waiting_for_command_name = State()


class ForceJoinStates(StatesGroup):
    waiting_for_channel_name = State()


class ContentListStates(StatesGroup):
    add_item_wizard = State()
    add_post_wizard = State()  # "Add Post" (photo/video + caption, broadcast to subscribers)
    waiting_for_excel = State()
    lookup_wizard = State()  # "send the code, or browse" step shared by Edit/Delete/Group
    edit_field_wizard = State()


class ShopStates(StatesGroup):
    """Chat-tool side (bot/handlers/tools/shop.py)."""

    add_product_wizard = State()
    waiting_for_zarinpal_id = State()
    waiting_for_card_number = State()
    waiting_for_card_holder = State()
    waiting_for_stripe_key = State()
    waiting_for_crypto_address = State()
    waiting_for_crypto_label = State()
    waiting_for_ton_address = State()
    waiting_for_free_preview_limit = State()
    waiting_for_default_unlock_price = State()
    waiting_for_campaign_percent = State()
    waiting_for_campaign_days = State()
    waiting_for_invoice_business_name = State()
    waiting_for_invoice_logo_url = State()
    waiting_for_invoice_address = State()
    waiting_for_invoice_footer_note = State()
    waiting_for_invoice_business_phone = State()
    waiting_for_invoice_signature_url = State()
    waiting_for_import_file = State()


class AdminBroadcastStates(StatesGroup):
    waiting_for_message = State()


class OnboardingStates(StatesGroup):
    """Optional phone-share step on easymakebot's own /start, used to
    localize the how-to-use guide (see bot/guide.py)."""

    waiting_for_phone = State()


class BuiltBotBroadcastStates(StatesGroup):
    """FSM used inside a live built bot's own dispatcher (bot/runtime.py)."""

    waiting_for_message = State()


class SubscriberOnboardingStates(StatesGroup):
    """Same optional phone-share step as OnboardingStates, but for a built
    bot's own subscribers (used by the "Guide & Video" flow block)."""

    waiting_for_phone = State()


class ShopOrderStates(StatesGroup):
    """Built-bot side (bot/runtime.py) — a buyer's own purchase flow."""

    waiting_for_transaction_ref = State()
    shipping_wizard = State()
    # Kept separate from waiting_for_transaction_ref so a single-item Buy
    # and a cart Checkout in progress at once can never cross-contaminate
    # each other's FSM data.
    waiting_for_checkout_transaction_ref = State()


class PostCommentStates(StatesGroup):
    """Built-bot side (bot/runtime.py) — writing a comment on a post."""

    waiting_for_comment = State()


class AdminPanelStates(StatesGroup):
    """/easybotadmin (bot/handlers/easybotadmin.py) — gated by
    bot/filters/admin.py:IsPlatformAdmin on every handler."""

    waiting_for_suspend_reason = State()
    waiting_for_delete_confirmation = State()  # must type the bot's exact @username
    waiting_for_rename = State()


class LivePlanStates(StatesGroup):
    """/live's platform-billing plan purchase (bot/handlers/live.py +
    bot/platform_billing.py)."""

    waiting_for_ton_tx_hash = State()
    # Redeeming a plan activation code bought on the marketing website
    # (bot/website_client.py). Applies to the currently selected bot.
    waiting_for_activation_code = State()
    # One-time phone share required before the first *paid* activation if we
    # don't already have a Telegram-verified number for this owner (fraud
    # accountability — see bot/handlers/live.py). The pending code / plan+method
    # is stashed in FSM data.
    waiting_for_activation_code_phone = State()
    waiting_for_plan_payment_phone = State()
