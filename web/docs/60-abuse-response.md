# 60 · Abuse / fraud response runbook

What to do when a bot built on easymakebot is reported for fraud, scams, spam, or
other illegal use. As the platform operator you **cut off and preserve evidence**;
you do not unmask or prosecute anyone yourself — that is law enforcement + Telegram
+ the payment provider under legal process. A cooperating operator with a complete
evidence file is a witness, not a target.

## 1. Freeze the evidence (before you change anything)

Collect and save, with timestamps, to a dated folder / ticket:

- **Telegram:** the offending bot's `@username` and, if you have it, its token; the
  owner's `telegram_id` + `@username` + first name; screenshots / message exports
  of the abusive content.
- **From the store (wp-admin → WooCommerce → Orders → the order):** the
  "easymakebot — ردیابی تخلف" box shows **buyer IP + country**, **crypto sender
  wallet** + **tx hash** (or the ZarinPal ref for rial orders), and the
  **redeeming Telegram id / @username / phone**. Also the billing email and, for
  fa accounts, the name / phone / address.
- **From the user profile (wp-admin → Users → the user):** the "easymakebot —
  شناسه" box: verify channel, phone, sign-up IP + country + time, and the
  **ToS acceptance** (version + timestamp + IP).
- **From the activation code row** (shown under the order line item): which bot the
  code was redeemed on, by whom, when.
- **From the bot DB** (`built_bots`): the owner `User` row — `phone_number`
  (Telegram-verified, captured at `/live` activation), `region`, `created_at`.

The two permanent, un-fakeable anchors are the **`telegram_id`** and the
**on-chain tx hash / bank reference**. Everything else (IP, @username) can be
changed or masked; capture it anyway.

## 2. Cut the bot off

- wp-admin has no kill switch for a running bot — do it on the **bot side**:
  `/easybotadmin` → suspend the bot (sets `suspended=true`; it stays offline even
  with time left on `live_until`), or revoke `live_until`.
- Block the owner's `telegram_id` from `/live` and from creating new bots
  (platform-admin action).
- Do **not** delete anything yet — suspension keeps the record and the bot's data
  intact for the investigation.

## 3. Report to Telegram

- In-app **Report** on the bot, and/or email `abuse@telegram.org` with the bot
  `@username`, a description, and the screenshots. Telegram holds the phone
  number behind the account and can ban the user + bot.

## 4. If it is serious (money lost, criminal content)

- File a complaint (شکایت) with the competent authority — in Iran, **پلیس فتا /
  دادسرای جرایم رایانه‌ای**; elsewhere, the local cybercrime unit.
- Hand them the evidence file from step 1. That is what lets them issue a legal
  request to Telegram (→ phone → SIM registration → person) and trace the
  payment (tx hash → KYC'd exchange, or ZarinPal → bank card).
- Point to the **ToS the user accepted** (step 1) — it establishes the platform
  is neutral and the user is solely responsible.

## 5. After

- Once the matter is closed, you may hard-delete the bot and its data
  (`/easybotadmin`), and delete the store account. Keep the evidence file per your
  retention policy (long enough for any follow-up; not indefinitely).
- If the same person returns under a new email/wallet, the `telegram_id` (and
  often the sign-up IP / phone) ties them to the prior case.

## What the platform records for this purpose

| Data | Where | Set when |
|---|---|---|
| Telegram id / @username / name | `emb_activation_codes` row + order meta `_emb_redeemer_*` | code redeemed in `/live` |
| Telegram-verified phone | bot `users.phone_number` + `emb_activation_codes.redeemed_phone` | first paid `/live` activation of any kind — website code OR in-bot Zarinpal/Stripe/TON (contact share; trial is exempt) |
| Buyer IP + country | order meta `_emb_buyer_ip` / `_emb_buyer_country` (needs Cloudflare in front) | order created |
| Crypto sender wallet + tx hash | order meta `_emb_ton_sender` / `_emb_ton_txid` | payment matched on-chain |
| ZarinPal reference | order meta (WC ZPal) | rial payment completed |
| Sign-up IP + country + time | user meta `emb_signup_*` | account created |
| ToS acceptance (version, time, IP) | user meta `emb_tos` | registration |
| Name / phone / address (fa accounts) | billing user-meta | fa registration |

## Residual risk (be honest about it)

A determined person can register a Telegram account on a foreign / virtual SIM and
operate from anywhere, paying in crypto from a fresh wallet. That defeats the
geo and phone signals. It does **not** defeat the `telegram_id` binding, the
permanent payment record, or the accepted ToS — which together still give you a
defensible, reportable position.
