<?php
/**
 * Plugin Name: easymakebot — accounts & verified purchase
 * Description: Site accounts with identity verification. Iranian users register
 *              on the WooCommerce My Account page (name / last name / phone /
 *              address / email) and confirm a code sent by SMS (Kavenegar,
 *              pluggable). International users sign in on /en/ with a
 *              passwordless email code. Only a logged-in *verified* user can
 *              buy a plan — fa checkout and the /en/ inline TON panel are both
 *              gated. Anti-abuse for the bot platform.
 *
 * REST (emb/v1):
 *   POST /auth-start   {email}          guest  → create/find user, email a code
 *   POST /auth-verify  {email,code}     guest  → verify + log in (sets cookie)
 *   POST /otp-verify   {code}           logged-in → verify the current user
 *   POST /otp-resend   {}               logged-in → resend the current user's code
 *
 * Settings: wp-admin › Settings › easymakebot (SMS driver + Kavenegar key/template).
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

const EMB_OTP_TTL          = 600; // 10 minutes
const EMB_OTP_MAX_TRIES    = 5;
const EMB_OTP_RESEND_WAIT  = 60;  // seconds between sends
const EMB_OTP_RESEND_MAX_H = 5;   // sends per hour

// Bump when the Terms of Service change to re-prompt for acceptance.
const EMB_TOS_VERSION = '2026-08-30';

/* ─────────────────────────  small shared helpers  ───────────────────────── */

/** Per-IP rate limiter (also used by emb-ton-gateway.php, which loads after this). */
function emb_rl_ok( $bucket, $max, $secs ) {
	$ip  = preg_replace( '/[^0-9a-f:.]/i', '', (string) emb_request_ip() );
	$k   = 'emb_rl_' . $bucket . '_' . md5( $ip );
	$hit = (int) get_transient( $k );
	if ( $hit >= $max ) {
		return false;
	}
	set_transient( $k, $hit + 1, $secs );
	return true;
}

/** Best-effort real client IP. Trusts Cloudflare's header only when present. */
function emb_request_ip() {
	$cf = $_SERVER['HTTP_CF_CONNECTING_IP'] ?? '';
	if ( $cf && filter_var( $cf, FILTER_VALIDATE_IP ) ) {
		return $cf;
	}
	$ip = $_SERVER['REMOTE_ADDR'] ?? '';
	return filter_var( $ip, FILTER_VALIDATE_IP ) ? $ip : '';
}

/** 2-letter country from Cloudflare's CF-IPCountry header ('' if not behind CF). */
function emb_request_country() {
	$c = strtoupper( substr( (string) ( $_SERVER['HTTP_CF_IPCOUNTRY'] ?? '' ), 0, 2 ) );
	return preg_match( '/^[A-Z]{2}$/', $c ) && 'XX' !== $c ? $c : '';
}

/** Record ToS acceptance (version + timestamp + IP + country) on a user. */
function emb_record_tos( $uid ) {
	update_user_meta( (int) $uid, 'emb_tos', array(
		'v'  => EMB_TOS_VERSION,
		'at' => gmdate( 'c' ),
		'ip' => emb_request_ip(),
		'cc' => emb_request_country(),
	) );
}

/** Record where an account was created from (once, at signup). */
function emb_record_signup_origin( $uid ) {
	$uid = (int) $uid;
	if ( ! get_user_meta( $uid, 'emb_signup_ip', true ) ) {
		update_user_meta( $uid, 'emb_signup_ip', emb_request_ip() );
		update_user_meta( $uid, 'emb_signup_country', emb_request_country() );
		update_user_meta( $uid, 'emb_signup_at', gmdate( 'c' ) );
	}
}

/** Terms / Privacy page URL for the current language. The EN copies are separate
 *  pages with -en slugs (Polylang free can't route /en/terms/); their canonical
 *  URL is /en/terms-en/ — use the real permalink so there's no redirect hop. */
function emb_legal_url( $fa_slug, $en_slug ) {
	if ( 'en' === emb_current_lang() ) {
		$p = get_page_by_path( $en_slug );
		return $p ? get_permalink( $p ) : home_url( '/en/' . $en_slug . '/' );
	}
	return home_url( '/' . $fa_slug . '/' );
}
function emb_terms_url() {
	return emb_legal_url( 'terms', 'terms-en' );
}
function emb_privacy_url() {
	return emb_legal_url( 'privacy', 'privacy-en' );
}

/** Has this user accepted the current ToS version? */
function emb_tos_ok( $uid = null ) {
	$uid = $uid ? (int) $uid : get_current_user_id();
	if ( ! $uid ) {
		return false;
	}
	if ( user_can( $uid, 'manage_woocommerce' ) ) {
		return true;
	}
	$t = get_user_meta( $uid, 'emb_tos', true );
	return is_array( $t ) && ! empty( $t['v'] );
}

/** fa | en for the current request (REST-safe). */
function emb_current_lang() {
	if ( function_exists( 'pll_current_language' ) ) {
		$l = pll_current_language();
		if ( $l ) {
			return $l;
		}
	}
	$path = (string) wp_parse_url( $_SERVER['REQUEST_URI'] ?? '/', PHP_URL_PATH );
	return preg_match( '#^/en(/|$)#', $path ) ? 'en' : 'fa';
}

/** Persian / Arabic-Indic digits → ASCII. */
function emb_digits( $s ) {
	return strtr( (string) $s, array(
		'۰' => '0', '۱' => '1', '۲' => '2', '۳' => '3', '۴' => '4',
		'۵' => '5', '۶' => '6', '۷' => '7', '۸' => '8', '۹' => '9',
		'٠' => '0', '١' => '1', '٢' => '2', '٣' => '3', '٤' => '4',
		'٥' => '5', '٦' => '6', '٧' => '7', '٨' => '8', '٩' => '9',
	) );
}

/** Normalise an Iranian mobile to 09xxxxxxxxx, or '' if invalid. */
function emb_normalize_phone_ir( $raw ) {
	$s = preg_replace( '/\D+/', '', emb_digits( $raw ) );
	if ( 0 === strpos( $s, '0098' ) ) {
		$s = '0' . substr( $s, 4 );
	} elseif ( 0 === strpos( $s, '98' ) && 12 === strlen( $s ) ) {
		$s = '0' . substr( $s, 2 );
	} elseif ( 10 === strlen( $s ) && 0 === strpos( $s, '9' ) ) {
		$s = '0' . $s;
	}
	return preg_match( '/^09\d{9}$/', $s ) ? $s : '';
}

