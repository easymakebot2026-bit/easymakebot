<?php
/**
 * Plugin Name: easymakebot — TON / USDT payment (auto-verified)
 * Description: International (USD) checkout for the plan store. The buyer sends
 *              TON or USDT-on-TON to our wallet with the order id as the transfer
 *              comment; a background poller matches it on-chain via tonapi.io and
 *              completes the order (which then issues an activation code).
 *
 * Plan USD prices are read from product meta `_emb_usd_price` (set in
 * scripts/shop-setup.php). The store currency stays IRT — this gateway charges
 * its own USD-derived amount and records it on the order.
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

const EMB_TON_ID = 'emb_ton';

// let esc_url() keep ton:// wallet deep links intact
add_filter( 'kses_allowed_protocols', function ( $p ) {
	$p[] = 'ton';
	return $p;
} );

/* ─────────────────────────  helpers (poller + gateway share these)  ───────────────────────── */


function emb_ton_settings() {
	return get_option( 'woocommerce_' . EMB_TON_ID . '_settings', array() );
}

function emb_ton_wallet() {
	$s = emb_ton_settings();
	return isset( $s['wallet'] ) ? trim( $s['wallet'] ) : '';
}

/**
 * WooCommerce is single-currency and this store is set to 0-decimal Toman.
 * The EN flow's orders are priced in USD and must keep cents ($24.99, not $25),
 * so bump the price precision to 2 whenever we're clearly in that USD context:
 * our REST endpoints, the EN front page, an admin screen for an emb_ton order,
 * or while the poller completes one (the `emb_ton_dp2` global).
 */
$GLOBALS['emb_ton_dp2'] = false;

function emb_ton_usd_context() {
	if ( ! empty( $GLOBALS['emb_ton_dp2'] ) ) {
		return true;
	}
	if ( false !== strpos( (string) ( $_SERVER['REQUEST_URI'] ?? '' ), '/emb/v1/ton-' ) ) {
		return true;
	}
	if ( function_exists( 'emb_shop_is_usd' ) && emb_shop_is_usd() ) {
		return true;
	}
	if ( is_admin() ) {
		$oid = absint( $_GET['post'] ?? ( $_GET['id'] ?? 0 ) );
		if ( $oid && 'emb_ton' === get_post_meta( $oid, '_payment_method', true ) ) {
			return true;
		}
	}
	return false;
}

add_filter( 'wc_get_price_decimals', function ( $dp ) {
	return emb_ton_usd_context() ? 2 : $dp;
}, 99 );

/**
 * USD total for an order. World orders are already priced in USD (see the
 * currency swap in the theme's inc/shop.php), so the order total IS the USD
 * figure. Fall back to Σ(_emb_usd_price × qty) if an order somehow wasn't.
 */
function emb_ton_order_usd( $order ) {
	if ( 'USD' === $order->get_currency() ) {
		return round( (float) $order->get_total(), 2 );
	}
	$sum = 0.0;
	foreach ( $order->get_items() as $item ) {
		$p = $item->get_product();
		if ( ! $p ) {
			continue;
		}
		$sum += (float) $p->get_meta( '_emb_usd_price' ) * max( 1, (int) $item->get_quantity() );
	}
	return round( $sum, 2 );
}

/** Live TON price in USD, cached 5 min. 0 on total failure. */
function emb_ton_usd_rate() {
	$cached = get_transient( 'emb_ton_usd_rate' );
	if ( $cached ) {
		return (float) $cached;
	}
	$rate = 0.0;
	$r = wp_remote_get( 'https://tonapi.io/v2/rates?tokens=ton&currencies=usd', array( 'timeout' => 12 ) );
	if ( ! is_wp_error( $r ) ) {
		$j    = json_decode( wp_remote_retrieve_body( $r ), true );
		$rate = (float) ( $j['rates']['TON']['prices']['USD'] ?? 0 );
	}
	if ( $rate <= 0 ) {
		$r = wp_remote_get( 'https://api.coingecko.com/api/v3/simple/price?ids=the-open-network&vs_currencies=usd', array( 'timeout' => 12 ) );
		if ( ! is_wp_error( $r ) ) {
			$j    = json_decode( wp_remote_retrieve_body( $r ), true );
			$rate = (float) ( $j['the-open-network']['usd'] ?? 0 );
		}
	}
	if ( $rate > 0 ) {
		set_transient( 'emb_ton_usd_rate', $rate, 5 * MINUTE_IN_SECONDS );
	}
	return $rate;
}

