<?php
/**
 * Title: Front page — full (EN)
 * Slug: easymakebot/front-page-en
 * Categories: easymakebot
 * Block Types: core/post-content
 * Post Types: page
 * Inserter: false
 */
$logo = esc_url( get_theme_file_uri( 'assets/logo-256.png' ) );
?>
<!-- wp:group {"className":"emb-hero","align":"full","layout":{"type":"constrained"}} -->
<div class="wp-block-group alignfull emb-hero">
	<!-- wp:columns {"verticalAlignment":"center"} -->
	<div class="wp-block-columns are-vertically-aligned-center">
		<!-- wp:column {"verticalAlignment":"center","width":"55%"} -->
		<div class="wp-block-column is-vertically-aligned-center" style="flex-basis:55%">
			<!-- wp:paragraph {"className":"emb-eyebrow"} --><p class="emb-eyebrow">No code · Right inside Telegram</p><!-- /wp:paragraph -->
			<!-- wp:heading {"level":1} --><h1 class="wp-block-heading">Build your Telegram bot in <span class="emb-hl">minutes</span>, not weeks</h1><!-- /wp:heading -->
			<!-- wp:paragraph {"className":"emb-hero__lead"} --><p class="emb-hero__lead">easymakebot is a bot that builds bots. Paste your BotFather token, assemble your bot from a simple tools menu, and it goes live on our server right there — commands, a shop, forced-join, broadcasts and a visual builder.</p><!-- /wp:paragraph -->
			<!-- wp:buttons {"style":{"spacing":{"blockGap":"12px","margin":{"top":"1.75rem"}}}} -->
			<div class="wp-block-buttons" style="margin-top:1.75rem">
				<!-- wp:button --><div class="wp-block-button"><a class="wp-block-button__link wp-element-button" href="https://t.me/easymakebot">Start free</a></div><!-- /wp:button -->
				<!-- wp:button {"className":"is-style-outline"} --><div class="wp-block-button is-style-outline"><a class="wp-block-button__link wp-element-button" href="#features">See how it works</a></div><!-- /wp:button -->
			</div>
			<!-- /wp:buttons -->
			<!-- wp:paragraph {"className":"emb-hero__note","style":{"spacing":{"margin":{"top":"1.1rem"}}}} --><p class="emb-hero__note" style="margin-top:1.1rem">72-hour free trial — no card, nothing to install.</p><!-- /wp:paragraph -->
		</div>
		<!-- /wp:column -->
		<!-- wp:column {"verticalAlignment":"center","width":"45%"} -->
		<div class="wp-block-column is-vertically-aligned-center" style="flex-basis:45%">
			<!-- wp:html -->
			<div class="emb-tg" role="img" aria-label="Example chat with the easymakebot bot on Telegram">
				<div class="emb-tg__head">
					<span class="emb-tg__av" style="background-image:url('<?php echo $logo; ?>')"></span>
					<span><b>easymakebot</b><span>bot · online</span></span>
				</div>
				<div class="emb-tg__body">
					<div class="emb-bubble"><span class="emb-u">/start</span><br>👋 Welcome! Your ID: <code>128500419</code><br>Create a bot or view the ones you already have.</div>
					<div class="emb-tg__kb"><span class="emb-tg__btn">🤖 My Bots</span><span class="emb-tg__btn">➕ New Bot</span></div>
					<div class="emb-bubble">Build environment ready. Pick from the “Build &amp; Edit Tools” menu:</div>
					<div class="emb-tg__kb">
						<span class="emb-tg__btn">1️⃣ Define Command</span>
						<span class="emb-tg__btn">2️⃣ Force Join 🔓</span>
						<span class="emb-tg__btn">3️⃣ Broadcast</span>
						<span class="emb-tg__btn">4️⃣ Content List</span>
						<span class="emb-tg__btn is-wide">5️⃣ Shop</span>
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


