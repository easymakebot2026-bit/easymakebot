# Deploying the bot (Germany) — linked to the website (Iran)

Two servers, two countries, one Cloudflare zone:

```
Iran     easymakebot.com       WordPress + WooCommerce + ZarinPal   (web/, its own runbook)
Germany  app.easymakebot.com   this bot + its Postgres + Caddy       (deploy/, this file)
```

Both A records live in the **same Cloudflare zone**, both **Proxied (orange)**:
`easymakebot.com` → Iran server IP, `app.easymakebot.com` → German server IP.

## How the two talk — and why the payment gateway still works

The bot **never touches an Iranian payment**. Flow for an Iran-region owner:

1. In `/live` they tap **🌐 Buy a plan on the website** → opens
   `https://easymakebot.com/plans/` **in their browser** (not Telegram's
   webview). They turn their Telegram VPN **off for that tab** and pay with
   ZarinPal on a native Iran IP — nothing here is proxied through Germany.
2. WooCommerce issues a one-time `EMB-XXXX-XXXX` code (thank-you page + email).
3. Back in the bot: **🎟 Activate with a code** → they paste it.
4. The bot (Germany) calls `https://easymakebot.com/wp-json/emb/v1/redeem`
   **through Cloudflare** (never a raw Iran IP), sets the bot's `live_until`,
   and starts it. This one call retries 3× with backoff.

International owners keep on-bot **TON / Stripe** (IP-agnostic). Iran owners get
no on-bot payment button unless you set `PLATFORM_ONBOT_ZARINPAL=true` — only
correct if the bot server is itself on an Iran IP.

---

## 0. Prerequisites

- **German server**: Ubuntu 24.04, Docker Engine + compose plugin, a non-root
  sudo user, ports 80/443 open. Nothing else needs to run on it.
- **Iran website** already deployed and green (`web/docs/10-deploy-runbook.md`),
  with a real `EMB_ACTIVATION_KEY` in its `web/.env` (not `change-me-…`).
- **Cloudflare DNS**: `A app → <German server IP>`, Proxied.
- **A `/plans/` (or shop) page on the website** that sells the plans and hands
  out an `EMB-…` code on purchase. (Set `WEBSITE_PLANS_URL` if the path differs.)
- Values in hand: `BOT_TOKEN` (@easymakebot), your Telegram ID, the site's
  `EMB_ACTIVATION_KEY`.

---

## 1. Code onto the German server

```bash
sudo git clone <this repo> /opt/easymakebot
sudo chown -R "$USER" /opt/easymakebot
cd /opt/easymakebot/deploy
```
(Updating later: `cd /opt/easymakebot && git pull && cd deploy`.)

---

## 2. Configure

```bash
cp .env.bot.example .env.bot
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"   # ENCRYPTION_KEY
openssl rand -base64 24                                                                       # POSTGRES_PASSWORD
nano .env.bot
```
| Key | Value |
|---|---|
| `BOT_TOKEN` | @easymakebot's token |
| `PLATFORM_ADMIN_ID` | your Telegram ID |
| `ENCRYPTION_KEY` | the Fernet key — **back it up offline** |
| `POSTGRES_PASSWORD` | the random string |
| `APP_DOMAIN` / `WEBAPP_URL` | `app.easymakebot.com` / `https://app.easymakebot.com` |
| `CADDY_EMAIL` | your email (Let's Encrypt) |
| `WEBSITE_URL` | `https://easymakebot.com` |
| `WEBSITE_ACTIVATION_KEY` | **exactly** the site's `EMB_ACTIVATION_KEY` |
| `WEBSITE_PLANS_URL` | leave blank for `…/plans/`, or set the real URL |

Leave `PLATFORM_ONBOT_ZARINPAL=false`, and `PLATFORM_*` / `VIDEO_URL_*` blank
unless you have them.

---

## 3. Start it

```bash
docker compose -f docker-compose.bot.yml up -d --build
docker compose -f docker-compose.bot.yml logs -f bot
```
`init_db()` creates + patches the schema on first boot — no manual migration.
Caddy fetches the `app.easymakebot.com` cert on the first HTTPS hit.

---

## 4. Point the Mini App URL at BotFather (optional)

@BotFather → @easymakebot → **Bot Settings → Menu Button / Web App URL** →
`https://app.easymakebot.com`. (The per-bot "🎨 Visual Builder" inline button
already uses `WEBAPP_URL`; this is only for the menu-button entry.)

---

## 5. Verify

**Mini App (German side):**
```bash
curl -sI https://app.easymakebot.com | grep -iE 'HTTP/|cache-control'
#   HTTP/2 200   +   cache-control: no-store, must-revalidate
curl -s -o /dev/null -w '%{http_code}\n' https://app.easymakebot.com/api/flow   # 401
```

**Website link (cross-border, via Cloudflare) — consumes no code:**
```bash
curl -s "https://easymakebot.com/wp-json/emb/v1/check?code=EMB-TEST-TEST" \
  -H "X-EMB-Key: <the shared key>"
#   {"ok":true,"valid":false,"reason":"not_found"}  ← key matches, plugin live, path OK
#   {"code":"emb_forbidden",...}                    ← keys don't match
#   404 / HTML                                      ← mu-plugin not active on the site
```

**In Telegram:**
1. `/start` @easymakebot → welcome (fa/en tips appear under options).
2. **My Bots → a bot → 🎨 Visual Builder** → canvas loads → Save works.
3. Send `/start` to that built bot → its configured reply comes back.
4. `/live` as an Iran-region owner → you see **🌐 Buy a plan on the website** +
   **🎟 Activate with a code** (no Zarinpal button) and the VPN-off note.
5. Buy on the site (browser, VPN off), get an `EMB-…` code, paste it in
   **Activate with a code** → bot logs show a `redeem` call → confirm:
   ```bash
   docker compose -f docker-compose.bot.yml exec bot-db \
     psql -U easymakebot -c "select bot_username, live_until from built_bots;"
   ```

---

## Day-2

| Task | Command (in `/opt/easymakebot/deploy`) |
|---|---|
| Update after `git pull` | `docker compose -f docker-compose.bot.yml up -d --build` |
| Logs | `docker compose -f docker-compose.bot.yml logs -f bot` |
| Restart bot only | `docker compose -f docker-compose.bot.yml restart bot` |
| DB shell | `docker compose -f docker-compose.bot.yml exec bot-db psql -U easymakebot` |
| DB backup | `docker compose -f docker-compose.bot.yml exec -T bot-db pg_dump -U easymakebot easymakebot | gzip > ~/emb-bot-$(date +%F).sql.gz` |

**Back up `ENCRYPTION_KEY` and the `bot_db_data` volume together.**

### Rollback
```bash
git -C /opt/easymakebot checkout <previous-tag>
docker compose -f docker-compose.bot.yml up -d --build
```
Schema is additive-only (`ADD COLUMN IF NOT EXISTS`), so an older image runs
fine against a newer DB.

### If Cloudflare/Iran connectivity to the redeem API is unreliable
`bot/website_client._post` already retries 3× (2s/4s/8s). If codes still fail
to redeem, check the site is reachable from the German box
(`curl -v https://easymakebot.com/wp-json/emb/v1/check?...`), and that the
site's nginx/Caddy `set_real_ip_from` list covers current Cloudflare ranges so
the origin doesn't see (and rate-limit) a single Cloudflare IP.

---

## Non-Docker alternative

`deploy/systemd/easymakebot-bot.service` runs the bot from a virtualenv under
systemd (needs a local Postgres, a built `webapp/dist`, and your own TLS proxy
for `APP_DOMAIN`). Docker is recommended.
