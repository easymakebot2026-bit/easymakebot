<?php
/**
 * Plugin Name: easymakebot — TON payment safety net
 * Description: Alerts the admin when a TON/USDT order sits on-hold far
 * longer than the poller's normal ~2-minute window. Purely additive —
 * does not modify emb-ton-gateway.php.
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

const EMB_TON_STUCK_THRESHOLD = 15 * MINUTE_IN_SECONDS;

add_action( 'emb_ton_poll', function () {
	if ( ! function_exists( 'wc_get_orders' ) ) {
		return;
	}
	$orders = wc_get_orders( array(
		'status'         => 'on-hold',
		'payment_method' => 'emb_ton',
		'limit'          => 50,
	) );
	foreach ( $orders as $order ) {
		if ( $order->get_meta( '_emb_ton_txid' ) ) {
			continue;
		}
		if ( $order->get_meta( '_emb_ton_admin_alerted' ) ) {
			continue;
		}
		$created = $order->get_date_created();
		if ( ! $created ) {
			continue;
		}
		$age = time() - $created->getTimestamp();
		if ( $age < EMB_TON_STUCK_THRESHOLD ) {
			continue;
		}
		$to      = get_option( 'admin_email' );
		$subject = sprintf( '[easymakebot] TON order #%d stuck on-hold %d+ min', $order->get_id(), (int) ( $age / 60 ) );
		$wallet  = function_exists( 'emb_ton_wallet' ) ? emb_ton_wallet() : '';
		$body    = sprintf(
			"Order #%d on-hold for %d+ minutes (normal ≈2-5 min).\n\n" .
			"Buyer email: %s\n" .
			"Expected: %s USD, comment: %s\n" .
			"Wallet: %s\n" .
			"Check manually: https://tonviewer.com/%s\n" .
			"Order screen: %s\n\n" .
			"If the on-chain transaction is confirmed but wasn't matched, complete the order manually from the order screen.",
			$order->get_id(),
			(int) ( $age / 60 ),
			$order->get_billing_email(),
			$order->get_meta( '_emb_ton_usd' ),
			$order->get_meta( '_emb_ton_comment' ),
			$wallet,
			$wallet,
			admin_url( 'post.php?post=' . $order->get_id() . '&action=edit' )
		);
		wp_mail( $to, $subject, $body );
		$order->update_meta_data( '_emb_ton_admin_alerted', 1 );
		$order->save();
	}
} );
