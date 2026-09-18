<?php
/**
 * Plugin Name: easymakebot — bot-side account verification bridge
 * Description: Lets the Telegram bot (bot/website_client.py, on a separate
 *              server) collect the same registration fields and OTP
 *              verification that emb-accounts.php already collects on the
 *              website, for bot CREATORS who pay to activate their bot in
 *              /live without ever having visited the website first.
 *
 *              emb-accounts.php's own REST routes (auth-start/auth-verify/
 *              otp-verify/otp-resend) are cookie/session based — built for a
 *              browser tab, not a server-to-server caller with no session.
 *              This file adds a bot-callable (X-EMB-Key header, same pattern
 *              as emb-activation-codes.php / emb-zarinpal-proxy.php) REST
 *              surface around the exact same user/OTP machinery, so the two
 *              systems end up with ONE identity per person (same
 *              `emb_verified` user-meta flag) whichever side they verify on.
 *
 * REST (emb/v1), all POST, header X-EMB-Key: EMB_BOT_VERIFY_KEY:
 *   /bot-verify/status   {channel, phone|email}
 *       → {ok, registered, verified}
 *   /bot-verify/start    {channel, phone|email, first_name?, last_name?,
 *                          address?, tos, telegram_id?, telegram_username?,
 *                          telegram_first_name?}
 *       → {ok, already_verified?} — creates/updates the account and sends
 *         an OTP (sms for channel=sms, email for channel=email). first_name/
 *         last_name/address are required (and phone must be free) for
 *         channel=sms — mirrors the WooCommerce fa registration form
 *         (emb_wc_register_fields). channel=email only needs the address —
 *         mirrors emb_rest_auth_start.
 *   /bot-verify/resend   {channel, phone|email}
 *       → {ok, already_verified?, channel?}
 *   /bot-verify/confirm  {channel, phone|email, code}
 *       → {ok, verified:true}
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

function emb_botverify_api_key() {
	$k = getenv( 'EMB_BOT_VERIFY_KEY' );
	if ( ! $k && defined( 'EMB_BOT_VERIFY_KEY' ) ) {
		$k = EMB_BOT_VERIFY_KEY;
	}
	return is_string( $k ) ? trim( $k ) : '';
}

function emb_botverify_rest_auth( WP_REST_Request $req ) {
	$key = emb_botverify_api_key();
	if ( '' === $key ) {
		return new WP_Error( 'emb_no_key', 'Bot-verify API key not configured on the server.', array( 'status' => 503 ) );
	}
	$given = trim( (string) $req->get_header( 'x-emb-key' ) );
	if ( ! hash_equals( $key, $given ) ) {
		return new WP_Error( 'emb_forbidden', 'Bad key.', array( 'status' => 403 ) );
	}
	// light throttle: 60 requests / 5 min / IP — same shape as the other bridges.
	$ip  = preg_replace( '/[^0-9a-f:.]/i', '', (string) ( $_SERVER['REMOTE_ADDR'] ?? '' ) );
	$k   = 'emb_botverify_rl_' . md5( $ip );
	$hit = (int) get_transient( $k );
	if ( $hit >= 60 ) {
		return new WP_Error( 'emb_rate', 'Too many requests.', array( 'status' => 429 ) );
	}
	set_transient( $k, $hit + 1, 5 * MINUTE_IN_SECONDS );
	return true;
}

add_action( 'rest_api_init', function () {
	foreach ( array( 'status', 'start', 'resend', 'confirm' ) as $route ) {
		register_rest_route( 'emb/v1', '/bot-verify/' . $route, array(
			'methods'             => 'POST',
			'permission_callback' => 'emb_botverify_rest_auth',
			'callback'            => 'emb_botverify_rest_' . $route,
		) );
	}
} );

/** Resolve {channel, phone09|email} → WP user id, or 0 if no account exists yet.
 *  Never creates anything — read-only lookup, shared by all four routes. */
