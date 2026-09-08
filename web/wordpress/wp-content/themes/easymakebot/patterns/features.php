<?php
/**
 * Title: امکانات — پنج ابزار
 * Slug: easymakebot/features
 * Categories: easymakebot
 */
?>
<!-- wp:group {"className":"emb-section emb-reveal","align":"full","layout":{"type":"constrained"}} -->
<div class="wp-block-group alignfull emb-section emb-reveal" id="features">
	<!-- wp:group {"className":"emb-section__intro","layout":{"type":"constrained"}} -->
	<div class="wp-block-group emb-section__intro">
		<!-- wp:paragraph {"className":"emb-kicker"} --><p class="emb-kicker">امکانات</p><!-- /wp:paragraph -->
		<!-- wp:heading --><h2 class="wp-block-heading">پنج ابزار، دقیقاً به همین ترتیب داخل ربات</h2><!-- /wp:heading -->
		<!-- wp:paragraph --><p>هر ربات که می‌سازی به این منو دسترسی دارد. لازم نیست همه را استفاده کنی — فقط آن‌هایی که می‌خواهی.</p><!-- /wp:paragraph -->
	</div>
	<!-- /wp:group -->

	<!-- wp:html -->
	<div class="emb-feat">
		<div class="emb-feat__num">01</div>
		<div>
			<h3>تعریف دستور</h3>
			<p class="emb-feat__desc">دستورهای ربات‌ات را می‌سازی — مثل <code>/start</code> یا <code>/help</code>. برای <code>/start</code> یک ویزارد کوتاه می‌پرسد: پیام خوش‌آمد، آیدی ادمین برای تماس و… . لیست دستورها به‌صورت خودکار در منوی تلگرام ربات‌ات ثبت می‌شود.</p>
			<div class="emb-chips"><span class="emb-chip">ویزارد /start</span><span class="emb-chip">همگام‌سازی خودکار منو</span><span class="emb-chip">دکمهٔ «نمایش دستورها»</span></div>
		</div>
		<div class="emb-feat__aside"><span style="color:var(--accent-deep)">command</span> = <span style="color:var(--mint)">/start</span><br>welcome  = "به فروشگاه من خوش اومدی"<br>admin    = <span style="color:var(--mint)">@my_username</span><br><span style="color:var(--accent-deep)">synced</span> → Telegram menu ✓</div>
	</div>
	<div class="emb-feat">
		<div class="emb-feat__num">02</div>
		<div>
			<h3>عضویت اجباری</h3>
			<p class="emb-feat__desc">کاربر تا وقتی عضو کانال‌های تو نشده، نمی‌تواند از ربات استفاده کند. چند کانال اضافه کن، و با یک کلید قفل (🔒 / 🔓) این شرط را روی <code>/start</code> روشن یا خاموش کن.</p>
			<div class="emb-chips"><span class="emb-chip">چند کانال</span><span class="emb-chip">کلید روشن/خاموش</span><span class="emb-chip">بررسی خودکار عضویت</span></div>
		</div>
		<div class="emb-feat__aside">channels = [ <span style="color:var(--mint)">@my_channel</span>, <span style="color:var(--mint)">@news</span> ]<br>gate on <span style="color:var(--accent-deep)">/start</span> → <span style="color:var(--mint)">ENABLED 🔒</span><br>not joined? → "Join, then tap ✅"</div>
	</div>
	<div class="emb-feat">
		<div class="emb-feat__num">03</div>
		<div>
			<h3>پیام همگانی</h3>
			<p class="emb-feat__desc">یک دستور می‌سازی که با آن هر پیامی — متن، عکس، فایل — را برای همهٔ کاربران ربات‌ات می‌فرستی. برای اطلاع‌رسانی، تخفیف و به‌روزرسانی.</p>
			<div class="emb-chips"><span class="emb-chip">به همهٔ کاربران</span><span class="emb-chip">متن / عکس / فایل</span></div>
		</div>
		<div class="emb-feat__aside">owner sends → <span style="color:var(--mint)">"۲۰٪ تخفیف امشب"</span><br>easymakebot → 1,240 users ✓<br>delivered: 1,231 · blocked: 9</div>
	</div>
	<div class="emb-feat">
		<div class="emb-feat__num">04</div>
		<div>
			<h3>لیست محتوا</h3>
			<p class="emb-feat__desc">یک کاتالوگ دسته‌بندی‌شده (والد/فرزند) از محتوا یا محصولات. دستی اضافه کن یا فایل اکسل نمونه را بگیر، پُر کن و یک‌جا بارگذاری کن. هر آیتم می‌تواند «برای فروش» با قیمت و دکمهٔ خرید باشد.</p>
			<div class="emb-chips"><span class="emb-chip">دسته‌بندی تودرتو</span><span class="emb-chip">ورود/خروج اکسل</span><span class="emb-chip">فیزیکی · دیجیتال · دسترسی</span></div>
		</div>
		<div class="emb-feat__aside">📁 <span style="color:var(--accent-deep)">دوره‌ها</span><br>&nbsp;&nbsp;└ 🎬 پایتون مقدماتی — <span style="color:var(--mint)">۲۹۰٬۰۰۰ ﷼</span> · Buy<br>&nbsp;&nbsp;└ 🎬 جاوااسکریپت<br>📁 <span style="color:var(--accent-deep)">کتاب‌ها</span> · upload.xlsx ✓</div>
	</div>
	<div class="emb-feat">
		<div class="emb-feat__num">05</div>
		<div>
			<h3>فروشگاه</h3>
			<p class="emb-feat__desc">محصولات مستقل، سبد خرید، سفارش و فاکتور PDF. درگاه‌ها را خودت وصل می‌کنی: زرین‌پال، کارت‌به‌کارت، استرایپ (بین‌المللی)، کیف‌پول کریپتو و TON. سفارش‌های اخیر را همان‌جا می‌بینی.</p>
			<div class="emb-chips"><span class="emb-chip">زرین‌پال</span><span class="emb-chip">کارت‌به‌کارت</span><span class="emb-chip">استرایپ</span><span class="emb-chip">کریپتو · TON</span><span class="emb-chip">فاکتور PDF</span></div>
		</div>
		<div class="emb-feat__aside">product: "اشتراک ۱ ماهه" · <span style="color:var(--mint)">access</span><br>price: <span style="color:var(--mint)">۹۹٬۰۰۰ تومان</span><br>pay: Zarinpal → paid ✓ → invoice.pdf<br>fulfilled: access granted</div>
	</div>

	<div class="emb-callout">
		<p class="emb-kicker" style="margin:0">علاوه بر این</p>
		<h3>🎨 سازندهٔ بصری (Mini App)</h3>
		<p>اگر ترجیح می‌دهی به‌جای چت، فلوی ربات را ببینی: یک بوم درگ‌اند‌دراپ داخل تلگرام باز می‌شود و فلوی <code>/start</code> را بلوک‌به‌بلوک می‌چینی — پیام، عضویت اجباری، راهنما و ویدیو، لیست محتوا، فروشگاه و پیام همگانی.</p>
	</div>
	<!-- /wp:html -->
</div>
<!-- /wp:group -->
