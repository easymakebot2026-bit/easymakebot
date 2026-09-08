<?php
/**
 * easymakebot theme — setup & assets.
 *
 * @package easymakebot
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

define( 'EMB_THEME_VER', '0.14.1' );

require_once get_theme_file_path( 'inc/tutorials.php' );
if ( class_exists( 'WooCommerce' ) ) {
	require_once get_theme_file_path( 'inc/shop.php' );
}

/* ── No WordPress admin bar on the front end ──────────────────────────────
 * Keeps the public site (and logged-in previews) clean. The toolbar is still
 * there inside /wp-admin.
 */
add_filter( 'show_admin_bar', '__return_false' );

/* ── Setup ─────────────────────────────────────────────────────────────── */
add_action( 'after_setup_theme', function () {
	add_theme_support( 'wp-block-styles' );
	add_theme_support( 'responsive-embeds' );
	add_theme_support( 'editor-styles' );
	add_theme_support( 'html5', array( 'style', 'script', 'navigation-widgets' ) );
	add_editor_style( 'assets/app.css' );
	load_theme_textdomain( 'easymakebot', get_template_directory() . '/languages' );
} );

/* ── Front-end assets ─────────────────────────────────────────────────── */
add_action( 'wp_enqueue_scripts', function () {
	// style.css (theme header) + the component stylesheet.
	wp_enqueue_style( 'easymakebot-style', get_stylesheet_uri(), array(), EMB_THEME_VER );
	wp_enqueue_style(
		'easymakebot-app',
		get_theme_file_uri( 'assets/app.css' ),
		array( 'easymakebot-style' ),
		EMB_THEME_VER
	);
	// Tiny progressive-enhancement script (FAQ <details> already works without JS).
	wp_enqueue_script(
		'easymakebot-app',
		get_theme_file_uri( 'assets/app.js' ),
		array(),
		EMB_THEME_VER,
		array( 'strategy' => 'defer', 'in_footer' => true )
	);

	// Auth state for app.js (buy-panel gate + /en/ sign-in widget).
	$lang = function_exists( 'pll_current_language' ) ? ( pll_current_language() ?: 'fa' ) : 'fa';
	wp_add_inline_script( 'easymakebot-app', 'window.embAuth=' . wp_json_encode( array(
		'loggedIn'   => is_user_logged_in(),
		'verified'   => function_exists( 'emb_is_verified' ) && emb_is_verified(),
		'lang'       => $lang,
		'nonce'      => wp_create_nonce( 'wp_rest' ),
		'restBase'   => esc_url_raw( rest_url( 'emb/v1/' ) ),
		'accountUrl' => function_exists( 'wc_get_page_permalink' ) ? wc_get_page_permalink( 'myaccount' ) : home_url( '/my-account/' ),
	) ) . ';', 'before' );
}, 20 );

/* ── Block pattern category ──────────────────────────────────────────── */
add_action( 'init', function () {
	register_block_pattern_category( 'easymakebot', array(
		'label' => __( 'easymakebot', 'easymakebot' ),
	) );
} );

/* ── Nav menu locations (classic menus, used by the Navigation block fallback) ── */
add_action( 'init', function () {
	register_nav_menus( array(
		'primary' => __( 'Primary', 'easymakebot' ),
		'footer'  => __( 'Footer', 'easymakebot' ),
	) );
} );

/* ── Primary nav: [emb_nav] ─────────────────────────────────────────────
 * A tiny hand-rolled nav so header/footer stay a single language-agnostic
 * template part. Labels switch on the active Polylang language; the target
 * URLs point at the matching (FA or EN) front-page anchors / sections.
 */
function emb_nav_items() {
	$lang = function_exists( 'pll_current_language' ) ? pll_current_language() : 'fa';
	$base = ( 'en' === $lang ) ? '/en/' : '/';
	if ( 'en' === $lang ) {
		return array(
			array( 'Why', $base . '#why' ),
			array( 'Features', $base . '#features' ),
			array( 'Tutorials', $base . 'tutorials/' ),
			array( 'Pricing', $base . '#pricing' ),
		);
	}
	return array(
		array( 'چرا', $base . '#why' ),
		array( 'امکانات', $base . '#features' ),
		array( 'آموزش', $base . 'tutorials/' ),
		array( 'هزینه', $base . '#pricing' ),
	);
}

add_shortcode( 'emb_nav', function () {
	$out = '<nav class="emb-nav" aria-label="Primary">';
	foreach ( emb_nav_items() as $it ) {
		$out .= sprintf( '<a class="emb-nav__item" href="%s">%s</a>', esc_url( $it[1] ), esc_html( $it[0] ) );
	}
	$out .= '</nav>';
	return $out;
} );

