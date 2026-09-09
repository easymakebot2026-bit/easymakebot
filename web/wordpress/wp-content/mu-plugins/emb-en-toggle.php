<?php
/**
 * Plugin Name: easymakebot — English side toggle
 *   Disable EN:  wp option update emb_en_enabled 0   (then restart wp)
 *   Enable  EN:  wp option update emb_en_enabled 1
 */
if ( ! defined( 'ABSPATH' ) ) { exit; }

function emb_en_enabled() {
	return '0' !== (string) get_option( 'emb_en_enabled', '1' );
}

add_action( 'template_redirect', function () {
	if ( emb_en_enabled() || is_admin() ) { return; }
	if ( ( defined( 'DOING_CRON' ) && DOING_CRON ) || ( defined( 'REST_REQUEST' ) && REST_REQUEST ) ) { return; }
	$path  = (string) wp_parse_url( $_SERVER['REQUEST_URI'] ?? '/', PHP_URL_PATH );
	$is_en = (bool) preg_match( '#^/en(/|$)#', $path );
	if ( ! $is_en && function_exists( 'pll_current_language' ) ) {
		$is_en = ( 'en' === pll_current_language() );
	}
	if ( ! $is_en && function_exists( 'pll_get_post_language' ) && is_singular() ) {
		$is_en = ( 'en' === pll_get_post_language( get_queried_object_id() ) );
	}
	if ( $is_en ) { wp_safe_redirect( home_url( '/' ), 302 ); exit; }
}, 1 );

add_filter( 'do_shortcode_tag', function ( $output, $tag ) {
	return ( 'emb_lang_switcher' === $tag && ! emb_en_enabled() ) ? '' : $output;
}, 10, 2 );

add_filter( 'pll_rel_hreflang_attributes', function ( $h ) {
	if ( ! emb_en_enabled() && is_array( $h ) ) { unset( $h['en'] ); }
	return $h;
}, 99 );
