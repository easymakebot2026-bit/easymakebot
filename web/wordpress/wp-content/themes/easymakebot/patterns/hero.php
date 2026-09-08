<?php
/**
 * Title: Hero — چت تلگرام
 * Slug: easymakebot/hero
 * Categories: easymakebot
 * Description: بخش قهرمان با ماکت چت ربات.
 */
$logo = esc_url( get_theme_file_uri( 'assets/logo-256.png' ) );
?>
<!-- wp:group {"className":"emb-hero","align":"full","layout":{"type":"constrained"}} -->
<div class="wp-block-group alignfull emb-hero">
	<!-- wp:columns {"verticalAlignment":"center"} -->
	<div class="wp-block-columns are-vertically-aligned-center">
		<!-- wp:column {"verticalAlignment":"center","width":"55%"} -->
		<div class="wp-block-column is-vertically-aligned-center" style="flex-basis:55%">
			<!-- wp:paragraph {"className":"emb-eyebrow"} --><p class="emb-eyebrow">بدون کدنویسی · داخل خودِ تلگرام</p><!-- /wp:paragraph -->
			<!-- wp:heading {"level":1} --><h1 class="wp-block-heading">ربات تلگرامت را <span class="emb-hl">در چند دقیقه</span> بساز، نه چند هفته</h1><!-- /wp:heading -->
			<!-- wp:paragraph {"className":"emb-hero__lead"} --><p class="emb-hero__lead">easymakebot یک ربات است که با آن ربات می‌سازی. توکن را از BotFather می‌گیری، از یک منوی ساده ابزارها را می‌چینی و ربات‌ات همان‌جا روی سرور ما زنده می‌شود — دستور، فروشگاه، عضویت اجباری، پیام همگانی و سازندهٔ بصری.</p><!-- /wp:paragraph -->
			<!-- wp:buttons {"style":{"spacing":{"blockGap":"12px","margin":{"top":"1.75rem"}}}} -->
			<div class="wp-block-buttons" style="margin-top:1.75rem">
				<!-- wp:button --><div class="wp-block-button"><a class="wp-block-button__link wp-element-button" href="https://t.me/easymakebot">رایگان شروع کن</a></div><!-- /wp:button -->
				<!-- wp:button {"className":"is-style-outline"} --><div class="wp-block-button is-style-outline"><a class="wp-block-button__link wp-element-button" href="#features">ببین چطور کار می‌کند</a></div><!-- /wp:button -->
			</div>
			<!-- /wp:buttons -->
			<!-- wp:paragraph {"className":"emb-hero__note","style":{"spacing":{"margin":{"top":"1.1rem"}}}} --><p class="emb-hero__note" style="margin-top:1.1rem">۷۲ ساعت آزمایش رایگان — بدون کارت، بدون نصب چیزی.</p><!-- /wp:paragraph -->
		</div>
		<!-- /wp:column -->

		<!-- wp:column {"verticalAlignment":"center","width":"45%"} -->
		<div class="wp-block-column is-vertically-aligned-center" style="flex-basis:45%">
			<!-- wp:html -->
			<div class="emb-tg" role="img" aria-label="نمونهٔ گفتگو با ربات easymakebot در تلگرام">
				<div class="emb-tg__head">
					<span class="emb-tg__av" style="background-image:url('<?php echo $logo; ?>')"></span>
					<span><b>easymakebot</b><span>ربات · آنلاین</span></span>
				</div>
				<div class="emb-tg__body">
					<div class="emb-bubble"><span class="emb-u">/start</span><br>👋 خوش آمدی! شناسهٔ تو: <code>128500419</code><br>یک ربات بساز یا ربات‌های قبلی‌ات را ببین.</div>
					<div class="emb-tg__kb">
						<span class="emb-tg__btn">🤖 ربات‌های من</span>
						<span class="emb-tg__btn">➕ ربات جدید</span>
					</div>
					<div class="emb-bubble">محیط ساخت باز شد. از منوی «ابزارهای ساخت و ویرایش» انتخاب کن:</div>
					<div class="emb-tg__kb">
						<span class="emb-tg__btn">1️⃣ تعریف دستور</span>
						<span class="emb-tg__btn">2️⃣ عضویت اجباری 🔓</span>
						<span class="emb-tg__btn">3️⃣ پیام همگانی</span>
						<span class="emb-tg__btn">4️⃣ لیست محتوا</span>
						<span class="emb-tg__btn is-wide">5️⃣ فروشگاه</span>
					</div>
				</div>
			</div>
			<!-- /wp:html -->
		</div>
		<!-- /wp:column -->
	</div>
	<!-- /wp:columns -->
</div>
<!-- /wp:group -->