add_shortcode( 'emb_footer_note', function () {
	$lang = function_exists( 'pll_current_language' ) ? pll_current_language() : 'fa';
	$year = gmdate( 'Y' );
	$home = ( 'en' === $lang ) ? '/en/' : '/';
	$txt  = ( 'en' === $lang )
		? 'build a bot, no code required.'
		: 'ربات بساز، بدون کدنویسی.';
	return sprintf(
		'<p class="emb-footer-note">© %s <a href="%s">easymakebot</a> — %s</p>',
		esc_html( $year ),
		esc_url( $home ),
		esc_html( $txt )
	);
} );

/* [emb_legal_links] — footer info/legal nav (About, Contact, Rules, Privacy),
 * each linking the current language's page. Items appear only if the page
 * exists, so it grows as scripts/enamad-setup.php adds pages. */
add_shortcode( 'emb_legal_links', function () {
	$en = function_exists( 'emb_current_lang' ) && 'en' === emb_current_lang();

	$slug = function ( $fa, $enslug ) use ( $en ) {
		return $en ? $enslug : $fa;
	};
	$items = array(
		array( $slug( 'about', 'about-en' ),     $en ? 'About'             : 'درباره ما' ),
		array( $slug( 'contact', 'contact-en' ), $en ? 'Contact'           : 'تماس با ما' ),
		array( $slug( 'terms', 'terms-en' ),     $en ? 'Terms of Service'  : 'قوانین و مقررات' ),
		array( $slug( 'privacy', 'privacy-en' ), $en ? 'Privacy'           : 'حریم خصوصی' ),
	);

	$out = '';
	foreach ( $items as $it ) {
		$page = get_page_by_path( $it[0] );
		if ( $page && 'publish' === get_post_status( $page ) ) {
			$out .= sprintf( '<a href="%s">%s</a>', esc_url( get_permalink( $page ) ), esc_html( $it[1] ) );
		}
	}
	return $out ? '<nav class="emb-legal" aria-label="' . esc_attr( $en ? 'Info' : 'اطلاعات' ) . '">' . $out . '</nav>' : '';
} );

/* [emb_enamad] — the eNamad (نماد اعتماد الکترونیکی) trust-seal code.
 * After eNamad issues the snippet:  wp option update emb_enamad_code '<paste it>'
 * (or paste it in wp-admin › Settings › easymakebot). Renders nothing until set. */
add_shortcode( 'emb_enamad', function () {
	$code = trim( (string) get_option( 'emb_enamad_code', '' ) );
	if ( '' === $code ) {
		return '';
	}
	// eNamad's snippet is a fixed <a ...><img ...></a> — allow just those tags.
	// NB: no 'rel' — eNamad's logo.aspx does a Referer check, and a
	// rel="noopener noreferrer" (which WP/other plugins may inject) strips the
	// Referer and the seal 403s. Also hard-strip any rel that slips through.
	$allowed = array(
		'a'   => array( 'referrerpolicy' => true, 'target' => true, 'href' => true ),
		'img' => array( 'referrerpolicy' => true, 'src' => true, 'alt' => true, 'style' => true, 'id' => true, 'code' => true, 'loading' => true ),
	);
	$html = wp_kses( $code, $allowed );
	$html = preg_replace( '/\srel=(["\']).*?\1/i', '', $html );
	return '<div class="emb-enamad">' . $html . '</div>';
} );

/* [emb_zarinpal_badge] — ZarinPal's official gateway-verified badge.
 * Fixed embed from https://www.zarinpal.com/docs/extensions/official-logo —
 * a script that draws the badge itself, so nothing to configure here. If
 * EMB_ENABLE_CSP is ever turned on, script-src must allow zarinpal.com
 * (already added in easymakebot-harden.php). */
add_shortcode( 'emb_zarinpal_badge', function () {
	return '<div class="emb-zarinpal-badge"><script src="https://www.zarinpal.com/webservice/TrustCode" type="text/javascript"></script></div>';
} );

/* Keep WordPress's wp_targeted_link_rel() from adding rel="noopener noreferrer"
 * to the eNamad seal link (it breaks the Referer check). */
add_filter( 'wp_targeted_link_rel', function ( $rel, $link_html ) {
	return ( false !== strpos( (string) $link_html, 'trustseal.enamad.ir' ) ) ? '' : $rel;
}, 10, 2 );

/**
 * [emb_theme_toggle] — cycles light / dark / auto. State + icon are set by
 * app.js; a no-JS visitor just never sees it toggle (site still follows the OS).
 */