/** Is this user identity-verified? Staff always count as verified. */
function emb_is_verified( $uid = null ) {
	$uid = $uid ? (int) $uid : get_current_user_id();
	if ( ! $uid ) {
		return false;
	}
	if ( user_can( $uid, 'manage_woocommerce' ) ) {
		return true;
	}
	return '1' === (string) get_user_meta( $uid, 'emb_verified', true );
}

/** True if a *verified* account (other than $exclude_uid) already holds this phone. */
function emb_phone_taken( $phone09, $exclude_uid = 0 ) {
	$ids = get_users( array(
		'meta_key'   => 'billing_phone',
		'meta_value' => $phone09,
		'fields'     => 'ID',
		'number'     => 30,
	) );
	foreach ( $ids as $id ) {
		if ( (int) $id === (int) $exclude_uid ) {
			continue;
		}
		if ( '1' === (string) get_user_meta( $id, 'emb_verified', true ) ) {
			return true;
		}
	}
	return false;
}

function emb_unique_login_from_email( $email ) {
	$base  = sanitize_user( current( explode( '@', $email ) ), true );
	$base  = $base ? strtolower( $base ) : 'user';
	$login = $base;
	$i     = 1;
	while ( username_exists( $login ) ) {
		$login = $base . $i;
		$i++;
	}
	return $login;
}

/* ─────────────────────────  SMS driver (pluggable)  ───────────────────────── */

function emb_sms_driver() {
	$d = get_option( 'emb_sms_driver', '' );
	if ( ! $d ) {
		$d = getenv( 'EMB_SMS_DRIVER' ) ?: 'log';
	}
	return in_array( $d, array( 'log', 'kavenegar', 'asanak' ), true ) ? $d : 'log';
}

/**
 * Send a verification code by SMS. Returns bool.
 * Filter `emb_sms_pre_send` ($result, $phone, $code) short-circuits (tests).
 */
function emb_sms_send( $phone09, $code, $uid = 0 ) {
	$pre = apply_filters( 'emb_sms_pre_send', null, $phone09, $code );
	if ( null !== $pre ) {
		return (bool) $pre;
	}
	$driver = emb_sms_driver();
	if ( 'kavenegar' === $driver ) {
		return emb_sms_send_kavenegar( $phone09, $code );
	}
	if ( 'asanak' === $driver ) {
		return emb_sms_send_asanak( $phone09, $code, $uid );
	}
	// 'log' driver — dev / pre-provisioning
	$line = gmdate( 'c' ) . "  sms→{$phone09}  code={$code}\n";
	error_log( '[emb-sms] ' . trim( $line ) );
	$f = WP_CONTENT_DIR . '/uploads/emb-sms.log';
	if ( is_writable( dirname( $f ) ) ) {
		file_put_contents( $f, $line, FILE_APPEND | LOCK_EX );
	}
	return true;
}

function emb_sms_send_kavenegar( $phone09, $code ) {
	$key = trim( (string) ( get_option( 'emb_sms_kavenegar_key', '' ) ?: getenv( 'EMB_SMS_API_KEY' ) ) );
	$tpl = trim( (string) ( get_option( 'emb_sms_kavenegar_template', '' ) ?: getenv( 'EMB_SMS_TEMPLATE' ) ) );
	if ( '' === $key || '' === $tpl ) {
		error_log( '[emb-sms] kavenegar: key/template not configured' );
		return false;
	}
	$url = sprintf(
		'https://api.kavenegar.com/v1/%s/verify/lookup.json?receptor=%s&token=%s&template=%s',
		rawurlencode( $key ),
		rawurlencode( $phone09 ),
		rawurlencode( $code ),
		rawurlencode( $tpl )
	);
	$res = wp_remote_get( $url, array( 'timeout' => 15 ) );
	if ( is_wp_error( $res ) ) {
		error_log( '[emb-sms] kavenegar: ' . $res->get_error_message() );
		return false;
	}
	$body = json_decode( wp_remote_retrieve_body( $res ), true );
	$ok   = isset( $body['return']['status'] ) && 200 === (int) $body['return']['status'];
	if ( ! $ok ) {
		error_log( '[emb-sms] kavenegar rejected: ' . wp_remote_retrieve_body( $res ) );
	}
	return $ok;
}

/**
 * Asanak (آسانک) — plain sendsms webservice (v2rest, JSON), sent from the
 * dedicated OTP line (the "source" number). No separate pattern/OTP endpoint
 * exists in Asanak's webservice — see https://asanak.com/api-docs/sms/single.
 * Success response shape: {"meta":{"status":200,"message":"success"},"data":[123456]}.
 * Anything else (including a flat {"status":"..."} error object) is a failure.
 */
function emb_sms_send_asanak( $phone09, $code, $uid = 0 ) {
	$user   = trim( (string) ( get_option( 'emb_sms_asanak_username', '' ) ?: getenv( 'EMB_SMS_ASANAK_USERNAME' ) ) );
	$pass   = trim( (string) ( get_option( 'emb_sms_asanak_password', '' ) ?: getenv( 'EMB_SMS_ASANAK_PASSWORD' ) ) );
	$source = trim( (string) ( get_option( 'emb_sms_asanak_source', '' ) ?: getenv( 'EMB_SMS_ASANAK_SOURCE' ) ) );
	if ( '' === $user || '' === $pass || '' === $source ) {
		error_log( '[emb-sms] asanak: username/password/source not configured' );
		return false;
	}
	$name = '';
	if ( $uid ) {
		$fn   = trim( (string) get_user_meta( (int) $uid, 'first_name', true ) );
		$ln   = trim( (string) get_user_meta( (int) $uid, 'last_name', true ) );
		$name = trim( $fn . '  ' . $ln );
	}
	$greeting = '' !== $name ? $name : 'کاربر';
	// Note: Asanak's dedicated OTP line rejects any message containing a link
	// (error 1014 "This source number can not send link") — no domain/URL here.
	$message  = sprintf(
		"%s عزیز:\n کد تآیید خدمت شما:  %s\n\nربات بساز، بدون کد نویسی 😉",
		$greeting,
		$code
	);
	$payload = wp_json_encode( array(
		'username'    => $user,
		'password'    => $pass,
		'source'      => $source,
		'destination' => $phone09,
		'message'     => $message,
	) );
	$res = wp_remote_post( 'https://sms.asanak.ir/webservice/v2rest/sendsms', array(
		'timeout' => 15,
		'headers' => array(
			'Content-Type' => 'application/json',
			'Accept'       => 'application/json',
		),
		'body'    => $payload,
	) );
	if ( is_wp_error( $res ) ) {
		error_log( '[emb-sms] asanak: ' . $res->get_error_message() );
		return false;
	}
	$http_code = (int) wp_remote_retrieve_response_code( $res );
	$body_raw  = wp_remote_retrieve_body( $res );
	$body      = json_decode( $body_raw, true );
	// Documented v2 success shape: {"meta":{"status":200,...},"data":[<msg id>,...]}.
	$ok = ( 200 === $http_code ) && is_array( $body )
		&& isset( $body['meta']['status'] ) && 200 === (int) $body['meta']['status']
		&& ! empty( $body['data'] );
	if ( ! $ok ) {
		error_log( '[emb-sms] asanak rejected: ' . $body_raw );
	}
	return $ok;
}