function emb_botverify_find_user( $channel, $phone09, $email ) {
	if ( 'sms' === $channel ) {
		if ( '' === $phone09 ) {
			return 0;
		}
		$ids = get_users( array(
			'meta_key'   => 'billing_phone',
			'meta_value' => $phone09,
			'fields'     => 'ID',
			'number'     => 5,
		) );
		if ( ! $ids ) {
			return 0;
		}
		// Several unverified rows can share a phone (nobody claimed it yet) —
		// prefer a verified one if any, else the most recently created row.
		foreach ( $ids as $id ) {
			if ( '1' === (string) get_user_meta( (int) $id, 'emb_verified', true ) ) {
				return (int) $id;
			}
		}
		return (int) $ids[0];
	}
	if ( '' === $email || ! is_email( $email ) ) {
		return 0;
	}
	$u = get_user_by( 'email', $email );
	return $u ? (int) $u->ID : 0;
}

function emb_botverify_rest_status( WP_REST_Request $req ) {
	$channel = 'sms' === $req->get_param( 'channel' ) ? 'sms' : 'email';
	$phone   = emb_normalize_phone_ir( (string) $req->get_param( 'phone' ) );
	$email   = sanitize_email( (string) $req->get_param( 'email' ) );
	$uid     = emb_botverify_find_user( $channel, $phone, $email );
	if ( ! $uid ) {
		return new WP_REST_Response( array( 'ok' => true, 'registered' => false, 'verified' => false ), 200 );
	}
	return new WP_REST_Response( array(
		'ok'         => true,
		'registered' => true,
		'verified'   => emb_is_verified( $uid ),
	), 200 );
}

/** Stamp the Telegram identity that triggered this registration, for the
 *  same abuse/fraud accountability reason emb-activation-codes.php records
 *  the redeemer's Telegram identity on the order. Best-effort, never blocks. */
function emb_botverify_stamp_telegram( $uid, WP_REST_Request $req ) {
	$tg_id = (int) $req->get_param( 'telegram_id' );
	if ( ! $tg_id ) {
		return;
	}
	$tg_user = substr( preg_replace( '/[^A-Za-z0-9_]/', '', (string) $req->get_param( 'telegram_username' ) ), 0, 64 );
	$tg_name = substr( sanitize_text_field( (string) $req->get_param( 'telegram_first_name' ) ), 0, 128 );
	update_user_meta( (int) $uid, 'emb_bot_telegram_id', $tg_id );
	if ( $tg_user ) {
		update_user_meta( (int) $uid, 'emb_bot_telegram_username', $tg_user );
	}
	if ( $tg_name ) {
		update_user_meta( (int) $uid, 'emb_bot_telegram_name', $tg_name );
	}
}