/** Our wallet's raw (0:hex) address, resolved once via tonapi and cached. */
function emb_ton_raw_address() {
	$w = emb_ton_wallet();
	if ( '' === $w ) {
		return '';
	}
	$key = 'emb_ton_raw_' . md5( $w );
	$raw = get_transient( $key );
	if ( $raw ) {
		return $raw;
	}
	$r = wp_remote_get( 'https://tonapi.io/v2/accounts/' . rawurlencode( $w ), array( 'timeout' => 12 ) );
	if ( ! is_wp_error( $r ) ) {
		$j   = json_decode( wp_remote_retrieve_body( $r ), true );
		$raw = strtolower( (string) ( $j['address'] ?? '' ) );
	}
	if ( $raw ) {
		set_transient( $key, $raw, DAY_IN_SECONDS );
	}
	return $raw;
}

/**
 * Recent INCOMING transfers to our wallet, normalised.
 * @return array<int,array{hash:string,comment:string,ton_nano:int,usdt:float,utime:int}>
 */
function emb_ton_fetch_incoming() {
	/**
	 * Short-circuit the tonapi call (used by tests). Return an array of
	 * {hash, comment, ton_nano, usdt, utime} to pretend those came in.
	 */
	$pre = apply_filters( 'emb_ton_pre_fetch_incoming', null );
	if ( is_array( $pre ) ) {
		return $pre;
	}
	$w = emb_ton_wallet();
	if ( '' === $w ) {
		return array();
	}
	$raw     = emb_ton_raw_address();
	$s       = emb_ton_settings();
	$headers = array();
	if ( ! empty( $s['tonapi_key'] ) ) {
		$headers['Authorization'] = 'Bearer ' . trim( $s['tonapi_key'] );
	}
	$r = wp_remote_get(
		'https://tonapi.io/v2/accounts/' . rawurlencode( $w ) . '/events?limit=50',
		array( 'timeout' => 15, 'headers' => $headers )
	);
	if ( is_wp_error( $r ) ) {
		return array();
	}
	$j   = json_decode( wp_remote_retrieve_body( $r ), true );
	$out = array();
	foreach ( (array) ( $j['events'] ?? array() ) as $ev ) {
		$hash  = (string) ( $ev['event_id'] ?? '' );
		$utime = (int) ( $ev['timestamp'] ?? 0 );
		foreach ( (array) ( $ev['actions'] ?? array() ) as $a ) {
			if ( ( $a['status'] ?? 'ok' ) !== 'ok' ) {
				continue;
			}
			$type = $a['type'] ?? '';
			if ( 'TonTransfer' === $type ) {
				$t = $a['TonTransfer'] ?? array();
				if ( $raw && strtolower( (string) ( $t['recipient']['address'] ?? '' ) ) !== $raw ) {
					continue;
				}
				$out[] = array(
					'hash'     => $hash,
					'comment'  => trim( (string) ( $t['comment'] ?? '' ) ),
					'ton_nano' => (int) ( $t['amount'] ?? 0 ),
					'usdt'     => 0.0,
					'utime'    => $utime,
					'sender'   => (string) ( $t['sender']['address'] ?? '' ),
				);
			} elseif ( 'JettonTransfer' === $type ) {
				$t = $a['JettonTransfer'] ?? array();
				if ( $raw && strtolower( (string) ( $t['recipient']['address'] ?? '' ) ) !== $raw ) {
					continue;
				}
				$sym = strtoupper( (string) ( $t['jetton']['symbol'] ?? '' ) );
				if ( false === strpos( $sym, 'USD' ) ) {
					continue; // only USDT-style jettons
				}
				$dec = (int) ( $t['jetton']['decimals'] ?? 6 );
				$amt = (float) ( $t['amount'] ?? 0 ) / pow( 10, $dec );
				$out[] = array(
					'hash'     => $hash,
					'comment'  => trim( (string) ( $t['comment'] ?? '' ) ),
					'ton_nano' => 0,
					'usdt'     => $amt,
					'utime'    => $utime,
					'sender'   => (string) ( $t['sender']['address'] ?? '' ),
				);
			}
		}
	}
	return $out;
}