/* ─────────────────────────  OTP core (channel-agnostic)  ───────────────────────── */

function emb_otp_key( $uid ) {
	return 'emb_otp_' . (int) $uid;
}

function emb_otp_mask( $channel, $dest ) {
	if ( 'sms' === $channel ) {
		return substr( $dest, 0, 4 ) . '***' . substr( $dest, -2 );
	}
	$p = explode( '@', (string) $dest );
	return substr( $p[0], 0, 2 ) . '***@' . ( $p[1] ?? '' );
}

function emb_otp_generate( $uid, $channel, $dest ) {
	$code = (string) random_int( 100000, 999999 );
	set_transient( emb_otp_key( $uid ), array(
		'hash'    => password_hash( $code, PASSWORD_DEFAULT ),
		'exp'     => time() + EMB_OTP_TTL,
		'tries'   => 0,
		'channel' => $channel,
		'dest'    => emb_otp_mask( $channel, $dest ),
	), EMB_OTP_TTL );
	return $code;
}

/** Generate + deliver a code. Returns true|WP_Error. */
function emb_otp_send( $uid, $channel, $dest, $lang = null ) {
	$uid = (int) $uid;
	if ( ! $lang ) {
		$lang = get_user_meta( $uid, 'emb_lang', true ) ?: emb_current_lang();
	}
	if ( get_transient( 'emb_otp_wait_' . $uid ) ) {
		return new WP_Error( 'too_soon', __( 'کمی صبر کنید و دوباره کد بگیرید.', 'easymakebot' ) );
	}
	$h = (int) get_transient( 'emb_otp_h_' . $uid );
	if ( $h >= EMB_OTP_RESEND_MAX_H ) {
		return new WP_Error( 'too_many_sends', __( 'درخواست کد زیاد شد. یک ساعت دیگر تلاش کنید.', 'easymakebot' ) );
	}
	$code = emb_otp_generate( $uid, $channel, $dest );
	$sent = ( 'email' === $channel ) ? emb_otp_email( $dest, $code, $lang ) : emb_sms_send( $dest, $code, $uid );
	if ( ! $sent ) {
		delete_transient( emb_otp_key( $uid ) );
		return new WP_Error( 'send_failed', __( 'ارسال کد ناموفق بود. بعداً تلاش کنید.', 'easymakebot' ) );
	}
	set_transient( 'emb_otp_wait_' . $uid, 1, EMB_OTP_RESEND_WAIT );
	set_transient( 'emb_otp_h_' . $uid, $h + 1, HOUR_IN_SECONDS );
	return true;
}

function emb_otp_email( $to, $code, $lang = null ) {
	$lang = $lang ?: emb_current_lang();
	if ( 'en' === $lang ) {
		$subject = 'Your easymakebot verification code';
		$body    = "Your easymakebot verification code is:\n\n    {$code}\n\n"
			. "It expires in 10 minutes. If you didn't request this, ignore this email.";
	} else {
		$subject = 'کد تأیید easymakebot';
		$body    = "کد تأیید شما:\n\n    {$code}\n\n"
			. 'این کد تا ۱۰ دقیقه معتبر است. اگر شما درخواست نکرده‌اید، این ایمیل را نادیده بگیرید.';
	}
	return (bool) wp_mail( $to, $subject, $body );
}

/** Check a submitted code for a user. Returns true|WP_Error. */
function emb_otp_verify( $uid, $code ) {
	$uid  = (int) $uid;
	$code = preg_replace( '/\D+/', '', emb_digits( $code ) );
	$rec  = get_transient( emb_otp_key( $uid ) );

	if ( ! $rec || empty( $rec['hash'] ) ) {
		return new WP_Error( 'no_pending', __( 'کدی در انتظار نیست — کد جدید بگیرید.', 'easymakebot' ) );
	}
	if ( time() > (int) $rec['exp'] ) {
		delete_transient( emb_otp_key( $uid ) );
		return new WP_Error( 'expired', __( 'کد منقضی شده — کد جدید بگیرید.', 'easymakebot' ) );
	}
	if ( (int) $rec['tries'] >= EMB_OTP_MAX_TRIES ) {
		delete_transient( emb_otp_key( $uid ) );
		return new WP_Error( 'too_many', __( 'تلاش زیاد — کد جدید بگیرید.', 'easymakebot' ) );
	}
	if ( strlen( $code ) < 4 || ! password_verify( $code, $rec['hash'] ) ) {
		$rec['tries']++;
		set_transient( emb_otp_key( $uid ), $rec, max( 1, (int) $rec['exp'] - time() ) );
		return new WP_Error( 'mismatch', __( 'کد نادرست است.', 'easymakebot' ) );
	}

	delete_transient( emb_otp_key( $uid ) );
	update_user_meta( $uid, 'emb_verified', '1' );
	update_user_meta( $uid, 'emb_verify_channel', $rec['channel'] );
	update_user_meta( $uid, 'emb_verified_at', current_time( 'mysql', true ) );
	return true;
}

