<?php
/**
 * Plugin Name: EMB Footer Social Icons
 * Description: Injects a minimal, single-color social icon row (Aparat, Instagram, Telegram) at the very top of the site footer, above the existing nav links. Theme-agnostic (works on classic and block/FSE themes) — targets the first <footer> element on the page and prepends the icon row as its first child via JS, so it doesn't depend on the theme's exact footer markup.
 *
 * Install: drop this file into web/wordpress/wp-content/mu-plugins/ (same convention as
 * emb-hreflang-schema.php, emb-tutorial-card-placeholder.php, etc.) — mu-plugins load
 * automatically, no activation needed.
 *
 * To change the icon color later, just edit the --emb-social-color value below.
 */

if (!defined('ABSPATH')) exit;

add_action('wp_footer', function () {
    $links = array(
        'aparat'    => 'https://www.aparat.com/easymakebot/',
        'instagram' => 'https://www.instagram.com/easymakebot',
        'telegram'  => 'https://t.me/easymakebot',
    );
    ?>
    <style>
        .emb-social-row {
            --emb-social-color: #2196F3; /* site brand blue — change here if needed */
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 22px;
            margin: 0 0 28px 0;
        }
        .emb-social-row a {
            display: inline-flex;
            width: 26px;
            height: 26px;
            color: var(--emb-social-color);
            opacity: 0.85;
            transition: opacity .15s ease, transform .15s ease;
        }
        .emb-social-row a:hover {
            opacity: 1;
            transform: translateY(-1px);
        }
        .emb-social-row svg {
            width: 100%;
            height: 100%;
            fill: none;
            stroke: currentColor;
            stroke-width: 1.6;
            stroke-linecap: round;
            stroke-linejoin: round;
        }
        .emb-social-row a.emb-icon-filled svg {
            fill: currentColor;
            stroke: none;
        }
    </style>
    <script>
    (function () {
        var footer = document.querySelector('footer');
        if (!footer || document.querySelector('.emb-social-row')) return;

        var row = document.createElement('div');
        row.className = 'emb-social-row';
        row.innerHTML =
            '<a href="<?php echo esc_url($links['aparat']); ?>" target="_blank" rel="noopener" aria-label="Aparat" class="emb-icon-filled">' +
                '<svg viewBox="0 0 68.33 68.33"><path d="M29.49,2,23.2.36A10.58,10.58,0,0,0,10.25,7.87L8.68,13.8A32.4,32.4,0,0,1,29.49,2Z"/><path d="M1.9,39.33.36,45.14A10.58,10.58,0,0,0,7.87,58.08l6,1.6A32.41,32.41,0,0,1,1.9,39.33Z"/><path d="M60.46,10.25,53.73,8.46a32.4,32.4,0,0,1,12.4,21.7l1.85-7A10.58,10.58,0,0,0,60.46,10.25Z"/><path d="M38.69,66.26,45.14,68a10.58,10.58,0,0,0,12.94-7.51l1.82-6.84A32.42,32.42,0,0,1,38.69,66.26Z"/><path d="M34.17,4.54A29.63,29.63,0,1,0,63.79,34.17,29.63,29.63,0,0,0,34.17,4.54ZM17.39,19.32a8.46,8.46,0,1,1,6.71,9.91A8.46,8.46,0,0,1,17.39,19.32ZM29.7,44.92A8.46,8.46,0,1,1,23,35,8.46,8.46,0,0,1,29.7,44.92Zm3.59-6.85a3.76,3.76,0,1,1,4.41-3A3.76,3.76,0,0,1,33.29,38.07ZM50.94,49a8.46,8.46,0,1,1-6.71-9.91A8.46,8.46,0,0,1,50.94,49Zm-5.6-15.68a8.46,8.46,0,1,1,9.91-6.71A8.46,8.46,0,0,1,45.34,33.33Z"/></svg>' +
            '</a>' +
            '<a href="<?php echo esc_url($links['instagram']); ?>" target="_blank" rel="noopener" aria-label="Instagram">' +
                '<svg viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="6"/><circle cx="12" cy="12" r="4.2"/><circle cx="17" cy="7" r="1" fill="currentColor" stroke="none"/></svg>' +
            '</a>' +
            '<a href="<?php echo esc_url($links['telegram']); ?>" target="_blank" rel="noopener" aria-label="Telegram">' +
                '<svg viewBox="0 0 24 24"><path d="M21 4 3 11.2l6 2.2M21 4l-3.4 16-7.6-6.6M21 4 9.6 14.8m0 0V20l3-3.2"/></svg>' +
            '</a>';

        footer.insertBefore(row, footer.firstChild);
    })();
    </script>
    <?php
}, 20);
