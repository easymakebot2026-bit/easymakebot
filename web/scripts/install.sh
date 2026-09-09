#!/bin/sh
# ─────────────────────────────────────────────────────────────────────────────
# First-run bootstrap for the easymakebot WordPress site. Idempotent — safe to
# re-run. Executes inside the wp-cli container:
#
#   docker compose run --rm --profile cli wpcli /scripts/install.sh
#
# Reads WP_* / SMTP_* from the environment (passed through by compose from .env).
# ─────────────────────────────────────────────────────────────────────────────
set -eu

WP="wp --path=/var/www/html"

echo "▶ waiting for the database…"
until $WP db check >/dev/null 2>&1; do sleep 2; done

# ── core install ───────────────────────────────────────────────────────────
if ! $WP core is-installed >/dev/null 2>&1; then
  echo "▶ installing WordPress core…"
  $WP core install \
    --url="${WP_HOME:?}" \
    --title="${WP_TITLE:-easymakebot}" \
    --admin_user="${WP_ADMIN_USER:?}" \
    --admin_password="${WP_ADMIN_PASSWORD:?}" \
    --admin_email="${WP_ADMIN_EMAIL:?}" \
    --skip-email
else
  echo "▶ core already installed — skipping."
fi

# ── base options / hardening ───────────────────────────────────────────────
echo "▶ applying base options…"
$WP option update blogdescription "بساز، بفروش، آموزش بده — با easymakebot"
$WP option update timezone_string "Asia/Tehran"
$WP option update permalink_structure "/%postname%/"
$WP option update default_comment_status "closed"
$WP option update default_ping_status "closed"
$WP option update users_can_register 0
$WP option update blog_public 0            # staging: discourage search engines (flip to 1 at launch)
$WP rewrite flush --hard

# Remove the bundled cruft plugins/themes we don't use.
$WP plugin delete akismet hello 2>/dev/null || true
$WP theme delete twentytwentythree twentytwentytwo 2>/dev/null || true

# ── required plugins (Phase 1 baseline) ───────────────────────────────────
# Installed one-by-one and non-fatally: plugin downloads come from
# downloads.wordpress.org, which can be flaky/blocked from some networks
# (see README "Iran networking note"). A miss here doesn't block the deploy —
# re-run this script, or `wp plugin install <slug> --activate` later.
echo "▶ installing baseline plugins…"
for slug in redis-cache limit-login-attempts-reloaded wp-mail-smtp polylang autodescription \
            woocommerce zarinpal-woocommerce-payment-gateway; do
  if $WP plugin is-installed "$slug" 2>/dev/null; then
    $WP plugin activate "$slug" 2>/dev/null || true
  else
    timeout 90 $WP plugin install "$slug" --activate \
      || echo "  ⚠ could not install '$slug' (network?) — skipping, re-run later"
  fi
done

# Redis object cache
$WP redis enable 2>/dev/null || $WP redis update-dropin 2>/dev/null || true
$WP redis status || true

# Limit Login Attempts Reloaded — lock 30 min after 4 tries, GDPR-safe IP logging
$WP option patch update limit_login_attempts_reloaded_options allowed_retries 4 2>/dev/null || true
$WP option patch update limit_login_attempts_reloaded_options lockout_duration 1800 2>/dev/null || true

# Mail: real SMTP if creds given; otherwise Mailpit on localhost dev.
# (Set as one JSON blob — `wp option patch` can't create nested keys.)
case "${WP_HOME:-}" in
  *localhost*|*127.0.0.1*)
    echo "▶ pointing WP Mail SMTP at Mailpit (local dev)…"
    $WP option update wp_mail_smtp --format=json '{"mail":{"mailer":"smtp","from_email":"dev@easymakebot.local","from_name":"easymakebot dev","return_path":true},"smtp":{"host":"mailpit","port":1025,"encryption":"none","auth":false,"autotls":false}}'
    ;;
  *)
    if [ -n "${SMTP_HOST:-}" ]; then
      echo "▶ configuring SMTP…"
      $WP option update wp_mail_smtp --format=json "$(cat <<JSON
{"mail":{"mailer":"smtp","from_email":"${SMTP_FROM:-no-reply@localhost}","from_name":"easymakebot","return_path":true},
 "smtp":{"host":"${SMTP_HOST}","port":${SMTP_PORT:-587},"encryption":"tls","auth":true,"autotls":true,
         "user":"${SMTP_USER:-}","pass":"${SMTP_PASS:-}"}}
JSON
)"
    fi
    ;;
esac

# ── theme + content (Phase 2) ────────────────────────────────────────────
if $WP theme is-installed easymakebot >/dev/null 2>&1; then
  echo "▶ theme + front page + i18n…"
  sh /scripts/theme-setup.sh || echo "  ⚠ theme-setup.sh had a non-fatal error"
  if $WP plugin is-active polylang 2>/dev/null; then
    $WP eval-file /scripts/i18n-setup.php || echo "  ⚠ i18n-setup.php had a non-fatal error"
  else
    echo "  ⚠ Polylang not active — skipping bilingual setup (re-run i18n-setup.php later)"
  fi
  if $WP plugin is-active autodescription 2>/dev/null; then
    $WP eval-file /scripts/seo-setup.php || echo "  ⚠ seo-setup.php had a non-fatal error"
  else
    echo "  ⚠ The SEO Framework not active — skipping SEO setup (re-run seo-setup.php later)"
  fi
  $WP eval-file /scripts/tutorials-setup.php || echo "  ⚠ tutorials-setup.php had a non-fatal error"
  if $WP plugin is-active woocommerce 2>/dev/null; then
    $WP eval-file /scripts/shop-setup.php || echo "  ⚠ shop-setup.php had a non-fatal error"
    $WP eval-file /scripts/accounts-setup.php || echo "  ⚠ accounts-setup.php had a non-fatal error"
    $WP eval-file /scripts/enamad-setup.php || echo "  ⚠ enamad-setup.php had a non-fatal error"
  else
    echo "  ⚠ WooCommerce not active — skipping shop + accounts setup (re-run *-setup.php later)"
  fi
else
  echo "⚠ easymakebot theme not present — leaving the default active."
fi

# ── enable auto-updates for all plugins & themes ────────────────────────
$WP plugin auto-updates enable --all 2>/dev/null || true
$WP theme auto-updates enable --all 2>/dev/null || true

echo "✅ bootstrap complete — $($WP option get siteurl)"