<!-- wp:group {"className":"emb-section is-band emb-reveal","align":"full","layout":{"type":"constrained"}} -->
<div class="wp-block-group alignfull emb-section is-band emb-reveal" id="why">
	<!-- wp:group {"className":"emb-section__intro","layout":{"type":"constrained"}} -->
	<div class="wp-block-group emb-section__intro">
		<!-- wp:paragraph {"className":"emb-kicker"} --><p class="emb-kicker">Why easymakebot</p><!-- /wp:paragraph -->
		<!-- wp:heading --><h2 class="wp-block-heading">Simple, because you were never meant to be a developer</h2><!-- /wp:heading -->
		<!-- wp:paragraph --><p>A bot usually means a server, hosting, code and upkeep. Here it’s a few messages in Telegram.</p><!-- /wp:paragraph -->
	</div>
	<!-- /wp:group -->
	<!-- wp:html -->
	<div class="emb-why" style="margin-top:var(--wp--preset--spacing--40)">
		<div class="emb-card"><div class="emb-ic">⌨️</div><h3>Not one line of code</h3><p>Everything is set with buttons and messages. If you can chat on Telegram, you can build a bot.</p></div>
		<div class="emb-card"><div class="emb-ic">⚡</div><h3>Minutes to live</h3><p>Give the token, add commands, tap “Go live”. Hosting and running the bot is on us.</p></div>
		<div class="emb-card"><div class="emb-ic">🪙</div><h3>Easy on the wallet</h3><p>The first 72 hours are free. After that just one simple monthly plan — no server bill, no dev contract.</p></div>
	</div>
	<!-- /wp:html -->
</div>
<!-- /wp:group -->

