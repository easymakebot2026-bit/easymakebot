#!/usr/bin/env bash
# Shared, READ-ONLY server health/security checks, sourced by
# deploy/server-check.sh (bot server) and web/scripts/server-check.sh
# (website server). Nothing here changes the system.
#
# Output is meant to be pasted into a chat/issue for review, so every line
# goes through `redact`: bot tokens, API keys, secrets, e-mail addresses and
# long random strings are masked. .env files are never printed — only their
# permissions are checked.

set -o pipefail

section() { printf '\n==================== %s ====================\n' "$1"; }
note()    { printf '  - %s\n' "$*"; }
warn()    { printf '  [WARN] %s\n' "$*"; }
have()    { command -v "$1" >/dev/null 2>&1; }

# sudo only when needed and available non-interactively-or-with-prompt.
SUDO=""
if [ "$(id -u)" -ne 0 ] && have sudo; then SUDO="sudo"; fi

redact() {
  sed -E \
    -e 's/[0-9]{6,12}:[A-Za-z0-9_-]{30,}/<BOT_TOKEN>/g' \
    -e 's/(sk|pk|rk)_(live|test)_[A-Za-z0-9]{8,}/<STRIPE_KEY>/g' \
    -e 's/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/<EMAIL>/g' \
    -e 's/(password|passwd|secret|token|key|authorization)(["]?[ ]*[:=][ ]*["]?)[^ ",;]{6,}/\1\2<REDACTED>/Ig' \
    -e 's/[A-Za-z0-9_+=-]{40,}/<LONG_STRING>/g'
}

audit_system() {
  section "System"
  note "Host: $(hostname) | $(. /etc/os-release 2>/dev/null; echo "${PRETTY_NAME:-unknown OS}") | kernel $(uname -r)"
  note "Uptime: $(uptime -p 2>/dev/null || uptime)"
  note "Load: $(cut -d' ' -f1-3 /proc/loadavg) | CPUs: $(nproc)"
  free -h | sed 's/^/  /'
  section "Disk"
  df -hT -x tmpfs -x devtmpfs -x overlay 2>/dev/null | sed 's/^/  /'
  df -P -x tmpfs -x devtmpfs -x overlay 2>/dev/null | awk 'NR>1 {gsub("%","",$5); if ($5+0 >= 85) print "  [WARN] " $6 " is " $5 "% full"}'
  if have docker; then
    note "Docker disk usage:"; $SUDO docker system df 2>/dev/null | sed 's/^/    /'
  fi
}

audit_updates() {
  section "OS updates"
  if have apt-get; then
    local n
    n=$(apt list --upgradable 2>/dev/null | grep -c upgradable || true)
    note "Upgradable packages: $n"
    apt list --upgradable 2>/dev/null | grep -i security | head -20 | sed 's/^/    security: /'
    if [ -f /var/run/reboot-required ]; then warn "Reboot required (kernel/libc update pending)"; fi
    if dpkg -l unattended-upgrades 2>/dev/null | grep -q '^ii'; then
      note "unattended-upgrades: installed ($(systemctl is-enabled unattended-upgrades 2>/dev/null || echo '?'))"
    else
      warn "unattended-upgrades is not installed — security patches aren't applied automatically"
    fi
  else
    note "Not an apt-based system — skipped"
  fi
}

audit_network() {
  section "Listening ports (anything public besides 22/80/443 deserves a look)"
  $SUDO ss -tulpnH 2>/dev/null | awk '{print "  " $1 " " $5 " " $7}' | sort -u
  section "Firewall"
  if have ufw; then $SUDO ufw status verbose 2>/dev/null | sed 's/^/  /'; else warn "ufw not installed"; fi
  if have docker; then
    note "Reminder: ports published by Docker (e.g. 5432, 8080) bypass ufw — check the list above."
  fi
  section "fail2ban"
  if have fail2ban-client; then
    $SUDO fail2ban-client status 2>/dev/null | sed 's/^/  /'
    $SUDO fail2ban-client status sshd 2>/dev/null | grep -E 'Currently|Total' | sed 's/^/  /'
  else
    warn "fail2ban not installed"
  fi
}

