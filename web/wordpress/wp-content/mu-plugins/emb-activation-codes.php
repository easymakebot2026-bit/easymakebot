<?php
/**
 * Plugin Name: easymakebot — activation codes
 * Description: Turns a paid plan order into one-time activation codes the buyer
 *              redeems inside the @easymakebot Telegram bot (which then sets that
 *              specific bot's live_until). Bridges the two separate systems.
 *
 * REST:
 *   POST /wp-json/emb/v1/redeem   {code, bot_id, telegram_id}   header X-EMB-Key
 *   GET  /wp-json/emb/v1/check?code=EMB-XXXX-XXXX                header X-EMB-Key
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

const EMB_ACTCODES_DB_VERSION = '2';
const EMB_ACTCODES_ALPHABET   = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'; // no I O 0 1

function emb_actcodes_table() {
	global $wpdb;
	return $wpdb->prefix . 'emb_activation_codes';
}

function emb_actcodes_api_key() {
	$k = getenv( 'EMB_ACTIVATION_KEY' );
	if ( ! $k && defined( 'EMB_ACTIVATION_KEY' ) ) {
		$k = EMB_ACTIVATION_KEY;
	}
	return is_string( $k ) ? trim( $k ) : '';
}

/* ── schema ─────────────────────────────────────────────────────────── */
add_action( 'init', function () {
	if ( get_option( 'emb_actcodes_db_version' ) === EMB_ACTCODES_DB_VERSION ) {
		return;
	}
	global $wpdb;
	require_once ABSPATH . 'wp-admin/includes/upgrade.php';
	$table   = emb_actcodes_table();
	$collate = $wpdb->get_charset_collate();
	dbDelta( "CREATE TABLE {$table} (
		id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
		code VARCHAR(24) NOT NULL,
		order_id BIGINT UNSIGNED NOT NULL DEFAULT 0,
		order_item_id BIGINT UNSIGNED NOT NULL DEFAULT 0,
		product_id BIGINT UNSIGNED NOT NULL DEFAULT 0,
		sku VARCHAR(64) NOT NULL DEFAULT '',
		months SMALLINT UNSIGNED NOT NULL DEFAULT 0,
		days INT UNSIGNED NOT NULL DEFAULT 0,
		status VARCHAR(16) NOT NULL DEFAULT 'pending',
		redeemed_bot_id VARCHAR(64) NOT NULL DEFAULT '',
		redeemed_by_tg BIGINT NOT NULL DEFAULT 0,
		redeemed_by_username VARCHAR(64) NOT NULL DEFAULT '',
		redeemed_by_name VARCHAR(128) NOT NULL DEFAULT '',
		redeemed_phone VARCHAR(24) NOT NULL DEFAULT '',
		redeemed_at DATETIME NULL,
		created_at DATETIME NOT NULL,
		PRIMARY KEY  (id),
		UNIQUE KEY code (code),
		KEY order_id (order_id),
		KEY status (status)
	) {$collate};" );
	update_option( 'emb_actcodes_db_version', EMB_ACTCODES_DB_VERSION );
} );

/* ── helpers ────────────────────────────────────────────────────────── */
function emb_actcodes_generate_code() {
	global $wpdb;
	$table = emb_actcodes_table();
	do {
		$body = '';
		for ( $i = 0; $i < 8; $i++ ) {
			$body .= EMB_ACTCODES_ALPHABET[ random_int( 0, strlen( EMB_ACTCODES_ALPHABET ) - 1 ) ];
		}
		$code  = 'EMB-' . substr( $body, 0, 4 ) . '-' . substr( $body, 4, 4 );
		$taken = $wpdb->get_var( $wpdb->prepare( "SELECT id FROM {$table} WHERE code = %s", $code ) );
	} while ( $taken );
	return $code;
}

/** Plan length in whole months → days (30-day months, matching the bot). */
function emb_actcodes_days_for( $months ) {
	return max( 0, (int) $months ) * 30;
}

/* ── issue codes when an order is paid ──────────────────────────────── */
add_action( 'woocommerce_order_status_processing', 'emb_actcodes_issue_for_order' );
add_action( 'woocommerce_order_status_completed', 'emb_actcodes_issue_for_order' );

