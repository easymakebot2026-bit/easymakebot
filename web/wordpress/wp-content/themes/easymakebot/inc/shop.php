<?php
/**
 * WooCommerce integration — the easymakebot "plans" store.
 *
 * Two flows, one product set:
 *   • fa site (/)    → normal WooCommerce: Toman prices, cart, ZarinPal checkout.
 *   • en site (/en/) → a self-contained TON / USDT flow driven from the home
 *     page's #pricing grid (no WC cart / checkout templates involved — those
 *     are all fa-slug URLs Polylang free can't localise). Each plan card opens
 *     an inline panel → REST `emb/v1/ton-order` creates a USD order and returns
 *     the pay box. See wp-content/mu-plugins/emb-ton-gateway.php.
 *
 * @package easymakebot
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/** 'USD' | 'IRT' for this request — /en/… ⇒ USD, else the Polylang language. */
function emb_shop_ccy() {
	$path = (string) wp_parse_url( $_SERVER['REQUEST_URI'] ?? '/', PHP_URL_PATH );
	if ( preg_match( '#^/en(/|$)#', $path ) ) {
		return 'USD';
	}
	if ( function_exists( 'pll_current_language' ) && did_action( 'wp' ) ) {
		return ( 'en' === pll_current_language() ) ? 'USD' : 'IRT';
	}
	return isset( $_COOKIE['emb_ccy'] ) && 'USD' === $_COOKIE['emb_ccy'] ? 'USD' : 'IRT';
}
function emb_shop_is_usd() {
	return 'USD' === emb_shop_ccy();
}

/* ─────────────────────────  theme support + store chrome  ───────────────────────── */

add_action( 'after_setup_theme', function () {
	add_theme_support( 'woocommerce', array(
		'thumbnail_image_width' => 480,
		'single_image_width'    => 800,
		'product_grid'          => array( 'default_columns' => 4, 'min_columns' => 2, 'max_columns' => 4 ),
	) );
	add_theme_support( 'wc-product-gallery-zoom' );
	add_theme_support( 'wc-product-gallery-lightbox' );
	add_theme_support( 'wc-product-gallery-slider' );
} );

add_action( 'init', function () {
	remove_action( 'woocommerce_before_main_content', 'woocommerce_breadcrumb', 20 );
	remove_action( 'woocommerce_before_shop_loop', 'woocommerce_result_count', 20 );
	remove_action( 'woocommerce_before_shop_loop', 'woocommerce_catalog_ordering', 30 );
	remove_action( 'woocommerce_sidebar', 'woocommerce_get_sidebar', 10 );
	remove_action( 'woocommerce_after_single_product_summary', 'woocommerce_output_related_products', 20 );
	remove_action( 'woocommerce_after_single_product_summary', 'woocommerce_upsell_display', 15 );
} );

/* ── Plans are virtual — the fa checkout only needs an email + a name ──── */
add_filter( 'woocommerce_checkout_fields', function ( $fields ) {
	if ( ! WC()->cart || WC()->cart->needs_shipping() ) {
		return $fields;
	}
	foreach ( array_keys( $fields['billing'] ?? array() ) as $key ) {
		if ( ! in_array( $key, array( 'billing_email', 'billing_first_name', 'billing_last_name' ), true ) ) {
			unset( $fields['billing'][ $key ] );
		}
	}
	foreach ( array( 'billing_first_name', 'billing_last_name' ) as $k ) {
		if ( isset( $fields['billing'][ $k ] ) ) {
			$fields['billing'][ $k ]['required'] = false;
		}
	}
	if ( isset( $fields['billing']['billing_first_name'] ) ) {
		$fields['billing']['billing_first_name']['class'] = array( 'form-row-first' );
	}
	if ( isset( $fields['billing']['billing_last_name'] ) ) {
		$fields['billing']['billing_last_name']['class'] = array( 'form-row-last' );
	}
	if ( isset( $fields['billing']['billing_email'] ) ) {
		$fields['billing']['billing_email']['class']    = array( 'form-row-wide' );
		$fields['billing']['billing_email']['priority'] = 1;
	}
	unset( $fields['shipping'], $fields['order']['order_comments'] );
	return $fields;
}, 20 );
add_filter( 'woocommerce_enable_order_notes_field', '__return_false' );