audit_ssh() {
  section "SSH daemon (effective settings)"
  if have sshd; then
    local cfg
    cfg=$($SUDO sshd -T 2>/dev/null)
    for k in permitrootlogin passwordauthentication pubkeyauthentication kbdinteractiveauthentication port maxauthtries x11forwarding; do
      printf '  %s\n' "$(printf '%s\n' "$cfg" | grep -m1 "^$k ")"
    done
    printf '%s\n' "$cfg" | grep -q '^permitrootlogin yes' && warn "Root can log in with SSH — set PermitRootLogin no (or prohibit-password)"
    printf '%s\n' "$cfg" | grep -q '^passwordauthentication yes' && warn "SSH password login is enabled — use keys only"
  else
    note "sshd not found"
  fi
  note "Accounts with a login shell:"
  awk -F: '$7 !~ /(nologin|false)$/ {print "    " $1 " (uid " $3 ")"}' /etc/passwd
  note "Recent logins:"
  last -n 8 2>/dev/null | head -8 | sed 's/^/    /'
  local fails
  fails=$($SUDO journalctl -u ssh -u sshd --since "24 hours ago" 2>/dev/null | grep -c 'Failed password\|Invalid user' || true)
  note "Failed SSH attempts in the last 24h: ${fails:-?}"
}

audit_docker() {
  section "Docker"
  if ! have docker; then warn "docker not installed"; return; fi
  note "$($SUDO docker version --format 'Engine {{.Server.Version}}' 2>/dev/null) | compose $($SUDO docker compose version --short 2>/dev/null)"
  $SUDO docker ps -a --format '  {{.Names}}\t{{.Image}}\t{{.Status}}' 2>/dev/null
  $SUDO docker ps -a --format '{{.Names}}' 2>/dev/null | while read -r c; do
    local rc st
    rc=$($SUDO docker inspect -f '{{.RestartCount}}' "$c" 2>/dev/null)
    st=$($SUDO docker inspect -f '{{.State.Status}}' "$c" 2>/dev/null)
    if [ "${rc:-0}" -gt 0 ]; then warn "$c has restarted $rc time(s)"; fi
    if [ "$st" != "running" ]; then warn "$c is $st"; fi
  done
  $SUDO docker ps --format '{{.Names}} {{.Ports}}' 2>/dev/null | grep -E '0\.0\.0\.0:(5432|3306|6379|8080)|:::(5432|3306|6379)' \
    | sed 's/^/  [WARN] published to the internet: /'
}

audit_logs() {  # $1 = container name or id, $2 = lines
  local c="$1" n="${2:-200}"
  section "Recent errors in $($SUDO docker inspect -f '{{.Name}}' "$c" 2>/dev/null | tr -d /) logs (redacted)"
  $SUDO docker logs --tail "$n" "$c" 2>&1 | grep -iE 'error|exception|traceback|critical|fatal' | tail -25 | redact | sed 's/^/  /'
}

audit_env_perms() {  # args: env files
  section "Secret files (permissions only — contents are never printed)"
  for f in "$@"; do
    if [ -f "$f" ]; then
      local p
      p=$(stat -c '%a %U:%G' "$f")
      note "$f → $p"
      case "${p%% *}" in 600|400|640) ;; *) warn "$f is readable by other users — run: chmod 600 $f";; esac
    else
      note "$f → (not present)"
    fi
  done
}

audit_tls() {  # $1 = domain
  local d="$1"
  section "TLS certificate for $d"
  if ! have openssl; then note "openssl missing"; return; fi
  local end
  end=$(echo | timeout 10 openssl s_client -servername "$d" -connect "$d:443" 2>/dev/null | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2)
  if [ -z "$end" ]; then warn "Could not read the certificate for $d"; return; fi
  local days=$(( ( $(date -d "$end" +%s) - $(date +%s) ) / 86400 ))
  note "Expires: $end ($days days)"
  if [ "$days" -lt 20 ]; then warn "Certificate for $d expires in $days days"; fi
  return 0
}

audit_http() {  # $1 = base URL
  local u="$1"
  section "HTTP checks for $u"
  note "Security headers:"
  curl -sS -o /dev/null -D - --max-time 15 "$u/" 2>/dev/null \
    | grep -iE '^(strict-transport-security|x-content-type-options|x-frame-options|content-security-policy|referrer-policy|server|x-powered-by):' \
    | sed 's/^/    /'
  for path in /.env /.git/HEAD /wp-config.php.bak /readme.html /xmlrpc.php /wp-json/wp/v2/users /debug.log /wp-content/debug.log; do
    local code
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "$u$path")
    printf '    %-28s %s\n' "$path" "$code"
    case "$path:$code" in
      /.env:200|/.git/HEAD:200|/wp-config.php.bak:200|/debug.log:200|/wp-content/debug.log:200)
        warn "$path is publicly readable — block it immediately";;
      /wp-json/wp/v2/users:200) warn "WordPress user list is public (username enumeration)";;
      /xmlrpc.php:200|/xmlrpc.php:405) warn "xmlrpc.php is reachable (brute-force/DDoS vector) — block it if unused";;
    esac
  done
}