function emb_actcodes_issue_for_order( $order_id ) {
	global $wpdb;
	$table = emb_actcodes_table();
	$order = wc_get_order( $order_id );
	if ( ! $order ) {
		return;
	}
	// already issued?
	if ( $wpdb->get_var( $wpdb->prepare( "SELECT COUNT(*) FROM {$table} WHERE order_id = %d", $order_id ) ) > 0 ) {
		return;
	}

	$issued = array();
	foreach ( $order->get_items() as $item_id => $item ) {
		$product = $item->get_product();
		if ( ! $product ) {
			continue;
		}
		$months = (int) $product->get_meta( '_emb_plan_months' );
		if ( $months < 1 ) {
			continue; // not a plan line
		}
		$qty = max( 1, (int) $item->get_quantity() );
		for ( $n = 0; $n < $qty; $n++ ) {
			$code = emb_actcodes_generate_code();
			$wpdb->insert( $table, array(
				'code'          => $code,
				'order_id'      => $order_id,
				'order_item_id' => $item_id,
				'product_id'    => $product->get_id(),
				'sku'           => $product->get_sku(),
				'months'        => $months,
				'days'          => emb_actcodes_days_for( $months ),
				'status'        => 'pending',
				'created_at'    => current_time( 'mysql', true ),
			) );
			$issued[] = $code;
		}
	}
	if ( $issued ) {
		$order->update_meta_data( '_emb_activation_codes', $issued );
		$order->add_order_note( 'کد(های) فعال‌سازی صادر شد: ' . implode( ', ', $issued ) );
		$order->save();
	}
}

/* ── void pending codes if the order is reversed ────────────────────── */
foreach ( array( 'refunded', 'cancelled', 'failed' ) as $bad ) {
	add_action( "woocommerce_order_status_{$bad}", function ( $order_id ) {
		global $wpdb;
		$wpdb->query( $wpdb->prepare(
			"UPDATE " . emb_actcodes_table() . " SET status = 'void' WHERE order_id = %d AND status = 'pending'",
			$order_id
		) );
	} );
}

/* ── show codes to the buyer ────────────────────────────────────────── */
function emb_actcodes_for_order( $order_id ) {
	global $wpdb;
	return $wpdb->get_results( $wpdb->prepare(
		"SELECT code, months, days, status FROM " . emb_actcodes_table() . " WHERE order_id = %d ORDER BY id",
		$order_id
	) );
}

function emb_actcodes_render_block( $order_id, $plain = false ) {
	$rows = emb_actcodes_for_order( $order_id );
	if ( ! $rows ) {
		return '';
	}
	$lines = array();
	foreach ( $rows as $r ) {
		$state = 'pending' === $r->status ? '' : ( 'redeemed' === $r->status ? ' (استفاده‌شده)' : ' (باطل)' );
		$lines[] = $r->code . ' — ' . $r->months . ' ماهه' . $state;
	}
	if ( $plain ) {
		return "کد فعال‌سازی:\n" . implode( "\n", $lines ) .
			"\n\nبرای فعال‌سازی: در تلگرام به @easymakebot برو، رباتت را انتخاب کن، «فعال‌سازی با کد» را بزن و کد را بفرست.";
	}
	ob_start();
	echo '<div class="emb-actcodes"><h3>کد فعال‌سازی</h3><ul>';
	foreach ( $lines as $l ) {
		echo '<li><code>' . esc_html( $l ) . '</code></li>';
	}
	echo '</ul><p>برای فعال کردن پلن روی ربات‌ات: در تلگرام به <strong>@easymakebot</strong> برو، ربات موردنظرت را انتخاب کن، '
		. '«<strong>فعال‌سازی با کد</strong>» را بزن و کد بالا را بفرست. کد فقط یک‌بار و برای یک ربات کار می‌کند.</p>'
		. '<p><a class="button" href="https://t.me/easymakebot" target="_blank" rel="noopener">باز کردن ربات</a></p></div>';
	return ob_get_clean();
}

add_action( 'woocommerce_thankyou', function ( $order_id ) {
	$order = wc_get_order( $order_id );
	if ( $order && $order->has_status( array( 'processing', 'completed' ) ) ) {
		echo emb_actcodes_render_block( $order_id ); // phpcs:ignore WordPress.Security.EscapeOutput
	}
}, 8 );

add_action( 'woocommerce_order_details_after_order_table', function ( $order ) {
	echo emb_actcodes_render_block( $order->get_id() ); // phpcs:ignore WordPress.Security.EscapeOutput
} );

