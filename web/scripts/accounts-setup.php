<?php
/**
 * Phase 4c — site accounts & verified purchase. Idempotent.
 *   docker compose run --rm wpcli wp eval-file /scripts/accounts-setup.php
 *
 * The Kavenegar API key + template are NOT set here — the operator adds them in
 *   wp-admin › Settings › easymakebot
 * once the Kavenegar account is verified and the OTP template is approved.
 * Until then the SMS driver stays "log" (code written to
 *   wp-content/uploads/emb-sms.log ).
 */

if ( ! defined( 'WP_CLI' ) ) { exit; }

/* ── 1. accounts on, guests off ─────────────────────────────────────── */
if ( class_exists( 'WooCommerce' ) ) {
	update_option( 'woocommerce_enable_myaccount_registration', 'yes' );
	update_option( 'woocommerce_enable_guest_checkout', 'no' );
	update_option( 'woocommerce_enable_signup_and_login_from_checkout', 'yes' );
	// fa users choose their own password on the register form
	update_option( 'woocommerce_registration_generate_password', 'no' );
} else {
	WP_CLI::warning( 'WooCommerce inactive — My Account registration not toggled.' );
}

/* ── 2. SMS driver default ──────────────────────────────────────────── */
if ( ! get_option( 'emb_sms_driver' ) ) {
	update_option( 'emb_sms_driver', getenv( 'EMB_SMS_DRIVER' ) ?: 'log' );
}
WP_CLI::log( '  emb_sms_driver = ' . get_option( 'emb_sms_driver' ) );
if ( getenv( 'EMB_SMS_API_KEY' ) && ! get_option( 'emb_sms_kavenegar_key' ) ) {
	update_option( 'emb_sms_kavenegar_key', trim( getenv( 'EMB_SMS_API_KEY' ) ) );
}
if ( getenv( 'EMB_SMS_TEMPLATE' ) && ! get_option( 'emb_sms_kavenegar_template' ) ) {
	update_option( 'emb_sms_kavenegar_template', trim( getenv( 'EMB_SMS_TEMPLATE' ) ) );
}

/* ── 3. never lock staff out — mark them verified + ToS-accepted ────── */
$staff = get_users( array( 'role__in' => array( 'administrator', 'shop_manager' ), 'fields' => 'ID' ) );
$tos_v = defined( 'EMB_TOS_VERSION' ) ? EMB_TOS_VERSION : gmdate( 'Y-m-d' );
foreach ( $staff as $uid ) {
	update_user_meta( $uid, 'emb_verified', '1' );
	update_user_meta( $uid, 'emb_verify_channel', 'staff' );
	if ( ! get_user_meta( $uid, 'emb_tos', true ) ) {
		update_user_meta( $uid, 'emb_tos', array( 'v' => $tos_v, 'at' => gmdate( 'c' ), 'ip' => '', 'cc' => '' ) );
	}
}
WP_CLI::log( '  marked ' . count( $staff ) . ' staff account(s) verified' );

