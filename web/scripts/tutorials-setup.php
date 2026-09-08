<?php
/**
 * Phase 3 — flush rewrites for the `tutorial` CPT and seed two sample
 * tutorials (fa + en) so /tutorials/ isn't empty on first run. Idempotent.
 *   docker compose run --rm wpcli wp eval-file /scripts/tutorials-setup.php
 */

if ( ! defined( 'WP_CLI' ) ) { exit; }
if ( ! post_type_exists( 'tutorial' ) ) { WP_CLI::error( 'tutorial CPT not registered — is the theme active?' ); }

flush_rewrite_rules();

$pll = function_exists( 'PLL' ) ? PLL() : null;

/** Create a tutorial in one language if a post with that slug doesn't exist. */
function emb_seed_tutorial( $pll, $slug, $lang, $title, $excerpt, $body, $video ) {
	if ( get_page_by_path( $slug, OBJECT, 'tutorial' ) ) {
		WP_CLI::log( "  tutorial '{$slug}': exists" );
		return get_page_by_path( $slug, OBJECT, 'tutorial' )->ID;
	}
	$id = wp_insert_post( array(
		'post_type'    => 'tutorial',
		'post_status'  => 'publish',
		'post_title'   => $title,
		'post_name'    => $slug,
		'post_excerpt' => $excerpt,
		'post_content' => $body,
	) );
	if ( is_wp_error( $id ) || ! $id ) { WP_CLI::warning( "  tutorial '{$slug}': insert failed" ); return 0; }
	if ( $video ) { update_post_meta( $id, '_emb_video_url', $video ); }
	if ( $pll ) { $pll->model->post->set_language( $id, $lang ); }
	WP_CLI::log( "  tutorial '{$slug}': #{$id} ({$lang})" );
	return $id;
}

$fa1 = emb_seed_tutorial( $pll, 'first-bot-in-5-minutes', 'fa',
	'اولین ربات‌ات را در ۵ دقیقه بساز',
	'از صفر: توکن گرفتن از BotFather، ساخت ربات و زدن اولین دستور.',
	'<!-- wp:paragraph --><p>در این آموزش قدم‌به‌قدم می‌بینی چطور از <code>@BotFather</code> توکن بگیری، در easymakebot یک ربات جدید بسازی و اولین دستور <code>/start</code> را تعریف کنی.</p><!-- /wp:paragraph -->' .
	'<!-- wp:heading {"level":2} --><h2 class="wp-block-heading">مرحله‌ها</h2><!-- /wp:heading -->' .
	'<!-- wp:list {"ordered":true} --><ol><li>به <code>@BotFather</code> پیام بده و <code>/newbot</code> بزن.</li><li>توکن را کپی کن.</li><li>در easymakebot «ربات جدید» را بزن و توکن را بفرست.</li><li>با «تعریف دستور» دستور <code>/start</code> را بساز.</li></ol><!-- /wp:list -->',
	'' );

$fa2 = emb_seed_tutorial( $pll, 'connect-a-shop', 'fa',
	'وصل کردن فروشگاه و درگاه پرداخت',
	'محصول بساز، زرین‌پال را وصل کن و اولین سفارش را بگیر.',
	'<!-- wp:paragraph --><p>ابزار «فروشگاه» را باز کن، یک محصول دیجیتال یا دسترسی بساز، شمارهٔ کارت یا مرچنت زرین‌پال را وارد کن و لینک خرید را برای کاربرها بفرست.</p><!-- /wp:paragraph -->',
	'' );

if ( $pll ) {
	$en1 = emb_seed_tutorial( $pll, 'first-bot-in-5-minutes-en', 'en',
		'Build your first bot in 5 minutes',
		'From zero: get a BotFather token, create the bot, add your first command.',
		'<!-- wp:paragraph --><p>This step-by-step tutorial shows how to get a token from <code>@BotFather</code>, create a new bot in easymakebot and define your first <code>/start</code> command.</p><!-- /wp:paragraph -->',
		'' );
	if ( $fa1 && $en1 ) {
		$pll->model->post->save_translations( $fa1, array( 'fa' => (int) $fa1, 'en' => (int) $en1 ) );
	}

	$en2 = emb_seed_tutorial( $pll, 'connect-a-shop-en', 'en',
		'Connect a shop and a payment gateway',
		'Create a product, connect Zarinpal, and take your first order.',
		'<!-- wp:paragraph --><p>Open the "Shop" tool, create a digital or access product, enter a card number or your Zarinpal merchant ID, and send the buy link to your users.</p><!-- /wp:paragraph -->',
		'' );
	if ( $fa2 && $en2 ) {
		$pll->model->post->save_translations( $fa2, array( 'fa' => (int) $fa2, 'en' => (int) $en2 ) );
	}
}

flush_rewrite_rules();
WP_CLI::success( 'tutorials setup done — /tutorials/' );
