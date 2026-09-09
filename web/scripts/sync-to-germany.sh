#!/bin/bash
set -eu

BACKUP_DIR="/opt/easymakebot/web/backups"
LATEST="$(ls -1dt "${BACKUP_DIR}"/*/ 2>/dev/null | head -n1)"

if [ -z "$LATEST" ]; then
  echo "[$(date -Is)] no backup folder found, skipping sync"
  exit 0
fi

STAMP="$(basename "$LATEST")"
echo "[$(date -Is)] syncing ${STAMP} to Germany"

ssh -i /root/.ssh/backup_sync -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 \
  root@82.115.26.92 "mkdir -p /root/offsite-backups/website/${STAMP}"

rsync -az -e "ssh -i /root/.ssh/backup_sync -o StrictHostKeyChecking=accept-new" \
  "${LATEST}" root@82.115.26.92:/root/offsite-backups/website/${STAMP}/

ssh -i /root/.ssh/backup_sync -o StrictHostKeyChecking=accept-new root@82.115.26.92 \
  "ls -1dt /root/offsite-backups/website/*/ 2>/dev/null | tail -n +31 | xargs -r rm -rf"

echo "[$(date -Is)] sync to Germany done"
