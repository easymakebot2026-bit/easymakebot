<?php
/**
 * eNamad (نماد اعتماد الکترونیکی) — the Persian pages the review requires:
 * درباره ما، تماس با ما، قوانین و مقررات (restructured), حریم خصوصی (already exists).
 * Idempotent.  docker compose run --rm wpcli wp eval-file /scripts/enamad-setup.php
 *
 * After running: open «تماس با ما» and «درباره ما» in wp-admin and fill the
 * bracketed placeholders with your REAL business name, postal address and phone
 * (must match the eNamad applicant). When eNamad issues the trust-seal snippet:
 *   wp option update emb_enamad_code '<paste the <a><img> snippet>'
 */

if ( ! defined( 'WP_CLI' ) ) { exit; }

$pll = function_exists( 'PLL' ) ? PLL() : null;

function emb_enamad_page( $slug, $lang, $title, $content, $genesis_title = '' ) {
	global $pll;
	$existing = get_page_by_path( $slug );
	$data = array(
		'post_type'    => 'page',
		'post_status'  => 'publish',
		'post_title'   => $title,
		'post_name'    => $slug,
		'post_content' => $content,
	);
	if ( $existing ) {
		$data['ID'] = $existing->ID;
		$id = wp_update_post( $data );
		WP_CLI::log( "  updated /{$slug}/ (#{$id})" );
	} else {
		$id = wp_insert_post( $data );
		WP_CLI::log( "  created /{$slug}/ (#{$id})" );
	}
	if ( $id && ! is_wp_error( $id ) ) {
		if ( $genesis_title ) {
			update_post_meta( $id, '_genesis_title', $genesis_title );
		}
		if ( $pll && function_exists( 'pll_set_post_language' ) && ! pll_get_post_language( $id ) ) {
			pll_set_post_language( $id, $lang );
		}
	}
	return $id;
}

/* ── درباره ما ─────────────────────────────────────────────────────── */
$about_fa = <<<'HTML'
<!-- wp:heading --><h2 class="wp-block-heading">درباره easymakebot</h2><!-- /wp:heading -->
<!-- wp:paragraph --><p>easymakebot یک پلتفرم ساخت ربات تلگرام بدون کدنویسی است. کاربر توکن ربات خود را از BotFather می‌گیرد، از یک منوی ساده دستورها، فروشگاه، عضویت اجباری و پیام همگانی را تنظیم می‌کند و ربات روی سرور easymakebot زنده و اجرا می‌شود.</p><!-- /wp:paragraph -->
<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">چه چیزی ارائه می‌دهیم</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>میزبانی و اجرای ربات‌های ساخته‌شده کاربران روی زیرساخت ما، به‌صورت پلن‌های زمان‌دار و قابل تمدید برای هر ربات (۱، ۳، ۶ و ۱۲ ماهه). ۷۲ ساعت اول هر ربات رایگان است.</p><!-- /wp:paragraph -->
<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">مالک و مسئول</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>[نام و نام خانوادگی مالک / نام کسب‌وکار — همان مشخصاتی که در اینماد ثبت می‌کنید]</p><!-- /wp:paragraph -->
<!-- wp:paragraph --><p>راه‌های ارتباطی در صفحهٔ <a href="/contact/">تماس با ما</a> آمده است.</p><!-- /wp:paragraph -->
HTML;

$about_en = <<<'HTML'
<!-- wp:heading --><h2 class="wp-block-heading">About easymakebot</h2><!-- /wp:heading -->
<!-- wp:paragraph --><p>easymakebot is a no-code Telegram bot builder. You paste a BotFather token, configure commands, a shop, forced-join and broadcasts from a simple menu, and the bot goes live on our servers. Hosting is sold as renewable, time-based per-bot plans; the first 72 hours of each bot are free.</p><!-- /wp:paragraph -->
<!-- wp:paragraph --><p>Contact details are on the <a href="/contact-en/">Contact</a> page.</p><!-- /wp:paragraph -->
HTML;

