<?php
/**
 * Plugin Name: easymakebot — Zarinpal proxy (bot payments)
 * Description: Lets the @easymakebot bot process (which runs on the German
 *              server) call Zarinpal through this Iran-hosted site instead
 *              of calling Zarinpal directly. Zarinpal routinely breaks a
 *              PaymentRequest/PaymentVerification call that originates from
 *              a foreign IP, especially combined with an Iranian buyer's own
 *              VPN — this endpoint makes the outbound call FROM Iran and
 *              just relays the JSON back, so the bot's own Zarinpal code
 *              (bot/shop.py: _zarinpal_request / _zarinpal_verify) doesn't
 *              have to change its parsing at all, only its target URL.
 *
 *              Used for BOTH money flows that already share that same code:
 *              a bot owner paying the platform for /live (bot/platform_billing.py)
 *              and a built bot's own shop taking payment from ITS customers
 *              (bot/shop.py) — enabling this fixes Zarinpal reliability for
 *              both at once.
 *
 * Security: only ever forwards to Zarinpal's own fixed API hosts below —
 *           the caller cannot pass an arbitrary target URL (no SSRF). Auth
 *           is the same shared-secret pattern as emb-activation-codes.php.
 *
 * REST:
 *   POST /wp-json/emb/v1/zarinpal/request   {merchant_id, amount, description, callback_url}   header X-EMB-Key
 *   POST /wp-json/emb/v1/zarinpal/verify    {merchant_id, amount, authority}                     header X-EMB-Key
 *   Both return Zarinpal's own JSON response unchanged (pass-through), plus
 *   an "ok" wrapper flag; the bot decides success/failure from that body,
 *   exactly like it does when it calls Zarinpal directly.
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

const EMB_ZP_REQUEST_URL = 'https://api.zarinpal.com/pg/v4/payment/request.json';
const EMB_ZP_VERIFY_URL  = 'https://api.zarinpal.com/pg/v4/payment/verify.json';

function emb_zp_proxy_key() {
	$k = getenv( 'EMB_ZARINPAL_PROXY_KEY' );
	if ( ! $k && defined( 'EMB_ZARINPAL_PROXY_KEY' ) ) {
		$k = EMB_ZARINPAL_PROXY_KEY;
	}
	return is_string( $k ) ? trim( $k ) : '';
}

function emb_zp_rest_auth( WP_REST_Request $req ) {
	$key = emb_zp_proxy_key();
	if ( '' === $key ) {
		return new WP_Error( 'emb_zp_no_key', 'Zarinpal proxy key not configured on the server.', array( 'status' => 503 ) );
	}
	$given = trim( (string) $req->get_header( 'x-emb-key' ) );
	if ( ! hash_equals( $key, $given ) ) {
		return new WP_Error( 'emb_zp_forbidden', 'Bad key.', array( 'status' => 403 ) );
	}
	// Light throttle, same shape as emb-activation-codes.php — this endpoint
	// moves real money, so a stolen/leaked key still can't be hammered.
	$ip  = preg_replace( '/[^0-9a-f:.]/i', '', (string) ( $_SERVER['REMOTE_ADDR'] ?? '' ) );
	$k   = 'emb_zp_rl_' . md5( $ip );
	$hit = (int) get_transient( $k );
	if ( $hit >= 60 ) {
		return new WP_Error( 'emb_zp_rate', 'Too many requests.', array( 'status' => 429 ) );
	}
	set_transient( $k, $hit + 1, 5 * MINUTE_IN_SECONDS );
	return true;
}

/** Forwards $payload to $url and relays Zarinpal's JSON body back verbatim
 * (wrapped with ok=true) — or {ok:false, error:"..."} on a transport failure,
 * a shape the bot side treats the same way it treats its own network
 * exceptions when calling Zarinpal directly. */
function emb_zp_forward( $url, array $payload ) {
	$response = wp_remote_post( $url, array(
		'timeout' => 15,
		'headers' => array( 'Content-Type' => 'application/json', 'Accept' => 'application/json' ),
		'body'    => wp_json_encode( $payload ),
	) );

	if ( is_wp_error( $response ) ) {
		return new WP_REST_Response( array( 'ok' => false, 'error' => 'network', 'detail' => $response->get_error_message() ), 200 );
	}

	$code = wp_remote_retrieve_response_code( $response );
	$body = json_decode( wp_remote_retrieve_body( $response ), true );
	if ( ! is_array( $body ) ) {
		return new WP_REST_Response( array( 'ok' => false, 'error' => 'bad_response', 'http_status' => $code ), 200 );
	}

	$body['ok'] = true;
	return new WP_REST_Response( $body, 200 );
}

add_action( 'rest_api_init', function () {
	register_rest_route( 'emb/v1', '/zarinpal/request', array(
		'methods'             => 'POST',
		'permission_callback' => 'emb_zp_rest_auth',
		'callback'            => function ( WP_REST_Request $req ) {
			$merchant_id = (string) $req->get_param( 'merchant_id' );
			$amount      = (int) $req->get_param( 'amount' );
			$description = (string) $req->get_param( 'description' );
			$callback    = (string) $req->get_param( 'callback_url' );
			if ( '' === $merchant_id || $amount <= 0 || '' === $callback ) {
				return new WP_REST_Response( array( 'ok' => false, 'error' => 'bad_params' ), 200 );
			}
			return emb_zp_forward( EMB_ZP_REQUEST_URL, array(
				'merchant_id'  => $merchant_id,
				'amount'       => $amount,
				'description'  => $description,
				'callback_url' => $callback,
			) );
		},
		'args' => array(
			'merchant_id'  => array( 'required' => true ),
			'amount'       => array( 'required' => true ),
			'description'  => array( 'required' => false ),
			'callback_url' => array( 'required' => true ),
		),
	) );

	register_rest_route( 'emb/v1', '/zarinpal/verify', array(
		'methods'             => 'POST',
		'permission_callback' => 'emb_zp_rest_auth',
		'callback'            => function ( WP_REST_Request $req ) {
			$merchant_id = (string) $req->get_param( 'merchant_id' );
			$amount      = (int) $req->get_param( 'amount' );
			$authority   = (string) $req->get_param( 'authority' );
			if ( '' === $merchant_id || $amount <= 0 || '' === $authority ) {
				return new WP_REST_Response( array( 'ok' => false, 'error' => 'bad_params' ), 200 );
			}
			return emb_zp_forward( EMB_ZP_VERIFY_URL, array(
				'merchant_id' => $merchant_id,
				'amount'      => $amount,
				'authority'   => $authority,
			) );
		},
		'args' => array(
			'merchant_id' => array( 'required' => true ),
			'amount'      => array( 'required' => true ),
			'authority'   => array( 'required' => true ),
		),
	) );
} );