/** Best destination to (re)send a logged-in user's code to. */
function emb_user_otp_target( $uid ) {
	$channel = get_user_meta( $uid, 'emb_verify_channel', true ) ?: 'email';
	if ( 'sms' === $channel ) {
		$phone = emb_normalize_phone_ir( get_user_meta( $uid, 'billing_phone', true ) );
		if ( $phone ) {
			return array( 'sms', $phone );
		}
	}
	$u = get_userdata( $uid );
	return array( 'email', $u ? $u->user_email : '' );
}

/* ─────────────────────────  REST endpoints  ───────────────────────── */

add_action( 'rest_api_init', function () {
	register_rest_route( 'emb/v1', '/auth-start', array(
		'methods'             => 'POST',
		'permission_callback' => '__return_true',
		'callback'            => 'emb_rest_auth_start',
	) );
	register_rest_route( 'emb/v1', '/auth-verify', array(
		'methods'             => 'POST',
		'permission_callback' => '__return_true',
		'callback'            => 'emb_rest_auth_verify',
	) );
	register_rest_route( 'emb/v1', '/otp-verify', array(
		'methods'             => 'POST',
		'permission_callback' => 'is_user_logged_in',
		'callback'            => 'emb_rest_otp_verify',
	) );
	register_rest_route( 'emb/v1', '/otp-resend', array(
		'methods'             => 'POST',
		'permission_callback' => 'is_user_logged_in',
		'callback'            => 'emb_rest_otp_resend',
	) );
} );