/* ── 3b. Terms of Service page (fa + en) ───────────────────────────── */
$terms_fa = <<<'HTML'
<!-- wp:heading --><h2 class="wp-block-heading">شرایط استفاده از easymakebot</h2><!-- /wp:heading -->
<!-- wp:paragraph --><p>با ساختن حساب کاربری یا خرید پلن، این شرایط را می‌پذیری.</p><!-- /wp:paragraph -->
<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">۱. استفادهٔ مجاز</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>سرویس فقط برای ساخت و اجرای ربات‌های قانونی است. این موارد ممنوع‌اند و حساب مربوطه بدون اطلاع قبلی مسدود می‌شود: کلاهبرداری و پانزی و طرح‌های پولی فریب‌کارانه؛ فیشینگ و سرقت اطلاعات؛ هرزنامه و ارسال انبوه ناخواسته؛ فروش کالا یا خدمات غیرقانونی؛ محتوای مجرمانه؛ جعل هویت اشخاص یا سازمان‌ها؛ بدافزار؛ نقض حقوق دیگران.</p><!-- /wp:paragraph -->
<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">۲. مسئولیت کاربر</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>مسئولیت کاملِ ربات‌هایی که می‌سازی و هر محتوا و تراکنشی که از طریق آن‌ها انجام می‌شود، فقط با توست. easymakebot صرفاً بستر فنی است و طرف معاملهٔ تو با کاربران رباتت نیست.</p><!-- /wp:paragraph -->
<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">۳. شناسه‌ها و همکاری قانونی</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>برای جلوگیری از سوءاستفاده، این اطلاعات ثبت و نگه‌داری می‌شود: شناسه و نام کاربری تلگرام، شمارهٔ موبایلِ تأییدشده، نشانی ایمیل، نشانی IP و کشورِ ثبت‌نام و خرید، و ردِ پرداخت (کد رهگیری درگاه یا شناسهٔ تراکنش و کیف‌پول در پرداخت رمزارزی). در صورت گزارش تخلف یا درخواست قانونیِ مراجع صالح (از جمله پلیس فتا و مراجع قضایی)، این اطلاعات در اختیار آن‌ها قرار می‌گیرد.</p><!-- /wp:paragraph -->
<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">۴. تعلیق و لغو</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>در صورت مشکوک‌شدن به تخلف، easymakebot می‌تواند ربات یا حساب را فوراً و بدون اطلاع قبلی آفلاین یا مسدود کند. در این حالت وجه پرداخت‌شده بازگردانده نمی‌شود.</p><!-- /wp:paragraph -->
<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">۵. سلب مسئولیت</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>سرویس «همان‌طور که هست» ارائه می‌شود. easymakebot مسئول خسارت‌های ناشی از استفادهٔ تو یا کاربران رباتت نیست.</p><!-- /wp:paragraph -->
<!-- wp:paragraph --><p><em>این نسخه از تاریخ درج‌شده معتبر است. تغییرات بعدی از همین صفحه اعلام می‌شود و ممکن است پذیرش دوباره لازم باشد.</em></p><!-- /wp:paragraph -->
HTML;

$terms_en = <<<'HTML'
<!-- wp:heading --><h2 class="wp-block-heading">easymakebot Terms of Service</h2><!-- /wp:heading -->
<!-- wp:paragraph --><p>By creating an account or buying a plan you accept these terms.</p><!-- /wp:paragraph -->
<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">1. Acceptable use</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>The service is for building and running lawful bots only. The following are prohibited and will get the account suspended without notice: fraud, Ponzi or deceptive money schemes; phishing or credential theft; spam or unsolicited bulk messaging; selling illegal goods or services; criminal content; impersonating people or organisations; malware; infringing others' rights.</p><!-- /wp:paragraph -->
<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">2. Your responsibility</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>You are solely responsible for the bots you build and for every message and transaction made through them. easymakebot is only the technical platform and is not a party to your dealings with your bots' users.</p><!-- /wp:paragraph -->
<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">3. Identifiers &amp; legal cooperation</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>To prevent abuse we record and retain: your Telegram ID and username, your verified phone number, your email, the IP address and country of sign-up and purchase, and the payment trail (gateway reference, or transaction hash and wallet for crypto). On an abuse report or a lawful request from a competent authority, this information is provided to them.</p><!-- /wp:paragraph -->
<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">4. Suspension &amp; termination</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>If abuse is suspected, easymakebot may take a bot or account offline immediately and without notice. No refund is given in that case.</p><!-- /wp:paragraph -->
<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">5. Disclaimer</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>The service is provided "as is". easymakebot is not liable for losses arising from your use or your bots' users.</p><!-- /wp:paragraph -->
<!-- wp:paragraph --><p><em>This version is effective from its published date. Later changes are announced on this page and may require re-acceptance.</em></p><!-- /wp:paragraph -->
HTML;