/* ── تماس با ما ────────────────────────────────────────────────────── */
$contact_fa = <<<'HTML'
<!-- wp:heading --><h2 class="wp-block-heading">تماس با ما</h2><!-- /wp:heading -->
<!-- wp:list --><ul class="wp-block-list">
<li><strong>نام کسب‌وکار / مالک:</strong> [نام و نام خانوادگی یا نام ثبتی — مطابق اینماد]</li>
<li><strong>نشانی:</strong> [نشانی کامل پستی به همراه کد پستی]</li>
<li><strong>تلفن تماس:</strong> [شماره تلفن ثابت یا همراهِ قابل تأیید]</li>
<li><strong>ایمیل:</strong> [ایمیل پشتیبانی]</li>
<li><strong>تلگرام:</strong> <a href="https://t.me/easymakebot" target="_blank" rel="noopener">@easymakebot</a></li>
<li><strong>ساعات پاسخ‌گویی:</strong> شنبه تا پنجشنبه، ۹ تا ۱۸</li>
</ul><!-- /wp:list -->
<!-- wp:paragraph --><p>برای پیگیری سفارش، مشکل پرداخت یا هر سؤالی می‌توانید از راه‌های بالا با ما در تماس باشید. سریع‌ترین راه، پیام در تلگرام به <strong>@easymakebot</strong> است.</p><!-- /wp:paragraph -->
HTML;

$contact_en = <<<'HTML'
<!-- wp:heading --><h2 class="wp-block-heading">Contact</h2><!-- /wp:heading -->
<!-- wp:list --><ul class="wp-block-list">
<li><strong>Business / owner:</strong> [name]</li>
<li><strong>Address:</strong> [postal address]</li>
<li><strong>Phone:</strong> [phone]</li>
<li><strong>Email:</strong> [support email]</li>
<li><strong>Telegram:</strong> <a href="https://t.me/easymakebot" target="_blank" rel="noopener">@easymakebot</a></li>
</ul><!-- /wp:list -->
HTML;

