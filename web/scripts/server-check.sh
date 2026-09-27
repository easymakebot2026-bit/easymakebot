#!/usr/bin/env bash
# Website server (Iran, WordPress) — deploy and/or audit.
#
#   ./web/scripts/server-check.sh            # audit only (read-only, safe to run anytime)
#   ./web/scripts/server-check.sh deploy     # DB backup -> git pull -> restart PHP -> audit
#
# The mu-plugins and theme are bind-mounted from this checkout, so a
# `git pull` is the whole code deploy; PHP is restarted so OPcache can't keep
# serving the old plugin code. The audit also re-checks every TON/USDT order
# the site already completed, because before this fix a fake "USDT" token
# was accepted as payment.
#
# Output is redacted (no keys/emails) so it can be pasted for review.
# Override compose files with COMPOSE_FILES="-f a.yml -f b.yml" if needed.

set -uo pipefail

WEB_DIR="$(cd "$(dirname "$0")/.." && pwd)"
REPO_DIR="$(cd "$WEB_DIR/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-$HOME/emb-backups}"
MODE="${1:-audit}"
export GIT_TERMINAL_PROMPT=0

# shellcheck source=deploy/audit-common.sh
. "$REPO_DIR/deploy/audit-common.sh"

# Use exactly the compose files the running stack was started with (the
# repo supports a Caddy track and an nginx track), read from Docker's own
# labels, unless COMPOSE_FILES is given.
detect_compose_files() {
  if [ -n "${COMPOSE_FILES:-}" ]; then echo "$COMPOSE_FILES"; return; fi
  local c files
  c=$($SUDO docker ps -q --filter "label=com.docker.compose.project.working_dir=$WEB_DIR" | head -1)
  if [ -n "$c" ]; then
    files=$($SUDO docker inspect -f '{{ index .Config.Labels "com.docker.compose.project.config_files" }}' "$c")
    echo "$files" | tr ',' '\n' | sed 's/^/-f /' | tr '\n' ' '
  else
    echo "-f $WEB_DIR/docker-compose.yml -f $WEB_DIR/docker-compose.prod.yml"
  fi
}
COMPOSE_ARGS="$(detect_compose_files)"
# shellcheck disable=SC2086
compose() { (cd "$WEB_DIR" && $SUDO docker compose $COMPOSE_ARGS "$@"); }
php_service() { compose ps --services 2>/dev/null | grep -vE 'wpcli|db|mysql|mariadb|nginx|caddy|backup|redis' | grep -m1 -E 'wordpress|php|wp|app'; }
wp() { compose run --rm -T wpcli wp "$@" 2>/dev/null; }

