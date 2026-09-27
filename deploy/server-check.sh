#!/usr/bin/env bash
# Bot server (Germany) — deploy and/or audit.
#
#   ./deploy/server-check.sh            # audit only (read-only, safe to run anytime)
#   ./deploy/server-check.sh deploy     # DB backup -> git pull -> rebuild -> health check -> audit
#
# Run from the repo checkout on the server (default /opt/easymakebot). The
# audit output is redacted (no tokens/keys/emails) so it can be pasted into
# a chat or issue for review. Deploy never deletes anything; the backup it
# takes first is kept in ~/emb-backups/.

set -uo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DEPLOY_DIR="$REPO_DIR/deploy"
COMPOSE_FILE="$DEPLOY_DIR/docker-compose.bot.yml"
ENV_FILE="$DEPLOY_DIR/.env.bot"
BACKUP_DIR="${BACKUP_DIR:-$HOME/emb-backups}"
MODE="${1:-audit}"
export GIT_TERMINAL_PROMPT=0

# shellcheck source=deploy/audit-common.sh
. "$DEPLOY_DIR/audit-common.sh"

compose() { $SUDO docker compose -f "$COMPOSE_FILE" "$@"; }

env_value() {  # reads one non-secret key from .env.bot without printing the file
  [ -f "$ENV_FILE" ] && grep -E "^$1=" "$ENV_FILE" | tail -1 | cut -d= -f2- | tr -d '"'"'"
}

db_service() { compose ps --services 2>/dev/null | grep -m1 -E 'db|postgres'; }
bot_service() { compose ps --services 2>/dev/null | grep -m1 -vE 'db|postgres|caddy'; }

backup_db() {
  section "Database backup"
  mkdir -p "$BACKUP_DIR" && chmod 700 "$BACKUP_DIR"
  local svc out
  svc=$(db_service)
  if [ -z "$svc" ]; then echo "  [ERROR] database service not found — refusing to deploy without a backup"; return 1; fi
  out="$BACKUP_DIR/emb-bot-$(date +%F-%H%M).sql.gz"
  if compose exec -T "$svc" sh -c 'pg_dump -U "${POSTGRES_USER:-easymakebot}" "${POSTGRES_DB:-easymakebot}"' | gzip > "$out" \
     && [ "$(gzip -dc "$out" | head -c 100000 | grep -c 'PostgreSQL database dump')" -gt 0 ]; then
    chmod 600 "$out"
    note "Saved $out ($(du -h "$out" | cut -f1))"
  else
    rm -f "$out"
    echo "  [ERROR] backup failed — deploy aborted, nothing was changed"
    return 1
  fi
}

do_deploy() {
  section "Deploy"
  cd "$REPO_DIR" || exit 1
  if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
    echo "  [ERROR] the checkout has local edits (git status) — resolve them first; nothing was changed"
    git status --short | sed 's/^/    /'
    exit 1
  fi
  backup_db || exit 1
  local before
  before=$(git rev-parse --short HEAD)
  git pull --ff-only || { echo "  [ERROR] git pull failed — nothing else was changed"; exit 1; }
  note "Code: $before -> $(git rev-parse --short HEAD) ($(git log -1 --format=%s))"
  compose up -d --build || { echo "  [ERROR] build/start failed — roll back with: git checkout $before && $0 deploy"; exit 1; }

  section "Health check"
  local svc ok=""
  svc=$(bot_service)
  for _ in $(seq 1 24); do
    if compose logs --tail 200 "$svc" 2>/dev/null | grep -q 'Bot is running'; then ok=1; break; fi
    sleep 5
  done
  if [ -n "$ok" ]; then
    note "Bot started successfully (database columns are migrated automatically on startup)"
  else
    warn "Did not see 'Bot is running' within 2 minutes — last log lines:"
    compose logs --tail 40 "$svc" 2>&1 | redact | sed 's/^/    /'
    note "To roll back: git checkout $before && $0 deploy   (DB backup is in $BACKUP_DIR)"
  fi
}

audit_bot() {
  section "easymakebot bot"
  cd "$REPO_DIR" || return
  note "Repo: $REPO_DIR @ $(git rev-parse --short HEAD 2>/dev/null) on $(git rev-parse --abbrev-ref HEAD 2>/dev/null) — $(git log -1 --format='%s (%cr)' 2>/dev/null)"
  git fetch -q origin 2>/dev/null && note "Commits on origin/main not deployed yet: $(git rev-list --count HEAD..origin/main 2>/dev/null)"
  compose ps 2>/dev/null | sed 's/^/  /'
  local bsvc dsvc bc
  bsvc=$(bot_service); dsvc=$(db_service)
  bc=$(compose ps -q "$bsvc" 2>/dev/null)
  [ -n "$bc" ] && audit_logs "$bc" 500

  if [ -n "$dsvc" ]; then
    section "Database"
    compose exec -T "$dsvc" sh -c 'psql -U "${POSTGRES_USER:-easymakebot}" -d "${POSTGRES_DB:-easymakebot}" -At -c "
      select '"'"'size: '"'"' || pg_size_pretty(pg_database_size(current_database()));
      select '"'"'built bots: '"'"' || count(*) || '"'"' (live now: '"'"' || count(*) filter (where live_until > now() and not suspended) || '"'"')'"'"' from built_bots;
      select '"'"'orders paid but not fulfilled: '"'"' || count(*) from orders where status = '"'"'paid'"'"';
      select '"'"'pending TON plan payments: '"'"' || count(*) from live_payments where status = '"'"'pending'"'"' and payment_method = '"'"'ton'"'"';
      select '"'"'duplicate bots (same Telegram bot): '"'"' || count(*) from (select telegram_bot_id from built_bots where telegram_bot_id is not null group by 1 having count(*) > 1) d;
    "' 2>&1 | sed 's/^/  /'
  fi

  section "Backups"
  if ls "$BACKUP_DIR"/*.sql.gz >/dev/null 2>&1; then
    local newest age
    newest=$(ls -t "$BACKUP_DIR"/*.sql.gz | head -1)
    age=$(( ( $(date +%s) - $(stat -c %Y "$newest") ) / 86400 ))
    note "Newest: $newest ($age days old, $(ls "$BACKUP_DIR"/*.sql.gz | wc -l) files)"
    [ "$age" -gt 2 ] && warn "No DB backup in the last 2 days — schedule a daily pg_dump (cron) and copy it off this server"
  else
    warn "No DB backups found in $BACKUP_DIR — the database (bot tokens, orders) has no backup here"
  fi
  $SUDO crontab -l 2>/dev/null | grep -q pg_dump || crontab -l 2>/dev/null | grep -q pg_dump \
    || warn "No cron job running pg_dump was found"

  audit_env_perms "$ENV_FILE" "$REPO_DIR/.env"
  local domain
  domain=$(env_value APP_DOMAIN)
  if [ -n "$domain" ]; then
    audit_tls "$domain"
    audit_http "https://$domain"
  fi
}

case "$MODE" in
  deploy) do_deploy ;;
  audit) ;;
  *) echo "usage: $0 [audit|deploy]"; exit 2 ;;
esac

{
  audit_system
  audit_updates
  audit_network
  audit_ssh
  audit_docker
  audit_bot
  section "Done"
  note "Paste everything above (it is already redacted) for review."
} 2>&1 | redact
