# Deploy runbook

Two tracks. Do **staging first**, verify, then repeat for production with the
production hostnames.

---

## Track A — self-managed VPS + Docker (this repo)

### A1. First deploy
```bash
# on the server, as your sudo user
git clone <this repo> /opt/easymakebot && cd /opt/easymakebot/web
cp .env.example .env
```
Edit `.env`:
- `WP_HOME` / `WP_SITEURL` → `https://staging.easymakebot.<tld>`
- `WP_FORCE_SSL_ADMIN=true`
- strong `MARIADB_ROOT_PASSWORD`, `MARIADB_PASSWORD`
- real 8 salts from https://api.wordpress.org/secret-key/1.1/salt/
- `WP_ADMIN_*`, `SMTP_*`, `RCLONE_REMOTE`

Bring it up with the **Caddy** front end (automatic TLS):
```bash
# edit Caddyfile: set your domain + email
docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.caddy.yml up -d
docker compose run --rm wpcli /scripts/install.sh
```
Or with **nginx + Cloudflare Origin cert**:
```bash
# put the Cloudflare origin cert/key in ./certs/{fullchain.pem,privkey.pem}
cp nginx/prod.conf.template nginx/prod.conf   # then edit server_name
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
docker compose run --rm wpcli /scripts/install.sh
```

### A2. Cloudflare real client IP (nginx track)
`nginx/cloudflare-realip.conf` must list Cloudflare's ranges so rate-limiting and
logs see the true IP:
```bash
{ for u in https://www.cloudflare.com/ips-v4 https://www.cloudflare.com/ips-v6; do
    curl -s $u | sed 's/^/set_real_ip_from /; s/$/;/'; done
  echo 'real_ip_header CF-Connecting-IP;'
} > nginx/cloudflare-realip.conf
docker compose ... restart nginx
```
(Add that block to a monthly cron — Cloudflare changes ranges rarely.)

### A3. Server hardening (once)
```bash
sudo apt update && sudo apt install -y ufw fail2ban unattended-upgrades
sudo ufw allow OpenSSH && sudo ufw allow 80,443/tcp && sudo ufw enable
sudo dpkg-reconfigure -plow unattended-upgrades
sudo systemctl enable --now fail2ban
```
`/etc/fail2ban/jail.local`: enable `sshd`; optionally a `nginx-http-auth` /
`wordpress` jail reading the nginx access log for repeated `POST /wp-login.php`.

---

## Track B — Iranian managed / cPanel WordPress host

You won't run Docker. Instead:

1. In the host panel, create the site at `staging.easymakebot.<tld>`, PHP 8.2+,
   a fresh MySQL DB + user.
2. Install WordPress (one-click, or upload). During setup use a **non-default
   table prefix** (e.g. `emb_`) and a long admin password.
3. Copy our code into place:
   - `web/wordpress/wp-content/mu-plugins/easymakebot-harden.php`
     → `wp-content/mu-plugins/` (create the folder if absent)
   - `web/wordpress/wp-content/themes/easymakebot/` → `wp-content/themes/`
   - later phases add `mu-plugins/easymakebot-core/` and the theme build
4. Edit `wp-config.php` — add the block from `config/wp-config-hardening.php`.
5. Add to the site root `.user.ini` (or `php.ini` in panel) the values from
   `config/php-security.ini` that the host permits.
6. Web-server rules: if Apache, drop `config/uploads.htaccess` into
   `wp-content/uploads/.htaccess` (blocks PHP there). If the panel exposes
   Nginx rules, port the `location` blocks from `nginx/default.conf`.
7. Plugins (Plugins → Add New): **Redis Object Cache** (only if the host offers
   Redis), **Limit Login Attempts Reloaded**, **WP Mail SMTP**. Enable
   auto-updates for all.
8. Put Cloudflare in front (checklist §3) and lock `/wp-admin` via Cloudflare
   Access or the host's IP allowlist.
9. Backups: rely on the host's daily backup **plus** UpdraftPlus → your own
   off-box bucket (never trust a single backup location).

---

## Post-deploy verification (both tracks) — see `docs/40-verification.md`
Run every check there before pointing DNS at production.

## Cut-over to production
1. Repeat the deploy with `WP_HOME=https://easymakebot.<tld>`.
2. `wp search-replace 'https://staging.easymakebot.<tld>' 'https://easymakebot.<tld>' --all-tables --precise` (via `docker compose run --rm wpcli`).
3. `wp option update blog_public 1` (allow indexing).
4. Cloudflare: enable HSTS, tighten WAF to "High", turn on "Under Attack" only if needed.
5. Confirm the uptime monitor is green.
