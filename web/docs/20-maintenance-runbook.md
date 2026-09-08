# Maintenance runbook

WordPress is **not** set-and-forget. Budget ~30 min/month. Neglected updates are
the #1 way WordPress sites get breached.

## Weekly (5 min)
- Skim the Cloudflare **Security → Events** dashboard for spikes / blocked attacks.
- Check the uptime monitor history — any blips?
- Glance at **Wordfence → Scan results** (or the host's malware scan) — expect
  "no issues".

## Monthly (~30 min)
1. **Take a fresh backup** and confirm it landed off-box:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml exec backup /backup.sh
   rclone lsd "$RCLONE_REMOTE"        # newest folder = today
   ```
2. **Apply updates on staging first.**
   ```bash
   # staging server
   docker compose run --rm wpcli wp core update
   docker compose run --rm wpcli wp plugin update --all
   docker compose run --rm wpcli wp theme update --all
   docker compose run --rm wpcli wp core update-db
   ```
   Then click through staging: home (FA + EN), a tutorial, a course lesson,
   add-to-cart → checkout with the test gateway. Nothing broken? Repeat on prod.
   (Managed host: use the panel's "update" with staging clone, same idea.)
3. **Refresh Cloudflare IP ranges** for nginx real-IP (Track A):
   ```bash
   { for u in https://www.cloudflare.com/ips-v4 https://www.cloudflare.com/ips-v6; do
       curl -s $u | sed 's/^/set_real_ip_from /; s/$/;/'; done
     echo 'real_ip_header CF-Connecting-IP;'; } > nginx/cloudflare-realip.conf
   docker compose -f docker-compose.yml -f docker-compose.prod.yml restart nginx
   ```
4. **Vulnerability scan:**
   ```bash
   docker run --rm wpscanteam/wpscan --url https://easymakebot.<tld> \
     --enumerate vp,vt --plugins-detection passive
   ```
   Address anything rated medium+.
5. Review admin users: `wp user list --role=administrator` — should be exactly one.

## When a plugin/theme update is available with a security advisory
Apply it **now** on prod (after a backup) — don't wait for the monthly window.
Subscribe to the WPScan feed or Patchstack mailing list.

## OS / Docker (Track A)
- `unattended-upgrades` handles OS security patches automatically; run
  `sudo apt update && sudo apt upgrade` monthly for the rest and reboot if a
  kernel update landed.
- `docker compose pull && docker compose ... up -d` monthly to pick up patched
  base images (`wordpress`, `mariadb`, `nginx`).

## Rotating secrets
- WP salts: paste a new set into `.env`, `docker compose up -d wordpress`
  (logs everyone out — expected).
- DB password: change in MariaDB + `.env` together, then `up -d`.
- Admin password: `wp user update <id> --user_pass="$(openssl rand -base64 24)"`.

## Quarterly
- Do a **real restore drill** into a scratch environment (see
  `docs/30-incident-restore.md`). A backup you've never restored is not a backup.