/* ── قوانین و مقررات (بازنویسی /terms/) ────────────────────────────── */
$terms_fa = <<<'HTML'
<!-- wp:heading --><h2 class="wp-block-heading">قوانین و مقررات easymakebot</h2><!-- /wp:heading -->
<!-- wp:paragraph --><p>با ساختن حساب کاربری یا خرید پلن در این سایت، این قوانین را می‌پذیرید. لطفاً پیش از خرید آن‌ها را بخوانید.</p><!-- /wp:paragraph -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">۱. معرفی سرویس</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>easymakebot امکان ساخت ربات تلگرام بدون کدنویسی و میزبانی و اجرای آن روی سرورهای ما را فراهم می‌کند. محصول قابل خرید، «پلن زنده‌ماندن ربات» است: بازه‌ای زمانی که طی آن یک ربات مشخص روی زیرساخت ما اجرا می‌شود.</p><!-- /wp:paragraph -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">۲. ثبت‌نام و احراز هویت</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>برای خرید باید حساب کاربری بسازید و شمارهٔ موبایل خود را با کد پیامکی تأیید کنید. اطلاعات واردشده باید صحیح و متعلق به خودتان باشد. یک حساب تأییدشده به‌ازای هر شمارهٔ موبایل.</p><!-- /wp:paragraph -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">۳. ثبت سفارش و پرداخت</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>قیمت پلن‌ها به تومان و در صفحهٔ «هزینه» درج شده است. پرداخت داخل ایران از طریق درگاه امن زرین‌پال (همهٔ کارت‌های عضو شتاب) انجام می‌شود. اطلاعات کارت بانکی شما هرگز روی سرور ما ذخیره نمی‌شود و مستقیماً در درگاه بانکی وارد می‌شود. پس از تأیید پرداخت، سفارش شما نهایی می‌گردد.</p><!-- /wp:paragraph -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">۴. تحویل خدمات</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>پس از تأیید پرداخت، یک «کد فعال‌سازی» (مثل <code>EMB-XXXX-XXXX</code>) بلافاصله در صفحهٔ سفارش نمایش داده و به ایمیل شما ارسال می‌شود. برای اعمال آن روی ربات‌تان، در تلگرام به <strong>@easymakebot</strong> بروید، ربات موردنظر را انتخاب کنید، گزینهٔ «فعال‌سازی با کد» را بزنید و کد را وارد کنید. سرویس بلافاصله فعال می‌شود. کد یک‌بارمصرف و مخصوص یک ربات است.</p><!-- /wp:paragraph -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">۵. شرایط لغو، عودت وجه و بازگشت</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>با توجه به ماهیت دیجیتال و آنیِ سرویس، پس از صدور کد فعال‌سازی امکان عودت وجه وجود ندارد. تنها استثنا: اگر به‌دلیل نقص فنی از سمت easymakebot سرویس اصلاً ارائه نشده باشد (کد صادر نشده یا ربات با وجود کد معتبر فعال نشده باشد)، وجه پرداختی طی حداکثر ۷۲ ساعت کاری به‌طور کامل عودت داده می‌شود. برای پیگیری از راه‌های ارتباطی صفحهٔ «تماس با ما» استفاده کنید.</p><!-- /wp:paragraph -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">۶. تعهدات کاربر و استفادهٔ مجاز</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>مسئولیت کامل ربات‌هایی که می‌سازید و هر محتوا و تراکنشی که از طریق آن‌ها انجام می‌شود، فقط با شماست. easymakebot صرفاً بستر فنی است و طرف معاملهٔ شما با کاربران رباتتان نیست. این موارد ممنوع است و حساب مربوطه بدون اطلاع قبلی مسدود می‌شود: کلاهبرداری و طرح‌های پولی فریب‌کارانه؛ فیشینگ و سرقت اطلاعات؛ هرزنامه و ارسال انبوه ناخواسته؛ فروش کالا یا خدمات غیرقانونی؛ محتوای مجرمانه؛ جعل هویت اشخاص یا سازمان‌ها؛ بدافزار؛ نقض حقوق دیگران.</p><!-- /wp:paragraph -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">۷. ثبت شناسه‌ها و همکاری قانونی</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>برای جلوگیری از سوءاستفاده، این اطلاعات ثبت و نگه‌داری می‌شود: شناسه و نام کاربری تلگرام، شمارهٔ موبایلِ تأییدشده، نشانی ایمیل، نشانی IP و کشورِ ثبت‌نام و خرید، و کد رهگیری پرداخت. در صورت گزارش تخلف یا درخواست قانونیِ مراجع صالح (از جمله پلیس فتا و مراجع قضایی)، این اطلاعات در اختیار آن‌ها قرار می‌گیرد. جزئیات در صفحهٔ <a href="/privacy/">حریم خصوصی</a>.</p><!-- /wp:paragraph -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">۸. تعلیق و لغو سرویس</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>در صورت مشکوک‌شدن به تخلف یا نقض این قوانین، easymakebot می‌تواند ربات یا حساب را فوراً و بدون اطلاع قبلی آفلاین یا مسدود کند. در این حالت، طبق بند ۵ وجه عودت داده نمی‌شود.</p><!-- /wp:paragraph -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">۹. سلب مسئولیت</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>سرویس «همان‌طور که هست» ارائه می‌شود. easymakebot تلاش می‌کند سرویس پایدار باشد ولی مسئول خسارت‌های ناشی از قطعی تلگرام، قطعی زیرساخت خارج از کنترل ما، یا استفادهٔ شما و کاربران رباتتان نیست.</p><!-- /wp:paragraph -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">۱۰. قانون حاکم و حل اختلاف</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>این قوانین تابع قوانین جمهوری اسلامی ایران است. در صورت بروز اختلاف، ابتدا از راه مذاکره و راه‌های ارتباطی صفحهٔ «تماس با ما» پیگیری می‌شود و در صورت عدم توافق، مراجع قضایی صالح ایران رسیدگی خواهند کرد.</p><!-- /wp:paragraph -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">۱۱. تغییرات</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>این نسخه از تاریخ درج‌شده معتبر است. تغییرات بعدی از همین صفحه اعلام می‌شود و ممکن است پذیرش دوباره لازم باشد.</p><!-- /wp:paragraph -->
HTML;

