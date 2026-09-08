<?php
/**
 * Paste this block into wp-config.php ABOVE the line
 *   /* That's all, stop editing! * /
 * on a managed / cPanel host (Track B). The Docker stack injects the same
 * constants via WORDPRESS_CONFIG_EXTRA, so you do NOT need this there.
 */

/* --- Editing & updates ------------------------------------------------ */
define( 'DISALLOW_FILE_EDIT', true );      // no code editor in wp-admin
define( 'WP_AUTO_UPDATE_CORE', 'minor' );  // security releases auto-apply
// Leave file mods ENABLED so plugin/theme auto-updates work:
// (do NOT set DISALLOW_FILE_MODS)

/* --- Force TLS for the dashboard & logins -------------------------- */
define( 'FORCE_SSL_ADMIN', true );
if ( isset( $_SERVER['HTTP_X_FORWARDED_PROTO'] ) && $_SERVER['HTTP_X_FORWARDED_PROTO'] === 'https' ) {
	$_SERVER['HTTPS'] = 'on';
}

/* --- Revisions / trash ------------------------------------------- */
define( 'WP_POST_REVISIONS', 10 );
define( 'EMPTY_TRASH_DAYS', 14 );

/* --- Debug OFF in production ------------------------------------ */
define( 'WP_DEBUG', false );
define( 'WP_DEBUG_DISPLAY', false );
@ini_set( 'display_errors', 0 );

/* --- Redis object cache (only if the host provides Redis) --------- */
// define( 'WP_REDIS_HOST', '127.0.0.1' );
// define( 'WP_REDIS_PORT', 6379 );
// define( 'WP_REDIS_PREFIX', 'emb_' );

/* --- Optional CSP (tune, then enable) --------------------------- */
// define( 'EMB_ENABLE_CSP', true );

/* --- Make sure $table_prefix is NOT the default 'wp_' ------------ */
// $table_prefix = 'emb_';
