# 50 · Theme & bilingual setup (Phase 2)

## What Phase 2 adds

- **`wp-content/themes/easymakebot/`** — a custom block theme.
  - `theme.json` — the blue, logo-derived palette (`--accent #0f7fc4`), the type
    scale, spacing, and layout widths. Fonts are **self-hosted** woff2 in
    `assets/fonts/` (Vazirmatn for FA + Latin body, Sora for Latin display,
    IBM Plex Sans as a Latin body fallback) — no Google Fonts CDN.
  - `assets/app.css` — the composite section styles (hero + Telegram chat mock,
    the numbered feature rows, pricing cards, FAQ accordion, final CTA). All
    classes are prefixed `emb-`. Loaded on the front end and in the editor.
  - `parts/header.html`, `parts/footer.html` — language-agnostic; the nav, the
    CTA button and the footer note come from shortcodes in `functions.php`
    (`[emb_nav]`, `[emb_cta_button]`, `[emb_footer_note]`, `[emb_lang_switcher]`)
    so one template part serves both languages.
  - `templates/` — `front-page`, `page`, `page-wide` (no title), `single`,
    `index`, `archive`, `404`.
  - `patterns/` — `hero`, `why`, `features`, `steps`, `pricing`, `faq`, `cta`
    (Persian) composed by `front-page.php`; `front-page-en.php` carries the full
    English page in one file.

- **Polylang** — `fa` is the default language and lives at `/`; `en` lives at
  `/en/`. The front page and the blog page are created in both languages and
  linked as translations.

- **The SEO Framework** (`autodescription`) — configured by
  `scripts/seo-setup.php`: XML sitemap at `/sitemap.xml` (+ `/en/sitemap.xml`),
  Organization + WebSite JSON-LD, Open Graph / Twitter cards, canonical + Polylang
  `hreflang`. Hand-written `_genesis_title` / `_genesis_description` on the FA + EN
  home, blog, and **`/shop/`** (the plan store); the **tutorials archive** title /
  description come from the TSF post-type-archive settings
  (`autodescription-site-settings['pta']['tutorial']`) so it isn't
  "Archives: Tutorials". `title_rem_additions` + `homepage_tagline=0` stop TSF
  appending the site name. `author_noindex` / `date_noindex` on; **`/verify/`,
  `/cart/`, `/checkout/`, `/my-account/` are `noindex`** and kept out of the
  sitemap (TSF auto-noindexes the WC pages; `/verify/` gets `_genesis_noindex`
  in seo-setup.php). `blog_public` is **1** (indexable) — flip to `0` on a staging
  host you don't want crawled.
  Known gap: `/en/tutorials/` inherits the Persian archive title (Polylang free
  can't translate TSF's pta settings).
  *Technical SEO only.* Ranking still needs real content, keywords and backlinks.

- **Sticky header + dark mode** — the header (`.site-header`, the template-part
  wrapper) is `position: sticky` with a `backdrop-filter` blur, so content
  frosts as it scrolls under it; `.is-stuck` (added by `app.js` past 8px scroll)
  drops a shadow. `.admin-bar .site-header { top: 32px }` keeps it clear of the
  logged-in WP toolbar. The `[emb_theme_toggle]` button cycles **auto → light →
  dark**; choice is saved in `localStorage['emb-theme']` and applied by a tiny
  inline `<head>` script before first paint (no flash). Dark palette lives in
  `app.css` as overrides of the `--wp--preset--color--*` tokens under
  `@media (prefers-color-scheme: dark)` and `:root[data-theme="dark"]`.

- **Tutorials (آموزش)** — a `tutorial` custom post type (`inc/tutorials.php`):
  block-editor body + featured image + a **"Video URL"** side field (`_emb_video_url`,
  Aparat / YouTube / Vimeo / direct mp4 — Aparat is registered as an oEmbed
  provider). Archive at `/tutorials/` (`templates/archive-tutorial.html`), single at
  `templates/single-tutorial.html` (video rendered on top via
  `[emb_tutorial_video]`). `[emb_tutorials count="3"]` shows the latest on the home
  page. Polylang-enabled. Seed + rewrite-flush: `scripts/tutorials-setup.php`.
  Add a tutorial: **wp-admin → آموزش‌ها → افزودن آموزش**.

