<?php
/**
 * READ-ONLY audit of every TON/USDT order the site has already accepted.
 *
 * Before the emb-ton-gateway fix, any jetton whose *symbol* contained "USD"
 * was accepted as USDT, so a self-minted worthless token could buy a plan.
 * This re-checks each paid order's on-chain transaction against the official
 * USDT master contract (emb_ton_is_official_usdt, from the fixed plugin) and
 * prints a verdict per order, plus what its activation codes were used for.
 *
 * It changes nothing — no order, code or setting is modified. Run it with:
 *   docker compose ... run --rm --no-deps -T wpcli wp eval-file /scripts/check-ton-orders.php
 */

if ( ! function_exists( 'emb_ton_is_official_usdt' ) ) {
	echo "The fixed emb-ton-gateway.php is not loaded yet — deploy it first.\n";
	return;
}

global $wpdb;
$codes_table = $wpdb->prefix . 'emb_activation_codes';

$orders = wc_get_orders( array(
	'payment_method' => 'emb_ton',
	'limit'          => -1,
	'status'         => array( 'processing', 'completed', 'refunded', 'cancelled' ),
	'orderby'        => 'date',
	'order'          => 'ASC',
) );

$checked = 0;
$fake    = array();
$unknown = array();

foreach ( $orders as $o ) {
	$tx = (string) $o->get_meta( '_emb_ton_txid' );
	if ( '' === $tx ) {
		continue; // completed by hand / never matched on-chain
	}
	$checked++;

	$verdict = '';
	$r = wp_remote_get( 'https://tonapi.io/v2/events/' . rawurlencode( $tx ), array( 'timeout' => 20 ) );
	$j = is_wp_error( $r ) ? null : json_decode( wp_remote_retrieve_body( $r ), true );
	if ( ! is_array( $j ) || empty( $j['actions'] ) ) {
		$verdict   = 'COULD NOT FETCH — check by hand on tonviewer.com';
		$unknown[] = $o->get_id();
	} else {
		$verdict = 'TON coin — OK';
		foreach ( (array) $j['actions'] as $a ) {
			if ( ( $a['type'] ?? '' ) !== 'JettonTransfer' ) {
				continue;
			}
			$jet = $a['JettonTransfer']['jetton'] ?? array();
			if ( emb_ton_is_official_usdt( $jet['address'] ?? '' ) ) {
				$verdict = 'real USDT — OK';
			} else {
				$verdict = sprintf( 'FAKE token "%s" (%s) — NOT A REAL PAYMENT', $jet['symbol'] ?? '?', $jet['address'] ?? '?' );
				$fake[]  = $o->get_id();
			}
		}
	}

	$codes = $wpdb->get_results( $wpdb->prepare(
		"SELECT code, status, redeemed_bot_id FROM {$codes_table} WHERE order_id = %d",
		$o->get_id()
	) );
	$code_info = array();
	foreach ( (array) $codes as $c ) {
		$code_info[] = $c->code . ' ' . $c->status . ( $c->redeemed_bot_id ? ' -> bot ' . $c->redeemed_bot_id : '' );
	}

	printf(
		"order #%d  %s  %s %s  status=%s  %s\n    codes: %s\n",
		$o->get_id(),
		$o->get_date_created() ? $o->get_date_created()->date( 'Y-m-d' ) : '?',
		$o->get_total(),
		$o->get_currency(),
		$o->get_status(),
		$verdict,
		$code_info ? implode( '; ', $code_info ) : '(none)'
	);
	usleep( 300000 ); // be gentle with tonapi's free rate limit
}

printf(
	"\nChecked %d paid TON/USDT order(s). Fake-token orders: %s. Could not verify: %s.\n",
	$checked,
	$fake ? '#' . implode( ', #', $fake ) : 'none',
	$unknown ? '#' . implode( ', #', $unknown ) : 'none'
);
echo "Nothing was changed. Decide what to do about any FAKE order before touching it.\n";