add_shortcode( 'emb_theme_toggle', function () {
	$lang  = function_exists( 'pll_current_language' ) ? pll_current_language() : 'fa';
	$label = ( 'en' === $lang ) ? 'Toggle light / dark theme' : 'تغییر حالت روشن / تاریک';
	return sprintf(
		'<button type="button" class="emb-theme-toggle" data-emb-theme-toggle aria-label="%s" title="%s"><span class="emb-theme-toggle__i" aria-hidden="true">◐</span></button>',
		esc_attr( $label ),
		esc_attr( $label )
	);
} );

// Set the theme attribute before first paint so there's no light→dark flash.
add_action( 'wp_head', function () {
	echo "<script>(function(){try{var t=localStorage.getItem('emb-theme');if(t==='dark'||t==='light'){document.documentElement.setAttribute('data-theme',t);}}catch(e){}})();</script>\n";
}, 0 );

add_shortcode( 'emb_cta_button', function () {
	$lang  = function_exists( 'pll_current_language' ) ? pll_current_language() : 'fa';
	$label = ( 'en' === $lang ) ? 'Open in Telegram' : 'شروع در تلگرام';
	return sprintf(
		'<a class="wp-block-button__link wp-element-button emb-cta-btn" href="%s">%s</a>',
		esc_url( 'https://t.me/easymakebot' ),
		esc_html( $label )
	);
} );

/* ── Language switcher: [emb_lang_switcher] ──────────────────────────────
 * Renders Polylang's switcher if the plugin is active; otherwise nothing.
 * Kept theme-side so the header template part is plugin-agnostic.
 */
add_shortcode( 'emb_lang_switcher', function () {
	if ( ! function_exists( 'pll_the_languages' ) ) {
		return '';
	}
	$links = pll_the_languages( array(
		'raw'                    => 1,
		'hide_if_no_translation' => 0,
		'display_names_as'       => 'slug',
	) );
	if ( empty( $links ) || ! is_array( $links ) ) {
		return '';
	}
	$out = '<nav class="emb-langsw" aria-label="Language">';
	foreach ( $links as $l ) {
		$cur = ! empty( $l['current_lang'] ) ? ' is-current' : '';
		$out .= sprintf(
			'<a class="emb-langsw__item%s" href="%s" lang="%s">%s</a>',
			esc_attr( $cur ),
			esc_url( $l['url'] ),
			esc_attr( $l['locale'] ),
			esc_html( strtoupper( $l['slug'] ) )
		);
	}
	$out .= '</nav>';
	return $out;
} );

/* ── Body classes: expose current language ────────────────────────────── */
add_filter( 'body_class', function ( $classes ) {
	if ( function_exists( 'pll_current_language' ) ) {
		$classes[] = 'lang-' . pll_current_language();
	}
	return $classes;
} );

// [emb_ad] — ads were removed before launch. Kept as a no-op so any stale
// shortcode left in saved content renders nothing instead of literal text.
add_shortcode( 'emb_ad', '__return_empty_string' );

/* ── SEO / performance head bits ──────────────────────────────────────── */
add_action( 'wp_head', function () {
	// Preload the primary UI font so first paint isn't blocked on it.
	printf(
		'<link rel="preload" as="font" type="font/woff2" href="%s" crossorigin>' . "\n",
		esc_url( get_theme_file_uri( 'assets/fonts/vazirmatn-400.woff2' ) )
	);
}, 1 );

// Let the browser prioritise the logo (it's the LCP-adjacent brand mark).
add_filter( 'get_custom_logo_image_attributes', function ( $attr ) {
	$attr['fetchpriority'] = 'high';
	$attr['decoding']      = 'async';
	return $attr;
} );

// Sensible default share image + description when a plugin hasn't set one.
add_action( 'wp_head', function () {
	if ( function_exists( 'the_seo_framework' ) || defined( 'WPSEO_VERSION' ) || class_exists( 'RankMath' ) ) {
		return; // an SEO plugin is handling meta.
	}
	$desc = get_bloginfo( 'description' );
	if ( is_singular() ) {
		$desc = has_excerpt() ? get_the_excerpt() : $desc;
	}
	if ( $desc ) {
		echo '<meta name="description" content="' . esc_attr( wp_strip_all_tags( $desc ) ) . '">' . "\n";
		echo '<meta property="og:description" content="' . esc_attr( wp_strip_all_tags( $desc ) ) . '">' . "\n";
	}
	echo '<meta property="og:site_name" content="' . esc_attr( get_bloginfo( 'name' ) ) . '">' . "\n";
	echo '<meta name="twitter:card" content="summary_large_image">' . "\n";
	$logo_id = (int) get_option( 'site_logo' );
	if ( $logo_id && ( $src = wp_get_attachment_image_url( $logo_id, 'full' ) ) ) {
		echo '<meta property="og:image" content="' . esc_url( $src ) . '">' . "\n";
	}
}, 5 );
