from datetime import datetime, timedelta, timezone

from aiogram import Bot, F, Router
from aiogram.filters import Command as CommandFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ReplyKeyboardRemove,
)
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from bot import live, platform_billing, website_client
from bot.config import load_config
from bot.db.base import async_session_maker
from bot.db.models import RedeemedActivationCode, User
from bot.filters.admin import IsPlatformAdmin
from bot.guide import SKIP_BUTTON_TEXT, owner_prefers_persian, normalize_typed_phone, phone_share_keyboard
from bot.keyboards import (
    cancel_inline_keyboard,
    live_plans_keyboard,
    live_region_keyboard,
    live_ton_admin_keyboard,
)
from bot.runtime import start_built_bot
from bot.states import LivePlanStates

router = Router(name="live")
_config = load_config()
_is_platform_admin = IsPlatformAdmin(_config.platform_admin_id)


async def _get_user(telegram_id: int) -> User | None:
    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        return result.scalar_one_or_none()


async def _send_live_status(
    message: Message, bot_id: str, telegram_id: int, state: FSMContext | None = None
) -> None:
    built_bot = await live.get_built_bot(bot_id)
    if built_bot is None:
        # No region known yet at this point (or ever, for a not-found bot) —
        # fall back to owner_prefers_persian same as everywhere else.
        is_fa = await owner_prefers_persian(message.from_user)
        await message.answer("ربات پیدا نشد." if is_fa else "Bot not found.")
        return

    user = await _get_user(telegram_id)
    region = await platform_billing.resolve_region(user) if user else None
    is_fa = region == "iran"

    if live.is_bot_suspended(built_bot):
        extra = (
            "\n\nپلن‌های پرداختی رو همچنان می‌تونی پایین ببینی، ولی ربات تا وقتی ادمین مسدودیت رو "
            "برنداره خاموش می‌مونه — حتی بعد از پرداخت موفق."
            if is_fa
            else "\n\nYou can still see payment plans below, but the bot will stay offline until the "
            "admin lifts the suspension, even after a successful payment."
        )
        await message.answer(f"{live.suspension_status_text(built_bot, is_fa)}{extra}")

    # One-time per PERSON (User.trial_used), not per bot — see bot/live.py:
    # mark_trial_used. A bot that already went live once (live_until is not
    # None) never shows the trial button either way.
    show_trial = built_bot.live_until is None and not (user.trial_used if user else False)

    if region is None:
        await message.answer(
            "One quick question first — where are you based? This decides which payment "
            "methods you'll see below. Tap a button, or just share your phone number below "
            "and we'll figure it out automatically.",
            reply_markup=live_region_keyboard(),
        )
        if state is not None:
            await state.set_state(LivePlanStates.waiting_for_region_phone)
            await message.answer(
                "📱 Share your phone (fastest — no need to pick manually), or tap Skip. "
                "Send /cancel to stop.",
                reply_markup=phone_share_keyboard(),
            )
        return

    methods = platform_billing.available_methods_for_region(region)
    can_redeem = website_client.is_configured()
    plans_url = (
        (_config.website_plans_url if region == "iran" else _config.website_plans_url_en)
        if can_redeem else None
    )

    if not methods and not show_trial and not plans_url and not can_redeem:
        extra = (
            "\n\nهنوز روش پرداختی برای منطقه‌ی تو تنظیم نشده — با ادمین پلتفرم تماس بگیر."
            if is_fa
            else "\n\nNo payment method is configured for your region yet — please contact the platform admin."
        )
        await message.answer(f"{live.status_text(built_bot, is_fa)}{extra}")
        return

    text = live.status_text(built_bot, is_fa)
    if not methods and plans_url:
        text += (
            "\n\nخرید پلن روی وب‌سایت انجام می‌شه (نه داخل تلگرام). اگه با فیلترشکن هستی، "
            "برای صفحهٔ پرداخت موقتاً خاموشش کن تا درگاه ایرانی درست کار کنه. بعد از پرداخت، "
            "کدی که می‌گیری (EMB-XXXX-XXXX) رو با «فعال‌سازی با کد» همین‌جا وارد کن."
            if is_fa
            else "\n\nPlans are bought on the website (opens automatically). Pay with TON (or card, if enabled) — once it confirms, you'll get a code (EMB-XXXX-XXXX). Enter it here with \"Activate with a code\"."
        )

    await message.answer(
        text,
        reply_markup=live_plans_keyboard(
            live.LIVE_PLANS,
            methods,
            show_trial,
            show_redeem=can_redeem,
            plans_url=plans_url,
            is_fa=is_fa,
        ),
    )