add_action( 'woocommerce_email_after_order_table', function ( $order, $sent_to_admin ) {
	if ( $sent_to_admin ) {
		return;
	}
	$block = emb_actcodes_render_block( $order->get_id() );
	if ( $block ) {
		echo '<div style="margin:16px 0">' . $block . '</div>'; // phpcs:ignore WordPress.Security.EscapeOutput
	}
}, 20, 2 );

// visible in the admin order screen, per line item
add_action( 'woocommerce_after_order_itemmeta', function ( $item_id, $item ) {
	global $wpdb;
	$rows = $wpdb->get_results( $wpdb->prepare(
		"SELECT code, status, redeemed_bot_id, redeemed_by_tg, redeemed_by_username, redeemed_by_name, redeemed_phone, redeemed_at
		   FROM " . emb_actcodes_table() . " WHERE order_item_id = %d ORDER BY id",
		$item_id
	) );
	if ( ! $rows ) {
		return;
	}
	foreach ( $rows as $r ) {
		echo '<p style="margin:.5em 0 0"><strong>کد:</strong> <code>' . esc_html( $r->code ) . '</code> — ' . esc_html( $r->status );
		if ( 'redeemed' === $r->status ) {
			$who = $r->redeemed_by_username ? '@' . $r->redeemed_by_username : ( $r->redeemed_by_name ?: '—' );
			echo '<br><span style="color:#666">فعال‌شده روی ربات <code>' . esc_html( $r->redeemed_bot_id ) . '</code>'
				. ' توسط ' . esc_html( $who ) . ' (tg ' . (int) $r->redeemed_by_tg . ')'
				. ( $r->redeemed_phone ? ' · تلفن <code>' . esc_html( $r->redeemed_phone ) . '</code>' : '' )
				. ( $r->redeemed_at ? ' · ' . esc_html( $r->redeemed_at ) . ' UTC' : '' )
				. '</span>';
		}
		echo '</p>';
	}
}, 10, 2 );

/* ── REST API ───────────────────────────────────────────────────────── */
add_action( 'rest_api_init', function () {
	register_rest_route( 'emb/v1', '/redeem', array(
		'methods'             => 'POST',
		'permission_callback' => 'emb_actcodes_rest_auth',
		'callback'            => 'emb_actcodes_rest_redeem',
		'args'                => array(
			'code'        => array( 'required' => true ),
			'bot_id'      => array( 'required' => true ),
			'telegram_id' => array( 'required' => false ),
		),
	) );
	register_rest_route( 'emb/v1', '/check', array(
		'methods'             => 'GET',
		'permission_callback' => 'emb_actcodes_rest_auth',
		'callback'            => 'emb_actcodes_rest_check',
		'args'                => array( 'code' => array( 'required' => true ) ),
	) );
} );

function emb_actcodes_rest_auth( WP_REST_Request $req ) {
	$key = emb_actcodes_api_key();
	if ( '' === $key ) {
		return new WP_Error( 'emb_no_key', 'Activation API key not configured on the server.', array( 'status' => 503 ) );
	}
	$given = (string) $req->get_header( 'x-emb-key' );
	if ( ! hash_equals( $key, $given ) ) {
		return new WP_Error( 'emb_forbidden', 'Bad key.', array( 'status' => 403 ) );
	}
	// light throttle: 40 requests / 5 min / IP
	$ip  = preg_replace( '/[^0-9a-f:.]/i', '', (string) ( $_SERVER['REMOTE_ADDR'] ?? '' ) );
	$k   = 'emb_actcodes_rl_' . md5( $ip );
	$hit = (int) get_transient( $k );
	if ( $hit >= 40 ) {
		return new WP_Error( 'emb_rate', 'Too many requests.', array( 'status' => 429 ) );
	}
	set_transient( $k, $hit + 1, 5 * MINUTE_IN_SECONDS );
	return true;
}

function emb_actcodes_normalize( $code ) {
	$code = strtoupper( trim( (string) $code ) );
	$code = preg_replace( '/[^A-Z0-9]/', '', $code );          // strip dashes/spaces
	if ( 0 === strpos( $code, 'EMB' ) ) {
		$code = substr( $code, 3 );
	}
	if ( strlen( $code ) !== 8 ) {
		return '';
	}
	return 'EMB-' . substr( $code, 0, 4 ) . '-' . substr( $code, 4, 4 );
}