<!-- wp:group {"className":"emb-section emb-reveal","align":"full","layout":{"type":"constrained"}} -->
<div class="wp-block-group alignfull emb-section emb-reveal" id="features">
	<!-- wp:group {"className":"emb-section__intro","layout":{"type":"constrained"}} -->
	<div class="wp-block-group emb-section__intro">
		<!-- wp:paragraph {"className":"emb-kicker"} --><p class="emb-kicker">Features</p><!-- /wp:paragraph -->
		<!-- wp:heading --><h2 class="wp-block-heading">Five tools, in the exact order you meet them in the bot</h2><!-- /wp:heading -->
		<!-- wp:paragraph --><p>Every bot you build gets this menu. Use only the ones you need.</p><!-- /wp:paragraph -->
	</div>
	<!-- /wp:group -->
	<!-- wp:html -->
	<div class="emb-feat"><div class="emb-feat__num">01</div><div><h3>Define Command</h3><p class="emb-feat__desc">Create your bot’s commands — like <code>/start</code> or <code>/help</code>. For <code>/start</code> a short wizard asks for the welcome text, an admin contact handle and more. Your command list is synced into the bot’s Telegram menu automatically.</p><div class="emb-chips"><span class="emb-chip">/start wizard</span><span class="emb-chip">Auto menu sync</span><span class="emb-chip">“Show commands”</span></div></div><div class="emb-feat__aside"><span style="color:var(--accent-deep)">command</span> = <span style="color:var(--mint)">/start</span><br>welcome  = "Welcome to my shop"<br>admin    = <span style="color:var(--mint)">@my_username</span><br><span style="color:var(--accent-deep)">synced</span> → Telegram menu ✓</div></div>
	<div class="emb-feat"><div class="emb-feat__num">02</div><div><h3>Force Join</h3><p class="emb-feat__desc">Users can’t use the bot until they’ve joined your channels. Add one or more channels, then flip a lock switch (🔒 / 🔓) to turn the gate on <code>/start</code> on or off.</p><div class="emb-chips"><span class="emb-chip">Multiple channels</span><span class="emb-chip">On/off toggle</span><span class="emb-chip">Auto membership check</span></div></div><div class="emb-feat__aside">channels = [ <span style="color:var(--mint)">@my_channel</span>, <span style="color:var(--mint)">@news</span> ]<br>gate on <span style="color:var(--accent-deep)">/start</span> → <span style="color:var(--mint)">ENABLED 🔒</span><br>not joined? → "Join, then tap ✅"</div></div>
	<div class="emb-feat"><div class="emb-feat__num">03</div><div><h3>Broadcast</h3><p class="emb-feat__desc">Create a command that sends any message — text, photo, file — to every user of your bot. For announcements, discounts and updates.</p><div class="emb-chips"><span class="emb-chip">To all subscribers</span><span class="emb-chip">Text / photo / file</span></div></div><div class="emb-feat__aside">owner sends → <span style="color:var(--mint)">"20% off tonight"</span><br>easymakebot → 1,240 users ✓<br>delivered: 1,231 · blocked: 9</div></div>
	<div class="emb-feat"><div class="emb-feat__num">04</div><div><h3>Content List</h3><p class="emb-feat__desc">A categorized (parent/child) catalog of content or products. Add items by hand, or download the sample Excel, fill it in and bulk-upload. Any item can be marked “for sale” with a price and a Buy button.</p><div class="emb-chips"><span class="emb-chip">Nested categories</span><span class="emb-chip">Excel import / export</span><span class="emb-chip">Physical · digital · access</span></div></div><div class="emb-feat__aside">📁 <span style="color:var(--accent-deep)">Courses</span><br>&nbsp;&nbsp;└ 🎬 Python basics — <span style="color:var(--mint)">290,000 ﷼</span> · Buy<br>&nbsp;&nbsp;└ 🎬 JavaScript<br>📁 <span style="color:var(--accent-deep)">Books</span> · upload.xlsx ✓</div></div>
	<div class="emb-feat"><div class="emb-feat__num">05</div><div><h3>Shop</h3><p class="emb-feat__desc">Standalone products, a cart, orders and PDF invoices. You connect the gateways yourself: Zarinpal, card-to-card, Stripe (international), a crypto wallet and TON. Recent orders show up right there.</p><div class="emb-chips"><span class="emb-chip">Zarinpal</span><span class="emb-chip">Card-to-card</span><span class="emb-chip">Stripe</span><span class="emb-chip">Crypto · TON</span><span class="emb-chip">PDF invoice</span></div></div><div class="emb-feat__aside">product: "1-month plan" · <span style="color:var(--mint)">access</span><br>price: <span style="color:var(--mint)">99,000 Toman</span><br>pay: Zarinpal → paid ✓ → invoice.pdf<br>fulfilled: access granted</div></div>
	<div class="emb-callout"><p class="emb-kicker" style="margin:0">On top of that</p><h3>🎨 Visual Builder (Mini App)</h3><p>Prefer to see your bot’s flow instead of chatting it: a drag-and-drop canvas opens inside Telegram and you assemble the <code>/start</code> flow block by block — message, forced-join, guide &amp; video, content list, shop and broadcast.</p></div>
	<!-- /wp:html -->
</div>
<!-- /wp:group -->


