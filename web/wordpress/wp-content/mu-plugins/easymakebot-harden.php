<?php
/**
 * Plugin Name: easymakebot — Hardening
 * Description: Must-use security hardening for the easymakebot website. Cannot be
 *              disabled from wp-admin. Pairs with nginx (uploads PHP block,
 *              wp-login rate limit) and Cloudflare (WAF, /wp-admin access).
 * Author:      easymakebot
 * Version:     1.0.0
 *
 * Toggle knobs (define in wp-config.php before this loads):
 *   define('EMB_ENABLE_CSP', true);      // send a Content-Security-Policy on the front end
 *   define('EMB_ALLOW_XMLRPC', true);    // re-enable XML-RPC (default: fully off)
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/* ───────────────────────────────────────────────────────────────────────────
 * 1. Kill XML-RPC (brute-force + pingback amplification vector)
 * ─────────────────────────────────────────────────────────────────────────── */
if ( ! defined( 'EMB_ALLOW_XMLRPC' ) || ! EMB_ALLOW_XMLRPC ) {
	add_filter( 'xmlrpc_enabled', '__return_false' );
	add_filter( 'xmlrpc_methods', '__return_empty_array' );
	// Drop the pingback header and the X-Pingback response header.
	add_filter( 'wp_headers', function ( $headers ) {
		unset( $headers['X-Pingback'] );
		return $headers;
	} );
	add_filter( 'pings_open', '__return_false', 10 );
}

/* ───────────────────────────────────────────────────────────────────────────
 * 2. Block user enumeration
 *    - REST: /wp/v2/users and /wp/v2/users/<id> for anyone who can't list users
 *    - Pretty/ugly ?author=<n> permalink probing
 * ─────────────────────────────────────────────────────────────────────────── */
add_filter( 'rest_endpoints', function ( $endpoints ) {
	if ( is_user_logged_in() && current_user_can( 'list_users' ) ) {
		return $endpoints;
	}
	foreach ( array( '/wp/v2/users', '/wp/v2/users/(?P<id>[\d]+)' ) as $route ) {
		if ( isset( $endpoints[ $route ] ) ) {
			unset( $endpoints[ $route ] );
		}
	}
	return $endpoints;
} );

// Kill author enumeration at the query stage — before redirect_canonical() can
// bounce ?author=<n> to /author/<slug>/ and leak the username.
add_action( 'parse_query', function ( $q ) {
	if ( is_admin() || ! $q->is_main_query() ) {
		return;
	}
	if ( is_user_logged_in() && current_user_can( 'list_users' ) ) {
		return;
	}
	$is_author_probe = ! empty( $q->query_vars['author'] )
		|| ! empty( $q->query_vars['author_name'] )
		|| isset( $_GET['author'] );
	if ( $is_author_probe ) {
		$q->set( 'author', '' );
		$q->set( 'author_name', '' );
		$q->is_author = false;
		$q->is_archive = false;
		$q->set_404();
		status_header( 404 );
		nocache_headers();
	}
} );
// Belt-and-braces: if an author archive still resolves, 404 it.
add_action( 'template_redirect', function () {
	if ( is_author() && ! ( is_user_logged_in() && current_user_can( 'list_users' ) ) ) {
		global $wp_query;
		$wp_query->set_404();
		status_header( 404 );
		nocache_headers();
	}
}, 0 );

/* ───────────────────────────────────────────────────────────────────────────
 * 3. Reduce fingerprinting
 * ─────────────────────────────────────────────────────────────────────────── */
remove_action( 'wp_head', 'wp_generator' );
add_filter( 'the_generator', '__return_empty_string' );
remove_action( 'wp_head', 'rsd_link' );                       // Really Simple Discovery
remove_action( 'wp_head', 'wlwmanifest_link' );               // Windows Live Writer
remove_action( 'wp_head', 'wp_shortlink_wp_head' );
add_filter( 'rest_response_link_curies', '__return_empty_array' );
// Drop the Link: <.../wp-json/> header (still reachable, just not advertised).
remove_action( 'template_redirect', 'rest_output_link_header', 11 );
add_filter( 'style_loader_src', 'emb_strip_asset_version', 20 );
add_filter( 'script_loader_src', 'emb_strip_asset_version', 20 );
/**
 * Strip `?ver=` only from WordPress *core* assets (/wp-includes/, /wp-admin/),
 * where the value is the WP version number and leaks it. Theme and plugin
 * assets keep their `?ver=` — it carries no sensitive info and we rely on it
 * for cache-busting when a release changes CSS/JS.
 */