/** The pay box shown on thank-you / my-account / emails for an on-hold TON order. */
function emb_ton_render_box( $order_id, $plain = false ) {
	$order = wc_get_order( $order_id );
	if ( ! $order || $order->get_payment_method() !== EMB_TON_ID ) {
		return '';
	}
	$wallet  = emb_ton_wallet();
	$comment = (string) $order->get_meta( '_emb_ton_comment' );
	$usd     = (float) $order->get_meta( '_emb_ton_usd' );
	$nano    = (int) $order->get_meta( '_emb_ton_expected_nano' );
	$ton     = $nano > 0 ? $nano / 1e9 : 0;
	$paid    = $order->is_paid() || $order->get_meta( '_emb_ton_txid' );

	if ( $paid ) {
		$msg = 'Payment received — your order is complete.';
		return $plain ? $msg : '<div class="emb-ton-box is-paid"><p>✅ ' . esc_html( $msg ) . '</p></div>';
	}
	if ( '' === $wallet ) {
		return $plain ? '' : '<div class="emb-ton-box"><p>Crypto payment is not configured yet — please contact support.</p></div>';
	}

	$deeplink = 'ton://transfer/' . rawurlencode( $wallet ) . '?amount=' . $nano . '&text=' . rawurlencode( $comment );
	$tonfmt   = rtrim( rtrim( number_format( $ton, 4, '.', '' ), '0' ), '.' );

	if ( $plain ) {
		return "Send ONE of these to the wallet below, with the comment/memo EXACTLY as shown:\n"
			. "  • {$usd} USDT  (USDT on the TON network)\n"
			. "  • {$tonfmt} TON\n"
			. "Wallet: {$wallet}\n"
			. "Comment / memo: {$comment}\n"
			. "It confirms automatically within a few minutes.";
	}

	ob_start(); ?>
	<div class="emb-ton-box">
		<h3>Pay with TON / USDT</h3>
		<p>Send <strong>one</strong> of the following, and set the transfer <strong>comment / memo</strong> exactly — that is how we match your payment:</p>
		<ul class="emb-ton-amounts">
			<li><span class="emb-ton-amt"><?php echo esc_html( $usd ); ?> USDT</span> <span class="emb-ton-hint">(USDT on the TON network — 1:1 with USD)</span></li>
			<li><span class="emb-ton-amt"><?php echo esc_html( $tonfmt ); ?> TON</span> <span class="emb-ton-hint">(live rate)</span></li>
		</ul>
		<div class="emb-ton-kv"><span>Wallet</span><code><?php echo esc_html( $wallet ); ?></code></div>
		<div class="emb-ton-kv"><span>Comment / memo</span><code><?php echo esc_html( $comment ); ?></code></div>
		<?php
		$check_url = add_query_arg(
			array( 'emb_ton_check' => $order->get_id(), 'key' => $order->get_order_key() ),
			home_url( '/' )
		);
		?>
		<p class="emb-ton-actions">
			<a class="button" href="<?php echo esc_url( $deeplink, array( 'ton', 'https' ) ); ?>">Open in Tonkeeper</a>
			<a class="button emb-ton-check" href="<?php echo esc_url( $check_url ); ?>">I've paid — check now</a>
		</p>
		<p class="emb-ton-note">Confirms automatically within a few minutes. You can safely close this page — the code is emailed to you.</p>
	</div>
	<?php
	return ob_get_clean();
}

/* ─────────────────────────  matcher / poller  ───────────────────────── */