<!-- wp:group {"className":"emb-section is-band emb-reveal","align":"full","layout":{"type":"constrained"}} -->
<div class="wp-block-group alignfull emb-section is-band emb-reveal" id="tutorial">
	<!-- wp:group {"className":"emb-section__intro","layout":{"type":"constrained"}} -->
	<div class="wp-block-group emb-section__intro">
		<!-- wp:paragraph {"className":"emb-kicker"} --><p class="emb-kicker">Tutorial</p><!-- /wp:paragraph -->
		<!-- wp:heading --><h2 class="wp-block-heading">From zero to a live bot, in four steps</h2><!-- /wp:heading -->
		<!-- wp:paragraph --><p>Each step is just a few messages in Telegram. Stuck anywhere? Send <code>/cancel</code>.</p><!-- /wp:paragraph -->
	</div>
	<!-- /wp:group -->
	<!-- wp:html -->
	<div class="emb-steps" style="margin-top:var(--wp--preset--spacing--40)">
		<div class="emb-step"><span class="emb-step__n">1</span><h3>Message easymakebot</h3><p>Send <code>/start</code>. It asks once (optional) for your phone number so it can show the guide and video in your language.</p></div>
		<div class="emb-step"><span class="emb-step__n">2</span><h3>Create a new bot</h3><p>Tap “New Bot” and send the token you got from <code>@BotFather</code>. The token is validated and your bot is registered.</p></div>
		<div class="emb-step"><span class="emb-step__n">3</span><h3>Assemble the tools</h3><p>Select your bot to enter its build environment. From “Build &amp; Edit Tools” add commands, forced-join, a content list or a shop — or open the Visual Builder.</p></div>
		<div class="emb-step"><span class="emb-step__n">4</span><h3>Go live</h3><p>Send <code>/live</code>. The 72-hour free trial brings your bot up on Telegram right now; to keep it, pick the monthly plan. Running and hosting is on us.</p></div>
	</div>
	<!-- /wp:html -->

	<!-- wp:heading {"level":3,"style":{"spacing":{"margin":{"top":"var:preset|spacing|50","bottom":"var:preset|spacing|30"}}}} --><h3 class="wp-block-heading" style="margin-top:var(--wp--preset--spacing--50);margin-bottom:var(--wp--preset--spacing--30)">Video tutorials</h3><!-- /wp:heading -->
	<!-- wp:shortcode -->[emb_tutorials count="3"]<!-- /wp:shortcode -->
</div>
<!-- /wp:group -->

<!-- wp:group {"className":"emb-section emb-reveal","align":"full","layout":{"type":"constrained"}} -->
<div class="wp-block-group alignfull emb-section emb-reveal" id="pricing">
	<!-- wp:group {"className":"emb-section__intro","layout":{"type":"constrained"}} -->
	<div class="wp-block-group emb-section__intro">
		<!-- wp:paragraph {"className":"emb-kicker"} --><p class="emb-kicker">Pricing</p><!-- /wp:paragraph -->
		<!-- wp:heading --><h2 class="wp-block-heading">Try it first, stay only if you want</h2><!-- /wp:heading -->
		<!-- wp:paragraph --><p>Simple pricing. You pay nothing until your bot is live.</p><!-- /wp:paragraph -->
	</div>
	<!-- /wp:group -->
	<!-- wp:heading {"level":3,"className":"emb-buy-head","anchor":"buy","style":{"spacing":{"margin":{"top":"var:preset|spacing|40","bottom":"var:preset|spacing|30"}}}} -->
	<h3 class="wp-block-heading emb-buy-head" id="buy" style="margin-top:var(--wp--preset--spacing--40);margin-bottom:var(--wp--preset--spacing--30)">Keep-alive plans — per bot, the longer you commit the cheaper it gets</h3>
	<!-- /wp:heading -->

	<!-- wp:shortcode -->[emb_plans]<!-- /wp:shortcode -->

	<!-- wp:html -->
	<p class="emb-paynote" style="margin-top:var(--wp--preset--spacing--30)"><strong>Pay in TON or USDT (TON network)</strong> — it confirms automatically on-chain within a few minutes. You'll verify your email with a one-time code before paying. &nbsp;—&nbsp; <strong>Your bot’s own shop</strong> is separate and can offer Zarinpal, card-to-card, Stripe, crypto and TON at the same time.</p>
	<!-- /wp:html -->
</div>
<!-- /wp:group -->

<!-- wp:group {"className":"emb-section is-band emb-reveal","align":"full","layout":{"type":"constrained"}} -->
<div class="wp-block-group alignfull emb-section is-band emb-reveal" id="account">
	<!-- wp:group {"className":"emb-section__intro","layout":{"type":"constrained"}} -->
	<div class="wp-block-group emb-section__intro">
		<!-- wp:paragraph {"className":"emb-kicker"} --><p class="emb-kicker">Account</p><!-- /wp:paragraph -->
		<!-- wp:heading --><h2 class="wp-block-heading">Sign in</h2><!-- /wp:heading -->
		<!-- wp:paragraph --><p>Passwordless — enter your email and we send a one-time code. Your account holds your plans and activation codes.</p><!-- /wp:paragraph -->
	</div>
	<!-- /wp:group -->
	<!-- wp:shortcode -->[emb_auth]<!-- /wp:shortcode -->