function emb_strip_asset_version( $src ) {
	if ( ! $src || false === strpos( $src, 'ver=' ) ) {
		return $src;
	}
	if ( strpos( $src, '/wp-includes/' ) !== false || strpos( $src, '/wp-admin/' ) !== false ) {
		$src = remove_query_arg( 'ver', $src );
	}
	return $src;
}

/* ───────────────────────────────────────────────────────────────────────────
 * 4. Login page: don't leak whether a username exists; no password hints
 * ─────────────────────────────────────────────────────────────────────────── */
add_filter( 'login_errors', function () {
	return __( 'Invalid credentials.', 'easymakebot' );
} );

/* ───────────────────────────────────────────────────────────────────────────
 * 5. Disable Application Passwords unless explicitly wanted (headless later)
 * ─────────────────────────────────────────────────────────────────────────── */
if ( ! defined( 'EMB_ALLOW_APP_PASSWORDS' ) || ! EMB_ALLOW_APP_PASSWORDS ) {
	add_filter( 'wp_is_application_passwords_available', '__return_false' );
}

/* ───────────────────────────────────────────────────────────────────────────
 * 6. Security response headers (belt-and-braces with nginx)
 * ─────────────────────────────────────────────────────────────────────────── */
add_action( 'send_headers', function () {
	if ( headers_sent() ) {
		return;
	}
	// Only set a header the front-end proxy hasn't already sent, so a
	// reverse proxy that also adds these (our nginx) doesn't produce dupes.
	$already = array();
	foreach ( headers_list() as $h ) {
		$already[ strtolower( strtok( $h, ':' ) ) ] = true;
	}
	$set = function ( $name, $value ) use ( $already ) {
		if ( empty( $already[ strtolower( $name ) ] ) ) {
			header( "$name: $value" );
		}
	};
	$set( 'X-Content-Type-Options', 'nosniff' );
	$set( 'X-Frame-Options', 'SAMEORIGIN' );
	$set( 'Referrer-Policy', 'strict-origin-when-cross-origin' );
	$set( 'Permissions-Policy', 'geolocation=(), microphone=(), camera=(), interest-cohort=()' );
	$set( 'Cross-Origin-Opener-Policy', 'same-origin' );

	if ( is_ssl() ) {
		$set( 'Strict-Transport-Security', 'max-age=31536000; includeSubDomains; preload' );
	}

	// Opt-in CSP (front end only — a strict CSP breaks the block editor).
	if ( defined( 'EMB_ENABLE_CSP' ) && EMB_ENABLE_CSP && ! is_admin() ) {
		$csp = "default-src 'self'; "
			. "img-src 'self' data: https:; "
			. "media-src 'self' https:; "
			. "font-src 'self' data:; "
			. "style-src 'self' 'unsafe-inline'; "
			. "script-src 'self' 'unsafe-inline' https://www.zarinpal.com https://cdn.zarinpal.com; "
			. "frame-src 'self' https://www.aparat.com https://player.vimeo.com https://www.youtube-nocookie.com; "
			. "connect-src 'self'; "
			. "frame-ancestors 'self'; "
			. "base-uri 'self'; "
			. "form-action 'self' https://www.zarinpal.com https://checkout.stripe.com;";
		header( 'Content-Security-Policy: ' . $csp );
	}
}, 99 );

/* ───────────────────────────────────────────────────────────────────────────
 * 7. Misc lock-downs
 * ─────────────────────────────────────────────────────────────────────────── */
// No plugin/theme file changes from the DB-driven editor even if the constant
// in wp-config.php were ever removed.
if ( ! defined( 'DISALLOW_FILE_EDIT' ) ) {
	define( 'DISALLOW_FILE_EDIT', true );
}

// Block the "install plugins/themes by upload" UI for everyone (updates still
// run automatically; deliberate installs happen via wp-cli / the runbook).
add_filter( 'map_meta_cap', function ( $caps, $cap ) {
	if ( in_array( $cap, array( 'install_plugins', 'install_themes', 'upload_plugins', 'upload_themes' ), true ) ) {
		$caps[] = 'do_not_allow';
	}
	return $caps;
}, 10, 2 );

// Turn off self-registration unless an admin has explicitly enabled it.
add_action( 'init', function () {
	if ( get_option( 'users_can_register' ) && ! defined( 'EMB_ALLOW_REGISTRATION' ) ) {
		update_option( 'users_can_register', 0 );
	}
} );

// Sensible defaults for comments-as-spam-surface: keep them closed site-wide
// unless a future feature needs them (the theme has no comment templates).
add_filter( 'comments_open', '__return_false', 20 );
add_filter( 'pings_open', '__return_false', 20 );