$terms_en = <<<'HTML'
<!-- wp:heading --><h2 class="wp-block-heading">easymakebot Terms &amp; Conditions</h2><!-- /wp:heading -->
<!-- wp:paragraph --><p>By creating an account or buying a plan you accept these terms.</p><!-- /wp:paragraph -->
<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">1. The service</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>easymakebot lets you build a Telegram bot without code and hosts it on our servers. The purchasable product is a "keep-alive plan": a period during which one specific bot runs on our infrastructure.</p><!-- /wp:paragraph -->
<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">2. Sign-up &amp; verification</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>You must create an account and verify a phone number. Your details must be accurate and your own. One verified account per phone number.</p><!-- /wp:paragraph -->
<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">3. Orders &amp; payment</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>Prices are shown on the Pricing section. Card details never touch our server. Your order is final once payment is confirmed.</p><!-- /wp:paragraph -->
<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">4. Delivery</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>After payment an activation code (e.g. <code>EMB-XXXX-XXXX</code>) is shown on the order page and emailed to you. Redeem it in <strong>@easymakebot</strong> on Telegram — pick your bot, choose "Activate with a code", paste it. The service activates immediately. The code is one-time and for one bot.</p><!-- /wp:paragraph -->
<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">5. Cancellation &amp; refunds</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>Because the service is digital and delivered instantly, there is no refund once an activation code has been issued — except where a technical fault on easymakebot's side meant the service was never delivered (no code issued, or the bot did not activate with a valid code). In that case the full amount is refunded within 3 business days. Contact us via the Contact page.</p><!-- /wp:paragraph -->
<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">6. Your responsibility &amp; acceptable use</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>You are solely responsible for the bots you build and every message and transaction made through them. easymakebot is only the technical platform. Prohibited: fraud, phishing, spam, selling illegal goods or services, criminal content, impersonation, malware, infringing others' rights. Violations get the account suspended without notice.</p><!-- /wp:paragraph -->
<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">7. Identifiers &amp; legal cooperation</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>We record your Telegram ID/username, verified phone, email, sign-up and purchase IP and country, and the payment reference, and disclose them on an abuse report or a lawful request from a competent authority. See the <a href="/privacy-en/">Privacy Policy</a>.</p><!-- /wp:paragraph -->
<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">8. Suspension &amp; disclaimer</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>If abuse is suspected we may take a bot or account offline immediately and without notice; no refund in that case. The service is provided "as is"; easymakebot is not liable for Telegram outages or losses from your use.</p><!-- /wp:paragraph -->
<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">9. Governing law</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>These terms are governed by the laws of the Islamic Republic of Iran; disputes are handled first by negotiation and then by the competent Iranian courts.</p><!-- /wp:paragraph -->
HTML;

emb_enamad_page( 'about', 'fa', 'درباره ما', $about_fa, 'درباره ما — easymakebot' );
emb_enamad_page( 'contact', 'fa', 'تماس با ما', $contact_fa, 'تماس با ما — easymakebot' );
emb_enamad_page( 'terms', 'fa', 'قوانین و مقررات', $terms_fa, 'قوانین و مقررات — easymakebot' );

if ( $pll && function_exists( 'pll_default_language' ) ) {
	$about_en_id   = emb_enamad_page( 'about-en', 'en', 'About', $about_en );
	$contact_en_id = emb_enamad_page( 'contact-en', 'en', 'Contact', $contact_en );
	emb_enamad_page( 'terms-en', 'en', 'Terms & Conditions', $terms_en );

	// link fa <-> en so the language switcher resolves once EN is re-enabled
	foreach ( array( 'about' => 'about-en', 'contact' => 'contact-en', 'terms' => 'terms-en' ) as $fa => $en ) {
		$fp = get_page_by_path( $fa );
		$ep = get_page_by_path( $en );
		if ( $fp && $ep && function_exists( 'pll_save_post_translations' ) ) {
			pll_save_post_translations( array( 'fa' => $fp->ID, 'en' => $ep->ID ) );
		}
	}
}

/* keep WordPress's privacy-policy setting pointed at our page */
$priv = get_page_by_path( 'privacy' );
if ( $priv ) {
	update_option( 'wp_page_for_privacy_policy', $priv->ID );
}

if ( function_exists( 'wp_cache_flush' ) ) { wp_cache_flush(); }
WP_CLI::success( 'eNamad pages ready — now fill the [placeholders] in «تماس با ما» and «درباره ما» with your real info, then apply at enamad.ir' );