function emb_ton_try_match_orders( $only_order_id = 0 ) {
	$wallet = emb_ton_wallet();
	if ( '' === $wallet ) {
		return 0;
	}
	$args = array(
		'status'         => 'on-hold',
		'payment_method' => EMB_TON_ID,
		'limit'          => 50,
		'date_created'   => '>' . ( time() - 14 * DAY_IN_SECONDS ),
	);
	if ( $only_order_id ) {
		$args = array( 'status' => 'on-hold', 'payment_method' => EMB_TON_ID, 'include' => array( (int) $only_order_id ) );
	}
	$orders = wc_get_orders( $args );
	if ( ! $orders ) {
		return 0;
	}
	$txs = emb_ton_fetch_incoming();
	if ( ! $txs ) {
		return 0;
	}

	$s   = emb_ton_settings();
	$tol = 1 - max( 0.0, min( 20.0, (float) ( $s['tolerance'] ?? 1 ) ) ) / 100;
	$done = 0;

	foreach ( $orders as $order ) {
		if ( $order->get_meta( '_emb_ton_txid' ) ) {
			continue;
		}
		$comment  = (string) $order->get_meta( '_emb_ton_comment' );
		$exp_nano = (int) $order->get_meta( '_emb_ton_expected_nano' );
		$exp_usd  = (float) $order->get_meta( '_emb_ton_usd' );

		foreach ( $txs as $t ) {
			if ( $t['comment'] === '' || strcasecmp( $t['comment'], $comment ) !== 0 ) {
				continue;
			}
			$match = ( $t['ton_nano'] > 0 && $exp_nano > 0 && $t['ton_nano'] >= $exp_nano * $tol )
				|| ( $t['usdt'] > 0 && $exp_usd > 0 && $t['usdt'] >= $exp_usd * $tol );
			if ( ! $match ) {
				continue;
			}
			$order->update_meta_data( '_emb_ton_txid', $t['hash'] );
			if ( ! empty( $t['sender'] ) ) {
				$order->update_meta_data( '_emb_ton_sender', sanitize_text_field( $t['sender'] ) );
			}
			$paid_str = $t['usdt'] > 0 ? ( $t['usdt'] . ' USDT' ) : ( number_format( $t['ton_nano'] / 1e9, 4 ) . ' TON' );
			$order->add_order_note( sprintf(
				'Crypto payment matched — %s, tx %s (comment %s)%s.',
				$paid_str,
				$t['hash'],
				$comment,
				! empty( $t['sender'] ) ? ', from ' . $t['sender'] : ''
			) );
			$order->save();
			$GLOBALS['emb_ton_dp2'] = true;   // keep USD cents in the completion email
			$order->payment_complete( $t['hash'] );
			$GLOBALS['emb_ton_dp2'] = false;
			$done++;
			break;
		}
	}
	return $done;
}

// recurring poll via Action Scheduler (bundled with WooCommerce)
add_action( 'emb_ton_poll', function () {
	$n = emb_ton_try_match_orders();
	// stop polling when nothing is pending
	$pending = wc_get_orders( array( 'status' => 'on-hold', 'payment_method' => EMB_TON_ID, 'limit' => 1, 'return' => 'ids' ) );
	if ( empty( $pending ) && function_exists( 'as_unschedule_all_actions' ) ) {
		as_unschedule_all_actions( 'emb_ton_poll' );
	}
} );

function emb_ton_schedule_poller() {
	if ( function_exists( 'as_schedule_recurring_action' ) && function_exists( 'as_has_scheduled_action' )
		&& ! as_has_scheduled_action( 'emb_ton_poll' ) ) {
		as_schedule_recurring_action( time() + 60, 120, 'emb_ton_poll', array(), 'emb-ton' );
	}
}

// on-demand "check now"
add_action( 'template_redirect', function () {
	if ( empty( $_GET['emb_ton_check'] ) ) {
		return;
	}
	$oid   = (int) $_GET['emb_ton_check'];
	$order = wc_get_order( $oid );
	if ( $order && current_user_can( 'read' ) ) {
		emb_ton_try_match_orders( $oid );
	} elseif ( $order && isset( $_GET['key'] ) && hash_equals( $order->get_order_key(), sanitize_text_field( wp_unslash( $_GET['key'] ) ) ) ) {
		emb_ton_try_match_orders( $oid );
	}
	wp_safe_redirect( remove_query_arg( array( 'emb_ton_check', 'key' ) ) );
	exit;
} );

/* ─────────────────────────  the gateway class  ───────────────────────── */

