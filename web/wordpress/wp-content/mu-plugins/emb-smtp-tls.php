<?php
/**
 * Plugin Name: EMB — relax SMTP TLS verification
 * Description: The ParsPack cPanel mail host (mail.easymakebot.com /
 * s438.bitcommand.com) presents a self-signed certificate that the container's
 * trust store cannot verify. This is a server-to-server hop inside ParsPack, so
 * we skip peer verification for the SMTP link only. Remove this file once
 * mail.easymakebot.com has a matching AutoSSL certificate.
 *
 * See docs/70-email.md for the full ParsPack mail setup (account h419862,
 * extra_hosts pin in docker-compose.prod.yml, DNS records).
 *
 * @package easymakebot
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

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
