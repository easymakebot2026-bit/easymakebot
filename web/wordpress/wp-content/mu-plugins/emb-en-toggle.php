<?php
/**
 * Plugin Name: easymakebot — English side toggle
 * Description: Turn the whole English (/en/) side off (e.g. during the eNamad
 *              review, so the site presents as Persian-only) and back on with a
 *              single option — nothing is deleted.
 *
 *   Disable EN:  wp option update emb_en_enabled 0   (then restart the wp container)
 *   Enable EN:   wp option update emb_en_enabled 1   (or: wp option delete emb_en_enabled)
 *
 * While off:
 *   • any /en/… URL and any Polylang-'en' page (terms-en, privacy-en, EN
 *     tutorials) 302-redirects to the Persian home;
 *   • the [emb_lang_switcher] header control renders nothing;
 *   • the en hreflang <link alternate> is dropped.
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/** EN side live? Default = on (only an explicit '0' turns it off). */
function emb_en_enabled() {
	return '0' !== (string) get_option( 'emb_en_enabled', '1' );
}

/* ── redirect every English surface to the Persian home ─────────────── */
add_action( 'template_redirect', function () {
	if ( emb_en_enabled() || is_admin() ) {
		return;
	}
	if ( ( defined( 'DOING_CRON' ) && DOING_CRON ) || ( defined( 'REST_REQUEST' ) && REST_REQUEST ) ) {
		return;
	}

	$path      = (string) wp_parse_url( $_SERVER['REQUEST_URI'] ?? '/', PHP_URL_PATH );
	$is_en     = (bool) preg_match( '#^/en(/|$)#', $path );

	if ( ! $is_en && function_exists( 'pll_current_language' ) ) {
		$is_en = ( 'en' === pll_current_language() );
	}
	if ( ! $is_en && function_exists( 'pll_get_post_language' ) && is_singular() ) {
		$is_en = ( 'en' === pll_get_post_language( get_queried_object_id() ) );
	}

	if ( $is_en ) {
		wp_safe_redirect( home_url( '/' ), 302 );
		exit;
	}
}, 1 );

/* ── hide the language switcher output ──────────────────────────────── */
add_filter( 'do_shortcode_tag', function ( $output, $tag ) {
	if ( 'emb_lang_switcher' === $tag && ! emb_en_enabled() ) {
		return '';
	}
	return $output;
}, 10, 2 );

/* ── drop the en hreflang alternate (Polylang) ─────────────────────── */
add_filter( 'pll_rel_hreflang_attributes', function ( $hreflangs ) {
	if ( ! emb_en_enabled() && is_array( $hreflangs ) ) {
		unset( $hreflangs['en'] );
	}
	return $hreflangs;
}, 99 );
