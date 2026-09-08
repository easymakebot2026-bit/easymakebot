<?php
/**
 * "آموزش" — a Tutorial custom post type: video + text + image, edited from
 * wp-admin, listed at /tutorials/. Bilingual via Polylang.
 *
 * @package easymakebot
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/* ── Custom post type + taxonomy ─────────────────────────────────────── */
add_action( 'init', function () {

	register_post_type( 'tutorial', array(
		'labels'        => array(
			'name'               => __( 'Tutorials', 'easymakebot' ),
			'singular_name'      => __( 'Tutorial', 'easymakebot' ),
			'menu_name'          => __( 'آموزش‌ها', 'easymakebot' ),
			'add_new'            => __( 'افزودن آموزش', 'easymakebot' ),
			'add_new_item'       => __( 'افزودن آموزش تازه', 'easymakebot' ),
			'edit_item'          => __( 'ویرایش آموزش', 'easymakebot' ),
			'new_item'           => __( 'آموزش تازه', 'easymakebot' ),
			'view_item'          => __( 'دیدن آموزش', 'easymakebot' ),
			'search_items'       => __( 'جستجوی آموزش‌ها', 'easymakebot' ),
			'not_found'          => __( 'آموزشی پیدا نشد', 'easymakebot' ),
			'all_items'          => __( 'همهٔ آموزش‌ها', 'easymakebot' ),
		),
		'public'        => true,
		'has_archive'   => 'tutorials',
		'rewrite'       => array( 'slug' => 'tutorials', 'with_front' => false ),
		'menu_icon'     => 'dashicons-video-alt3',
		'menu_position' => 22,
		'supports'      => array( 'title', 'editor', 'excerpt', 'thumbnail', 'revisions', 'custom-fields', 'author' ),
		'show_in_rest'  => true,
	) );

	register_taxonomy( 'tutorial_cat', 'tutorial', array(
		'labels'            => array(
			'name'          => __( 'دسته‌های آموزش', 'easymakebot' ),
			'singular_name' => __( 'دستهٔ آموزش', 'easymakebot' ),
			'menu_name'     => __( 'دسته‌ها', 'easymakebot' ),
		),
		'public'            => true,
		'hierarchical'      => true,
		'show_admin_column' => true,
		'show_in_rest'      => true,
		'rewrite'           => array( 'slug' => 'tutorials/topic', 'with_front' => false ),
	) );
} );

/* ── "Video URL" meta box (Aparat / YouTube / Vimeo / direct mp4) ─────── */
add_action( 'add_meta_boxes', function () {
	add_meta_box(
		'emb_tutorial_video',
		__( 'ویدیوی آموزش', 'easymakebot' ),
		'emb_tutorial_video_box',
		'tutorial',
		'side',
		'high'
	);
} );

function emb_tutorial_video_box( $post ) {
	wp_nonce_field( 'emb_tutorial_video', 'emb_tutorial_video_nonce' );
	$url = get_post_meta( $post->ID, '_emb_video_url', true );
	echo '<p><label for="emb_video_url"><strong>' . esc_html__( 'لینک ویدیو', 'easymakebot' ) . '</strong></label></p>';
	echo '<input type="url" id="emb_video_url" name="emb_video_url" value="' . esc_attr( $url ) . '" placeholder="https://www.aparat.com/v/…" style="width:100%">';
	echo '<p class="description">' . esc_html__( 'لینک آپارات، یوتیوب، ویمئو یا یک فایل mp4. بالای صفحهٔ آموزش نمایش داده می‌شود. برای ویدیوهای داخل متن از بلوک ویدیو استفاده کن.', 'easymakebot' ) . '</p>';
}

add_action( 'save_post_tutorial', function ( $post_id ) {
	if ( ! isset( $_POST['emb_tutorial_video_nonce'] ) ||
		! wp_verify_nonce( sanitize_key( $_POST['emb_tutorial_video_nonce'] ), 'emb_tutorial_video' ) ) {
		return;
	}
	if ( defined( 'DOING_AUTOSAVE' ) && DOING_AUTOSAVE ) {
		return;
	}
	if ( ! current_user_can( 'edit_post', $post_id ) ) {
		return;
	}
	$url = isset( $_POST['emb_video_url'] ) ? esc_url_raw( wp_unslash( $_POST['emb_video_url'] ) ) : '';
	if ( $url ) {
		update_post_meta( $post_id, '_emb_video_url', $url );
	} else {
		delete_post_meta( $post_id, '_emb_video_url' );
	}
} );

/* ── Aparat oEmbed (WordPress already knows YouTube/Vimeo) ───────────── */
add_action( 'init', function () {
	wp_oembed_add_provider( '#https?://(www\.)?aparat\.com/v/.*#i', 'https://www.aparat.com/oembed', true );
	wp_oembed_add_provider( '#https?://(www\.)?aparat\.com/.*#i', 'https://www.aparat.com/oembed', true );
} );

/* ── [emb_tutorial_video] — renders the meta video (embed or <video>) ── */
add_shortcode( 'emb_tutorial_video', function () {
	if ( ! is_singular( 'tutorial' ) ) {
		return '';
	}
	$url = get_post_meta( get_the_ID(), '_emb_video_url', true );
	if ( ! $url ) {
		return '';
	}
	$out = '<div class="emb-tut__video">';
	if ( preg_match( '/\.(mp4|webm|ogv)(\?.*)?$/i', $url ) ) {
		$out .= '<video controls preload="metadata" playsinline src="' . esc_url( $url ) . '"></video>';
	} else {
		$embed = wp_oembed_get( $url, array( 'width' => 1200 ) );
		$out  .= $embed ? $embed : '<a href="' . esc_url( $url ) . '" target="_blank" rel="noopener">' . esc_html__( 'تماشای ویدیو', 'easymakebot' ) . '</a>';
	}
	$out .= '</div>';
	return $out;
} );