$terms = get_page_by_path( 'terms' );
if ( ! $terms ) {
	$tid = wp_insert_post( array(
		'post_type'    => 'page',
		'post_status'  => 'publish',
		'post_title'   => 'شرایط استفاده',
		'post_name'    => 'terms',
		'post_content' => $terms_fa,
	) );
	if ( $tid && ! is_wp_error( $tid ) ) {
		update_post_meta( $tid, '_genesis_title', 'شرایط استفاده — easymakebot' );
		if ( function_exists( 'pll_set_post_language' ) ) {
			pll_set_post_language( $tid, 'fa' );
			// EN translation so /en/ links resolve
			$ten = wp_insert_post( array(
				'post_type'    => 'page',
				'post_status'  => 'publish',
				'post_title'   => 'Terms of Service',
				'post_name'    => 'terms-en',
				'post_content' => $terms_en,
			) );
			if ( $ten && ! is_wp_error( $ten ) ) {
				pll_set_post_language( $ten, 'en' );
				if ( function_exists( 'pll_save_post_translations' ) ) {
					pll_save_post_translations( array( 'fa' => $tid, 'en' => $ten ) );
				}
			}
		}
		WP_CLI::log( "  created /terms/ page #{$tid}" );
	}
} else {
	WP_CLI::log( '  /terms/ page: exists' );
}

/* ── 3c. Privacy policy page (fa + en) ─────────────────────────────── */
$priv_fa = <<<'HTML'
<!-- wp:heading --><h2 class="wp-block-heading">حریم خصوصی easymakebot</h2><!-- /wp:heading -->
<!-- wp:paragraph --><p>این صفحه می‌گوید چه اطلاعاتی جمع می‌کنیم، چرا، و چه مدت نگه می‌داریم.</p><!-- /wp:paragraph -->
<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">۱. چه چیزی جمع می‌کنیم</h3><!-- /wp:heading -->
<!-- wp:list --><ul class="wp-block-list"><li>حساب: نام و نام‌خانوادگی، ایمیل، شمارهٔ موبایل، آدرس (کاربران ایران).</li><li>تأیید هویت: کد یک‌بارمصرف پیامکی یا ایمیلی و زمان تأیید.</li><li>فنی: نشانی IP و کشورِ ثبت‌نام و خرید، و زمان پذیرش «شرایط استفاده».</li><li>پرداخت: کد رهگیری درگاه، یا شناسهٔ تراکنش و آدرس کیف‌پول در پرداخت رمزارزی. اطلاعات کارت بانکی هرگز روی سرور ما ذخیره نمی‌شود.</li><li>هنگام فعال‌سازی ربات: شناسه و نام کاربری تلگرام و شمارهٔ تأییدشده‌ی تلگرام.</li></ul><!-- /wp:list -->
<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">۲. چرا</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>برای ارائهٔ سرویس، پردازش پرداخت، پشتیبانی، و جلوگیری از سوءاستفاده و کلاهبرداری. اطلاعات هویتی و پرداخت فقط در صورت گزارش تخلف یا درخواست قانونی مراجع صالح در اختیار آن‌ها قرار می‌گیرد.</p><!-- /wp:paragraph -->
<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">۳. اشتراک‌گذاری با دیگران</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>اطلاعات شما را نمی‌فروشیم. فقط با سرویس‌دهنده‌های لازم برای کارکرد سرویس (درگاه پرداخت، سرویس پیامک، میزبان) و در صورت الزام قانونی به اشتراک می‌گذاریم.</p><!-- /wp:paragraph -->
<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">۴. نگه‌داری</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>تا زمانی که حساب فعال است و پس از آن به‌اندازهٔ لازم برای تعهدات قانونی، مالی و رسیدگی به تخلف. IP و لاگ‌های امنیتی برای بازهٔ محدود نگه داشته می‌شوند.</p><!-- /wp:paragraph -->
<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">۵. حقوق شما</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>برای مشاهده، اصلاح یا حذف اطلاعات حسابت، یا سؤال دربارهٔ این سیاست، در تلگرام به <strong>@easymakebot</strong> پیام بده.</p><!-- /wp:paragraph -->
HTML;

