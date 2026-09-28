#!/usr/bin/env bash
# Bot database backup — meant to run daily from cron:
#
#   /etc/cron.d/emb-bot-backup:
#   15 3 * * * root /opt/easymakebot/deploy/backup-db.sh >> /root/emb-backups/backup.log 2>&1
#
# Writes one timestamped, compressed dump per run to $BACKUP_DIR and NEVER
# deletes or overwrites anything (a dump is ~100 KB, so years of them fit
# easily). A dump is only kept under its final name once it has been checked
# to be a real PostgreSQL dump; a failed run leaves a *.partial file for
# inspection and exits non-zero.
#
# These copies live on the same server. For real safety, also copy them
# somewhere else (another machine / cloud storage) regularly.

set -euo pipefail

DEPLOY_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKUP_DIR="${BACKUP_DIR:-/root/emb-backups}"

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

out="$BACKUP_DIR/emb-bot-$(date +%F-%H%M).sql.gz"
tmp="$out.partial"

docker compose --env-file "$DEPLOY_DIR/.env.bot" -f "$DEPLOY_DIR/docker-compose.bot.yml" \
  exec -T bot-db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip > "$tmp"

# Read the header into a variable first: `gzip | head | grep -q` would trip
# pipefail when head/grep exit early and the writer gets SIGPIPE.
header=$(gzip -dc "$tmp" 2>/dev/null | head -c 2000 || true)
case "$header" in
  *"PostgreSQL database dump"*)
    mv "$tmp" "$out"
    chmod 600 "$out"
    echo "$(date -Is) ok $out ($(du -h "$out" | cut -f1))"
    ;;
  *)
    echo "$(date -Is) FAILED — $tmp is not a valid dump" >&2
    exit 1
    ;;
esac