/** en passwordless: create/find the user, email a code. Never leaks existence. */
function emb_rest_auth_start( WP_REST_Request $req ) {
	if ( ! emb_rl_ok( 'authstart', 8, 15 * MINUTE_IN_SECONDS ) ) {
		return new WP_REST_Response( array( 'ok' => false, 'error' => 'rate_limited' ), 200 );
	}
	$email = sanitize_email( (string) $req->get_param( 'email' ) );
	$lang  = in_array( $req->get_param( 'lang' ), array( 'fa', 'en' ), true ) ? $req->get_param( 'lang' ) : emb_current_lang();
	$tos   = filter_var( $req->get_param( 'tos' ), FILTER_VALIDATE_BOOLEAN );
	if ( ! is_email( $email ) ) {
		return new WP_REST_Response( array( 'ok' => false, 'error' => 'bad_email' ), 200 );
	}
	if ( ! $tos ) {
		return new WP_REST_Response( array( 'ok' => false, 'error' => 'tos_required' ), 200 );
	}

	$user = get_user_by( 'email', $email );
	if ( $user ) {
		$uid = $user->ID;
	} else {
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
	update_user_meta( $uid, 'emb_lang', $lang );
	emb_record_tos( $uid );

	$r = emb_otp_send( $uid, 'email', $email, $lang );
	if ( is_wp_error( $r ) ) {
		return new WP_REST_Response( array( 'ok' => false, 'error' => $r->get_error_code() ), 200 );
	}
	return new WP_REST_Response( array( 'ok' => true ), 200 );
}

/** en passwordless: check the code and log the user in. */
function emb_rest_auth_verify( WP_REST_Request $req ) {
	if ( ! emb_rl_ok( 'authverify', 25, 15 * MINUTE_IN_SECONDS ) ) {
		return new WP_REST_Response( array( 'ok' => false, 'error' => 'rate_limited' ), 200 );
	}
	$email = sanitize_email( (string) $req->get_param( 'email' ) );
	$user  = $email ? get_user_by( 'email', $email ) : null;
	if ( ! $user ) {
		return new WP_REST_Response( array( 'ok' => false, 'error' => 'no_pending' ), 200 );
	}
	$r = emb_otp_verify( $user->ID, (string) $req->get_param( 'code' ) );
	if ( is_wp_error( $r ) ) {
		return new WP_REST_Response( array( 'ok' => false, 'error' => $r->get_error_code(), 'message' => $r->get_error_message() ), 200 );
	}
	// Reflect the new logged-in cookie into $_COOKIE *now* so wp_create_nonce()
	// below is bound to the new session token — otherwise the fresh nonce we
	// hand back would still fail the next request's cookie check.
	add_action( 'set_logged_in_cookie', 'emb_capture_logged_in_cookie' );
	wp_set_auth_cookie( $user->ID, true );
	wp_set_current_user( $user->ID );

	// The caller's page nonce was minted while logged out; hand back a fresh one
	// so the next REST call (e.g. ton-order) passes the cookie nonce check.
	return new WP_REST_Response( array(
		'ok'       => true,
		'verified' => true,
		'nonce'    => wp_create_nonce( 'wp_rest' ),
	), 200 );
}

function emb_capture_logged_in_cookie( $logged_in_cookie ) {
	$_COOKIE[ LOGGED_IN_COOKIE ] = $logged_in_cookie;
}

/** Logged-in verify form (fa My Account or [emb_verify]). */
function emb_rest_otp_verify( WP_REST_Request $req ) {
	$uid = get_current_user_id();
	if ( ! emb_rl_ok( 'otpverify_' . $uid, 25, 15 * MINUTE_IN_SECONDS ) ) {
		return new WP_REST_Response( array( 'ok' => false, 'error' => 'rate_limited' ), 200 );
	}
	$r = emb_otp_verify( $uid, (string) $req->get_param( 'code' ) );
	if ( is_wp_error( $r ) ) {
		return new WP_REST_Response( array( 'ok' => false, 'error' => $r->get_error_code(), 'message' => $r->get_error_message() ), 200 );
	}
	return new WP_REST_Response( array( 'ok' => true, 'verified' => true ), 200 );
}

function emb_rest_otp_resend( WP_REST_Request $req ) {
	$uid = get_current_user_id();
	if ( emb_is_verified( $uid ) ) {
		return new WP_REST_Response( array( 'ok' => true, 'verified' => true ), 200 );
	}
	list( $channel, $dest ) = emb_user_otp_target( $uid );
	if ( ! $dest ) {
		return new WP_REST_Response( array( 'ok' => false, 'error' => 'no_target' ), 200 );
	}
	$r = emb_otp_send( $uid, $channel, $dest );
	if ( is_wp_error( $r ) ) {
		return new WP_REST_Response( array( 'ok' => false, 'error' => $r->get_error_code(), 'message' => $r->get_error_message() ), 200 );
	}
	return new WP_REST_Response( array( 'ok' => true, 'channel' => $channel ), 200 );
}

/* ─────────────────────────  fa registration (WooCommerce My Account)  ───────────────────────── */

add_action( 'woocommerce_register_form', 'emb_wc_register_fields' );
function emb_wc_register_fields() {
	$val = static function ( $k ) {
		return isset( $_POST[ $k ] ) ? esc_attr( wp_unslash( $_POST[ $k ] ) ) : ''; // phpcs:ignore WordPress.Security.NonceVerification
	};
	?>
	<p class="woocommerce-form-row woocommerce-form-row--first form-row form-row-first">
		<label for="emb_first_name">نام&nbsp;<span class="required">*</span></label>
		<input type="text" class="woocommerce-Input woocommerce-Input--text input-text" name="emb_first_name" id="emb_first_name" value="<?php echo $val( 'emb_first_name' ); ?>" required />
	</p>
	<p class="woocommerce-form-row woocommerce-form-row--last form-row form-row-last">
		<label for="emb_last_name">نام خانوادگی&nbsp;<span class="required">*</span></label>
		<input type="text" class="woocommerce-Input woocommerce-Input--text input-text" name="emb_last_name" id="emb_last_name" value="<?php echo $val( 'emb_last_name' ); ?>" required />
	</p>
	<p class="woocommerce-form-row woocommerce-form-row--wide form-row form-row-wide">
		<label for="emb_phone">شمارهٔ موبایل&nbsp;<span class="required">*</span></label>
		<input type="tel" class="woocommerce-Input woocommerce-Input--text input-text" name="emb_phone" id="emb_phone" inputmode="numeric" autocomplete="tel" placeholder="09xxxxxxxxx" value="<?php echo $val( 'emb_phone' ); ?>" required />
		<small>کد تأیید با پیامک به این شماره فرستاده می‌شود.</small>
	</p>
	<p class="woocommerce-form-row woocommerce-form-row--wide form-row form-row-wide">
		<label for="emb_address">آدرس&nbsp;<span class="required">*</span></label>
		<textarea class="woocommerce-Input input-text" name="emb_address" id="emb_address" rows="2" required><?php echo $val( 'emb_address' ); ?></textarea>
	</p>
	<p class="woocommerce-form-row form-row form-row-wide emb-tos-row">
		<label class="woocommerce-form__label woocommerce-form__label-for-checkbox">
			<input type="checkbox" name="emb_tos" id="emb_tos" value="1" required <?php checked( ! empty( $_POST['emb_tos'] ) ); // phpcs:ignore WordPress.Security.NonceVerification ?> />
			<span>«<a href="<?php echo esc_url( emb_terms_url() ); ?>" target="_blank" rel="noopener">قوانین و مقررات</a>» را خوانده‌ام و می‌پذیرم.&nbsp;<span class="required">*</span></span>
		</label>
	</p>
	<?php
}

add_filter( 'woocommerce_registration_errors', 'emb_wc_register_validate', 10, 3 );
function emb_wc_register_validate( $errors, $username, $email ) {
	// phpcs:disable WordPress.Security.NonceVerification -- WooCommerce verifies its own register nonce
	$fn = sanitize_text_field( wp_unslash( $_POST['emb_first_name'] ?? '' ) );
	$ln = sanitize_text_field( wp_unslash( $_POST['emb_last_name'] ?? '' ) );
	$ad = sanitize_textarea_field( wp_unslash( $_POST['emb_address'] ?? '' ) );
	$ph = emb_normalize_phone_ir( wp_unslash( $_POST['emb_phone'] ?? '' ) );
	// phpcs:enable
	if ( '' === $fn || '' === $ln ) {
		$errors->add( 'emb_name', 'نام و نام خانوادگی لازم است.' );
	}
	if ( '' === $ad ) {
		$errors->add( 'emb_address', 'آدرس لازم است.' );
	}
	if ( '' === $ph ) {
		$errors->add( 'emb_phone', 'شمارهٔ موبایل معتبر نیست (مثل 09121234567).' );
	} elseif ( emb_phone_taken( $ph ) ) {
		$errors->add( 'emb_phone', 'این شماره قبلاً ثبت و تأیید شده است. وارد شوید.' );
	}
	if ( empty( $_POST['emb_tos'] ) ) { // phpcs:ignore WordPress.Security.NonceVerification
		$errors->add( 'emb_tos', 'برای ثبت‌نام باید «قوانین و مقررات» را بپذیرید.' );
	}
	return $errors;
}

add_action( 'woocommerce_created_customer', 'emb_wc_register_save' );
function emb_wc_register_save( $uid ) {
	// phpcs:disable WordPress.Security.NonceVerification
	$fn = sanitize_text_field( wp_unslash( $_POST['emb_first_name'] ?? '' ) );
	$ln = sanitize_text_field( wp_unslash( $_POST['emb_last_name'] ?? '' ) );
	$ad = sanitize_textarea_field( wp_unslash( $_POST['emb_address'] ?? '' ) );
	$ph = emb_normalize_phone_ir( wp_unslash( $_POST['emb_phone'] ?? '' ) );
	// phpcs:enable
	if ( '' === $ph ) {
		return; // not the fa register form (or invalid) — nothing to verify by SMS
	}
	update_user_meta( $uid, 'first_name', $fn );
	update_user_meta( $uid, 'last_name', $ln );
	update_user_meta( $uid, 'billing_first_name', $fn );
	update_user_meta( $uid, 'billing_last_name', $ln );
	update_user_meta( $uid, 'billing_phone', $ph );
	update_user_meta( $uid, 'billing_address_1', $ad );
	update_user_meta( $uid, 'emb_verify_channel', 'sms' );
	update_user_meta( $uid, 'emb_lang', 'fa' );
	emb_record_tos( $uid );
	emb_record_signup_origin( $uid );
	emb_otp_send( $uid, 'sms', $ph, 'fa' );
}

/* ─────────────────────────  verify screen (fa My Account + [emb_verify])  ───────────────────────── */

/** Replace the My Account content with the verify screen for logged-in, unverified users. */
add_action( 'template_redirect', function () {
	if ( ! function_exists( 'is_account_page' ) || ! is_account_page() ) {
		return;
	}
	if ( is_user_logged_in() && ! emb_is_verified() ) {
		add_filter( 'the_content', 'emb_account_content_gate', 99 );
	}
} );
function emb_account_content_gate( $content ) {
	return is_account_page() ? emb_verify_form_html() : $content;
}

/** Stack the WooCommerce "My Account" nav tabs (پیشخوان/سفارش‌ها/...) one per row —
 *  the theme's own layout wraps them into uneven, messy rows. CSS-only, scoped to
 *  the account page, so it can't affect anything else on the site. */
add_action( 'wp_head', function () {
	if ( ! function_exists( 'is_account_page' ) || ! is_account_page() ) {
		return;
	}
	?>
	<style>
		.woocommerce-MyAccount-navigation ul {
			display: flex !important;
			flex-direction: column !important;
			align-items: stretch !important;
			gap: 8px !important;
		}
		.woocommerce-MyAccount-navigation ul li {
			width: 100% !important;
			margin: 0 !important;
			list-style: none !important;
		}
		.woocommerce-MyAccount-navigation ul li a {
			display: block !important;
			width: 100% !important;
			box-sizing: border-box !important;
			text-align: center !important;
		}
	</style>
	<?php
} );

function emb_verify_form_html() {
	if ( ! is_user_logged_in() ) {
		return '';
	}
	$uid = get_current_user_id();
	if ( emb_is_verified( $uid ) ) {
		$en = 'en' === emb_current_lang();
		return '<div class="emb-verify is-done"><p>✅ '
			. ( $en ? 'Your account is verified.' : 'حساب شما تأیید شده است.' ) . '</p></div>';
	}
	list( $channel, $dest ) = emb_user_otp_target( $uid );
	$mask = emb_otp_mask( $channel, $dest );
	$en   = 'en' === emb_current_lang();
	// Isolate the masked phone/email in its own bidi run so it doesn't get
	// visually reordered when embedded inside the RTL Persian sentence.
	$mask_html = '<bdi dir="ltr">' . esc_html( $mask ) . '</bdi>';
	$via  = 'sms' === $channel
		? ( $en ? "SMS to {$mask_html}" : "پیامک به {$mask_html}" )
		: ( $en ? "email to {$mask_html}" : "ایمیل به {$mask_html}" );

	ob_start();
	?>
	<div class="emb-verify" data-emb-verify>
		<h2><?php echo $en ? 'Verify your account' : 'تأیید حساب'; ?></h2>
		<p><?php echo $en
			? "We sent a 6-digit code by {$via}. Enter it to activate your account and unlock purchases."
			: "کد ۶ رقمی با {$via} فرستادیم. برای فعال‌شدن حساب و امکان خرید، آن را وارد کنید."; ?></p>
		<label class="emb-verify__field"><span><?php echo $en ? 'Verification code' : 'کد تأیید'; ?></span>
			<input type="text" inputmode="numeric" autocomplete="one-time-code" maxlength="6" data-emb-code placeholder="------">
		</label>
		<p class="emb-verify__err" role="alert" hidden></p>
		<button type="button" class="button emb-verify__go"><?php echo $en ? 'Verify' : 'تأیید'; ?></button>
		<p class="emb-verify__meta">
			<a href="#" data-emb-resend><?php echo $en ? "Didn't get it? Resend" : 'کد را نگرفتید؟ ارسال دوباره'; ?></a>
			&nbsp;·&nbsp;
			<a href="<?php echo esc_url( wp_logout_url( home_url( $en ? '/en/' : '/' ) ) ); ?>"><?php echo $en ? 'Sign out' : 'خروج از حساب'; ?></a>
		</p>
	</div>
	<?php
	return ob_get_clean();
}

add_shortcode( 'emb_verify', 'emb_verify_form_html' );

/* ─────────────────────────  [emb_auth] — /en/ sign-in + fa fallback  ───────────────────────── */

add_shortcode( 'emb_auth', function () {
	$en = 'en' === emb_current_lang();

	if ( is_user_logged_in() ) {
		if ( ! emb_is_verified() ) {
			return emb_verify_form_html();
		}
		$u   = wp_get_current_user();
		$out = 'en' === emb_current_lang() ? 'Signed in as ' : 'واردشده با ';
		return '<div class="emb-auth is-in"><p>' . esc_html( $out ) . '<strong>' . esc_html( $u->user_email ) . '</strong>'
			. ' · <a href="' . esc_url( wp_logout_url( home_url( $en ? '/en/' : '/' ) ) ) . '">'
			. ( $en ? 'Sign out' : 'خروج' ) . '</a></p></div>';
	}

	if ( ! $en ) {
		// fa: WooCommerce My Account handles login + register
		return '<div class="emb-auth"><p>برای ورود یا ثبت‌نام به صفحهٔ حساب کاربری بروید.</p>'
			. '<p><a class="button" href="' . esc_url( wc_get_page_permalink( 'myaccount' ) ) . '">ورود / ثبت‌نام</a></p></div>';
	}

	// en: passwordless email code
	ob_start();
	?>
	<div class="emb-auth" data-emb-auth>
		<p>No password. Enter your email and we'll send a one-time code.</p>
		<div data-emb-auth-step="email">
			<label class="emb-auth__field"><span>Email</span>
				<input type="email" inputmode="email" autocomplete="email" data-emb-auth-email placeholder="you@example.com">
			</label>
			<label class="emb-auth__tos"><input type="checkbox" data-emb-auth-tos> I agree to the <a href="<?php echo esc_url( emb_terms_url() ); ?>" target="_blank" rel="noopener">Terms of Service</a>.</label>
			<button type="button" class="button emb-auth__go" data-emb-auth-send>Email me a code</button>
		</div>
		<div data-emb-auth-step="code" hidden>
			<label class="emb-auth__field"><span>Code</span>
				<input type="text" inputmode="numeric" autocomplete="one-time-code" maxlength="6" data-emb-auth-code placeholder="------">
			</label>
			<button type="button" class="button emb-auth__go" data-emb-auth-verify>Verify &amp; sign in</button>
			<p class="emb-auth__meta"><a href="#" data-emb-auth-restart>Use a different email</a></p>
		</div>
		<p class="emb-auth__err" role="alert" hidden></p>
	</div>
	<?php
	return ob_get_clean();
} );

/* ─────────────────────────  [emb_account_link] — header  ───────────────────────── */

add_shortcode( 'emb_account_link', function () {
	$en      = 'en' === emb_current_lang();
	$account = function_exists( 'wc_get_page_permalink' ) ? wc_get_page_permalink( 'myaccount' ) : home_url( '/my-account/' );

	if ( ! is_user_logged_in() ) {
		$href = $en ? ( home_url( '/en/' ) . '#account' ) : $account;
		return '<a class="emb-nav__item emb-account-link" href="' . esc_url( $href ) . '">'
			. ( $en ? 'Sign in' : 'ورود / ثبت‌نام' ) . '</a>';
	}
	if ( ! emb_is_verified() ) {
		$href = $en ? ( home_url( '/en/' ) . '#account' ) : $account;
		return '<a class="emb-nav__item emb-account-link is-unverified" href="' . esc_url( $href ) . '">'
			. ( $en ? 'Verify account' : 'تأیید حساب' ) . '</a>';
	}
	if ( $en ) {
		return '<a class="emb-nav__item emb-account-link" href="' . esc_url( wp_logout_url( home_url( '/en/' ) ) ) . '">Sign out</a>';
	}
	return '<a class="emb-nav__item emb-account-link" href="' . esc_url( $account ) . '">حساب من</a>';
} );

/* ─────────────────────────  purchase gate  ───────────────────────── */

/** fa: bounce cart / checkout for logged-out or unverified visitors. */
add_action( 'template_redirect', function () {
	if ( ! function_exists( 'is_cart' ) || ( ! is_cart() && ! is_checkout() ) ) {
		return;
	}
	if ( is_wc_endpoint_url( 'order-received' ) ) {
		return; // don't trap the thank-you page
	}
	$account = wc_get_page_permalink( 'myaccount' );
	if ( ! is_user_logged_in() ) {
		wp_safe_redirect( add_query_arg( 'emb_login', 'buy', $account ) );
		exit;
	}
	if ( ! emb_is_verified() ) {
		wp_safe_redirect( $account );
		exit;
	}
}, 5 );

/** fa: hard stop at checkout submission, just in case. */
add_action( 'woocommerce_checkout_process', function () {
	if ( ! is_user_logged_in() || ! emb_is_verified() ) {
		wc_add_notice( 'برای تکمیل خرید باید وارد حساب کاربری تأییدشده شوید.', 'error' );
	}
} );

/** A friendly banner on My Account when the visitor was sent there to log in. */
add_action( 'woocommerce_before_customer_login_form', function () {
	if ( isset( $_GET['emb_login'] ) && 'buy' === $_GET['emb_login'] ) { // phpcs:ignore WordPress.Security.NonceVerification
		wc_print_notice( 'برای خرید پلن، اول وارد شوید یا ثبت‌نام کنید.', 'notice' );
	}
} );

/* ─────────────────────────  admin: identity / forensic panels  ───────────────────────── */

/** User profile — a read-only "easymakebot identity" block for abuse handling. */
function emb_admin_user_identity_block( $user ) {
	if ( ! current_user_can( 'edit_users' ) ) {
		return;
	}
	$uid  = $user->ID;
	$tos  = get_user_meta( $uid, 'emb_tos', true );
	$rows = array(
		'وضعیت تأیید'      => emb_is_verified( $uid ) ? 'تأییدشده (' . esc_html( get_user_meta( $uid, 'emb_verify_channel', true ) ?: '—' ) . ')' : 'تأییدنشده',
		'موبایل'          => esc_html( get_user_meta( $uid, 'billing_phone', true ) ?: '—' ),
		'IP ثبت‌نام'       => esc_html( get_user_meta( $uid, 'emb_signup_ip', true ) ?: '—' ),
		'کشور ثبت‌نام'     => esc_html( get_user_meta( $uid, 'emb_signup_country', true ) ?: '—' ),
		'زمان ثبت‌نام'     => esc_html( get_user_meta( $uid, 'emb_signup_at', true ) ?: '—' ),
		'پذیرش شرایط'      => is_array( $tos ) ? esc_html( "v{$tos['v']} · {$tos['at']} · {$tos['ip']} · {$tos['cc']}" ) : '—',
	);
	echo '<h2>easymakebot — شناسه</h2><table class="form-table" role="presentation"><tbody>';
	foreach ( $rows as $k => $v ) {
		echo '<tr><th>' . esc_html( $k ) . '</th><td>' . $v . '</td></tr>'; // phpcs:ignore WordPress.Security.EscapeOutput
	}
	echo '</tbody></table>';
}
add_action( 'show_user_profile', 'emb_admin_user_identity_block' );
add_action( 'edit_user_profile', 'emb_admin_user_identity_block' );

/** Order screen — buyer origin + crypto sender + redeemer, for abuse handling. */
add_action( 'woocommerce_admin_order_data_after_billing_address', function ( $order ) {
	$fields = array(
		'IP خریدار'        => $order->get_meta( '_emb_buyer_ip' ) ?: $order->get_customer_ip_address(),
		'کشور خریدار'      => $order->get_meta( '_emb_buyer_country' ),
		'کیف‌پول فرستنده'  => $order->get_meta( '_emb_ton_sender' ),
		'tx کریپتو'        => $order->get_meta( '_emb_ton_txid' ),
		'تلگرام واردکننده' => trim( ( $order->get_meta( '_emb_redeemer_username' ) ? '@' . $order->get_meta( '_emb_redeemer_username' ) . ' ' : '' ) . ( $order->get_meta( '_emb_redeemer_tg' ) ? '(' . $order->get_meta( '_emb_redeemer_tg' ) . ')' : '' ) ),
		'تلفن واردکننده'   => $order->get_meta( '_emb_redeemer_phone' ),
	);
	$fields = array_filter( $fields, static function ( $v ) { return '' !== (string) $v; } );
	if ( ! $fields ) {
		return;
	}
	echo '<div class="address"><p><strong>easymakebot — ردیابی تخلف</strong></p>';
	foreach ( $fields as $k => $v ) {
		echo '<p>' . esc_html( $k ) . ': <code>' . esc_html( $v ) . '</code></p>';
	}
	echo '</div>';
} );

/* ─────────────────────────  settings page (SMS driver)  ───────────────────────── */

add_action( 'admin_menu', function () {
	add_options_page( 'easymakebot', 'easymakebot', 'manage_options', 'easymakebot-accounts', 'emb_accounts_settings_page' );
} );

function emb_accounts_settings_page() {
	if ( ! current_user_can( 'manage_options' ) ) {
		return;
	}
	if ( isset( $_POST['emb_accounts_nonce'] ) && wp_verify_nonce( sanitize_text_field( wp_unslash( $_POST['emb_accounts_nonce'] ) ), 'emb_accounts_save' ) ) {
		$posted_driver = (string) ( $_POST['emb_sms_driver'] ?? '' );
		$driver        = in_array( $posted_driver, array( 'kavenegar', 'asanak' ), true ) ? $posted_driver : 'log';
		update_option( 'emb_sms_driver', $driver );
		update_option( 'emb_sms_kavenegar_key', sanitize_text_field( wp_unslash( $_POST['emb_sms_kavenegar_key'] ?? '' ) ) );
		update_option( 'emb_sms_kavenegar_template', sanitize_text_field( wp_unslash( $_POST['emb_sms_kavenegar_template'] ?? '' ) ) );
		update_option( 'emb_sms_asanak_username', sanitize_text_field( wp_unslash( $_POST['emb_sms_asanak_username'] ?? '' ) ) );
		update_option( 'emb_sms_asanak_password', sanitize_text_field( wp_unslash( $_POST['emb_sms_asanak_password'] ?? '' ) ) );
		update_option( 'emb_sms_asanak_source', sanitize_text_field( wp_unslash( $_POST['emb_sms_asanak_source'] ?? '' ) ) );
		// eNamad snippet — store raw; [emb_enamad] runs it through wp_kses on output.
		update_option( 'emb_enamad_code', trim( (string) wp_unslash( $_POST['emb_enamad_code'] ?? '' ) ) );
		echo '<div class="notice notice-success is-dismissible"><p>ذخیره شد.</p></div>';
	}
	$driver      = emb_sms_driver();
	$key         = get_option( 'emb_sms_kavenegar_key', '' );
	$tpl         = get_option( 'emb_sms_kavenegar_template', '' );
	$asanak_user = get_option( 'emb_sms_asanak_username', '' );
	$asanak_pass = get_option( 'emb_sms_asanak_password', '' );
	$asanak_src  = get_option( 'emb_sms_asanak_source', '' );
	$enamad      = get_option( 'emb_enamad_code', '' );
	?>
	<div class="wrap">
		<h1>easymakebot — تأیید حساب / پیامک</h1>
		<p>کد تأیید موبایل کاربران ایرانی از این سرویس فرستاده می‌شود. تا وقتی روی «log» است،
			کد فقط در فایل <code>wp-content/uploads/emb-sms.log</code> نوشته می‌شود (برای تست).</p>
		<form method="post">
			<?php wp_nonce_field( 'emb_accounts_save', 'emb_accounts_nonce' ); ?>
			<table class="form-table" role="presentation">
				<tr>
					<th scope="row"><label for="emb_sms_driver">درایور پیامک</label></th>
					<td>
						<select name="emb_sms_driver" id="emb_sms_driver">
							<option value="log" <?php selected( $driver, 'log' ); ?>>log (تست — بدون ارسال واقعی)</option>
							<option value="kavenegar" <?php selected( $driver, 'kavenegar' ); ?>>Kavenegar (کاوه‌نگار)</option>
							<option value="asanak" <?php selected( $driver, 'asanak' ); ?>>Asanak (آسانک)</option>
						</select>
					</td>
				</tr>
				<tr>
					<th scope="row"><label for="emb_sms_kavenegar_key">Kavenegar API Key</label></th>
					<td><input type="password" class="regular-text" name="emb_sms_kavenegar_key" id="emb_sms_kavenegar_key" value="<?php echo esc_attr( $key ); ?>" autocomplete="off" />
						<p class="description">از پنل کاوه‌نگار › حساب کاربری › کلید وب‌سرویس.</p></td>
				</tr>
				<tr>
					<th scope="row"><label for="emb_sms_kavenegar_template">نام الگو (template)</label></th>
					<td><input type="text" class="regular-text" name="emb_sms_kavenegar_template" id="emb_sms_kavenegar_template" value="<?php echo esc_attr( $tpl ); ?>" placeholder="embverify" />
						<p class="description">همان نام انگلیسی الگوی تأییدشده در پنل کاوه‌نگار (متد verify/lookup).</p></td>
				</tr>
				<tr>
					<th scope="row"><label for="emb_sms_asanak_username">نام کاربری آسانک</label></th>
					<td><input type="text" class="regular-text" name="emb_sms_asanak_username" id="emb_sms_asanak_username" value="<?php echo esc_attr( $asanak_user ); ?>" dir="ltr" autocomplete="off" />
						<p class="description">نام کاربری وب‌سرویس پنل آسانک.</p></td>
				</tr>
				<tr>
					<th scope="row"><label for="emb_sms_asanak_password">رمز عبور آسانک</label></th>
					<td><input type="password" class="regular-text" name="emb_sms_asanak_password" id="emb_sms_asanak_password" value="<?php echo esc_attr( $asanak_pass ); ?>" dir="ltr" autocomplete="off" />
						<p class="description">رمز عبور وب‌سرویس پنل آسانک.</p></td>
				</tr>
				<tr>
					<th scope="row"><label for="emb_sms_asanak_source">شماره خط اختصاصی OTP (source)</label></th>
					<td><input type="text" class="regular-text" name="emb_sms_asanak_source" id="emb_sms_asanak_source" value="<?php echo esc_attr( $asanak_src ); ?>" dir="ltr" placeholder="98998207650" />
						<p class="description">همان شماره اختصاصی خط OTP که در پنل آسانک نشان داده می‌شود.</p></td>
				</tr>
				<tr>
					<th scope="row"><label for="emb_enamad_code">کد نماد اعتماد (اینماد)</label></th>
					<td><textarea class="large-text code" rows="4" name="emb_enamad_code" id="emb_enamad_code" dir="ltr"><?php echo esc_textarea( $enamad ); ?></textarea>
						<p class="description">کد <code>&lt;a&gt;…&lt;img&gt;…&lt;/a&gt;</code> که اینماد بعد از تأیید می‌دهد را اینجا بچسبان — خودکار در فوتر سایت نمایش داده می‌شود.</p></td>
				</tr>
			</table>
			<?php submit_button( 'ذخیره' ); ?>
		</form>
	</div>
	<?php
}