function emb_botverify_rest_start( WP_REST_Request $req ) {
	if ( ! emb_rl_ok( 'botverify_start', 10, 15 * MINUTE_IN_SECONDS ) ) {
		return new WP_REST_Response( array( 'ok' => false, 'error' => 'rate_limited' ), 200 );
	}
	$channel = 'sms' === $req->get_param( 'channel' ) ? 'sms' : 'email';
	$tos     = filter_var( $req->get_param( 'tos' ), FILTER_VALIDATE_BOOLEAN );
	if ( ! $tos ) {
		return new WP_REST_Response( array( 'ok' => false, 'error' => 'tos_required' ), 200 );
	}
	$email = sanitize_email( (string) $req->get_param( 'email' ) );
	if ( ! is_email( $email ) ) {
		return new WP_REST_Response( array( 'ok' => false, 'error' => 'bad_email' ), 200 );
	}

	if ( 'sms' === $channel ) {
		$phone = emb_normalize_phone_ir( (string) $req->get_param( 'phone' ) );
		$fn    = substr( sanitize_text_field( (string) $req->get_param( 'first_name' ) ), 0, 100 );
		$ln    = substr( sanitize_text_field( (string) $req->get_param( 'last_name' ) ), 0, 100 );
		$ad    = substr( sanitize_textarea_field( (string) $req->get_param( 'address' ) ), 0, 500 );
		if ( '' === $phone ) {
			return new WP_REST_Response( array( 'ok' => false, 'error' => 'bad_phone' ), 200 );
		}
		if ( '' === $fn || '' === $ln || '' === $ad ) {
			return new WP_REST_Response( array( 'ok' => false, 'error' => 'missing_fields' ), 200 );
		}
		// Someone else's already-VERIFIED phone — same rule the website's own
		// registration form enforces (emb_wc_register_validate).
		if ( emb_phone_taken( $phone ) ) {
			return new WP_REST_Response( array( 'ok' => false, 'error' => 'phone_taken' ), 200 );
		}

		$uid = emb_botverify_find_user( 'sms', $phone, '' );
		if ( $uid && emb_is_verified( $uid ) ) {
			emb_botverify_stamp_telegram( $uid, $req );
			return new WP_REST_Response( array( 'ok' => true, 'already_verified' => true ), 200 );
		}
		// Resolve the email side too, UNCONDITIONALLY (not just when the phone
		// found nothing) — otherwise reusing an unverified phone-matched
		// account below would silently overwrite billing_email with whatever
		// email the caller typed, without ever checking who that email
		// actually belongs to. A verified stranger's email is always a hard
		// block; a DIFFERENT unverified account under that email is treated
		// the same way rather than guessing which of the two to keep.
		$existing_email_user = get_user_by( 'email', $email );
		$email_uid           = $existing_email_user ? (int) $existing_email_user->ID : 0;
		if ( $email_uid && $email_uid !== $uid && ( emb_is_verified( $email_uid ) || $uid ) ) {
			return new WP_REST_Response( array( 'ok' => false, 'error' => 'email_taken' ), 200 );
		}
		if ( ! $uid && $email_uid ) {
			// No account under this phone yet, but the email they typed
			// already has one (an earlier attempt, or a partial site signup)
			// and it's confirmed above to be unverified — safe to reuse.
			$uid = $email_uid;
		}
		if ( ! $uid ) {
			$role = get_role( 'customer' ) ? 'customer' : 'subscriber';
			$uid  = wp_insert_user( array(
				'user_login' => emb_unique_login_from_email( $email ),
				'user_email' => $email,
				'user_pass'  => wp_generate_password( 24, true, true ),
				'role'       => $role,
			) );
			if ( is_wp_error( $uid ) ) {
				return new WP_REST_Response( array( 'ok' => false, 'error' => 'server' ), 200 );
			}
			emb_record_signup_origin( $uid );
		}
		update_user_meta( $uid, 'first_name', $fn );
		update_user_meta( $uid, 'last_name', $ln );
		update_user_meta( $uid, 'billing_first_name', $fn );
		update_user_meta( $uid, 'billing_last_name', $ln );
		update_user_meta( $uid, 'billing_phone', $phone );
		update_user_meta( $uid, 'billing_address_1', $ad );
		update_user_meta( $uid, 'billing_email', $email );
		update_user_meta( $uid, 'emb_verify_channel', 'sms' );
		update_user_meta( $uid, 'emb_lang', 'fa' );
		emb_botverify_stamp_telegram( $uid, $req );
		emb_record_tos( $uid );

		$r = emb_otp_send( $uid, 'sms', $phone, 'fa' );
		if ( is_wp_error( $r ) ) {
			return new WP_REST_Response( array( 'ok' => false, 'error' => $r->get_error_code() ), 200 );
		}
		return new WP_REST_Response( array( 'ok' => true ), 200 );
	}

	// international / email channel — mirrors emb_rest_auth_start exactly,
	// just triggered by the bot instead of the /en/ passwordless form.
	$uid = emb_botverify_find_user( 'email', '', $email );
	if ( $uid && emb_is_verified( $uid ) ) {
		emb_botverify_stamp_telegram( $uid, $req );
		return new WP_REST_Response( array( 'ok' => true, 'already_verified' => true ), 200 );
	}
	if ( ! $uid ) {
		$role = get_role( 'customer' ) ? 'customer' : 'subscriber';
		$uid  = wp_insert_user( array(
			'user_login' => emb_unique_login_from_email( $email ),
			'user_email' => $email,
			'user_pass'  => wp_generate_password( 24, true, true ),
			'role'       => $role,
		) );
		if ( is_wp_error( $uid ) ) {
			return new WP_REST_Response( array( 'ok' => false, 'error' => 'server' ), 200 );
		}
		update_user_meta( $uid, 'emb_verify_channel', 'email' );
		update_user_meta( $uid, 'billing_email', $email );
		emb_record_signup_origin( $uid );
	}
	update_user_meta( $uid, 'emb_lang', 'en' );
	emb_botverify_stamp_telegram( $uid, $req );
	emb_record_tos( $uid );

	$r = emb_otp_send( $uid, 'email', $email, 'en' );
	if ( is_wp_error( $r ) ) {
		return new WP_REST_Response( array( 'ok' => false, 'error' => $r->get_error_code() ), 200 );
	}
	return new WP_REST_Response( array( 'ok' => true ), 200 );
}