/* ── Latest tutorials, for the home page: [emb_tutorials count="3"] ───── */
add_shortcode( 'emb_tutorials', function ( $atts ) {
	$a = shortcode_atts( array( 'count' => 3 ), $atts, 'emb_tutorials' );
	$args = array(
		'post_type'      => 'tutorial',
		'posts_per_page' => max( 1, (int) $a['count'] ),
		'no_found_rows'  => true,
	);
	if ( function_exists( 'pll_current_language' ) ) {
		$args['lang'] = pll_current_language();
	}
	$q = new WP_Query( $args );
	if ( ! $q->have_posts() ) {
		return '';
	}
	$lang    = function_exists( 'pll_current_language' ) ? pll_current_language() : 'fa';
	$more    = ( 'en' === $lang ) ? 'All tutorials' : 'همهٔ آموزش‌ها';
	$archive = get_post_type_archive_link( 'tutorial' );

	$out = '<div class="emb-tut-grid">';
	while ( $q->have_posts() ) {
		$q->the_post();
		$thumb = get_the_post_thumbnail( get_the_ID(), 'medium_large', array( 'loading' => 'lazy', 'alt' => '' ) );
		$out  .= '<a class="emb-tut-card" href="' . esc_url( get_permalink() ) . '">';
		$out  .= '<span class="emb-tut-card__media">' . ( $thumb ? $thumb : '<span class="emb-tut-card__ph">▶</span>' ) . '</span>';
		$out  .= '<span class="emb-tut-card__title">' . esc_html( get_the_title() ) . '</span>';
		$out  .= '<span class="emb-tut-card__excerpt">' . esc_html( wp_trim_words( get_the_excerpt(), 16 ) ) . '</span>';
		$out  .= '</a>';
	}
	wp_reset_postdata();
	$out .= '</div>';
	if ( $archive ) {
		$out .= '<p class="emb-tut-more"><a class="wp-block-button__link wp-element-button" href="' . esc_url( $archive ) . '">' . esc_html( $more ) . '</a></p>';
	}
	return $out;
} );

/* ── Language-aware UI bits for the tutorial templates: [emb_tut_ui key="…"] ──
 * Block templates can't branch on language; these keep archive-tutorial.html /
 * single-tutorial.html correct in both fa and en.
 *   key = head  → archive kicker + <h1> + intro paragraph
 *   key = none  → "no tutorials yet" paragraph
 *   key = back  → "← all tutorials" button, linking the current language's archive
 */
add_shortcode( 'emb_tut_ui', function ( $atts ) {
	$a   = shortcode_atts( array( 'key' => 'head' ), $atts, 'emb_tut_ui' );
	$en  = function_exists( 'pll_current_language' ) ? ( 'en' === pll_current_language() ) : false;
	$arc = get_post_type_archive_link( 'tutorial' );

	switch ( $a['key'] ) {
		case 'none':
			return '<p>' . ( $en ? 'No tutorials published yet.' : 'هنوز آموزشی منتشر نشده.' ) . '</p>';

		case 'back':
			if ( ! $arc ) {
				return '';
			}
			return '<div class="wp-block-buttons" style="margin-top:var(--wp--preset--spacing--40)">'
				. '<div class="wp-block-button is-style-outline"><a class="wp-block-button__link wp-element-button" href="'
				. esc_url( $arc ) . '">' . ( $en ? '← All tutorials' : '← همهٔ آموزش‌ها' ) . '</a></div></div>';

		case 'head':
		default:
			$h1    = $en ? 'Tutorials' : 'آموزش‌ها';
			$intro = $en
				? 'Videos and step-by-step guides for building a bot with easymakebot.'
				: 'ویدیوها و راهنماهای گام‌به‌گام ساخت ربات با easymakebot.';
			return '<div class="wp-block-group emb-section__intro">'
				. '<p class="emb-kicker">easymakebot</p>'
				. '<h1 class="wp-block-heading">' . esc_html( $h1 ) . '</h1>'
				. '<p class="has-ink-soft-color has-text-color" style="font-size:1.05rem">' . esc_html( $intro ) . '</p>'
				. '</div>';
	}
} );

/* Make TSF's <title> for the tutorial archive follow the language too
 * (Polylang free can't translate TSF's post-type-archive settings). */
add_filter( 'the_seo_framework_pre_get_document_title', function ( $title ) {
	if ( function_exists( 'is_post_type_archive' ) && is_post_type_archive( 'tutorial' )
		&& function_exists( 'pll_current_language' ) && 'en' === pll_current_language() ) {
		return 'Tutorials — easymakebot';
	}
	return $title;
}, 20 );
// fallback for non-TSF renders
add_filter( 'document_title', function ( $title ) {
	if ( function_exists( 'is_post_type_archive' ) && is_post_type_archive( 'tutorial' )
		&& function_exists( 'pll_current_language' ) && 'en' === pll_current_language() ) {
		return 'Tutorials — easymakebot';
	}
	return $title;
}, 999 );

/* ── Polylang: make the CPT + taxonomy translatable ──────────────────── */
add_filter( 'pll_get_post_types', function ( $types ) {
	$types['tutorial'] = 'tutorial';
	return $types;
} );
add_filter( 'pll_get_taxonomies', function ( $tax ) {
	$tax['tutorial_cat'] = 'tutorial_cat';
	return $tax;
} );
