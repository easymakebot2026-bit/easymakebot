<?php
/**
 * Phase 2 — Polylang bilingual setup (fa default + en), idempotent.
 *   docker compose run --rm wpcli wp eval-file /scripts/i18n-setup.php
 *
 * Polylang 3.8: language CRUD lives on PLL()->model->languages->add(),
 * options are an Options object (update_option('polylang',…) is blocked).
 */

if ( ! defined( 'WP_CLI' ) ) { exit; }
if ( ! function_exists( 'PLL' ) || ! PLL() ) { WP_CLI::error( 'Polylang is not active.' ); }

$pll = PLL();

/* ── 1. languages ─────────────────────────────────────────────────────── */
$languages = array(
	array( 'name' => 'فارسی',  'slug' => 'fa', 'locale' => 'fa_IR', 'rtl' => true,  'term_group' => 0, 'flag' => 'ir' ),
	array( 'name' => 'English', 'slug' => 'en', 'locale' => 'en_US', 'rtl' => false, 'term_group' => 1, 'flag' => 'us' ),
);
foreach ( $languages as $l ) {
	$existing = $pll->model->get_language( $l['slug'] );
	if ( $existing ) { WP_CLI::log( "  lang {$l['slug']}: exists" ); continue; }
	$r = $pll->model->languages->add( $l );
	WP_CLI::log( is_wp_error( $r ) ? "  lang {$l['slug']}: " . $r->get_error_message() : "  lang {$l['slug']}: added" );
}
if ( method_exists( $pll->model, 'clean_languages_cache' ) ) {
	$pll->model->clean_languages_cache();
}
wp_cache_flush();

/* ── 2. URL behaviour: /en/ prefix for English, none for default fa ───── */
$opts = array(
	'default_lang'  => 'fa',
	'force_lang'    => 1,
	'hide_default'  => 1,
	'redirect_lang' => 1,
	'browser'       => 0,
	'media_support' => 0,
	'post_types'    => array( 'post', 'page' ),
	'taxonomies'    => array( 'category', 'post_tag' ),
);
if ( isset( $pll->options ) && method_exists( $pll->options, 'merge' ) ) {
	$err = $pll->options->merge( $opts );
	if ( is_wp_error( $err ) && $err->has_errors() ) { WP_CLI::warning( 'options: ' . $err->get_error_message() ); }
	$pll->options->save();
	WP_CLI::log( '  options merged + saved' );
} else {
	WP_CLI::warning( 'options object unavailable — set them in wp-admin › Languages › Settings' );
}

/* ── 3. assign existing content to fa ─────────────────────────────────── */
foreach ( get_posts( array( 'post_type' => array( 'post', 'page' ), 'numberposts' => -1, 'post_status' => 'any' ) ) as $p ) {
	if ( ! $pll->model->post->get_language( $p->ID ) ) {
		$pll->model->post->set_language( $p->ID, 'fa' );
		WP_CLI::log( "  fa <- #{$p->ID} {$p->post_title}" );
	}
}
foreach ( get_terms( array( 'taxonomy' => array( 'category', 'post_tag' ), 'hide_empty' => false ) ) as $t ) {
	if ( ! $pll->model->term->get_language( $t->term_id ) ) {
		$pll->model->term->set_language( $t->term_id, 'fa' );
	}
}

/* ── 4. EN page translations ─────────────────────────────────────────── */
function emb_translate_page( $pll, $fa_id, $slug, $title, $content ) {
	if ( ! $fa_id ) { return; }
	if ( get_page_by_path( $slug ) ) { WP_CLI::log( "  en page '{$slug}': exists" ); return; }
	$en_id = wp_insert_post( array(
		'post_type' => 'page', 'post_status' => 'publish',
		'post_title' => $title, 'post_name' => $slug, 'post_content' => $content,
	) );
	if ( is_wp_error( $en_id ) || ! $en_id ) { WP_CLI::warning( "  en page '{$slug}': insert failed" ); return; }
	$pll->model->post->set_language( $en_id, 'en' );
	$pll->model->post->save_translations( (int) $fa_id, array( 'fa' => (int) $fa_id, 'en' => (int) $en_id ) );
	WP_CLI::log( "  en page '{$slug}': #{$en_id} linked to fa #{$fa_id}" );
}

emb_translate_page( $pll, (int) get_option( 'page_on_front' ), 'home-en', 'Home',
	'<!-- wp:pattern {"slug":"easymakebot/front-page-en"} /-->' );
emb_translate_page( $pll, (int) get_option( 'page_for_posts' ), 'blog-en', 'Blog', '' );

flush_rewrite_rules();
WP_CLI::success( 'i18n setup done' );
