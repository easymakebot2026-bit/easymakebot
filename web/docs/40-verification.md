# Verification checklist

Run locally after `docker compose up -d`, then again on `staging.` over real TLS.
`BASE` = `http://localhost:8080` locally, or `https://staging.easymakebot.<tld>`.

## Stack health
- [ ] `docker compose ps` — `db` and `redis` healthy, `wordpress` + `nginx` up.
- [ ] `curl -sSI $BASE/` → `200` and `X-Content-Type-Options: nosniff`,
      `X-Frame-Options: SAMEORIGIN`, `Referrer-Policy`, `Permissions-Policy`
      present. (staging also: `Strict-Transport-Security`.)
- [ ] `docker compose run --rm wpcli wp redis status` → "Connected".

## Security smoke
- [ ] `curl -s -o /dev/null -w '%{http_code}\n' $BASE/xmlrpc.php` → `405`.
- [ ] `curl -s "$BASE/?author=1" -o /dev/null -w '%{http_code}\n'` → `404`
      (no redirect to `/author/<name>/`).
- [ ] `curl -s "$BASE/wp-json/wp/v2/users"` → `[]` or `401`/`rest_forbidden`,
      **not** a list of usernames.
- [ ] `curl -s $BASE/wp-content/uploads/probe.php` after
      `docker compose run --rm wpcli sh -c 'echo "<?php echo 1;" > /var/www/html/wp-content/uploads/probe.php'`
      → served as text / `403`, **never** prints `1`. (delete probe.php after)
- [ ] `curl -sI $BASE/wp-config.php` → `403`.
- [ ] `curl -sI $BASE/.env` and `$BASE/readme.html` → `403` / `404`.
- [ ] Repeated `POST $BASE/wp-login.php` (>6 in a minute) starts returning `429`.
- [ ] `wp-admin` on staging: Cloudflare Access challenge appears before the WP
      login form; after login, a 2FA prompt (once the 2FA plugin is added).

## WordPress baseline
- [ ] `wp option get permalink_structure` → `/%postname%/`.
- [ ] `wp plugin list --status=active` → `redis-cache`,
      `limit-login-attempts-reloaded`, `wp-mail-smtp` (+ later phases).
- [ ] `wp user list --role=administrator` → exactly one.
- [ ] `wp option get blog_public` → `0` on staging, `1` only after go-live.
- [ ] Test email: `wp eval 'wp_mail("you@example.com","test","hi");'` → arrives
      in Mailpit (local, http://localhost:8025) or the real inbox (staging).

## Later phases (recorded here so the list stays in one place)
- [ ] **P2** home renders FA (RTL) + EN; language switcher works; logo + favicon.
- [ ] **P3** `tutorial` / `course` / `lesson` appear in wp-admin and save.
- [ ] **P4** a test order with "Cash on delivery" reaches *completed*; the
      easymakebot-subscription product emits a redemption code on the
      order-received page + email.
- [ ] **P5** `/redeem <code>` in the Telegram bot sets `live_until` on the
      chosen bot.

## Pre-launch (staging, external tools)
- [ ] https://securityheaders.com/?q=staging… → A or A+.
- [ ] `docker run --rm wpscanteam/wpscan --url https://staging… --enumerate vp,vt`
      → no medium+ findings.
- [ ] Backup + **restore drill** into a scratch DB (docs/30) succeeds.
- [ ] Lighthouse (mobile) ≥ 90 performance / 100 best-practices.