@router.message(CommandFilter("live"))
async def cmd_live(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    data = await state.get_data()
    bot_id = data.get("active_bot_id")
    if bot_id is None:
        text = 'اول یه ربات از «ربات‌های من» انتخاب کن.' if is_fa else 'First select a bot from "My Bots".'
        await message.answer(text)
        return

    await _send_live_status(message, bot_id, message.from_user.id, state)


@router.callback_query(F.data.startswith("live:region:"))
async def choose_region(callback: CallbackQuery, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(callback.from_user)
    region = callback.data.split(":")[-1]
    user = await _get_user(callback.from_user.id)
    if user is None:
        text = "یه مشکلی پیش اومد — اول /start رو بزن." if is_fa else "Something went wrong — try /start first."
        await callback.answer(text, show_alert=True)
        return

    await platform_billing.set_region(user.id, region)
    await callback.answer()

    # Picking a region manually supersedes the auto-detect-via-phone prompt
    # _send_live_status may have just started (see waiting_for_region_phone).
    current_state = await state.get_state()
    if current_state == LivePlanStates.waiting_for_region_phone.state:
        await state.set_state(None)
        await callback.message.answer(
            "ممنون! از دکمه‌ی زیر پرداخت می‌کنی، دیگه لازم نیست شماره رو بفرستی."
            if is_fa
            else "Thanks! You'll pay from the button below now — no need to send your phone.",
            reply_markup=ReplyKeyboardRemove(),
        )

    data = await state.get_data()
    bot_id = data.get("active_bot_id")
    if bot_id:
        await _send_live_status(callback.message, bot_id, callback.from_user.id, state)


# --- Auto region detection: share phone instead of picking Iran/international
# manually (live:region:* above still works any time and wins over this) ---


async def _resume_live_after_region_phone(message: Message, state: FSMContext, phone: str) -> None:
    """Shared tail for both handlers below: save the phone, clear the wait
    state, and re-render /live — region is re-derived fresh inside
    _send_live_status from the phone we just saved
    (platform_billing.resolve_region), so this renders the right payment
    methods without asking anything else."""
    await _save_user_phone(message.from_user.id, phone)
    await state.set_state(None)
    is_fa = await owner_prefers_persian(message.from_user)

    data = await state.get_data()
    bot_id = data.get("active_bot_id")
    if not bot_id:
        text = "یه مشکلی پیش اومد — دوباره /live رو بفرست." if is_fa else "Something went wrong — send /live again."
        await message.answer(text, reply_markup=ReplyKeyboardRemove())
        return

    await message.answer("ممنون! 🙌" if is_fa else "Thanks! 🙌", reply_markup=ReplyKeyboardRemove())
    await _send_live_status(message, bot_id, message.from_user.id, state)


@router.message(LivePlanStates.waiting_for_region_phone, F.contact)
async def receive_region_phone_contact(message: Message, state: FSMContext) -> None:
    phone = message.contact.phone_number
    if not phone.startswith("+"):
        phone = f"+{phone}"
    await _resume_live_after_region_phone(message, state, phone)


@router.message(LivePlanStates.waiting_for_region_phone, F.text)
async def receive_region_phone_text(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    if (message.text or "").strip() == SKIP_BUTTON_TEXT:
        await state.set_state(None)
        text = (
            "باشه — از دکمه‌های «ایران» / «خارج از ایران» بالا انتخاب کن."
            if is_fa
            else "No problem — use the Iran / Outside Iran buttons above."
        )
        await message.answer(text, reply_markup=ReplyKeyboardRemove())
        return

    phone = normalize_typed_phone(message.text)
    if phone is None:
        text = (
            "برای تشخیص خودکار، شماره رو با دکمه بفرست یا با کد کشور تایپ کن (مثلاً +989121234567) — "
            "یا از دکمه‌های ایران/خارج از ایران بالا انتخاب کن."
            if is_fa
            else "To auto-detect, share your phone with the button or type it with the country "
            "code (e.g. +989121234567) — or use the Iran / Outside Iran buttons above."
        )
        await message.answer(text, reply_markup=phone_share_keyboard())
        return
    await _resume_live_after_region_phone(message, state, phone)


@router.callback_query(F.data == "live:trial")
async def start_trial(callback: CallbackQuery, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(callback.from_user)
    data = await state.get_data()
    bot_id = data.get("active_bot_id")
    built_bot = await live.get_built_bot(bot_id) if bot_id else None
    if built_bot is None:
        await callback.answer("ربات پیدا نشد." if is_fa else "Bot not found.", show_alert=True)
        return
    if built_bot.live_until is not None:
        text = "دوره‌ی آزمایشی این ربات قبلاً استفاده شده." if is_fa else "The trial has already been used for this bot."
        await callback.answer(text, show_alert=True)
        return

    owner = await _get_user(callback.from_user.id)
    if owner is not None and owner.trial_used:
        text = (
            "آزمایشی رایگانت قبلاً روی یکی دیگه از ربات‌هات مصرف شده — هر حساب فقط یه بار "
            "می‌تونه از تست رایگان استفاده کنه. برای فعال‌سازی این ربات یکی از پلن‌های پرداختی "
            "پایین رو انتخاب کن."
            if is_fa
            else "Your free trial has already been used on another one of your bots — each "
            "account only gets one. Choose a payment plan below to activate this bot."
        )
        await callback.answer(text, show_alert=True)
        return

    until = live.trial_until()
    built_bot = await live.set_live_until(built_bot.id, until)
    await live.mark_trial_used(built_bot.owner_id)
    if not built_bot.suspended:
        start_built_bot(built_bot.id, built_bot.token)

    await callback.answer()
    if is_fa:
        text = f"🎉 ربات تو تا {until:%Y-%m-%d %H:%M} UTC روی تلگرام فعاله — برو تستش کن!"
    else:
        text = f"🎉 Your bot is now live on Telegram until {until:%Y-%m-%d %H:%M} UTC — go test it!"
    await callback.message.answer(text)


# --- Activate with a code bought on the marketing website ----------------


_REDEEM_ERRORS = {
    "already_used": "That code has already been used.",
    "not_found": "No code matches that. Check for typos.",
    "malformed_code": "That doesn't look like a valid code — it should be like EMB-XXXX-XXXX.",
    "void": "That code was cancelled (its order was refunded or failed).",
    "not_configured": "Code activation isn't available right now.",
    "network": "Couldn't reach the store. Please try again in a minute.",
    "bad_response": "The store returned an unexpected response. Please try again later.",
}
_REDEEM_ERRORS_FA = {
    "already_used": "این کد قبلاً استفاده شده.",
    "not_found": "کدی مطابق این پیدا نشد. تایپی رو چک کن.",
    "malformed_code": "این شبیه یه کد معتبر نیست — باید به شکل EMB-XXXX-XXXX باشه.",
    "void": "این کد لغو شده (سفارشش برگشت خورده یا ناموفق بوده).",
    "not_configured": "فعال‌سازی با کد الان در دسترس نیست.",
    "network": "اتصال به فروشگاه برقرار نشد. یه دقیقه دیگه دوباره امتحان کن.",
    "bad_response": "فروشگاه پاسخ غیرمنتظره‌ای برگردوند. بعداً دوباره امتحان کن.",
}


@router.callback_query(F.data == "live:redeem")
async def ask_activation_code(callback: CallbackQuery, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(callback.from_user)
    data = await state.get_data()
    if not data.get("active_bot_id"):
        await callback.answer("ربات پیدا نشد." if is_fa else "Bot not found.", show_alert=True)
        return
    await state.set_state(LivePlanStates.waiting_for_activation_code)
    await callback.answer()
    if is_fa:
        text = (
            "کد فعال‌سازی که از خرید روی وب‌سایت گرفتی رو بفرست — شکلش اینجوریه: "
            "<code>EMB-XXXX-XXXX</code>.\n\n"
            "این کد روی همین رباتی که الان انتخاب کردی اعمال می‌شه. برای توقف /cancel رو بفرست."
        )
    else:
        text = (
            "Send the activation code from your website purchase — it looks like "
            "<code>EMB-XXXX-XXXX</code>.\n\n"
            "It will be applied to the bot you have selected right now. Send /cancel to stop."
        )
    await callback.message.answer(text, reply_markup=cancel_inline_keyboard(is_fa))


_ACTIVATION_PHONE_PROMPT = (
    "One-time check before we activate a paid plan: share the phone number on "
    "your Telegram account with the button below (or type it with the country "
    "code, e.g. +989121234567).\n\n"
    "This links the bot to you and is required for paid activations. Send "
    "/cancel to stop."
)


async def _save_user_phone(telegram_id: int, phone: str) -> None:
    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if user is not None:
            user.phone_number = phone
            await session.commit()


async def _apply_activation_code(
    message: Message, state: FSMContext, code: str, bot_id: str, phone: str | None
) -> None:
    """Redeem `code` for the currently selected bot and start it. `phone` is the
    Telegram-verified number we forward to the store for accountability."""
    is_fa = await owner_prefers_persian(message.from_user)
    built_bot = await live.get_built_bot(bot_id)
    if built_bot is None:
        await state.clear()
        text = (
            'ربات پیدا نشد. یه ربات از «ربات‌های من» انتخاب کن، بعد دوباره /live رو بزن.'
            if is_fa
            else 'Bot not found. Pick a bot from "My Bots", then send /live again.'
        )
        await message.answer(text, reply_markup=ReplyKeyboardRemove())
        return

    u = message.from_user
    result = await website_client.redeem_activation_code(
        code,
        str(bot_id),
        u.id,
        username=u.username,
        first_name=u.first_name,
        phone=phone,
    )

    if not result.get("ok"):
        err = str(result.get("error", "unknown"))
        if is_fa:
            human = _REDEEM_ERRORS_FA.get(err, f"فعال‌سازی ناموفق بود ({err}). با پشتیبانی تماس بگیر.")
        else:
            human = _REDEEM_ERRORS.get(err, f"Activation failed ({err}). Please contact support.")
        await message.answer(f"❌ {human}", reply_markup=ReplyKeyboardRemove())
        if err in ("not_configured",):
            await state.clear()
        else:
            await state.set_state(LivePlanStates.waiting_for_activation_code)
        return  # keep the state so they can just resend a corrected code

    days = int(result.get("days") or 0)
    if days <= 0:
        await state.clear()
        text = "❌ این کد هیچ زمانی نداره. با پشتیبانی تماس بگیر." if is_fa else "❌ That code carries no time. Please contact support."
        await message.answer(text, reply_markup=ReplyKeyboardRemove())
        return

    # website_client.redeem_activation_code() can legitimately report success
    # twice for the same code (its own retry recovery — see its docstring),
    # and a user can also resend the same code after a real failure message.
    # This ledger makes applying the code's `days` to live_until exactly-once
    # on the bot's side, regardless of how many times redemption is reported
    # as successful.
    # Use the website's normalized form of the code (it collapses casing/
    # dashes/spacing the same way on every call) as the ledger key, not the
    # raw text the user typed, so re-typed variants of the same code still
    # dedupe correctly.
    ledger_code = str(result.get("code") or code)
    already_applied = False
    async with async_session_maker() as session:
        session.add(RedeemedActivationCode(code=ledger_code, bot_id=built_bot.id))
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            already_applied = True

    if already_applied:
        await state.clear()
        built_bot = await live.get_built_bot(bot_id)
        until_text = f"{built_bot.live_until:%Y-%m-%d %H:%M} UTC" if built_bot and built_bot.live_until else "?"
        text = (
            f"✅ این کد قبلاً برای این ربات فعال شده بود — رباتت تا {until_text} فعاله."
            if is_fa
            else f"✅ This code was already activated for this bot — it's live until {until_text}."
        )
        await message.answer(text, reply_markup=ReplyKeyboardRemove())
        return

    now = datetime.now(timezone.utc)
    base = built_bot.live_until if (built_bot.live_until and built_bot.live_until > now) else now
    until = base + timedelta(days=days)

    built_bot = await live.set_live_until(built_bot.id, until)
    if built_bot is not None and not built_bot.suspended:
        start_built_bot(built_bot.id, built_bot.token)

    await state.clear()
    months = result.get("months")
    if is_fa:
        span = f"پلن {months} ماهه" if months else f"{days} روز"
        note = "\n\nاز تاریخ انقضای فعلی‌اش تمدید شد." if base != now else ""
        suspended_note = (
            "\n\n⚠️ این ربات توسط ادمین مسدود شده، پس تا وقتی برداشته نشه خاموش می‌مونه."
            if built_bot is not None and built_bot.suspended
            else ""
        )
        text = (
            f"🎉 کد پذیرفته شد — {span} اضافه شد.\n"
            f"رباتت تا {until:%Y-%m-%d %H:%M} UTC روی تلگرام فعاله." + note + suspended_note
        )
    else:
        span = f"a {months}-month plan" if months else f"{days} days"
        note = "\n\nIt was extended from its current expiry date." if base != now else ""
        suspended_note = (
            "\n\n⚠️ This bot is suspended by the admin, so it stays offline until that's lifted."
            if built_bot is not None and built_bot.suspended
            else ""
        )
        text = (
            f"🎉 Code accepted — {span} added.\n"
            f"Your bot is live on Telegram until {until:%Y-%m-%d %H:%M} UTC." + note + suspended_note
        )
    await message.answer(text, reply_markup=ReplyKeyboardRemove())


@router.message(LivePlanStates.waiting_for_activation_code)
async def receive_activation_code(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    code = (message.text or "").strip()
    if not code:
        text = "کد رو بفرست، یا /cancel بزن." if is_fa else "Please send the code, or /cancel."
        await message.answer(text)
        return

    data = await state.get_data()
    bot_id = data.get("active_bot_id")
    built_bot = await live.get_built_bot(bot_id) if bot_id else None
    if built_bot is None:
        await state.clear()
        text = (
            'ربات پیدا نشد. یه ربات از «ربات‌های من» انتخاب کن، بعد دوباره /live رو بزن.'
            if is_fa
            else 'Bot not found. Pick a bot from "My Bots", then send /live again.'
        )
        await message.answer(text)
        return

    user = await _get_user(message.from_user.id)
    phone = (user.phone_number or "").strip() if user else ""

    if not phone:
        # No verified number on file — ask for one before we burn the code.
        await state.update_data(pending_activation_code=code)
        await state.set_state(LivePlanStates.waiting_for_activation_code_phone)
        await message.answer(_ACTIVATION_PHONE_PROMPT, reply_markup=phone_share_keyboard())
        return

    await _apply_activation_code(message, state, code, str(bot_id), phone)


@router.message(LivePlanStates.waiting_for_activation_code_phone, F.contact)
async def receive_activation_phone_contact(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    phone = message.contact.phone_number
    if not phone.startswith("+"):
        phone = f"+{phone}"
    await _save_user_phone(message.from_user.id, phone)

    data = await state.get_data()
    code = str(data.get("pending_activation_code") or "").strip()
    bot_id = data.get("active_bot_id")
    if not code or not bot_id:
        await state.clear()
        text = "یه مشکلی پیش اومد — دوباره /live رو بفرست." if is_fa else "Something went wrong — send /live again."
        await message.answer(text, reply_markup=ReplyKeyboardRemove())
        return
    await _apply_activation_code(message, state, code, str(bot_id), phone)


@router.message(LivePlanStates.waiting_for_activation_code_phone, F.text)
async def receive_activation_phone_text(message: Message, state: FSMContext) -> None:
    if (message.text or "").strip() == SKIP_BUTTON_TEXT:
        await message.answer(
            "A phone number is required to activate a paid plan. Please use the "
            "button, or type it with the country code — or /cancel.",
            reply_markup=phone_share_keyboard(),
        )
        return
    phone = normalize_typed_phone(message.text)
    if phone is None:
        await message.answer(
            "Please share your phone with the button, or type it with the country "
            "code (e.g. +989121234567). Send /cancel to stop.",
            reply_markup=phone_share_keyboard(),
        )
        return
    await _save_user_phone(message.from_user.id, phone)

    is_fa = await owner_prefers_persian(message.from_user)
    data = await state.get_data()
    code = str(data.get("pending_activation_code") or "").strip()
    bot_id = data.get("active_bot_id")
    if not code or not bot_id:
        await state.clear()
        text = "یه مشکلی پیش اومد — دوباره /live رو بفرست." if is_fa else "Something went wrong — send /live again."
        await message.answer(text, reply_markup=ReplyKeyboardRemove())
        return
    await _apply_activation_code(message, state, code, str(bot_id), phone)


# --- Plan payment: Zarinpal (Iran) / Stripe or TON (international) --------


_PLAN_PAYMENT_PHONE_PROMPT = (
    "One-time check before a paid plan: share the phone number on your Telegram "
    "account with the button below (or type it with the country code, e.g. "
    "+989121234567).\n\n"
    "This links the bot to you and is required for any paid activation. Send "
    "/cancel to stop."
)


def _terms_line(is_fa: bool) -> str:
    if _config.website_url:
        if is_fa:
            return f"\n\nبا پرداخت، قوانین استفاده رو می‌پذیری: {_config.website_url}/terms/"
        return f"\n\nBy paying you accept the Terms of Service: {_config.website_url}/terms/"
    return ""


async def _start_plan_payment_flow(
    target: Message, state: FSMContext, plan_key: str, method: str, bot_id: str,
    telegram_id: int,
    remove_kb: bool = False,
    is_fa: bool = False,
) -> None:
    """Create the LivePayment and hand the buyer the pay link / instructions.
    Runs only once we hold a Telegram-verified phone for the owner.
    `remove_kb` drops the phone-share reply keyboard (set when we came via it)."""
    if remove_kb:
        text = "ممنون! 🙌" if is_fa else "Thanks! 🙌"
        await target.answer(text, reply_markup=ReplyKeyboardRemove())

    if method in ("zarinpal", "ton"):
        # One-time identity check before a Zarinpal/TON payment: the owner
        # needs a verified account on the marketing website (same
        # `emb_verified` flag the website itself gates plan purchases on —
        # see web/wordpress/wp-content/mu-plugins/emb-accounts.php). If they
        # never visited the website, this collects the same fields it would
        # have and sends an OTP, right here in the bot. Suspends the flow
        # (returns without creating a LivePayment) until verified; the
        # eventual code-confirm handler below resumes by re-entering this
        # same function. Silently skipped if WEBSITE_VERIFY_KEY isn't
        # configured on this install (graceful-omit).
        verified = await _ensure_site_verified(
            target, state, plan_key, method, bot_id, telegram_id, is_fa
        )
        if not verified:
            return

    payment = await platform_billing.create_live_payment(bot_id, plan_key, method)
    if payment is None:
        await state.set_state(None)
        await target.answer("پلن پیدا نشد." if is_fa else "Plan not found.")
        return

    if method in ("zarinpal", "stripe"):
        await state.set_state(None)
        starter = (
            platform_billing.start_zarinpal_live_payment
            if method == "zarinpal"
            else platform_billing.start_stripe_live_payment
        )
        pay_url = await starter(payment, _config.webapp_url)
        if pay_url is None:
            text = "شروع پرداخت ممکن نشد. بعداً دوباره امتحان کن." if is_fa else "Couldn't start the payment. Please try again later."
            await target.answer(text)
            return
        pay_text = "برای پرداخت بزن:" if is_fa else "Tap below to pay:"
        pay_button = "🔗 پرداخت" if is_fa else "🔗 Pay Now"
        await target.answer(
            pay_text + _terms_line(is_fa),
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text=pay_button, url=pay_url)]]
            ),
        )
        return

    if method == "ton":
        if not _config.platform_ton_wallet_address:
            await state.set_state(None)
            text = "TON هنوز راه‌اندازی نشده. با ادمین پلتفرم تماس بگیر." if is_fa else "TON isn't set up yet. Please contact the platform admin."
            await target.answer(text)
            return
        await state.update_data(live_payment_id=payment.id)
        await state.set_state(LivePlanStates.waiting_for_ton_tx_hash)
        if is_fa:
            text = (
                f"💎 آدرس کیف‌پول TON:\n{_config.platform_ton_wallet_address}\n\n"
                f"💰 مبلغ: ${payment.price} (معادلش رو با TON پرداخت کن)\n\n"
                "بعد از پرداخت، هش تراکنش رو بفرست." + _terms_line(is_fa)
            )
        else:
            text = (
                f"💎 TON wallet address:\n{_config.platform_ton_wallet_address}\n\n"
                f"💰 Amount: ${payment.price} (pay the equivalent in TON)\n\n"
                "After paying, send the transaction hash." + _terms_line(is_fa)
            )
        await target.answer(text, reply_markup=cancel_inline_keyboard(is_fa))


@router.callback_query(F.data.startswith("live:pay:"))
async def start_plan_payment(callback: CallbackQuery, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(callback.from_user)
    _, _, plan_key, method = callback.data.split(":")
    data = await state.get_data()
    bot_id = data.get("active_bot_id")
    if bot_id is None:
        await callback.answer("ربات پیدا نشد." if is_fa else "Bot not found.", show_alert=True)
        return

    await callback.answer()

    user = await _get_user(callback.from_user.id)
    phone = (user.phone_number or "").strip() if user else ""
    if not phone:
        await state.update_data(pending_plan_pay={"plan_key": plan_key, "method": method})
        await state.set_state(LivePlanStates.waiting_for_plan_payment_phone)
        await callback.message.answer(
            _PLAN_PAYMENT_PHONE_PROMPT, reply_markup=phone_share_keyboard()
        )
        return

    await _start_plan_payment_flow(
        callback.message, state, plan_key, method, str(bot_id),
        telegram_id=callback.from_user.id, is_fa=is_fa,
    )


async def _resume_plan_payment_after_phone(message: Message, state: FSMContext, phone: str) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    await _save_user_phone(message.from_user.id, phone)
    data = await state.get_data()
    pend = data.get("pending_plan_pay") or {}
    bot_id = data.get("active_bot_id")
    if not pend.get("plan_key") or not pend.get("method") or not bot_id:
        await state.clear()
        text = "یه مشکلی پیش اومد — دوباره /live رو بفرست." if is_fa else "Something went wrong — send /live again."
        await message.answer(text, reply_markup=ReplyKeyboardRemove())
        return
    await _start_plan_payment_flow(
        message, state, pend["plan_key"], pend["method"], str(bot_id),
        telegram_id=message.from_user.id, remove_kb=True, is_fa=is_fa,
    )


@router.message(LivePlanStates.waiting_for_plan_payment_phone, F.contact)
async def receive_plan_payment_phone_contact(message: Message, state: FSMContext) -> None:
    phone = message.contact.phone_number
    if not phone.startswith("+"):
        phone = f"+{phone}"
    await _resume_plan_payment_after_phone(message, state, phone)


@router.message(LivePlanStates.waiting_for_plan_payment_phone, F.text)
async def receive_plan_payment_phone_text(message: Message, state: FSMContext) -> None:
    if (message.text or "").strip() == SKIP_BUTTON_TEXT:
        await message.answer(
            "A phone number is required for a paid plan. Please use the button, "
            "or type it with the country code — or /cancel.",
            reply_markup=phone_share_keyboard(),
        )
        return
    phone = normalize_typed_phone(message.text)
    if phone is None:
        await message.answer(
            "Please share your phone with the button, or type it with the country "
            "code (e.g. +989121234567). Send /cancel to stop.",
            reply_markup=phone_share_keyboard(),
        )
        return
    await _resume_plan_payment_after_phone(message, state, phone)


# --- Website identity verification gate (Zarinpal / TON only) -------------
# See _start_plan_payment_flow's call site above for when this runs.


# Bilingual error text for every verify_* error code lives in
# bot/website_client.py:verify_error_text — shared with bot/runtime.py's
# flow-builder verify_gate node so the two surfaces never drift on wording
# for the same bridge/error vocabulary.
_verify_error_text = website_client.verify_error_text


async def _mark_site_verified(telegram_id: int, email: str | None = None) -> None:
    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if user is not None:
            user.site_verified = True
            if email:
                user.site_email = email
            await session.commit()


async def _ensure_site_verified(
    target: Message, state: FSMContext, plan_key: str, method: str, bot_id: str,
    telegram_id: int, is_fa: bool,
) -> bool:
    """Returns True if the owner is already (or just became) verified and the
    payment flow should proceed immediately. Returns False if it suspended
    the flow to collect fields / an OTP code — the pending plan+method is
    stashed in FSM data (pending_plan_pay) so the eventual code-confirm
    handler can resume _start_plan_payment_flow itself."""
    if not website_client.verify_is_configured():
        return True  # feature not deployed on this install — don't block payment

    user = await _get_user(telegram_id)
    if user is not None and user.site_verified:
        return True

    await state.update_data(pending_plan_pay={"plan_key": plan_key, "method": method})

    channel = "sms" if method == "zarinpal" else "email"
    phone = (user.phone_number or "").strip() if user else ""
    email = (user.site_email or "").strip() if user else ""

    status = await website_client.check_verification_status(
        channel, phone=phone or None, email=email or None
    )
    if not status.get("ok"):
        await target.answer(f"❌ {_verify_error_text(is_fa, str(status.get('error', 'network')))}")
        await state.set_state(None)
        return False

    if status.get("verified"):
        await _mark_site_verified(telegram_id, email or None)
        return True

    await state.update_data(verify_channel=channel)

    if status.get("registered"):
        # Already has an account for this phone/email — no need to re-collect
        # name/address, just send it a fresh code.
        resend = await website_client.resend_verification(
            channel, phone=phone or None, email=email or None
        )
        if not resend.get("ok"):
            await target.answer(f"❌ {_verify_error_text(is_fa, str(resend.get('error', 'network')))}")
            await state.set_state(None)
            return False
        await state.update_data(verify_phone=phone or None, verify_email=email or None)
        await state.set_state(LivePlanStates.waiting_for_verify_code)
        await target.answer(
            _verify_code_prompt(is_fa, channel), reply_markup=cancel_inline_keyboard(is_fa)
        )
        return False

    if channel == "sms":
        await state.set_state(LivePlanStates.waiting_for_verify_first_name)
        await target.answer(_verify_intro_iran(is_fa), reply_markup=cancel_inline_keyboard(is_fa))
    else:
        await state.set_state(LivePlanStates.waiting_for_verify_email)
        await target.answer(_verify_intro_intl(is_fa), reply_markup=cancel_inline_keyboard(is_fa))
    return False


def _verify_intro_iran(is_fa: bool) -> str:
    terms = _terms_line(is_fa)
    if is_fa:
        return (
            "قبل از پرداخت با زرین‌پال، چون اولین بارته، باید حسابت رو تأیید کنیم — همون "
            "مشخصاتی که تو سایت هم گرفته می‌شه.\n\nاول اسمت رو بفرست." + terms
        )
    return (
        "Before paying with Zarinpal, since this is your first time, we need to verify your "
        "account — the same details the website collects.\n\nFirst, send your first name." + terms
    )


def _verify_intro_intl(is_fa: bool) -> str:
    terms = _terms_line(is_fa)
    if is_fa:
        return "قبل از پرداخت با TON، ایمیلت رو بفرست تا یه کد تأیید براش بفرستیم." + terms
    return "Before paying with TON, send your email so we can send a verification code." + terms


def _verify_code_prompt(is_fa: bool, channel: str) -> str:
    via = ("پیامک" if channel == "sms" else "ایمیل") if is_fa else ("SMS" if channel == "sms" else "email")
    if is_fa:
        return f"کد ۶ رقمی که با {via} فرستادیم رو بفرست. کد رو نگرفتی؟ /resend رو بزن."
    return f"Send the 6-digit code we just sent by {via}. Didn't get it? Send /resend."


@router.message(LivePlanStates.waiting_for_verify_first_name)
async def receive_verify_first_name(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    name = (message.text or "").strip()
    if not name or len(name) > 100:
        text = "اسمت رو بفرست (حداکثر ۱۰۰ کاراکتر)، یا /cancel." if is_fa else "Send your first name (max 100 characters), or /cancel."
        await message.answer(text)
        return
    await state.update_data(verify_first_name=name)
    await state.set_state(LivePlanStates.waiting_for_verify_last_name)
    text = "حالا فامیلت رو بفرست." if is_fa else "Now send your last name."
    await message.answer(text)


@router.message(LivePlanStates.waiting_for_verify_last_name)
async def receive_verify_last_name(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    name = (message.text or "").strip()
    if not name or len(name) > 100:
        text = "فامیلت رو بفرست (حداکثر ۱۰۰ کاراکتر)، یا /cancel." if is_fa else "Send your last name (max 100 characters), or /cancel."
        await message.answer(text)
        return
    await state.update_data(verify_last_name=name)
    await state.set_state(LivePlanStates.waiting_for_verify_address)
    text = "حالا آدرست رو بفرست." if is_fa else "Now send your address."
    await message.answer(text)


@router.message(LivePlanStates.waiting_for_verify_address)
async def receive_verify_address(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    address = (message.text or "").strip()
    if not address or len(address) > 500:
        text = "آدرست رو بفرست (حداکثر ۵۰۰ کاراکتر)، یا /cancel." if is_fa else "Send your address (max 500 characters), or /cancel."
        await message.answer(text)
        return
    await state.update_data(verify_address=address)
    await state.set_state(LivePlanStates.waiting_for_verify_email)
    text = "در آخر، ایمیلت رو بفرست." if is_fa else "Finally, send your email."
    await message.answer(text)


def _looks_like_email(value: str) -> bool:
    return bool(value) and 3 <= len(value) <= 254 and "@" in value and "." in value.split("@")[-1]


@router.message(LivePlanStates.waiting_for_verify_email)
async def receive_verify_email(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    email = (message.text or "").strip()
    if not _looks_like_email(email):
        text = "این یه ایمیل معتبر به نظر نمی‌رسه. دوباره بفرست، یا /cancel." if is_fa else "That doesn't look like a valid email. Please resend it, or /cancel."
        await message.answer(text)
        return

    data = await state.get_data()
    channel = data.get("verify_channel") or "email"
    telegram_id = message.from_user.id
    u = message.from_user

    if channel == "sms":
        user = await _get_user(telegram_id)
        phone = (user.phone_number or "").strip() if user else ""
        result = await website_client.start_verification(
            "sms",
            phone=phone,
            email=email,
            first_name=data.get("verify_first_name"),
            last_name=data.get("verify_last_name"),
            address=data.get("verify_address"),
            tos=True,
            telegram_id=telegram_id,
            telegram_username=u.username,
            telegram_first_name=u.first_name,
        )
    else:
        phone = None
        result = await website_client.start_verification(
            "email",
            email=email,
            tos=True,
            telegram_id=telegram_id,
            telegram_username=u.username,
            telegram_first_name=u.first_name,
        )

    if not result.get("ok"):
        err = str(result.get("error", "network"))
        await message.answer(f"❌ {_verify_error_text(is_fa, err)}")
        if err in ("phone_taken", "email_taken", "not_configured"):
            await state.set_state(None)
        # else: stay in this same state so they can resend a corrected email
        return

    if result.get("already_verified"):
        await _mark_site_verified(telegram_id, email)
        await _resume_plan_payment_after_verification(message, state, is_fa)
        return

    await state.update_data(verify_email=email, verify_phone=phone)
    await state.set_state(LivePlanStates.waiting_for_verify_code)
    text = "ممنون! 🙌" if is_fa else "Thanks! 🙌"
    await message.answer(text)
    await message.answer(_verify_code_prompt(is_fa, channel), reply_markup=cancel_inline_keyboard(is_fa))


async def _resume_plan_payment_after_verification(message: Message, state: FSMContext, is_fa: bool) -> None:
    data = await state.get_data()
    pend = data.get("pending_plan_pay") or {}
    bot_id = data.get("active_bot_id")
    if not pend.get("plan_key") or not pend.get("method") or not bot_id:
        await state.clear()
        text = "یه مشکلی پیش اومد — دوباره /live رو بفرست." if is_fa else "Something went wrong — send /live again."
        await message.answer(text)
        return
    text = "✅ حسابت تأیید شد!" if is_fa else "✅ Your account is verified!"
    await message.answer(text)
    await _start_plan_payment_flow(
        message, state, pend["plan_key"], pend["method"], str(bot_id),
        telegram_id=message.from_user.id, is_fa=is_fa,
    )


@router.message(LivePlanStates.waiting_for_verify_code, CommandFilter("resend"))
async def resend_verify_code(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    data = await state.get_data()
    channel = data.get("verify_channel") or "email"
    phone = data.get("verify_phone")
    email = data.get("verify_email")
    result = await website_client.resend_verification(channel, phone=phone, email=email)
    if not result.get("ok"):
        await message.answer(f"❌ {_verify_error_text(is_fa, str(result.get('error', 'network')))}")
        return
    if result.get("already_verified"):
        await _mark_site_verified(message.from_user.id, email)
        await _resume_plan_payment_after_verification(message, state, is_fa)
        return
    text = "یه کد جدید فرستادیم." if is_fa else "Sent a new code."
    await message.answer(text)


@router.message(LivePlanStates.waiting_for_verify_code)
async def receive_verify_code(message: Message, state: FSMContext) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    code = (message.text or "").strip()
    if not code:
        text = "کد رو بفرست، یا /cancel بزن." if is_fa else "Please send the code, or /cancel."
        await message.answer(text)
        return

    data = await state.get_data()
    channel = data.get("verify_channel") or "email"
    phone = data.get("verify_phone")
    email = data.get("verify_email")
    result = await website_client.confirm_verification(channel, code, phone=phone, email=email)
    if not result.get("ok"):
        await message.answer(f"❌ {_verify_error_text(is_fa, str(result.get('error', 'mismatch')))}")
        return  # keep the state so they can retry (or /resend, or /cancel)

    await _mark_site_verified(message.from_user.id, email)
    await _resume_plan_payment_after_verification(message, state, is_fa)


@router.message(LivePlanStates.waiting_for_ton_tx_hash)
async def receive_ton_tx_hash(message: Message, state: FSMContext, bot: Bot) -> None:
    is_fa = await owner_prefers_persian(message.from_user)
    data = await state.get_data()
    payment_id = data.get("live_payment_id")
    if not payment_id:
        await state.clear()
        return

    tx_hash = (message.text or "").strip()
    if not tx_hash:
        text = "هش تراکنش رو بفرست، یا /cancel بزن." if is_fa else "Please send the transaction hash, or /cancel to abort."
        await message.answer(text)
        return

    payment = await platform_billing.submit_ton_live_payment(payment_id, tx_hash)
    await state.clear()
    text = (
        "ممنون! پرداختت در انتظار بررسی ادمین پلتفرمه."
        if is_fa
        else "Thanks! Your payment is pending review by the platform admin."
    )
    await message.answer(text)

    built_bot = await live.get_built_bot(payment.bot_id)
    owner = await _get_user(message.from_user.id)
    u = message.from_user
    try:
        await bot.send_message(
            _config.platform_admin_id,
            f"🧾 New /live TON payment #{payment.id}\n"
            f"Bot: @{built_bot.bot_username if built_bot else '?'}\n"
            f"Plan: {payment.plan_key} — ${payment.price}\n"
            f"Owner: {('@' + u.username) if u.username else u.first_name} "
            f"(tg {u.id}"
            + (f", phone {owner.phone_number}" if owner and owner.phone_number else "")
            + ")\n"
            f"Transaction hash: {tx_hash}",
            reply_markup=live_ton_admin_keyboard(payment.id),
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("live:ton_approve:"), _is_platform_admin)
async def approve_ton_payment(callback: CallbackQuery) -> None:
    payment_id = int(callback.data.split(":")[-1])
    payment = await platform_billing.approve_ton_live_payment(payment_id)
    if payment is None:
        await callback.answer("Not found.", show_alert=True)
        return
    await callback.answer("Approved ✅")
    await callback.message.edit_reply_markup(reply_markup=None)


@router.callback_query(F.data.startswith("live:ton_reject:"), _is_platform_admin)
async def reject_ton_payment(callback: CallbackQuery) -> None:
    payment_id = int(callback.data.split(":")[-1])
    await platform_billing.reject_ton_live_payment(payment_id)
    await callback.answer("Rejected")
    await callback.message.edit_reply_markup(reply_markup=None)