add_action( 'plugins_loaded', function () {
	if ( ! class_exists( 'WC_Payment_Gateway' ) ) {
		return;
	}

	class EMB_Gateway_TON extends WC_Payment_Gateway {

		public function __construct() {
			$this->id                 = EMB_TON_ID;
			$this->method_title       = 'TON / USDT (international)';
			$this->method_description = 'Auto-verified TON / USDT-on-TON payments, priced in USD (product meta _emb_usd_price). Shown to non-Iran billing countries.';
			$this->has_fields         = false;
			$this->supports           = array( 'products' );
			$this->icon               = '';

			$this->init_form_fields();
			$this->init_settings();
			$this->enabled     = $this->get_option( 'enabled', 'yes' );
			$this->title       = $this->get_option( 'title', 'Pay with TON / USDT (crypto)' );
			$this->description = $this->get_option( 'description', 'Send TON or USDT on the TON network. Confirms automatically.' );

			add_action( 'woocommerce_update_options_payment_gateways_' . $this->id, array( $this, 'process_admin_options' ) );
			add_action( 'woocommerce_thankyou_' . $this->id, 'emb_ton_thankyou_box' );
			add_action( 'woocommerce_view_order', 'emb_ton_thankyou_box' );
			add_action( 'woocommerce_email_before_order_table', array( $this, 'email_box' ), 10, 3 );
		}

		public function init_form_fields() {
			$this->form_fields = array(
				'enabled'     => array(
					'title'   => 'Enable',
					'type'    => 'checkbox',
					'label'   => 'Enable TON / USDT payments',
					'default' => 'yes',
				),
				'title'       => array(
					'title'   => 'Title (shown at checkout)',
					'type'    => 'text',
					'default' => 'Pay with TON / USDT (crypto)',
				),
				'description' => array(
					'title'   => 'Description',
					'type'    => 'textarea',
					'default' => 'Send TON or USDT on the TON network to our wallet. Your bot activates automatically once the payment confirms (a few minutes).',
				),
				'wallet'      => array(
					'title'       => 'TON wallet address (receive)',
					'type'        => 'text',
					'description' => 'Your Tonkeeper receive address (UQ… / EQ…). USDT-on-TON goes here too.',
					'default'     => '',
				),
				'tonapi_key'  => array(
					'title'       => 'tonapi.io API key (optional)',
					'type'        => 'password',
					'description' => 'A free key from tonconsole.com raises the rate limit. Works without one.',
					'default'     => '',
				),
				'tolerance'   => array(
					'title'       => 'Under-payment tolerance (%)',
					'type'        => 'number',
					'description' => 'Accept a payment this much below the expected amount (fees / rate drift). 0–20.',
					'default'     => '1',
				),
			);
		}

		// Not selectable on the on-site checkout — the /en/ flow creates
		// emb_ton orders through the REST endpoint below.
		public function is_available() {
			return false;
		}

		public function process_payment( $order_id ) {
			return array( 'result' => 'failure' );
		}

		public function email_box( $order, $sent_to_admin, $plain ) {
			if ( $sent_to_admin || $order->get_payment_method() !== $this->id || ! $order->has_status( 'on-hold' ) ) {
				return;
			}
			$box = emb_ton_render_box( $order->get_id(), (bool) $plain );
			echo $plain ? "\n\n" . $box . "\n\n" : '<div style="margin:16px 0">' . wp_kses_post( $box ) . '</div>';
		}
	}

	add_filter( 'woocommerce_payment_gateways', function ( $gws ) {
		$gws[] = 'EMB_Gateway_TON';
		return $gws;
	} );
} );

function emb_ton_thankyou_box( $order_id ) {
	echo emb_ton_render_box( $order_id ); // phpcs:ignore WordPress.Security.EscapeOutput
}

/* ─────────────────────────  /en/ purchase flow (REST)  ─────────────────────────
 * The English site never touches the WC cart / checkout / order-received
 * templates (all fa-slug URLs). The #pricing grid posts here; we create a
 * USD order, return the pay box, and a status endpoint the panel polls.
 */
add_action( 'rest_api_init', function () {
	register_rest_route( 'emb/v1', '/ton-order', array(
		'methods'             => 'POST',
		'permission_callback' => '__return_true',
		'callback'            => 'emb_ton_rest_create_order',
	) );
	register_rest_route( 'emb/v1', '/ton-status', array(
		'methods'             => 'GET',
		'permission_callback' => '__return_true',
		'callback'            => 'emb_ton_rest_status',
	) );
} );

function emb_ton_rl_ok( $bucket, $max, $secs ) {
	$ip  = preg_replace( '/[^0-9a-f:.]/i', '', (string) ( $_SERVER['REMOTE_ADDR'] ?? '' ) );
	$k   = "emb_ton_rl_{$bucket}_" . md5( $ip );
	$hit = (int) get_transient( $k );
	if ( $hit >= $max ) {
		return false;
	}
	set_transient( $k, $hit + 1, $secs );
	return true;
}

