<?php
/**
 * Plugin Name: EMB — relax SMTP TLS verification
 * The ParsPack cPanel mail host presents a cert the container's trust store
 * can't verify. SMTP link only; server-to-server inside ParsPack.
 * Remove once mail.easymakebot.com has a matching AutoSSL cert.
 */
if ( ! defined( 'ABSPATH' ) ) { exit; }
add_action( 'phpmailer_init', function ( $phpmailer ) {
	if ( isset( $phpmailer->Mailer ) && 'smtp' === $phpmailer->Mailer ) {
		$phpmailer->SMTPOptions = array(
			'ssl' => array(
				'verify_peer'       => false,
				'verify_peer_name'  => false,
				'allow_self_signed' => true,
			),
		);
	}
}, 100 );
