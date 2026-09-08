# Phase 0 — Provisioning checklist (things only you can do)

Work top to bottom. Nothing here needs code; it's accounts, DNS, and secrets.
When every box is ticked, hand the values to the deploy step (Phase 1).

## 1. Domain
- [ ] Register the domain (e.g. `easymakebot.ir` for the IR audience and/or a
      `.com`). An `.ir` domain is bought through an Iranian registrar (nic.ir
      resellers).
- [ ] Decide the hostnames:
      - `easymakebot.<tld>` — production
      - `staging.easymakebot.<tld>` — staging (built and tested first)

## 2. Hosting — pick ONE
### Option A (recommended): Iranian managed / cloud WordPress host
- [ ] Buy a plan that gives you: **PHP 8.2+**, an isolated environment
      (VPS-backed or containerised — *not* cheap shared hosting), **daily
      off-server backups included**, free SSL, **SSH access**, and permission
      to put Cloudflare in front.
- [ ] Note the SSH host/user, the control-panel URL, and the PHP version.

### Option B: self-managed VPS abroad + Docker
- [ ] Provision Ubuntu 24.04 LTS, ≥ 2 vCPU / 4 GB RAM / 40 GB SSD
      (Hetzner CX22 / Contabo). 
- [ ] Create a non-root sudo user; add your SSH public key; disable password &
      root SSH login.
- [ ] Install Docker Engine + the compose plugin.

## 3. Cloudflare (free plan) — every option uses this
- [ ] Create a Cloudflare account, add the domain, and change the domain's
      nameservers at the registrar to the two Cloudflare gives you.
- [ ] DNS: `A` record `easymakebot` → server IP, **Proxied (orange cloud)**.
      Same for `staging` and `www`.
- [ ] SSL/TLS mode: **Full (strict)** (needs a real cert on the origin — Caddy
      or a Cloudflare Origin Certificate; see the deploy runbook).
- [ ] Rules → **Rate limiting**: `/wp-login.php` → 5 req / 1 min / IP → Block 1h.
- [ ] Security → **Bot Fight Mode**: On.
- [ ] Speed → **Always Use HTTPS**: On. Enable **HSTS** after go-live.
- [ ] (Recommended) Zero Trust → **Access** → self-hosted app for
      `easymakebot.<tld>/wp-admin*` and `/wp-login.php`, policy = your email
      (one-time PIN). Free for up to 50 users.

## 4. Payments
- [ ] **Zarinpal**: create a merchant account, verify it, get the
      **Merchant ID** (UUID). Sandbox first if available.
- [ ] **International gateway — decide now** (blocks Phase 4):
      - (a) Stripe via a foreign entity/account → get test + live keys, or
      - (b) a crypto gateway (NOWPayments / Cryptomus) → API key + IPN secret, or
      - (c) launch Zarinpal-only, handle non-IR sales manually.

## 5. Transactional email (SMTP)
- [ ] Get SMTP credentials for order/receipt email. An Iranian option
      (e.g. a mail-sending service or your host's SMTP) avoids deliverability
      issues to Iranian inboxes. Note host / port / user / pass / from-address.

## 6. Off-box backups
- [ ] Create a bucket on an S3-compatible store (Backblaze B2 has a free tier;
      or an Iranian object storage such as ArvanCloud). Note the bucket name,
      key ID, and application key.
- [ ] `rclone config` a remote pointing at it (the deploy runbook shows how);
      the remote name goes in `.env` as `RCLONE_REMOTE`.

## 7. Monitoring
- [ ] Create a free uptime monitor (UptimeRobot / BetterStack) for
      `https://easymakebot.<tld>` and the TLS-expiry check.

## 8. Hand-off values for Phase 1
Collect these into the server's `.env` (never commit it):

| Key | From |
|---|---|
| `WP_HOME`, `WP_SITEURL` | your domain (start with the `staging.` host) |
| `MARIADB_ROOT_PASSWORD`, `MARIADB_PASSWORD` | `openssl rand -base64 24` each |
| `WP_*_KEY`, `WP_*_SALT` (8) | https://api.wordpress.org/secret-key/1.1/salt/ |
| `WP_ADMIN_USER/PASSWORD/EMAIL` | your choice (long random password) |
| `SMTP_*` | step 5 |
| `RCLONE_REMOTE` | step 6 |
