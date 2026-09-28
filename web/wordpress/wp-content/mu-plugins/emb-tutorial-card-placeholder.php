<?php
/**
 * emb-tutorial-card-placeholder.php
 *
 * Fallback for the /tutorials/ archive grid: when a "Tutorial" post has no
 * featured image, show the site logo centered on the tinted card background
 * instead of a blank card.
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

add_filter( 'render_block_core/post-featured-image', function ( $block_content, $parsed_block, $block_instance ) {
	if ( '' !== trim( $block_content ) ) {
		return $block_content;
	}

	$post_id = 0;
	if ( isset( $block_instance->context['postId'] ) ) {
		$post_id = (int) $block_instance->context['postId'];
	} elseif ( get_the_ID() ) {
		$post_id = (int) get_the_ID();
	}

	if ( ! $post_id || 'tutorial' !== get_post_type( $post_id ) ) {
		return $block_content;
	}

	$open  = '';
	$close = '';
	if ( ! empty( $parsed_block['attrs']['isLink'] ) ) {
		$open  = '<a href="' . esc_url( get_permalink( $post_id ) ) . '">';
		$close = '</a>';
	}

	$logo = esc_url( get_theme_file_uri( 'assets/logo-256.png' ) );

	return '<figure class="wp-block-post-featured-image emb-tut-card__media emb-tut-card__media--placeholder">'
		. $open . '<img src="' . $logo . '" alt="" loading="lazy" class="emb-tut-card__ph-logo" />' . $close
		. '</figure>';
}, 10, 3 );
