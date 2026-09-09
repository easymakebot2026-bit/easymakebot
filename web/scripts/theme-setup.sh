#!/bin/sh
# ─────────────────────────────────────────────────────────────────────────────
# Phase 2 — activate the theme, wire the front page from block patterns, set the
# logo. Idempotent. Run after scripts/install.sh:
#
#   docker compose run --rm --profile cli wpcli /scripts/theme-setup.sh
# ─────────────────────────────────────────────────────────────────────────────
set -eu
WP="wp --path=/var/www/html"

echo "▶ activating theme"
$WP theme activate easymakebot

echo "▶ importing logo → site logo + site icon"
if [ -z "$($WP option get site_logo 2>/dev/null)" ]; then
  LOGO_SRC=/var/www/html/wp-content/themes/easymakebot/assets/logo-256.png
  ATT=$($WP media import "$LOGO_SRC" --title="easymakebot" --porcelain 2>/dev/null | tail -n1)
  if [ -n "${ATT:-}" ] && [ "$ATT" -eq "$ATT" ] 2>/dev/null; then
    $WP option update site_logo "$ATT"
    $WP option update site_icon "$ATT"
  fi
else
  echo "  (site_logo already set — skipping import)"
fi

echo "▶ front page from patterns"
HOME_ID=$($WP post list --post_type=page --name=home --field=ID | head -n1)
FRONT_CONTENT='<!-- wp:pattern {"slug":"easymakebot/hero"} /--><!-- wp:pattern {"slug":"easymakebot/why"} /--><!-- wp:pattern {"slug":"easymakebot/features"} /--><!-- wp:pattern {"slug":"easymakebot/steps"} /--><!-- wp:pattern {"slug":"easymakebot/pricing"} /--><!-- wp:pattern {"slug":"easymakebot/faq"} /--><!-- wp:pattern {"slug":"easymakebot/cta"} /-->'
if [ -z "$HOME_ID" ]; then
  HOME_ID=$($WP post create --post_type=page --post_status=publish \
    --post_title="خانه" --post_name="home" --post_content="$FRONT_CONTENT" --porcelain)
else
  $WP post update "$HOME_ID" --post_content="$FRONT_CONTENT" >/dev/null
fi
$WP option update show_on_front page
$WP option update page_on_front "$HOME_ID"

echo "▶ blog page"
BLOG_ID=$($WP post list --post_type=page --name=blog --field=ID | head -n1)
[ -z "$BLOG_ID" ] && BLOG_ID=$($WP post create --post_type=page --post_status=publish \
  --post_title="وبلاگ" --post_name="blog" --porcelain)
$WP option update page_for_posts "$BLOG_ID"

echo "▶ pretty permalinks"
$WP rewrite structure '/%postname%/' --hard >/dev/null 2>&1 || true

$WP cache flush >/dev/null 2>&1 || true
$WP rewrite flush --hard >/dev/null 2>&1 || true
echo "✅ theme setup done — $($WP option get home)"