function emb_ton_rest_create_order( WP_REST_Request $req ) {
	if ( ! emb_ton_rl_ok( 'order', 12, 10 * MINUTE_IN_SECONDS ) ) {
		return new WP_REST_Response( array( 'ok' => false, 'error' => 'rate_limited' ), 429 );
	}
	// Only a logged-in, verified account may buy (anti-abuse). The /en/ panel
	// runs the email-code sign-in first (emb/v1/auth-*), see emb-accounts.php.
	if ( ! is_user_logged_in() || ( function_exists( 'emb_is_verified' ) && ! emb_is_verified() ) ) {
		return new WP_REST_Response( array( 'ok' => false, 'error' => 'login_required' ), 200 );
	}
	if ( '' === emb_ton_wallet() ) {
		return new WP_REST_Response( array( 'ok' => false, 'error' => 'not_configured' ), 200 );
	}
	$pid   = absint( $req->get_param( 'product_id' ) );
	$user  = wp_get_current_user();
	$email = sanitize_email( $user->user_email );  // the verified account's email
	$product = $pid ? wc_get_product( $pid ) : null;
	$months  = $product ? (int) $product->get_meta( '_emb_plan_months' ) : 0;
	$usd     = $product ? (float) $product->get_meta( '_emb_usd_price' ) : 0;

	if ( ! $product || $months < 1 || $usd <= 0 ) {
		return new WP_REST_Response( array( 'ok' => false, 'error' => 'bad_product' ), 200 );
	}
	if ( ! is_email( $email ) ) {
		return new WP_REST_Response( array( 'ok' => false, 'error' => 'bad_email' ), 200 );
	}

	// price precision: emb_ton_usd_context() already returns true for this
	// /emb/v1/ton- request, so wc_get_price_decimals() is 2 here (the store is
	// otherwise 0-decimal Toman).
	$order = wc_create_order( array( 'status' => 'pending', 'customer_id' => $user->ID ) );
	$order->add_product( $product, 1, array( 'subtotal' => $usd, 'total' => $usd ) );
	$order->set_currency( 'USD' );
	$order->set_billing_email( $email );
	$order->set_payment_method( 'emb_ton' );
	$order->set_payment_method_title( 'TON / USDT' );
	$order->set_created_via( 'emb-en' );
	$order->calculate_totals( false );
	$order->set_total( $usd );

	$rate = emb_ton_usd_rate();
	$nano = $rate > 0 ? (int) round( ( $usd / $rate ) * 1e9 ) : 0;
	$order->update_meta_data( '_emb_ton_usd', $usd );
	$order->update_meta_data( '_emb_ton_rate', $rate );
	$order->update_meta_data( '_emb_ton_expected_nano', $nano );
	$order->update_meta_data( '_emb_ton_comment', 'EMB-' . $order->get_id() );
	// buyer origin (forensic — abuse handling). CF headers when Cloudflare is in front.
	if ( function_exists( 'emb_request_ip' ) ) {
		$order->update_meta_data( '_emb_buyer_ip', emb_request_ip() );
		$order->update_meta_data( '_emb_buyer_country', emb_request_country() );
	}
	$order->update_status( 'on-hold', 'Awaiting TON / USDT payment (EN flow).' );
	$order->save();

	emb_ton_schedule_poller();

	return new WP_REST_Response( array(
		'ok'       => true,
		'order_id' => $order->get_id(),
		'key'      => $order->get_order_key(),
		'pay_html' => emb_ton_render_box( $order->get_id() ),
	), 200 );
}

function emb_ton_rest_status( WP_REST_Request $req ) {
	$oid   = absint( $req->get_param( 'order_id' ) );
	$key   = sanitize_text_field( (string) $req->get_param( 'key' ) );
	$order = $oid ? wc_get_order( $oid ) : null;
	if ( ! $order || ! hash_equals( $order->get_order_key(), $key ) ) {
		return new WP_REST_Response( array( 'ok' => false, 'error' => 'not_found' ), 200 );
	}
	// opportunistic on-demand match
	if ( $order->has_status( 'on-hold' ) ) {
		emb_ton_try_match_orders( $oid );
		$order = wc_get_order( $oid );
	}
	$paid  = $order->is_paid() || (bool) $order->get_meta( '_emb_ton_txid' );
	$codes = array();
	if ( $paid ) {
		$meta = $order->get_meta( '_emb_activation_codes' );
		$codes = is_array( $meta ) ? $meta : array();
	}
	return new WP_REST_Response( array(
		'ok'     => true,
		'status' => $paid ? 'paid' : 'pending',
		'email'  => $order->get_billing_email(),
		'codes'  => $codes,
	), 200 );
}