// The fa store only offers ZarinPal; the TON gateway is used by the /en/ REST
// flow, not the on-site checkout, so hide it from the classic checkout page.
add_filter( 'woocommerce_available_payment_gateways', function ( $gws ) {
	if ( ! is_admin() ) {
		unset( $gws['emb_ton'] );
	}
	return $gws;
} );

/* ─────────────────────────  shortcodes  ───────────────────────── */

/**
 * [emb_plans] — the plan grid.
 *   fa: normal WooCommerce cards (Toman price, ?add-to-cart link).
 *   en: USD price from `_emb_usd_price`, English name from `_emb_en_name`,
 *       a button that opens the inline TON panel (app.js).
 */
add_shortcode( 'emb_plans', function () {
	$q = new WP_Query( array(
		'post_type'      => 'product',
		'posts_per_page' => 12,
		'post_status'    => 'publish',
		'orderby'        => 'meta_value_num',
		'meta_key'       => '_emb_plan_months',
		'order'          => 'ASC',
		'no_found_rows'  => true,
	) );
	if ( ! $q->have_posts() ) {
		wp_reset_postdata();
		return '';
	}
	$usd = emb_shop_is_usd();
	// fa: only a logged-in, verified account may add to cart (see emb-accounts.php).
	$can_buy = ! function_exists( 'emb_is_verified' ) || emb_is_verified();
	$account = function_exists( 'wc_get_page_permalink' ) ? wc_get_page_permalink( 'myaccount' ) : home_url( '/my-account/' );
	ob_start();
	echo '<ul class="products emb-plan-products columns-4' . ( $usd ? ' is-usd' : '' ) . '">';
	while ( $q->have_posts() ) {
		$q->the_post();
		$product = wc_get_product( get_the_ID() );
		if ( ! $product ) {
			continue;
		}
		if ( $usd ) {
			$price   = (float) $product->get_meta( '_emb_usd_price' );
			$name    = $product->get_meta( '_emb_en_name' ) ?: $product->get_name();
			$months  = (int) $product->get_meta( '_emb_plan_months' );
			printf(
				'<li class="product"><h2 class="woocommerce-loop-product__title">%s</h2>'
				. '<span class="price"><span class="woocommerce-Price-amount amount">$%s</span>'
				. '<span class="emb-price-sub">%s</span></span>'
				. '<button type="button" class="button emb-buy" data-emb-buy="%d" data-emb-usd="%s" data-emb-name="%s">%s</button></li>',
				esc_html( $name ),
				esc_html( number_format( $price, 2 ) ),
				esc_html( $months <= 1 ? 'one bot · 30 days' : "one bot · {$months} months" ),
				(int) $product->get_id(),
				esc_attr( number_format( $price, 2 ) ),
				esc_attr( $name ),
				esc_html__( 'Choose', 'easymakebot' )
			);
		} else {
			$cta = $can_buy
				? sprintf(
					'<a href="%s" data-quantity="1" class="button product_type_simple add_to_cart_button ajax_add_to_cart" data-product_id="%d" rel="nofollow">%s</a>',
					esc_url( $product->add_to_cart_url() ),
					(int) $product->get_id(),
					esc_html( 'افزودن به سبد خرید' )
				)
				: sprintf(
					'<a href="%s" class="button emb-plan-login">%s</a>',
					esc_url( $account ),
					esc_html( is_user_logged_in() ? 'تأیید حساب برای خرید' : 'برای خرید وارد شوید' )
				);
			printf(
				'<li class="product"><a class="woocommerce-loop-product__link" href="%s">'
				. '<h2 class="woocommerce-loop-product__title">%s</h2>'
				. '<span class="price">%s</span></a>%s</li>',
				esc_url( get_permalink() ),
				esc_html( $product->get_name() ),
				wp_kses_post( $product->get_price_html() ),
				$cta // phpcs:ignore WordPress.Security.EscapeOutput -- built with esc_* above
			);
		}
	}
	echo '</ul>';
	if ( $usd ) {
		// the panel the "Choose" buttons open. app.js shows the sign-in step
		// (email → code) only when the visitor isn't a verified account yet.
		echo '<div class="emb-buy-panel" id="emb-buy-panel" hidden>'
			. '<button type="button" class="emb-buy-panel__x" aria-label="Close">✕</button>'
			. '<h3 class="emb-buy-panel__title">You picked <span data-emb-slot="name"></span> — <span data-emb-slot="usd"></span></h3>'

			. '<div class="emb-buy-panel__auth" data-emb-step="email" hidden>'
			. '<p>First, verify your email. No password — we send a one-time code.</p>'
			. '<label class="emb-buy-panel__field"><span>Email</span>'
			. '<input type="email" inputmode="email" autocomplete="email" data-emb-slot="email" placeholder="you@example.com"></label>'
			. '<label class="emb-buy-panel__tos"><input type="checkbox" data-emb-slot="tos"> I agree to the '
			. '<a href="' . esc_url( function_exists( 'emb_terms_url' ) ? emb_terms_url() : home_url( '/terms/' ) ) . '" target="_blank" rel="noopener">Terms of Service</a>.</label>'
			. '<button type="button" class="button emb-buy-panel__send">Email me a code</button>'
			. '</div>'

			. '<div class="emb-buy-panel__auth" data-emb-step="code" hidden>'
			. '<p>Enter the 6-digit code we emailed you.</p>'
			. '<label class="emb-buy-panel__field"><span>Code</span>'
			. '<input type="text" inputmode="numeric" autocomplete="one-time-code" maxlength="6" data-emb-slot="code" placeholder="------"></label>'
			. '<button type="button" class="button emb-buy-panel__verify">Verify &amp; continue</button>'
			. '<p class="emb-buy-panel__mini"><a href="#" data-emb-slot="restart">Use a different email</a></p>'
			. '</div>'

			. '<div class="emb-buy-panel__pay" data-emb-step="pay" hidden>'
			. '<p>The activation code is emailed to your account after the payment confirms on-chain.</p>'
			. '<button type="button" class="button emb-buy-panel__go">Get payment details</button>'
			. '</div>'

			. '<p class="emb-buy-panel__err" role="alert" hidden></p>'
			. '<div class="emb-buy-panel__result" hidden></div>'
			. '</div>';
	}
	wp_reset_postdata();
	return ob_get_clean();
} );

add_shortcode( 'emb_shop_intro', function () {
	if ( emb_shop_is_usd() ) {
		return '<div class="emb-section__intro emb-shop-intro">'
			. '<p class="emb-kicker">Plans</p><h1>Keep your bot live</h1>'
			. '<p>Pick a length. Each plan keeps one bot running on Telegram. Renew anytime.</p>'
			. '<p class="emb-shop-intro__note">Prices are in <strong>USD</strong>. You pay in <strong>TON</strong> or '
			. '<strong>USDT on the TON network</strong> — it confirms automatically on-chain within a few minutes.</p>'
			. '</div>';
	}
	return '<div class="emb-section__intro emb-shop-intro">'
		. '<p class="emb-kicker">پلن‌ها</p><h1>ربات‌ات را زنده نگه دار</h1>'
		. '<p>یک بازهٔ زمانی انتخاب کن. هر پلن، یک ربات را روی تلگرام فعال نگه می‌دارد. هر وقت خواستی تمدید کن.</p>'
		. '</div>';
} );

/* Activation codes / "open the bot" are rendered by
 * wp-content/mu-plugins/emb-activation-codes.php. */
