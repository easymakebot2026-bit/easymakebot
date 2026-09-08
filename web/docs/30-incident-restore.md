# Incident response & restore

## If you suspect a compromise
1. **Don't panic-delete.** Put Cloudflare into **"Under Attack"** mode and, if
   it's bad, pause the site (Cloudflare → "Pause Cloudflare on Site" is the
   wrong way; instead add a WAF rule to block all, or stop the container:
   `docker compose stop nginx`).
2. Snapshot evidence: `docker compose logs --since 72h > /tmp/incident-logs.txt`,
   copy the current DB + `wp-content` somewhere read-only.
3. Rotate everything: WP salts, DB password, all admin passwords, SMTP creds,
   payment gateway keys, the Phase 5 `EMB_WEB_SECRET`.
4. `wp user list --role=administrator` and `wp option get users_can_register` —
   remove any account you don't recognise.
5. `wp core verify-checksums` and `wp plugin verify-checksums --all` — reinstall
   anything that fails.
6. Restore from the **last known-good backup** (below), then re-apply all
   updates before un-pausing.
7. Force logout everyone: change the salts (already done in step 3).

## Restore drill / full restore

### With the Docker stack
```bash
cd /opt/easymakebot/web
STAMP=<folder-from-rclone-lsd>        # e.g. 20260901-030000

# 1. pull the backup down
rclone copy "$RCLONE_REMOTE/$STAMP" ./restore/$STAMP
cd ./restore/$STAMP && sha256sum -c SHA256SUMS && cd -

# 2. stop the app (keep db up)
docker compose stop wordpress nginx

# 3. restore the database
zcat ./restore/$STAMP/db.sql.gz | \
  docker compose exec -T db mariadb -u root -p"$MARIADB_ROOT_PASSWORD" "$MARIADB_DATABASE"

# 4. restore uploads
docker compose run --rm -v "$PWD/restore/$STAMP:/r" wpcli \
  sh -c 'cd /var/www/html/wp-content && rm -rf uploads && tar -xzf /r/uploads.tar.gz'

# 5. back up, verify
docker compose start wordpress nginx
docker compose run --rm wpcli wp core verify-checksums
curl -I https://staging.easymakebot.<tld>
```

### On a managed host
Use the host's restore-from-backup for the DB + files, then re-import your
UpdraftPlus off-box copy if the host copy is also suspect. Verify with
`wp core verify-checksums` (via the host's WP-CLI / SSH).

## RPO / RTO
- Backups run nightly at 03:00 → worst-case data loss ~24 h. For a busy shop,
  raise `backup` cron to every 6 h.
- A clean restore of this size is ~15–30 min once you have the backup in hand.

## Contacts / references
- Host support: _fill in_
- Cloudflare account: _fill in_
- Domain registrar: _fill in_
- Zarinpal panel: _fill in_
