"""Every user-facing sentence, Persian and English. Elder-facing texts are
short, warm and never technical — they are read by people who may find a
phone hard to use."""

STATUS_ICON = {"ok": "✅", "concern": "⚠️", "missed": "❌", "undelivered": "📵", "pending": "⏳"}

_STATUS_WORD = {
    "fa": {"ok": "جواب داد", "concern": "نگران‌کننده", "missed": "بی‌جواب", "undelivered": "نرسید", "pending": "در انتظار"},
    "en": {"ok": "answered", "concern": "worrying", "missed": "no answer", "undelivered": "not delivered", "pending": "waiting"},
}


def _summary(lang: str):
    def render(elder: str, events, **_) -> str:
        head = f"🌙 گزارش امروز {elder}:" if lang == "fa" else f"🌙 Today with {elder}:"
        lines = [head]
        for label, status, response in events:
            line = f"{STATUS_ICON.get(status, '•')} {label} — {_STATUS_WORD[lang].get(status, status)}"
            if response:
                line += f"\n   «{response[:200]}»"
            lines.append(line)
        return "\n".join(lines)
    return render


TEXTS: dict[str, dict] = {
    # --- language / menu ---
    "choose_lang": {"fa": "زبان را انتخاب کنید:", "en": "Choose your language:"},
    "welcome": {
        "fa": "به همدم خوش آمدید 🌿\nهمدم هر روز حال پدر یا مادرتان را می‌پرسد، داروهایشان را یادآوری می‌کند و هر چیز نگران‌کننده‌ای را فوراً به شما خبر می‌دهد — هر جای دنیا که باشید.",
        "en": "Welcome to Hamdam 🌿\nHamdam checks on your parent every day, reminds them of their medicine and tells you right away if anything looks wrong — wherever in the world you both are.",
    },
    "menu": {
        "fa": "چه کاری انجام دهیم؟\n(اگر خودتان پدر/مادر هستید، فقط کد ۸ رقمی را که فرزندتان داده بفرستید.)",
        "en": "What would you like to do?\n(If you are the parent, just send the 8-digit code your family gave you.)",
    },
    "btn_add": {"fa": "➕ افزودن پدر/مادر", "en": "➕ Add a parent"},
    "btn_list": {"fa": "👵 پدر و مادرهای من", "en": "👵 My parents"},
    "btn_join": {"fa": "🔗 پیوستن با کد خانواده", "en": "🔗 Join with a family code"},
    "btn_lang": {"fa": "🌐 زبان", "en": "🌐 Language"},
    # --- add flow ---
    "ask_where": {"fa": "پدر/مادرتان کجا زندگی می‌کنند؟", "en": "Where does your parent live?"},
    "ask_elder_name": {"fa": "شما ایشان را چه صدا می‌زنید؟ (مثلاً: مامان)", "en": "What do you call them? (e.g. Mum)"},
    "ask_elder_title": {
        "fa": "ربات ایشان را چطور خطاب کند؟ (مثلاً: مادر عزیز، حاج‌خانم)",
        "en": "How should the bot address them? (e.g. Dear Mary)",
    },
    "ask_tz": {"fa": "منطقه زمانی ایشان را انتخاب کنید (یا بنویسید، مثل Europe/Paris):",
               "en": "Pick their time zone (or type one, e.g. Europe/Paris):"},
    "ask_checkin_time": {"fa": "ساعت احوال‌پرسی روزانه به وقت ایشان؟ (مثلاً 10:00)",
                         "en": "Daily check-in time, their local time? (e.g. 10:00)"},
    "ask_summary_time": {"fa": "ساعت گزارش شبانه برای شما، به وقت ایشان؟ (مثلاً 21:00)",
                         "en": "Evening summary time, their local time? (e.g. 21:00)"},
    "ask_elder_phone": {"fa": "شماره موبایل ایشان (برای پیامک پشتیبان وقتی پیام‌رسان در دسترس نیست):",
                        "en": "Their mobile number (SMS backup when the messenger can't be reached):"},
    "circle_created": {
        "fa": "✅ {elder} اضافه شد. {days} روز استفاده رایگان دارید.",
        "en": "✅ {elder} added. You have a {days}-day free trial.",
    },
    "invite_elder": {
        "fa": "📲 برای وصل کردن ایشان: در {app} ربات همدم را باز کنند و این کد را بفرستند:\n{code}",
        "en": "📲 To connect them: they open the Hamdam bot on {app} and send this code:\n{code}",
    },
    "new_elder_code": {"fa": "کد جدید برای ایشان:\n{code}", "en": "New code for them:\n{code}"},
    "invite_family": {
        "fa": "👨‍👩‍👧 خواهر و برادرها هم می‌توانند با این کد خانواده (از هر کشوری) عضو شوند:\n{code}",
        "en": "👨‍👩‍👧 Siblings can join from any country with this family code:\n{code}",
    },
    "ask_family_code": {"fa": "کد خانواده را بفرستید:", "en": "Send the family code:"},
    "no_circles": {"fa": "هنوز کسی اضافه نشده.", "en": "Nobody added yet."},
    "your_circles": {"fa": "انتخاب کنید:", "en": "Choose:"},
    # --- circle view ---
    "view_head": {"fa": "👵 {elder} — {place}", "en": "👵 {elder} — {place}"},
    "view_linked": {"fa": "🟢 وصل است", "en": "🟢 Connected"},
    "view_not_linked": {"fa": "⚪️ هنوز وصل نشده (از «دعوت» کد را بگیرید)", "en": "⚪️ Not connected yet (get the code from “Invite”)"},
    "view_times": {"fa": "⏰ احوال‌پرسی {checkin} · گزارش {summary} ({tz})",
                   "en": "⏰ Check-in {checkin} · summary {summary} ({tz})"},
    "view_meds": {"fa": "💊", "en": "💊"},
    "view_days": {"fa": "📅 {days} روز اشتراک باقی مانده", "en": "📅 {days} days of subscription left"},
    "view_paused": {"fa": "⏸ متوقف", "en": "⏸ Paused"},
    "view_today": {"fa": "امروز:", "en": "Today:"},
    "btn_meds": {"fa": "💊 داروها", "en": "💊 Medicines"},
    "btn_checkin_time": {"fa": "⏰ ساعت احوال‌پرسی", "en": "⏰ Check-in time"},
    "btn_summary_time": {"fa": "🌙 ساعت گزارش", "en": "🌙 Summary time"},
    "btn_pause": {"fa": "⏸ توقف موقت", "en": "⏸ Pause"},
    "btn_resume": {"fa": "▶️ ادامه", "en": "▶️ Resume"},
    "btn_locals": {"fa": "🏘 رابط محلی", "en": "🏘 Local contact"},
    "btn_elder_phone": {"fa": "📱 شماره ایشان", "en": "📱 Their phone"},
    "btn_invite": {"fa": "🔗 دعوت", "en": "🔗 Invite"},
    "btn_pay": {"fa": "💳 اشتراک", "en": "💳 Subscribe"},
    "btn_leave": {"fa": "🚪 خروج از این خانواده", "en": "🚪 Leave"},
    "btn_new_elder_code": {"fa": "🔄 کد جدید برای پدر/مادر", "en": "🔄 New code for the parent"},
    "leave_confirm": {"fa": "مطمئنید؟ دیگر خبری دریافت نمی‌کنید.", "en": "Sure? You'll stop receiving updates."},
    "btn_yes_leave": {"fa": "بله، خارج شو", "en": "Yes, leave"},
    "left": {"fa": "خارج شدید.", "en": "Done."},
    # --- meds / locals ---
    "meds_head": {"fa": "💊 داروها (برای حذف بزنید):", "en": "💊 Medicines (tap to remove):"},
    "btn_add_med": {"fa": "➕ داروی جدید", "en": "➕ Add medicine"},
    "ask_med_name": {"fa": "اسم دارو؟ (مثلاً قرص فشار)", "en": "Medicine name? (e.g. blood-pressure pill)"},
    "ask_med_time": {"fa": "ساعت مصرف به وقت ایشان؟ (مثلاً 08:00)", "en": "Time, their local time? (e.g. 08:00)"},
    "locals_head": {
        "fa": "🏘 رابط محلی کسی نزدیک ایشان است (همسایه، فامیل). اگر خبر فوری باشد، یا ارتباط شما قطع باشد، با پیامک خبردار می‌شود:",
        "en": "🏘 A local contact lives near them (a neighbour, a relative). They get an SMS for urgent news, or when you can't be reached:",
    },
    "locals_no_sms": {"fa": "پیامک در منطقه ایشان هنوز فعال نیست.", "en": "SMS isn't available in their region yet."},
    "btn_add_local": {"fa": "➕ رابط جدید", "en": "➕ Add contact"},
    "ask_local_name": {"fa": "اسم رابط؟", "en": "Contact's name?"},
    "ask_local_phone": {"fa": "شماره موبایل رابط؟", "en": "Contact's mobile number?"},
    # --- payment ---
    "pay_none": {"fa": "پرداخت در منطقه شما هنوز فعال نیست. با پشتیبانی در تماس باشید.",
                 "en": "Payment isn't available in your region yet — please contact support."},
    "pay_choose_plan": {"fa": "مدت اشتراک:", "en": "Choose a plan:"},
    "plan_m1": {"fa": "یک ماهه", "en": "1 month"},
    "plan_m3": {"fa": "سه ماهه (۱۰٪ تخفیف)", "en": "3 months (10% off)"},
    "pay_choose_method": {"fa": "روش پرداخت:", "en": "Payment method:"},
    "method_zarinpal": {"fa": "💳 درگاه بانکی — {amount} تومان", "en": "💳 Iranian bank card — {amount} Toman"},
    "method_ton": {"fa": "💎 TON — معادل ${amount}", "en": "💎 TON — ${amount} equivalent"},
    "pay_zarinpal": {"fa": "مبلغ {amount} تومان. برای پرداخت این لینک را باز کنید:",
                     "en": "{amount} Toman. Open this link to pay:"},
    "pay_ton": {
        "fa": "💎 معادل ${amount} را به این کیف پول TON بفرستید:\n{wallet}\n\nدر توضیح (comment) بنویسید: {memo}\nبعد هش تراکنش را همین‌جا بفرستید.",
        "en": "💎 Send the equivalent of ${amount} in TON to:\n{wallet}\n\nPut this in the comment: {memo}\nThen send the transaction hash here.",
    },
    "pay_ton_sent": {"fa": "ممنون! پس از بررسی (معمولاً چند ساعت) فعال می‌شود.", "en": "Thanks! It's activated after review (usually within hours)."},
    "paid_ok": {"fa": "🎉 پرداخت تأیید شد — {days} روز اضافه شد.", "en": "🎉 Payment confirmed — {days} days added."},
    "paid_rejected": {"fa": "❌ پرداخت تأیید نشد. لطفاً با پشتیبانی تماس بگیرید.", "en": "❌ The payment couldn't be confirmed. Please contact support."},
    "sub_extended": {"fa": "📅 اشتراک {elder} تا {until} تمدید شد.", "en": "📅 {elder}'s subscription now runs until {until}."},
    "sub_expired": {
        "fa": "⏳ اشتراک {elder} تمام شده و احوال‌پرسی‌ها متوقف شده‌اند. از «💳 اشتراک» تمدید کنید.",
        "en": "⏳ {elder}'s subscription has ended and check-ins are paused. Renew from “💳 Subscribe”.",
    },
    # --- errors ---
    "err_peer_down": {
        "fa": "📵 ارتباط با سرور منطقه ایشان الان برقرار نیست (احتمالاً قطعی اینترنت). مراقبت روزانه آنجا ادامه دارد؛ کمی بعد دوباره امتحان کنید.",
        "en": "📵 Their region's server can't be reached right now (likely an internet shutdown). Daily care continues there; please try again later.",
    },
    "err_failed": {"fa": "مشکلی پیش آمد، دوباره امتحان کنید.", "en": "Something went wrong — please try again."},
    "err_forbidden": {"fa": "به این خانواده دسترسی ندارید.", "en": "You're not a member of this family."},
    "err_not_found": {"fa": "پیدا نشد.", "en": "Not found."},
    "err_invalid": {"fa": "مقدار درست نیست.", "en": "That value isn't valid."},
    "err_bad_code": {"fa": "این کد معتبر نیست.", "en": "That code isn't valid."},
    "err_sms_unavailable": {"fa": "پیامک در منطقه ایشان فعال نیست.", "en": "SMS isn't available in their region."},
    "err_time": {"fa": "ساعت را مثل 09:30 بنویسید.", "en": "Please write the time like 09:30."},
    "err_tz": {"fa": "منطقه زمانی شناخته نشد (مثال: Europe/Paris).", "en": "Unknown time zone (e.g. Europe/Paris)."},
    # --- elder ---
    "elder_welcome": {
        "fa": "سلام {title} 🌸\nمن همدم هستم. هر روز حالتان را می‌پرسم و داروهایتان را یادآوری می‌کنم. هر وقت خواستید می‌توانید پیام یا صدا بفرستید؛ به خانواده‌تان می‌رسانم.",
        "en": "Hello {title} 🌸\nI'm Hamdam. I'll ask how you are each day and remind you of your medicine. Send me a message or a voice note any time — I'll pass it to your family.",
    },
    "elder_checkin": {"fa": "سلام {title} 🌸 روزتان بخیر!\nحالتان چطور است؟", "en": "Good day {title} 🌸\nHow are you today?"},
    "elder_reminder": {"fa": "{title} جان، فقط می‌خواستم مطمئن شوم حالتان خوب است 🌷", "en": "{title}, just making sure you're alright 🌷"},
    "elder_med": {"fa": "⏰ {title}، وقت {med} است.", "en": "⏰ {title}, it's time for {med}."},
    "elder_med_reminder": {"fa": "{title}، {med} را خوردید؟", "en": "{title}, did you take {med}?"},
    "btn_ok": {"fa": "😊 خوبم", "en": "😊 I'm fine"},
    "btn_bad": {"fa": "😕 خوب نیستم", "en": "😕 Not so good"},
    "btn_taken": {"fa": "✅ خوردم", "en": "✅ Taken"},
    "elder_thanks": {"fa": "خدا را شکر 🌼 روز خوبی داشته باشید.", "en": "Lovely 🌼 Have a good day."},
    "elder_med_ok": {"fa": "آفرین 🌼", "en": "Well done 🌼"},
    "elder_sorry": {
        "fa": "متأسفم {title} 💐 به خانواده‌تان خبر دادم. اگر دوست دارید بگویید چه شده — می‌توانید پیام صوتی بفرستید.",
        "en": "I'm sorry, {title} 💐 I've told your family. Tell me what's wrong if you like — a voice note is fine.",
    },
    "elder_got_it": {"fa": "به خانواده‌تان رساندم 🌷", "en": "I've passed it on to your family 🌷"},
    "elder_got_concern": {"fa": "به خانواده‌تان خبر دادم 💐 ان‌شاءالله زود بهتر می‌شوید.",
                          "en": "I've let your family know 💐 I hope you feel better soon."},
    "elder_got_urgent": {"fa": "به خانواده‌تان فوری خبر دادم 💐 اگر حالتان بد است با اورژانس (۱۱۵) تماس بگیرید.",
                         "en": "I've alerted your family 💐 If you feel unwell, please call emergency services."},
    "sms_no_reply": {"fa": "(همدم)", "en": "(Hamdam)"},
    "checkin_label": {"fa": "احوال‌پرسی", "en": "Check-in"},
    # --- family notifications ---
    "elder_linked": {"fa": "🟢 {elder} وصل شد! احوال‌پرسی از نوبت بعدی شروع می‌شود.", "en": "🟢 {elder} is connected! Check-ins start from the next scheduled time."},
    "family_joined": {"fa": "👋 {name} به خانواده {elder} پیوست.", "en": "👋 {name} joined {elder}'s family."},
    "msg_from_elder": {"fa": "💬 {elder}: {text}", "en": "💬 {elder}: {text}"},
    "voice_from_elder": {"fa": "🎙 پیام صوتی از {elder}", "en": "🎙 Voice message from {elder}"},
    "concern_from_elder": {"fa": "⚠️ {elder} نوشته: «{text}»", "en": "⚠️ {elder} wrote: “{text}”"},
    "urgent_from_elder": {
        "fa": "🚨 فوری — {elder} نوشته: «{text}»\nلطفاً همین حالا تماس بگیرید.",
        "en": "🚨 Urgent — {elder} wrote: “{text}”\nPlease call now.",
    },
    "alert_said_unwell": {"fa": "⚠️ {elder} گفت امروز حالش خوب نیست. بهتر است تماس بگیرید.",
                          "en": "⚠️ {elder} said they're not feeling well today. It may be worth a call."},
    "alert_missed_checkin": {
        "fa": "❗️ {elder} به احوال‌پرسی امروز جواب نداده. شاید گوشی دم دستش نیست — بهتر است تماس بگیرید.",
        "en": "❗️ {elder} hasn't answered today's check-in. Maybe the phone isn't nearby — consider calling.",
    },
    "alert_missed_med": {"fa": "💊 {elder} مصرف «{med}» را تأیید نکرده.", "en": "💊 {elder} hasn't confirmed taking “{med}”."},
    "alert_undelivered": {
        "fa": "📵 پیام به {elder} نرسید (احتمالاً اینترنت یا گوشی ایشان). اگر رابط محلی دارید، در جریان قرار می‌گیرد.",
        "en": "📵 We couldn't reach {elder} (their internet or phone may be down). Their local contact, if any, is informed.",
    },
    "local_alert_missed": {
        "fa": "همدم: {elder} امروز به احوال‌پرسی جواب نداده‌اند و خانواده‌شان فعلاً در دسترس نیستند. اگر ممکن است تماس بگیرید یا سری بزنید. ممنون 🌷",
        "en": "Hamdam: {elder} hasn't answered today's check-in and their family can't be reached right now. If you can, please call or visit. Thank you 🌷",
    },
    "outage_started": {
        "fa": "📵 ارتباط اینترنتی با «{place}» قطع شده است.\nنگران نباشید: احوال‌پرسی و یادآوری دارو آنجا بدون وقفه ادامه دارد و اگر چیزی فوری باشد رابط محلی با پیامک خبردار می‌شود. همه گزارش‌ها و پیام‌ها بعد از وصل شدن به شما می‌رسد.",
        "en": "📵 The internet link to “{place}” is down.\nDon't worry: check-ins and medicine reminders continue there without interruption, and the local contact is alerted by SMS if anything is urgent. All reports and messages will reach you once it's back.",
    },
    "outage_over": {"fa": "🟢 ارتباط با «{place}» برقرار شد. گزارش‌های این مدت در راه است.",
                    "en": "🟢 The link to “{place}” is back. Reports from the gap are on their way."},
    "summary": {"fa": _summary("fa"), "en": _summary("en")},
}


def t(lang: str, key: str, **kw) -> str:
    """Missing key -> "" (callers can `or` a fallback). Missing language -> English."""
    entry = TEXTS.get(key)
    if entry is None:
        return ""
    template = entry.get(lang) or entry.get("en")
    if callable(template):
        return template(**kw)
    try:
        return template.format(**kw)
    except (KeyError, IndexError):
        return template