$priv_en = <<<'HTML'
<!-- wp:heading --><h2 class="wp-block-heading">easymakebot Privacy Policy</h2><!-- /wp:heading -->
<!-- wp:paragraph --><p>This page explains what we collect, why, and how long we keep it.</p><!-- /wp:paragraph -->
<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">1. What we collect</h3><!-- /wp:heading -->
<!-- wp:list --><ul class="wp-block-list"><li>Account: first and last name, email, phone number, address (Iranian users).</li><li>Verification: the one-time SMS or email code and the time you verified.</li><li>Technical: the IP address and country of sign-up and purchase, and the time you accepted the Terms of Service.</li><li>Payment: the gateway reference, or the transaction hash and wallet address for crypto. Card details never touch our server.</li><li>At bot activation: your Telegram ID and username and your Telegram-verified phone number.</li></ul><!-- /wp:list -->
<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">2. Why</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>To provide the service, process payments, offer support, and prevent abuse and fraud. Identity and payment data is disclosed only on an abuse report or a lawful request from a competent authority.</p><!-- /wp:paragraph -->
<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">3. Sharing</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>We do not sell your data. We share it only with the providers needed to run the service (payment gateway, SMS provider, host) and where legally required.</p><!-- /wp:paragraph -->
<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">4. Retention</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>While your account is active, and after that only as long as needed for legal, financial and abuse-handling obligations. IPs and security logs are kept for a limited period.</p><!-- /wp:paragraph -->
<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">5. Your rights</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>To see, correct or delete your account data, or to ask about this policy, message <strong>@easymakebot</strong> on Telegram.</p><!-- /wp:paragraph -->
HTML;

if ( ! get_page_by_path( 'privacy' ) ) {
	$pid = wp_insert_post( array(
		'post_type'    => 'page',
		'post_status'  => 'publish',
		'post_title'   => 'حریم خصوصی',
		'post_name'    => 'privacy',
		'post_content' => $priv_fa,
	) );
	if ( $pid && ! is_wp_error( $pid ) ) {
		update_post_meta( $pid, '_genesis_title', 'حریم خصوصی — easymakebot' );
		if ( function_exists( 'pll_set_post_language' ) ) {
			pll_set_post_language( $pid, 'fa' );
			$pen = wp_insert_post( array(
				'post_type'    => 'page',
				'post_status'  => 'publish',
				'post_title'   => 'Privacy Policy',
				'post_name'    => 'privacy-en',
				'post_content' => $priv_en,
			) );
			if ( $pen && ! is_wp_error( $pen ) ) {
				pll_set_post_language( $pen, 'en' );
				if ( function_exists( 'pll_save_post_translations' ) ) {
					pll_save_post_translations( array( 'fa' => $pid, 'en' => $pen ) );
				}
			}
		}
		// Point WordPress's own "privacy policy page" setting at ours.
		update_option( 'wp_page_for_privacy_policy', $pid );
		WP_CLI::log( "  created /privacy/ page #{$pid}" );
	}
} else {
	WP_CLI::log( '  /privacy/ page: exists' );
}

/* ── 4. fa fallback verify page (no-JS visitors / bookmark) ─────────── */
if ( ! get_page_by_path( 'verify' ) ) {
	$vid = wp_insert_post( array(
		'post_type'    => 'page',
		'post_status'  => 'publish',
		'post_title'   => 'تأیید حساب',
		'post_name'    => 'verify',
		'post_content' => '<!-- wp:shortcode -->[emb_verify]<!-- /wp:shortcode -->',
	) );
	if ( $vid && ! is_wp_error( $vid ) ) {
		if ( function_exists( 'pll_set_post_language' ) ) { pll_set_post_language( $vid, 'fa' ); }
		WP_CLI::log( "  created /verify/ page #{$vid}" );
	}
} else {
	WP_CLI::log( '  /verify/ page: exists' );
}

if ( function_exists( 'wp_cache_flush' ) ) { wp_cache_flush(); }
flush_rewrite_rules();
WP_CLI::success( 'accounts setup done — set the Kavenegar key in wp-admin › Settings › easymakebot when ready' );
