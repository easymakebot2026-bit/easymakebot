<?php
/**
 * Phase 4 — WooCommerce + ZarinPal + the 4 plan products (Iran / IRT).
 * Idempotent.  docker compose run --rm wpcli wp eval-file /scripts/shop-setup.php
 *
 * The ZarinPal *merchant code* is NOT set here — add it yourself in
 *   wp-admin › WooCommerce › Settings › Payments › پرداخت امن زرین‌پال
 * and turn "sandbox" off when you go live.
 */

if ( ! defined( 'WP_CLI' ) ) { exit; }
if ( ! class_exists( 'WooCommerce' ) ) { WP_CLI::error( 'WooCommerce is not active.' ); }

/* ── 1. store basics ─────────────────────────────────────────────────── */
update_option( 'woocommerce_default_country', 'IR' );
update_option( 'woocommerce_currency', 'IRT' );                 // تومان (added by the ZarinPal plugin)
update_option( 'woocommerce_currency_pos', 'right_space' );
update_option( 'woocommerce_price_thousand_sep', '،' );
update_option( 'woocommerce_price_decimal_sep', '.' );
update_option( 'woocommerce_price_num_decimals', 0 );
update_option( 'woocommerce_allowed_countries', 'all' );        // international handled later
update_option( 'woocommerce_enable_guest_checkout', 'no' );     // need an account to tie the plan to a person
update_option( 'woocommerce_enable_signup_and_login_from_checkout', 'yes' );
update_option( 'woocommerce_enable_myaccount_registration', 'yes' );
update_option( 'woocommerce_registration_generate_username', 'yes' );
update_option( 'woocommerce_registration_generate_password', 'yes' );
update_option( 'woocommerce_calc_taxes', 'no' );
update_option( 'woocommerce_enable_reviews', 'no' );
update_option( 'woocommerce_manage_stock', 'no' );
update_option( 'woocommerce_cart_redirect_after_add', 'yes' );  // plan → straight toward checkout
// no physical goods
update_option( 'woocommerce_ship_to_countries', 'disabled' );
update_option( 'woocommerce_shipping_cost_requires_address', 'no' );

if ( class_exists( 'WC_Install' ) ) {
	WC_Install::create_pages();
}

/* ── 2. ZarinPal gateway defaults (no credentials) ───────────────────── */
$z = get_option( 'woocommerce_WC_ZPal_settings', array() );
$z = is_array( $z ) ? $z : array();
$z['enabled']     = 'yes';
$z['sandbox']     = isset( $z['sandbox'] ) && 'no' === $z['sandbox'] ? 'no' : ( $z['sandbox'] ?? 'yes' );
$z['title']       = 'پرداخت آنلاین (زرین‌پال)';
$z['description'] = 'پرداخت امن با همهٔ کارت‌های عضو شتاب از طریق درگاه زرین‌پال.';
if ( empty( $z['merchantcode'] ) ) {
	WP_CLI::warning( 'ZarinPal merchant code is empty — set it in wp-admin › WooCommerce › Payments.' );
}
update_option( 'woocommerce_WC_ZPal_settings', $z );

/* ── 2b. TON / USDT gateway (international, USD pricing) ──────────────── */
$ton = get_option( 'woocommerce_emb_ton_settings', array() );
$ton = is_array( $ton ) ? $ton : array();
$ton['enabled']     = $ton['enabled'] ?? 'yes';
$ton['title']       = $ton['title'] ?? 'Pay with TON / USDT (crypto)';
$ton['description'] = $ton['description'] ?? 'Send TON or USDT on the TON network to our wallet. Your bot activates automatically once the payment confirms (a few minutes).';
$ton['tolerance']   = $ton['tolerance'] ?? '1';
if ( empty( $ton['wallet'] ) ) {
	// Prefill the receive address supplied by the operator; change it in
	// wp-admin › WooCommerce › Payments › "TON / USDT (international)".
	$ton['wallet'] = 'UQCsXmq18JNw6yffYmxJ1PYI--NhWeIMGk5MJLLIB3sa05pi';
}
update_option( 'woocommerce_emb_ton_settings', $ton );

