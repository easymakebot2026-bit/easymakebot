<?php
/**
 * Phase 2 — SEO baseline (The SEO Framework). Idempotent.
 *   docker compose run --rm wpcli wp eval-file /scripts/seo-setup.php
 *
 * NOTE: sets blog_public = 1 (allow indexing). On a staging host you may want
 * that back to 0 — see docs/50-theme-and-i18n.md.
 */

if ( ! defined( 'WP_CLI' ) ) { exit; }

/* Allow search engines. */
update_option( 'blog_public', 1 );

/* Short tagline — used in schema / OG fallbacks (NOT appended to <title>,
 * see title_rem_additions below). */
update_option( 'blogdescription', 'ساخت ربات تلگرام بدون کدنویسی' );

/* The SEO Framework global settings. */
$tsf = get_option( 'autodescription-site-settings', array() );
if ( is_array( $tsf ) ) {
	$tsf['knowledge_output'] = 1;
	$tsf['knowledge_type']   = 'organization';
	$tsf['knowledge_name']   = 'easymakebot';
	$tsf['knowledge_logo']   = 1;
	$tsf['sitemaps_output']  = 1;
	$tsf['sitemap_styles']   = 1;
	// Every real page sets its own complete <title> — don't let TSF append the
	// site name / tagline (that was producing doubled titles).
	$tsf['title_rem_additions'] = 1;   // non-homepage title additions
	$tsf['homepage_tagline']    = 0;   // don't append the tagline to the homepage title
	$tsf['homepage_title']      = '';  // fall back to the page's own _genesis_title
	$tsf['og_tags']          = 1;
	$tsf['twitter_tags']     = 1;
	$tsf['oembed_scripts']   = 1;
	$tsf['ping_google']      = 1;
	$tsf['ping_use_cron']    = 1;
	$tsf['author_noindex']   = 1;   // no thin author archives
	$tsf['date_noindex']     = 1;   // no thin date archives
	$tsf['site_noindex']     = 0;

	// Post-type-archive SEO for the tutorials archive (/tutorials/ + /en/tutorials/)
	// — otherwise TSF emits "Archives: Tutorials".
	if ( ! isset( $tsf['pta'] ) || ! is_array( $tsf['pta'] ) ) {
		$tsf['pta'] = array();
	}
	$tsf['pta']['tutorial'] = array_merge(
		$tsf['pta']['tutorial'] ?? array(),
		array(
			'doctitle'           => 'آموزش ساخت ربات تلگرام — easymakebot',
			'title_no_additions' => 1,
			'description'        => 'ویدیوها و راهنماهای گام‌به‌گام ساخت، تنظیم و رشد ربات تلگرام با easymakebot.',
		)
	);

	update_option( 'autodescription-site-settings', $tsf );
	WP_CLI::log( '  TSF settings updated (incl. tutorial archive)' );
}

/* Per-page title + meta description (FA + EN home, + blog). */
$meta = array(
	'home-en' => array(
		'title' => 'Build a Telegram bot in minutes — easymakebot',
		'desc'  => 'easymakebot is a no-code Telegram bot builder: paste your BotFather token, add commands, a shop, forced-join and broadcasts, and go live. 72-hour free trial.',
	),
	'home' => array(
		'title' => 'ساخت ربات تلگرام در چند دقیقه، بدون کدنویسی — easymakebot',
		'desc'  => 'با easymakebot ربات تلگرام بساز بدون یک خط کد: توکن BotFather را بده، دستور و فروشگاه و عضویت اجباری و پیام همگانی اضافه کن و زنده کن. ۷۲ ساعت آزمایش رایگان.',
	),
	'blog' => array(
		'title' => 'وبلاگ easymakebot — آموزش و نکته‌های ساخت ربات تلگرام',
		'desc'  => 'راهنماها، آموزش‌ها و نکته‌های ساخت و رشد ربات تلگرام با easymakebot.',
	),
	'blog-en' => array(
		'title' => 'easymakebot blog — Telegram bot how-tos and tips',
		'desc'  => 'Guides, tutorials and tips for building and growing a Telegram bot with easymakebot.',
	),
	'shop' => array(
		'title' => 'پلن‌های زنده‌ماندن ربات — easymakebot',
		'desc'  => 'پلن‌های ۱، ۳، ۶ و ۱۲ ماهه برای زنده نگه‌داشتن ربات تلگرام روی سرور easymakebot. پرداخت با زرین‌پال (تومان) داخل ایران و TON/USDT خارج از ایران.',
	),
);
foreach ( $meta as $slug => $m ) {
	$page = get_page_by_path( $slug );
	if ( ! $page ) { continue; }
	update_post_meta( $page->ID, '_genesis_title', $m['title'] );
	update_post_meta( $page->ID, '_genesis_description', $m['desc'] );
	update_post_meta( $page->ID, '_open_graph_title', $m['title'] );
	update_post_meta( $page->ID, '_open_graph_description', $m['desc'] );
	update_post_meta( $page->ID, '_twitter_title', $m['title'] );
	update_post_meta( $page->ID, '_twitter_description', $m['desc'] );
	WP_CLI::log( "  meta set: {$slug} (#{$page->ID})" );
}

/* Thin utility pages: keep them out of the index. (TSF already auto-noindexes
 * cart / checkout / my-account; /verify/ is our own page so set it here.) */
foreach ( array( 'verify', 'cart', 'checkout' ) as $slug ) {
	$page = get_page_by_path( $slug );
	if ( $page ) {
		update_post_meta( $page->ID, '_genesis_noindex', '1' );
		WP_CLI::log( "  noindex: {$slug} (#{$page->ID})" );
	}
}

flush_rewrite_rules();
WP_CLI::success( 'seo setup done — sitemap at /sitemap.xml' );