function emb_botverify_rest_resend( WP_REST_Request $req ) {
	if ( ! emb_rl_ok( 'botverify_resend', 10, 15 * MINUTE_IN_SECONDS ) ) {
		return new WP_REST_Response( array( 'ok' => false, 'error' => 'rate_limited' ), 200 );
	}
	$channel = 'sms' === $req->get_param( 'channel' ) ? 'sms' : 'email';
	$phone   = emb_normalize_phone_ir( (string) $req->get_param( 'phone' ) );
	$email   = sanitize_email( (string) $req->get_param( 'email' ) );
	$uid     = emb_botverify_find_user( $channel, $phone, $email );
	if ( ! $uid ) {
		return new WP_REST_Response( array( 'ok' => false, 'error' => 'no_target' ), 200 );
	}
	if ( emb_is_verified( $uid ) ) {
		return new WP_REST_Response( array( 'ok' => true, 'already_verified' => true ), 200 );
	}
	$dest = 'sms' === $channel ? $phone : $email;
	$r    = emb_otp_send( $uid, $channel, $dest, 'sms' === $channel ? 'fa' : 'en' );
	if ( is_wp_error( $r ) ) {
		return new WP_REST_Response( array( 'ok' => false, 'error' => $r->get_error_code() ), 200 );
	}
	return new WP_REST_Response( array( 'ok' => true, 'channel' => $channel ), 200 );
}

function emb_botverify_rest_confirm( WP_REST_Request $req ) {
	if ( ! emb_rl_ok( 'botverify_confirm', 25, 15 * MINUTE_IN_SECONDS ) ) {
		return new WP_REST_Response( array( 'ok' => false, 'error' => 'rate_limited' ), 200 );
	}
	$channel = 'sms' === $req->get_param( 'channel' ) ? 'sms' : 'email';
	$phone   = emb_normalize_phone_ir( (string) $req->get_param( 'phone' ) );
	$email   = sanitize_email( (string) $req->get_param( 'email' ) );
	$uid     = emb_botverify_find_user( $channel, $phone, $email );
	if ( ! $uid ) {
		return new WP_REST_Response( array( 'ok' => false, 'error' => 'no_pending' ), 200 );
	}
	$r = emb_otp_verify( $uid, (string) $req->get_param( 'code' ) );
	if ( is_wp_error( $r ) ) {
		return new WP_REST_Response( array( 'ok' => false, 'error' => $r->get_error_code(), 'message' => $r->get_error_message() ), 200 );
	}
	return new WP_REST_Response( array( 'ok' => true, 'verified' => true ), 200 );
}
