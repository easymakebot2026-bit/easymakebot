# easymakebot — website (WordPress + WooCommerce)

Bilingual (FA/EN) WordPress site with a custom block theme, hardened by default.
Separate app from the Telegram bot in the repo root — its own database, its own
container stack. See the approved plan for scope and phases:
`~/.claude/plans/stateless-watching-thunder.md`.

## Layout

```
web/
├── docker-compose.yml            # base stack (local dev): db, redis, wordpress-fpm, nginx, mailpit
├── docker-compose.prod.yml       # prod overrides: 80/443, backups, logging, no mailpit
├── docker-compose.caddy.yml      # alt prod front end with automatic TLS
├── Caddyfile
├── .env.example                  # copy to .env, fill in (never commit .env)
├── nginx/
│   ├── 00-zones.conf             # rate-limit zone + forwarded-proto map (http{} context)
│   ├── default.conf              # local vhost (:8080) + security rules
│   ├── prod.conf.template        # -> nginx/prod.conf for the TLS origin
│   ├── fastcgi_params_wp
│   └── cloudflare-realip.conf    # regenerate on the server (runbook §A2)
├── config/
│   ├── php-security.ini          # disable_functions, limits, opcache
│   ├── wp-config-hardening.php    # paste-in block for managed/cPanel hosts
│   └── uploads.htaccess          # Apache: block PHP in wp-content/uploads
├── scripts/
│   ├── install.sh                # idempotent first-run bootstrap (via wp-cli)
│   └── backup.sh                 # nightly DB + uploads -> rclone remote
├── wordpress/wp-content/
│   ├── mu-plugins/
│   │   └── easymakebot-harden.php # must-use hardening (Phase 1)
│   └── themes/easymakebot/        # custom block theme (stub now; built in Phase 2)
└── docs/
    ├── 00-provisioning-checklist.md
    ├── 10-deploy-runbook.md
    ├── 20-maintenance-runbook.md
    ├── 30-incident-restore.md
    ├── 40-verification.md
    ├── 50-theme-and-i18n.md
    └── 60-abuse-response.md
```

## Local development

```bash
cd web
cp .env.example .env          # dev defaults are fine; only the *_PASSWORD lines must be non-empty
docker compose up -d --wait
docker compose run --rm wpcli /scripts/install.sh
open http://localhost:8080          # site
open http://localhost:8025          # Mailpit (outgoing mail)
```

Our theme and mu-plugins are **bind-mounted**, so edits under
`wordpress/wp-content/{themes/easymakebot,mu-plugins}` show up immediately.

Common wp-cli:
```bash
docker compose run --rm wpcli wp plugin list
docker compose run --rm wpcli wp user list
docker compose run --rm wpcli wp search-replace OLD NEW --all-tables --precise
```

Reset everything (drops the DB + WP files):
```bash
docker compose down -v
```

## Iran networking note

Docker Hub and `wordpress.org` (plugin/theme updates) are frequently throttled or
blocked from inside Iran. This machine already has an ArvanCloud registry mirror
(`/etc/docker/daemon.json` → `docker.arvancloud.ir`). For a **production VPS,
host it outside Iran** (Docker Hub + wp.org reachable) or configure a registry
mirror + a `wp.org` proxy. The managed-Iranian-host track sidesteps this — the
host handles updates.

## Production

Follow `docs/10-deploy-runbook.md`. Short version (Docker + Caddy):
```bash
# real values in .env, Caddyfile domain set
docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.caddy.yml up -d
docker compose run --rm wpcli /scripts/install.sh
```
Then work through `docs/40-verification.md`.

## Status

- [x] **Phase 1** — hardened baseline (this stack) — verified from a clean build,
      11/11 checks in `docs/40-verification.md` pass
- [ ] Phase 2 — custom bilingual block theme (theme dir is a stub)
- [ ] Phase 3 — content model (tutorial / course / lesson)
- [ ] Phase 4 — WooCommerce: easymakebot subscription + course store
- [ ] Phase 5 — bot integration (redemption codes)
- [ ] Phase 6 — launch hardening pass

Phase 1 verified: stack healthy; Redis object cache connected; theme + 3 baseline
plugins active with auto-updates; security headers single + no version leak;
xmlrpc 405; author/REST user enumeration blocked; PHP in uploads not executed;
wp-login rate-limited (429); mail caught by Mailpit.