backup_db() {
  section "Database backup"
  mkdir -p "$BACKUP_DIR" && chmod 700 "$BACKUP_DIR"
  local out="$BACKUP_DIR/emb-web-$(date +%F-%H%M).sql.gz"
  if wp db export - | gzip > "$out" && [ "$(gzip -dc "$out" | head -c 200000 | grep -c 'CREATE TABLE')" -gt 0 ]; then
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
  for f in "$WEB_DIR"/wordpress/wp-content/mu-plugins/*.php; do
    compose run --rm -T wpcli php -l "/var/www/html/wp-content/mu-plugins/$(basename "$f")" >/dev/null 2>&1 \
      || warn "PHP syntax check could not confirm $(basename "$f")"
  done
  local svc
  svc=$(php_service)
  if [ -n "$svc" ]; then
    compose restart "$svc" >/dev/null && note "Restarted $svc (clears OPcache)"
  else
    warn "Could not find the PHP/WordPress service to restart — restart it manually"
  fi
  sleep 5
  local site code
  site=$(wp option get home)
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "$site/")
  if [ "$code" = "200" ]; then note "Site answers 200 at $site"; else warn "Site returned HTTP $code — roll back with: git checkout $before && restart $svc"; fi
}

audit_ton_orders() {
  section "Re-check of TON/USDT orders already completed (fake-token fix)"
  # Needs the fixed plugin (emb_ton_is_official_usdt) — run after deploy.
  wp eval '
    if ( ! function_exists( "emb_ton_is_official_usdt" ) ) { echo "  plugin not updated yet — run this script with: deploy\n"; return; }
    $orders = wc_get_orders( array( "payment_method" => "emb_ton", "limit" => -1, "status" => array( "processing", "completed" ) ) );
    $bad = 0; $checked = 0;
    foreach ( $orders as $o ) {
      $tx = (string) $o->get_meta( "_emb_ton_txid" );
      if ( "" === $tx ) { continue; }
      $r = wp_remote_get( "https://tonapi.io/v2/events/" . rawurlencode( $tx ), array( "timeout" => 15 ) );
      $j = is_wp_error( $r ) ? null : json_decode( wp_remote_retrieve_body( $r ), true );
      if ( ! $j ) { printf( "  order #%d: could not fetch the transaction — check manually\n", $o->get_id() ); continue; }
      $checked++;
      $verdict = "TON (native coin) — OK";
      foreach ( (array) ( $j["actions"] ?? array() ) as $a ) {
        if ( ( $a["type"] ?? "" ) === "JettonTransfer" ) {
          $ok = emb_ton_is_official_usdt( $a["JettonTransfer"]["jetton"]["address"] ?? "" );
          $verdict = $ok ? "real USDT — OK" : "FAKE token (" . ( $a["JettonTransfer"]["jetton"]["symbol"] ?? "?" ) . ") — NOT PAID";
          if ( ! $ok ) { $bad++; }
        }
      }
      printf( "  order #%d (%s): %s\n", $o->get_id(), $o->get_date_created() ? $o->get_date_created()->date( "Y-m-d" ) : "?", $verdict );
    }
    printf( "  checked %d order(s); %d paid with a fake token%s\n", $checked, $bad,
      $bad ? " — void their activation codes in the order screen and review the bots they activated" : "" );
  '
}

audit_wordpress() {
  section "WordPress"
  cd "$REPO_DIR" || return
  note "Repo: $REPO_DIR @ $(git rev-parse --short HEAD 2>/dev/null) — $(git log -1 --format='%s (%cr)' 2>/dev/null)"
  git fetch -q origin 2>/dev/null && note "Commits on origin/main not deployed yet: $(git rev-list --count HEAD..origin/main 2>/dev/null)"
  note "Compose: $COMPOSE_ARGS"
  compose ps 2>/dev/null | sed 's/^/  /'
  note "Core: $(wp core version) | updates: $(wp core check-update --format=count 2>/dev/null || echo 0)"
  if wp core verify-checksums >/dev/null; then note "Core file checksums: OK"; else warn "WordPress core files differ from the official release — possible tampering"; fi
  note "Plugins with updates available:"
  wp plugin list --update=available --fields=name,version,update_version --format=csv | sed 's/^/    /'
  wp plugin verify-checksums --all >/dev/null || warn "Some plugin files don't match wordpress.org checksums (normal for premium plugins; investigate others)"
  note "Administrators: $(wp user list --role=administrator --format=count)"
  note "Open registration (users_can_register): $(wp option get users_can_register)"
  [ "$(wp config get WP_DEBUG 2>/dev/null)" = "1" ] && warn "WP_DEBUG is on in production"
  [ "$(wp config get DISALLOW_FILE_EDIT 2>/dev/null)" = "1" ] || warn "DISALLOW_FILE_EDIT is not set — admins can edit PHP from the dashboard"
  note "Activation codes: $(wp db query "SELECT CONCAT(status, '=', COUNT(*)) FROM $(wp db prefix)emb_activation_codes GROUP BY status" --skip-column-names 2>/dev/null | tr '\n' ' ')"
  note "TON orders waiting (on-hold): $(wp eval 'echo count( wc_get_orders( array( "payment_method" => "emb_ton", "status" => "on-hold", "limit" => -1, "return" => "ids" ) ) );')"
  local key
  key=$(wp config get EMB_ACTIVATION_KEY 2>/dev/null || true)
  case "$key" in ""|change-me*) warn "EMB_ACTIVATION_KEY is empty or still the placeholder";; esac

  local wpc
  wpc=$(compose ps -q "$(php_service)" 2>/dev/null)
  [ -n "$wpc" ] && audit_logs "$wpc" 500

  section "Backups"
  local newest
  newest=$(ls -t "$BACKUP_DIR"/*.sql.gz "$WEB_DIR"/backups/* 2>/dev/null | head -1)
  if [ -n "$newest" ]; then
    note "Newest: $newest ($(( ( $(date +%s) - $(stat -c %Y "$newest") ) / 86400 )) days old)"
  else
    warn "No backup files found here — check that the nightly backup job is running and copies off-site"
  fi

  audit_env_perms "$WEB_DIR/.env"
  local site host
  site=$(wp option get home)
  host=$(echo "$site" | sed -E 's#https?://([^/]+).*#\1#')
  if [ -n "$host" ]; then
    audit_tls "$host"
    audit_http "$site"
  fi
  audit_ton_orders
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
  audit_wordpress
  section "Done"
  note "Paste everything above (it is already redacted) for review."
} 2>&1 | redact