function emb_actcodes_rest_check( WP_REST_Request $req ) {
	global $wpdb;
	$code = emb_actcodes_normalize( $req->get_param( 'code' ) );
	if ( '' === $code ) {
		return new WP_REST_Response( array( 'ok' => true, 'valid' => false, 'reason' => 'malformed' ), 200 );
	}
	$row = $wpdb->get_row( $wpdb->prepare(
		"SELECT months, days, status FROM " . emb_actcodes_table() . " WHERE code = %s", $code
	) );
	if ( ! $row ) {
		return new WP_REST_Response( array( 'ok' => true, 'valid' => false, 'reason' => 'not_found' ), 200 );
	}
	return new WP_REST_Response( array(
		'ok'     => true,
		'valid'  => 'pending' === $row->status,
		'status' => $row->status,
		'months' => (int) $row->months,
		'days'   => (int) $row->days,
	), 200 );
}

function emb_actcodes_rest_redeem( WP_REST_Request $req ) {
	global $wpdb;
	$table  = emb_actcodes_table();
	$code   = emb_actcodes_normalize( $req->get_param( 'code' ) );
	$bot_id = substr( preg_replace( '/[^0-9a-fA-F-]/', '', (string) $req->get_param( 'bot_id' ) ), 0, 64 );
	$tg     = (int) $req->get_param( 'telegram_id' );
	// Redeemer identity forwarded by the bot (bot/website_client.py) — bound to
	// the code for fraud / abuse accountability.
	$tg_user  = substr( preg_replace( '/[^A-Za-z0-9_]/', '', (string) $req->get_param( 'telegram_username' ) ), 0, 64 );
	$tg_name  = substr( sanitize_text_field( (string) $req->get_param( 'telegram_first_name' ) ), 0, 128 );
	$tg_phone = substr( preg_replace( '/[^0-9+]/', '', (string) $req->get_param( 'phone' ) ), 0, 24 );

	if ( '' === $code ) {
		return new WP_REST_Response( array( 'ok' => false, 'error' => 'malformed_code' ), 200 );
	}
	if ( '' === $bot_id ) {
		return new WP_REST_Response( array( 'ok' => false, 'error' => 'missing_bot_id' ), 200 );
	}

	// atomic claim
	$updated = $wpdb->query( $wpdb->prepare(
		"UPDATE {$table}
		    SET status = 'redeemed', redeemed_bot_id = %s, redeemed_by_tg = %d,
		        redeemed_by_username = %s, redeemed_by_name = %s, redeemed_phone = %s,
		        redeemed_at = %s
		  WHERE code = %s AND status = 'pending'",
		$bot_id, $tg, $tg_user, $tg_name, $tg_phone, current_time( 'mysql', true ), $code
	) );

	if ( 1 !== (int) $updated ) {
		$row = $wpdb->get_row( $wpdb->prepare( "SELECT status FROM {$table} WHERE code = %s", $code ) );
		$err = ! $row ? 'not_found' : ( 'redeemed' === $row->status ? 'already_used' : 'void' );
		return new WP_REST_Response( array( 'ok' => false, 'error' => $err ), 200 );
	}

	$row = $wpdb->get_row( $wpdb->prepare( "SELECT order_id, months, days FROM {$table} WHERE code = %s", $code ) );
	$order = $row ? wc_get_order( (int) $row->order_id ) : null;
	if ( $order ) {
		$who = $tg_user ? "@{$tg_user} (tg {$tg})" : "tg {$tg}";
		$order->add_order_note( sprintf(
			'کد %s روی ربات %s فعال شد — %s%s.',
			$code,
			$bot_id,
			$who,
			$tg_phone ? ", تلفن {$tg_phone}" : ''
		) );
		if ( $tg_phone ) {
			$order->update_meta_data( '_emb_redeemer_phone', $tg_phone );
		}
		$order->update_meta_data( '_emb_redeemer_tg', $tg );
		if ( $tg_user ) {
			$order->update_meta_data( '_emb_redeemer_username', $tg_user );
		}
		$order->save();
	}

	return new WP_REST_Response( array(
		'ok'     => true,
		'code'   => $code,
		'months' => (int) $row->months,
		'days'   => (int) $row->days,
	), 200 );
}
