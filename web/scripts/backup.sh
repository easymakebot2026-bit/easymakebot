#!/bin/sh
# ─────────────────────────────────────────────────────────────────────────────
# Nightly off-box backup: dumps the DB + tars wp-content/uploads, pushes both
# to an rclone remote, prunes remote copies older than BACKUP_KEEP_DAYS.
# Run by the `backup` container's crond (see docker-compose.prod.yml), or by
# hand:  docker compose -f ... exec backup /backup.sh
# ─────────────────────────────────────────────────────────────────────────────
set -eu

STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="/backups/${STAMP}"
mkdir -p "$OUT"

echo "[$(date -Is)] backup ${STAMP} starting"

# --- database ---------------------------------------------------------------
mysqldump \
  --host=db --user="${MARIADB_USER}" --password="${MARIADB_PASSWORD}" \
  --single-transaction --quick --routines --triggers --no-tablespaces \
  "${MARIADB_DATABASE}" | gzip -9 > "${OUT}/db.sql.gz"

# --- uploads (media library) ---------------------------------------------
tar -C /var/www/html/wp-content -czf "${OUT}/uploads.tar.gz" uploads 2>/dev/null || \
  echo "  (no uploads dir yet)"

# --- checksum + manifest -----------------------------------------------
( cd "$OUT" && sha256sum ./* > SHA256SUMS )
du -sh "$OUT"

# --- push off-box -----------------------------------------------------
echo "[$(date -Is)] uploading to ${RCLONE_REMOTE}/${STAMP}"
rclone copy --transfers 4 --retries 3 "$OUT" "${RCLONE_REMOTE}/${STAMP}"

# --- prune -----------------------------------------------------------
echo "[$(date -Is)] pruning remote copies older than ${BACKUP_KEEP_DAYS}d"
rclone delete --min-age "${BACKUP_KEEP_DAYS}d" "${RCLONE_REMOTE}" 2>/dev/null || true
rclone rmdirs --leave-root "${RCLONE_REMOTE}" 2>/dev/null || true

# --- prune local staging copies (keep last 3) --------------------------
ls -1dt /backups/*/ 2>/dev/null | tail -n +4 | xargs -r rm -rf

echo "[$(date -Is)] backup ${STAMP} done"
