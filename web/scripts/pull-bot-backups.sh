#!/bin/bash
# Runs on the IRAN server (cron, daily after the bot's 03:05 backup):
#
#   30 3 * * * /opt/easymakebot/web/scripts/pull-bot-backups.sh >> /var/log/pull-bot-backups.log 2>&1
#
# Copies the bot database backups FROM the German server. Since 2026-09-24 the
# German server can no longer open connections to this server (its push of the
# same backups times out), but this server can still reach Germany — the
# website backup goes that way every night (sync-to-germany.sh) with the same
# key. So the bot backups are now pulled instead of pushed.
#
# Copy only: nothing is deleted on either server (no rsync --delete). Files
# land next to the ones the old push already put here.

set -eu

DEST="/root/offsite-backups/bot"
mkdir -p "$DEST"
chmod 700 /root/offsite-backups "$DEST"

echo "[$(date -Is)] pulling bot db backups from Germany"
rsync -az \
  -e "ssh -i /root/.ssh/backup_sync -o StrictHostKeyChecking=accept-new -o ConnectTimeout=15" \
  root@82.115.26.92:/root/bot-backups/ "$DEST/"
echo "[$(date -Is)] done — $(ls -1 "$DEST" | wc -l) backup folder(s) in $DEST, newest: $(ls -1t "$DEST" | head -1)"