</div>
<!-- /wp:group -->

<!-- wp:group {"className":"emb-section is-band emb-reveal","align":"full","layout":{"type":"constrained"}} -->
<div class="wp-block-group alignfull emb-section is-band emb-reveal" id="faq">
	<!-- wp:group {"className":"emb-section__intro","layout":{"type":"constrained"}} -->
	<div class="wp-block-group emb-section__intro">
		<!-- wp:paragraph {"className":"emb-kicker"} --><p class="emb-kicker">FAQ</p><!-- /wp:paragraph -->
		<!-- wp:heading --><h2 class="wp-block-heading">A few things to know before you start</h2><!-- /wp:heading -->
	</div>
	<!-- /wp:group -->
	<!-- wp:html -->
	<div class="emb-faq" style="margin-top:var(--wp--preset--spacing--40)">
		<details><summary>Really no coding?</summary><p>Yes. All the building happens with buttons and messages inside Telegram. No code editor, no terminal.</p></details>
		<details><summary>What do I need to start?</summary><p>Just a Telegram account and a bot token from <code>@BotFather</code> (free, takes a minute).</p></details>
		<details><summary>Where does my bot run?</summary><p>On easymakebot’s server. Each built bot has its own polling loop and we keep it live for you.</p></details>
		<details><summary>Can I sell things?</summary><p>Yes. The Shop tool supports physical, digital and access/membership products, with a cart, payment and PDF invoices.</p></details>
		<details><summary>What if I don’t renew?</summary><p>The bot goes offline on Telegram and editing locks, but everything you built stays and comes back the moment you pay again.</p></details>
		<details><summary>What language does the bot speak to users?</summary><p>Whatever you write it to say, in any language. The built-in guide switches between Persian and English based on the user’s phone country code.</p></details>
		<details><summary>How does payment work outside Iran, and what happens after?</summary><p>Sign in with just your email — we send a one-time code, no password. Pick a plan and pay with TON or USDT on the TON network (card payments are sanctions-blocked for us, so this is the option). Once your transaction confirms on-chain — usually a few minutes — the same panel shows your activation code. Enter that code inside the bot, under <code>/live</code>, to extend your bot's subscription.</p></details>
	</div>
	<!-- /wp:html -->
</div>
<!-- /wp:group -->

<!-- wp:group {"className":"emb-section emb-reveal","align":"full","layout":{"type":"constrained"}} -->
<div class="wp-block-group alignfull emb-section emb-reveal">
	<!-- wp:group {"className":"emb-cta","layout":{"type":"constrained","contentSize":"640px"}} -->
	<div class="wp-block-group emb-cta">
		<!-- wp:heading {"textAlign":"center"} --><h2 class="wp-block-heading has-text-align-center">Your bot is one message away</h2><!-- /wp:heading -->
		<!-- wp:paragraph {"align":"center"} --><p class="has-text-align-center">Open easymakebot in Telegram, send <code>/start</code>, and put your first bot live today.</p><!-- /wp:paragraph -->
		<!-- wp:buttons {"layout":{"type":"flex","justifyContent":"center"},"style":{"spacing":{"margin":{"top":"1.5rem"}}}} -->
		<div class="wp-block-buttons" style="margin-top:1.5rem">
			<!-- wp:button --><div class="wp-block-button"><a class="wp-block-button__link wp-element-button" href="https://t.me/easymakebot">Open @easymakebot</a></div><!-- /wp:button -->
		</div>
		<!-- /wp:buttons -->
	</div>
	<!-- /wp:group -->
</div>
<!-- /wp:group -->