- **Ads — removed before launch.** The `[emb_ad]` slots, the `emb-ad-*` widget
  sidebars, `scripts/ads-setup.php` and the house-ad CSS are all gone;
  `[emb_ad]` is kept as a no-op shortcode only so stale saved content doesn't
  print literal text.

- **Legal pages** — `/terms/` + `/privacy/` (fa, `pll` language fa) with EN
  copies `/en/terms-en/` + `/en/privacy-en/` (distinct `-en` slugs — Polylang
  free can't route `/en/terms/`). Created by `scripts/accounts-setup.php`
  (real AUP + privacy text, bilingual; WP's `wp_page_for_privacy_policy` points
  at ours). Helpers `emb_terms_url()` / `emb_privacy_url()` (in
  `emb-accounts.php`) return the current language's canonical URL; used by the
  ToS checkboxes and the footer `[emb_legal_links]` shortcode.

- **Bilingual tutorial templates** — `archive-tutorial.html` /
  `single-tutorial.html` had hardcoded Persian headings, nav labels and a
  hardcoded `/tutorials/` "all tutorials" link. Now driven by
  `[emb_tut_ui key="head|none|back"]` (in `inc/tutorials.php`) + core
  `post-navigation-link` set to show the adjacent post's own title. The TSF
  `<title>` for `/en/tutorials/` is forced to English via the
  `the_seo_framework_pre_get_document_title` filter (Polylang free can't
  translate TSF's post-type-archive settings).

## Reproducing it

`scripts/install.sh` runs these automatically when the theme is present. To run
them by hand against a live stack:

```sh
cd web
docker compose run --rm wpcli sh /scripts/theme-setup.sh              # theme, front page, logo, permalinks
docker compose run --rm wpcli wp eval-file /scripts/i18n-setup.php    # fa + en, translations
docker compose run --rm wpcli wp eval-file /scripts/seo-setup.php     # TSF settings, titles, sitemap
docker compose run --rm wpcli wp eval-file /scripts/tutorials-setup.php  # tutorial CPT rewrites + seed
docker compose run --rm wpcli wp eval-file /scripts/shop-setup.php      # WooCommerce + plans + ZarinPal
```

All scripts are idempotent.

## Editing content

Everything on the home page is normal Gutenberg blocks — edit **Pages → خانه**
(FA) or **Pages → Home** (EN) in wp-admin. The look is driven by the `emb-*`
classes in `assets/app.css`; changing copy or reordering sections needs no code.

To restyle globally, edit `theme.json` (colours/type) or `assets/app.css`
(section layout). After editing `theme.json`, run
`docker compose run --rm wpcli wp theme update easymakebot --version=dev` is *not*
needed — just hard-refresh; WP reads `theme.json` live in dev.

## Gotchas

- **nginx serves `wp-content` static files directly.** The theme and mu-plugins
  are bind-mounted into the nginx container as well as the PHP containers (see
  both compose files). If you add another bind-mounted plugin/theme, mount it
  into nginx too or its CSS/JS/fonts will 404.
- `/sitemap.xml`, `/robots.txt` and `/*sitemap*.xsl` are **dynamic** — nginx has
  explicit `location` blocks routing them to PHP *before* the static-asset regex
  (in `default.conf` and `prod.conf.template`).
- `easymakebot-harden.php` strips `?ver=` from **core** assets only
  (`/wp-includes/`, `/wp-admin/`) — theme/plugin assets keep it, so bumping
  `EMB_THEME_VER` in `functions.php` busts the CSS/JS cache on a release.
- After any change to Polylang's language/URL settings, flush rewrite rules
  (`wp rewrite flush --hard`) or `/en/` 404s.
- The nav labels for a **new** page you want in the header live in
  `functions.php → emb_nav_items()` (one array per language), not in a WP menu.

- **Plans store (Phase 4 — Iran / ZarinPal)** — WooCommerce, currency **IRT
  (تومان)**, country IR, no shipping/tax, guest checkout off. Four virtual
  products (`emb-plan-1m/3m/6m/12m`, SKUs) at 990,000 / 2,670,000 / 4,750,000 /
  7,900,000 تومان, category `plans`. The plan grid is the `[emb_plans]`
  shortcode (a language-scoped `WP_Query`, ordered by `_emb_plan_months`),
  embedded in the home page's `#pricing` section (`patterns/pricing.php`) and in
  `templates/archive-product.html` at `/shop/` (alongside `[emb_shop_intro]`; no
  breadcrumb/sort/count). `templates/single-product.html` for the plan page.
  Gateway: **پرداخت امن زرین‌پال** (`zarinpal-woocommerce-payment-gateway`, id
  `WC_ZPal`), enabled, **sandbox ON**. Theme glue: `inc/shop.php`
  (`add_theme_support('woocommerce')`, trims store chrome, `[emb_shop_intro]`,
  checkout fields trimmed to email + name for virtual carts, hides `emb_ton`
  from the on-site checkout). Styling lives in `app.css` (WooCommerce section).
  Setup: `scripts/shop-setup.php` (idempotent). **YOU must add the ZarinPal
  merchant code** in wp-admin › WooCommerce › تنظیمات › پرداخت‌ها › پرداخت امن
  زرین‌پال, then turn **sandbox off** to go live.

- **WordPress core is now 7.1** (`docker-compose.yml` image `wordpress:7.1-php8.3-fpm`;
  WooCommerce 11 requires WP ≥ 6.9). If the container was created from the old
  6.7 image, `docker compose up -d` re-pulls; the WP files in the `wp_data`
  volume were already updated in place with `wp core update`.

- **Plan activation codes (bridge to the bot)** —
  `wp-content/mu-plugins/emb-activation-codes.php` + table
  `{prefix}emb_activation_codes`. When a plan order is paid
  (`woocommerce_order_status_processing`/`completed`) one code `EMB-XXXX-XXXX`
  is issued per plan line item and shown on the thank-you page, the customer
  email, and My Account. Refund/cancel/fail → the pending code is voided.
  REST (needs header `X-EMB-Key` = env `EMB_ACTIVATION_KEY`, in
  `docker-compose.yml`'s `x-wp-env` + `.env`):
  - `POST /wp-json/emb/v1/redeem` `{code, bot_id, telegram_id}` → atomically
    marks the code redeemed, returns `{ok:true, days, months}`.
  - `GET  /wp-json/emb/v1/check?code=…` → `{valid, status, days, months}` (no consume).
  The @easymakebot bot calls `redeem` from `/live` → "🎟 Activate with a code"
  (`bot/website_client.py`, `bot/handlers/live.py`); it sets the *selected*
  bot's `live_until` (extending from a future expiry if there is one).
  **Set `EMB_ACTIVATION_KEY` in `web/.env` and the same value as
  `WEBSITE_ACTIVATION_KEY` in the bot's `.env`** (+ `WEBSITE_URL`), or the
  endpoint 503s and the bot hides the option.

- **International plans — TON / USDT, auto-verified (Phase 4b)** —
  `wp-content/mu-plugins/emb-ton-gateway.php` + an inline panel on `/en/`.
  Polylang free can't route `/en/cart/` or `/en/checkout/` (needs the paid WC
  addon), and a shared cart across `/` and `/en/` mixed currencies/languages, so
  **the EN side has no WooCommerce cart or checkout templates at all**. Instead:

  - **The grid.** `[emb_plans]` (in `patterns/front-page-en.php`) renders the 4
    plans with **USD** prices from product meta `_emb_usd_price` (9.99 / 24.99 /
    42.99 / 69.99; set by `shop-setup.php`) and English names from `_emb_en_name`.
    Currency context is URL-based: `emb_shop_ccy()` in `inc/shop.php` returns
    `USD` for any `/en/…` path. Each card's "Choose" button carries
    `data-emb-buy` / `-usd` / `-name`.
  - **The panel.** `assets/app.js` opens `#emb-buy-panel` (a modal + scrim),
    collects an email, and `POST`s to **`/wp-json/emb/v1/ton-order`**
    `{product_id, email}`. That creates a WooCommerce order **in USD**
    (`set_currency('USD')`, `payment_method = emb_ton`, status **on-hold**,
    `created_via = emb-en`), stores meta
    `_emb_ton_{usd,rate,expected_nano,comment}` (comment = `EMB-<order_id>`),
    and returns `{order_id, key, pay_html}`. The panel swaps in `pay_html` (the
    same pay box used on the fa thank-you page: wallet + "send X USDT / Y TON" +
    the `EMB-<id>` memo + a `ton://transfer/…` deep link) and polls
    **`GET /wp-json/emb/v1/ton-status?order_id=&key=`** every 15 s; on `paid` it
    shows the activation code inline.
  - **Matching.** A recurring Action-Scheduler job (`emb_ton_poll`, 2-min, self-
    unschedules when nothing is on-hold), the `ton-status` endpoint's
    opportunistic check, and an on-demand `?emb_ton_check=<id>&key=<order_key>`
    link all call `emb_ton_try_match_orders()`, which pulls
    `tonapi.io/v2/accounts/{wallet}/events`, matches **by memo + amount ≥
    expected × (1 − tolerance%)** (TON *or* USDT leg), writes `_emb_ton_txid`,
    and calls `payment_complete()` → the activation code issues as usual
    (`emb-activation-codes.php`). Idempotent on re-run.
  - **Single-currency workaround.** The store is 0-decimal IRT, which would
    round a USD order to whole dollars. `emb_ton_usd_context()` +
    a `wc_get_price_decimals` filter force **2 decimals** whenever the request is
    USD-side (our REST routes, any `/en/` page, an admin screen for an `emb_ton`
    order, or the `emb_ton_dp2` global set around `payment_complete()` so the
    completion email keeps cents). The fa store is untouched. Payment matching
    reads `_emb_ton_usd` meta directly, so it's exact regardless.
  - **The fa checkout** keeps normal WooCommerce (Toman / ZarinPal); `inc/shop.php`
    unsets `emb_ton` from `woocommerce_available_payment_gateways` and the
    gateway's `is_available()`/`process_payment()` both refuse — it exists only
    for the REST flow.
  - **Set the receive wallet** in wp-admin › WooCommerce › Payments ›
    "TON / USDT (international)" (prefilled with the operator's Tonkeeper
    address, `UQCsXmq18JNw6yffYmxJ1PYI--NhWeIMGk5MJLLIB3sa05pi`); an optional
    free `tonapi.io` key raises the rate limit. USDT on TRON (TRC-20) is **not**
    auto-matched (no memo field) — buyers must use the TON network.
  - Verified end-to-end (mocked on-chain event via the `emb_ton_pre_fetch_incoming`
    filter): `/en/` grid → panel → `ton-order` creates a `$24.99` USD order →
    pay box with working deep link → simulated payment → order `processing` +
    code `EMB-XXXX-XXXX` → `ton-status` returns `{status:paid, codes:[…]}`.
    Under-payment rejected; re-runs idempotent. The fa `/` grid still shows
    Toman + "افزودن به سبد خرید" and ZarinPal is the only checkout gateway.

- **Site accounts & verified purchase (Phase 4c)** —
  `wp-content/mu-plugins/emb-accounts.php` + `scripts/accounts-setup.php`.
  **Only a logged-in, verified account may buy a plan** (anti-abuse). Accounts
  are native WP users + the WooCommerce My Account page; profile data lands in
  standard billing user-meta so checkout auto-fills. Staff
  (`administrator`/`shop_manager`) are auto-verified.
  - **fa registration** — extra fields injected on the WooCommerce register form
    (`woocommerce_register_form`): first name, last name, **موبایل**
    (`billing_phone`, `09xxxxxxxxx`, normalised incl. Persian digits + `+98`),
    **آدرس** (`billing_address_1`). Password is user-chosen
    (`woocommerce_registration_generate_password = no`).
    `woocommerce_registration_errors` validates + enforces **one verified account
    per phone**; `woocommerce_created_customer` saves meta, sets
    `emb_verify_channel = sms`, and sends an SMS code. Until verified, the My
    Account page content is replaced (via a `the_content` filter armed in
    `template_redirect`) with the **verify form** (`[emb_verify]` /
    `[data-emb-verify]` — code input + resend + logout).
  - **en registration/login** — passwordless email code, REST-driven so it works
    inline (no `/en/my-account/` route under Polylang free):
    `POST emb/v1/auth-start {email,lang}` (find/create user, email a code — never
    reveals whether the user existed) → `POST emb/v1/auth-verify {email,code}`
    (verify + `wp_set_auth_cookie`; returns a **fresh `wp_rest` nonce**, since the
    page nonce was minted logged-out — `set_logged_in_cookie` is captured into
    `$_COOKIE` first so the new nonce validates on the next call). Surfaces:
    the `#account` section on `/en/` (`[emb_auth]` widget) and an **email-code
    pre-step inside the buy panel** (`app.js`: `email → code → pay`, skipped when
    `window.embAuth.verified`).
  - **OTP core** — 6 digits, 10-min TTL (transient `emb_otp_{uid}`,
    `password_hash`), 5 verify attempts, resend throttle 60 s + 5/hour. Logged-in
    endpoints `emb/v1/otp-verify` / `otp-resend` back the verify form.
  - **SMS driver** (`emb_sms_send`, filter `emb_sms_pre_send` for tests):
    `emb_sms_driver()` option `log` (default — writes
    `wp-content/uploads/emb-sms.log`) | `kavenegar` (`verify/lookup` endpoint,
    ok when `return.status == 200`). Key + template: **wp-admin › Settings ›
    easymakebot** (`add_options_page`) or env `EMB_SMS_API_KEY` /
    `EMB_SMS_TEMPLATE` / `EMB_SMS_DRIVER` (in `docker-compose.yml` `x-wp-env`).
  - **Gates** — logged-out/unverified: fa `[emb_plans]` shows
    "برای خرید وارد شوید" → `/my-account/`; `template_redirect` bounces
    `cart`/`checkout` (guest → `?emb_login=buy`, unverified → My Account);
    `woocommerce_checkout_process` adds an error notice. `emb_ton_rest_create_order`
    returns `{ok:false,error:'login_required'}` and ties the order to the verified
    user (`customer_id`, account email).
  - **Header** — `[emb_account_link]` (added to `parts/header.html`): logged-out
    "ورود / ثبت‌نام" / "Sign in"; unverified "تأیید حساب" / "Verify account"
    (`is-unverified` dot); verified "حساب من" (fa) / "Sign out" (en).
  - **Fraud / abuse accountability** — a required **Terms of Service** checkbox
    on every registration path (fa form + en `[emb_auth]` + buy panel), linking
    `/terms/` (+ `/terms-en/`); acceptance stored as user meta `emb_tos`
    (`EMB_TOS_VERSION` + timestamp + IP + country — bump the constant to
    re-prompt). REST `auth-start` returns `{error:'tos_required'}` without it.
    Sign-up + purchase **IP / country** captured (`emb_signup_*`, order meta
    `_emb_buyer_*`) via `emb_request_ip()` / `emb_request_country()` (Cloudflare
    `CF-Connecting-IP` / `CF-IPCountry` — no-op until CF is in front). Crypto
    **sender wallet** stored on match (`_emb_ton_sender`, from the tonapi event).
    The bot's `/live` code-redeem now forwards the redeemer's **Telegram id /
    @username / name** and a **Telegram-verified phone** (contact-share gate
    before the first paid activation — `bot/handlers/live.py`); the website
    stores them on the `emb_activation_codes` row (schema v2:
    `redeemed_by_username` / `redeemed_by_name` / `redeemed_phone`) and the
    order. Admin sees it all in the "شناسه" user-profile box and the
    "ردیابی تخلف" order box. Full playbook: `docs/60-abuse-response.md`.
  - **Operator setup:** create a Kavenegar account, pass identity check, add an
    approved `verify/lookup` OTP template, then in wp-admin › Settings ›
    easymakebot set driver = Kavenegar + paste the API key + template name.
    Until then `log` driver keeps the whole flow testable.
  - Verified end-to-end: fa register (Persian-digit phone) → SMS code from the log
    → verify → dashboard + checkout unlocked (ZarinPal); en logged-out → buy panel
    email → code (EN subject) → verify (fresh nonce) → pay box `EMB-<id>` /
    `24.99 USDT` → simulated payment → `processing` + activation code; guest
    `ton-order` → `login_required`; OTP `too_soon`/`expired`/`too_many` all fire.
