<?php
/**
 * emb-hreflang-schema.php
 *
 * Two SEO gaps found in the 2026-09-19 technical/SEO audit of easymakebot.com:
 *
 *  1. hreflang: Polylang (multilingual) and The SEO Framework are both
 *     active, but NEITHER emits <link rel="alternate" hreflang="..."> tags —
 *     checked the raw <head> of the fa homepage, en homepage, and a tutorial
 *     page, no hreflang anywhere. Each plugin likely assumes the other
 *     handles it. Without this, Google can't reliably match the fa/en
 *     versions of the same page to the right searchers.
 *  2. Structured data: no schema.org/JSON-LD anywhere on the site. This adds
 *     a minimal Organization schema on the homepage (safe starting point).
 *
 * Purely additive — only appends <link>/<script> tags into <head> via
 * wp_head; touches no existing markup, settings, or plugin behavior.
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/* ── 1) hreflang alternates for every translated page ────────────────── */
add_action( 'wp_head', function () {
	if ( ! function_exists( 'pll_the_languages' ) ) {
		return;
	}

	$languages = pll_the_languages( array( 'raw' => 1 ) );
	if ( empty( $languages ) || ! is_array( $languages ) ) {
		return;
	}

	foreach ( $languages as $lang ) {
		if ( empty( $lang['url'] ) || empty( $lang['locale'] ) ) {
			continue;
		}
		$hreflang = strtolower( substr( $lang['locale'], 0, 2 ) ); // fa, en
		printf(
			'<link rel="alternate" hreflang="%s" href="%s" />' . "\n",
			esc_attr( $hreflang ),
			esc_url( $lang['url'] )
		);
	}

	// x-default -> the site's default language (fa)
	$default_lang = function_exists( 'pll_default_language' ) ? pll_default_language( 'slug' ) : 'fa';
	foreach ( $languages as $lang ) {
		if ( isset( $lang['slug'] ) && $lang['slug'] === $default_lang && ! empty( $lang['url'] ) ) {
			printf( '<link rel="alternate" hreflang="x-default" href="%s" />' . "\n", esc_url( $lang['url'] ) );
			break;
		}
	}
}, 5 );

/* ── 2) basic Organization structured data on the homepage ───────────── */
add_action( 'wp_head', function () {
	if ( ! is_front_page() ) {
		return;
	}

	$lang = function_exists( 'pll_current_language' ) ? pll_current_language() : 'fa';
	$desc = ( 'en' === $lang )
		? 'No-code Telegram bot builder — build, launch and monetize your own Telegram bot without writing code.'
		: 'ساخت ربات تلگرام بدون کدنویسی — بساز، فعال کن و از ربات تلگرامی‌ات درآمد کسب کن.';

	$schema = array(
		'@context'    => 'https://schema.org',
		'@type'       => 'Organization',
		'name'        => 'easymakebot',
		'url'         => home_url( '/' ),
		'description' => $desc,
		'logo'        => esc_url( get_theme_file_uri( 'assets/logo-256.png' ) ),
	);

	echo '<script type="application/ld+json">' . wp_json_encode( $schema, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE ) . '</script>' . "\n";
}, 6 );