/* ── 3. plan category + products ─────────────────────────────────────── */
$cat = term_exists( 'plans', 'product_cat' );
if ( ! $cat ) {
	$cat = wp_insert_term( 'پلن‌ها', 'product_cat', array( 'slug' => 'plans' ) );
}
$cat_id = is_array( $cat ) ? (int) $cat['term_id'] : (int) $cat;

$plans = array(
	array( 'sku' => 'emb-plan-1m',  'name' => '۱ ماهه',  'en' => '1 month',   'price' => 590000,  'usd' => 5.99,  'months' => 1,  'note' => '۳۰ روز زنده‌ماندن یک ربات روی تلگرام.' ),
	array( 'sku' => 'emb-plan-3m',  'name' => '۳ ماهه',  'en' => '3 months',  'price' => 1590000, 'usd' => 15.99, 'months' => 3,  'note' => '۹۰ روز زنده‌ماندن یک ربات — حدود ۱۰٪ ارزان‌تر از خرید ماهانه.' ),
	array( 'sku' => 'emb-plan-6m',  'name' => '۶ ماهه',  'en' => '6 months',  'price' => 2990000, 'usd' => 28.99, 'months' => 6,  'note' => '۱۸۰ روز زنده‌ماندن یک ربات — حدود ۱۵٪ ارزان‌تر از خرید ماهانه.' ),
	array( 'sku' => 'emb-plan-12m', 'name' => '۱۲ ماهه', 'en' => '12 months', 'price' => 4990000, 'usd' => 49.99, 'months' => 12, 'note' => 'یک سال کامل زنده‌ماندن یک ربات — حدود ۳۰٪ ارزان‌تر، معادل ماهی حدود ۴۱۵ هزار تومان.' ),
);

foreach ( $plans as $p ) {
	$existing = wc_get_product_id_by_sku( $p['sku'] );
	$product  = $existing ? wc_get_product( $existing ) : new WC_Product_Simple();
	$product->set_name( $p['name'] );
	$product->set_sku( $p['sku'] );
	$product->set_status( 'publish' );
	$product->set_catalog_visibility( 'visible' );
	$product->set_regular_price( (string) $p['price'] );
	$product->set_price( (string) $p['price'] );
	$product->set_virtual( true );
	$product->set_sold_individually( true );          // one plan per checkout
	$product->set_reviews_allowed( false );
	$product->set_short_description( $p['note'] );
	$product->set_description(
		'<p>' . esc_html( $p['note'] ) . '</p>' .
		'<p>پس از پرداخت، سفارش شما ثبت می‌شود و پلن روی ربات شما فعال می‌گردد. ' .
		'اگر هنوز ربات نساخته‌اید، اول در تلگرام به <strong>@easymakebot</strong> پیام دهید.</p>'
	);
	$product->set_category_ids( array( $cat_id ) );
	$product->update_meta_data( '_emb_plan_months', (int) $p['months'] );
	$product->update_meta_data( '_emb_usd_price', (float) $p['usd'] );  // shown on the /en/ side (currency swap)
	$product->update_meta_data( '_emb_en_name', $p['en'] );             // English name on the /en/ side
	$pid = $product->save();
	if ( function_exists( 'pll_set_post_language' ) ) { pll_set_post_language( $pid, 'fa' ); }
	WP_CLI::log( "  product {$p['sku']} → #{$pid} ({$p['price']} تومان / \${$p['usd']})" );
}

/* ── 4. the plan grid lives in the home page's #pricing section
 *       ([emb_plans] in patterns/pricing.php + front-page-en.php). Polylang
 *       free can't route /en/{page}/ for regular pages, but /en/ (the front
 *       page) works — so that's where the cards are. No separate shop page. ── */

/* ── 5. make /shop/ show the plans, newest-priced first ──────────────── */
update_option( 'woocommerce_shop_page_display', '' );
update_option( 'woocommerce_default_catalog_orderby', 'price' );

if ( function_exists( 'wc_delete_product_transients' ) ) { wc_delete_product_transients(); }
flush_rewrite_rules();
WP_CLI::success( 'shop setup done — /shop/  ·  set the ZarinPal merchant code in wp-admin' );
