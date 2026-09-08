<?php
/**
 * My Account — login / register, shown one at a time (not side by side).
 * Overrides WooCommerce's default two-column form-login.php. Toggled by
 * ?action=register on the My Account URL; every other query arg (e.g. the
 * emb_login=buy hint from emb-accounts.php) is preserved across the toggle.
 *
 * @see WC_Shortcode_My_Account, templates/myaccount/form-login.php
 */

defined( 'ABSPATH' ) || exit;

$emb_registration_open = 'yes' === get_option( 'woocommerce_enable_myaccount_registration' );
$emb_show_register     = $emb_registration_open && isset( $_GET['action'] ) && 'register' === $_GET['action']; // phpcs:ignore WordPress.Security.NonceVerification

$emb_current_url  = home_url( add_query_arg( null, null ) );
$emb_register_url = add_query_arg( 'action', 'register', $emb_current_url );
$emb_login_url    = remove_query_arg( 'action', $emb_current_url );

do_action( 'woocommerce_before_customer_login_form' );
?>

<div class="emb-auth emb-account-form" id="customer_login">

<?php if ( ! $emb_show_register ) : ?>

	<h2><?php esc_html_e( 'ورود', 'easymakebot' ); ?></h2>

	<form class="woocommerce-form woocommerce-form-login login" method="post">

		<?php do_action( 'woocommerce_login_form_start' ); ?>

		<label class="emb-auth__field">
			<span><?php esc_html_e( 'نام کاربری یا آدرس ایمیل', 'easymakebot' ); ?>&nbsp;<span class="required">*</span></span>
			<input type="text" name="username" id="username" autocomplete="username" value="<?php echo ( ! empty( $_POST['username'] ) ) ? esc_attr( wp_unslash( $_POST['username'] ) ) : ''; // phpcs:ignore WordPress.Security.NonceVerification ?>" />
		</label>
		<label class="emb-auth__field">
			<span><?php esc_html_e( 'گذرواژه', 'easymakebot' ); ?>&nbsp;<span class="required">*</span></span>
			<input type="password" name="password" id="password" autocomplete="current-password" />
		</label>

		<?php do_action( 'woocommerce_login_form' ); ?>

		<label class="emb-auth__tos">
			<input type="checkbox" name="rememberme" id="rememberme" value="forever" />
			<span><?php esc_html_e( 'مرا به خاطر بسپار', 'easymakebot' ); ?></span>
		</label>

		<?php wp_nonce_field( 'woocommerce-login', 'woocommerce-login-nonce' ); ?>
		<button type="submit" class="emb-auth__go button woocommerce-form-login__submit" name="login" value="<?php esc_attr_e( 'ورود', 'easymakebot' ); ?>"><?php esc_html_e( 'ورود', 'easymakebot' ); ?></button>

		<?php do_action( 'woocommerce_login_form_end' ); ?>

	</form>

	<p class="emb-auth__meta">
		<a class="woocommerce-LostPassword lost_password" href="<?php echo esc_url( wp_lostpassword_url() ); ?>"><?php esc_html_e( 'گذرواژهٔ خود را فراموش کرده‌اید؟', 'easymakebot' ); ?></a>
		<?php if ( $emb_registration_open ) : ?>
			&nbsp;·&nbsp;<?php esc_html_e( 'حساب ندارید؟', 'easymakebot' ); ?>
			<a class="emb-account-form__switch" href="<?php echo esc_url( $emb_register_url ); ?>"><?php esc_html_e( 'ثبت‌نام', 'easymakebot' ); ?></a>
		<?php endif; ?>
	</p>

<?php else : ?>

	<h2><?php esc_html_e( 'ثبت‌نام', 'easymakebot' ); ?></h2>

	<form method="post" class="woocommerce-form woocommerce-form-register register" <?php do_action( 'woocommerce_register_form_tag' ); ?>>

		<?php do_action( 'woocommerce_register_form_start' ); ?>

		<?php if ( 'no' === get_option( 'woocommerce_registration_generate_username' ) ) : ?>
		<label class="emb-auth__field">
			<span><?php esc_html_e( 'نام کاربری', 'easymakebot' ); ?>&nbsp;<span class="required">*</span></span>
			<input type="text" name="username" id="reg_username" autocomplete="username" value="<?php echo ( ! empty( $_POST['username'] ) ) ? esc_attr( wp_unslash( $_POST['username'] ) ) : ''; // phpcs:ignore WordPress.Security.NonceVerification ?>" />
		</label>
		<?php endif; ?>

		<label class="emb-auth__field">
			<span><?php esc_html_e( 'آدرس ایمیل', 'easymakebot' ); ?>&nbsp;<span class="required">*</span></span>
			<input type="email" name="email" id="reg_email" autocomplete="email" value="<?php echo ( ! empty( $_POST['email'] ) ) ? esc_attr( wp_unslash( $_POST['email'] ) ) : ''; // phpcs:ignore WordPress.Security.NonceVerification ?>" />
		</label>

		<?php if ( 'no' === get_option( 'woocommerce_registration_generate_password' ) ) : ?>
		<label class="emb-auth__field">
			<span><?php esc_html_e( 'گذرواژه', 'easymakebot' ); ?>&nbsp;<span class="required">*</span></span>
			<input type="password" name="password" id="reg_password" autocomplete="new-password" />
		</label>
		<?php else : ?>
		<p><?php esc_html_e( 'لینک تنظیم گذرواژه به ایمیل شما فرستاده می‌شود.', 'easymakebot' ); ?></p>
		<?php endif; ?>

		<?php do_action( 'woocommerce_register_form' ); ?>

		<?php wp_nonce_field( 'woocommerce-register', 'woocommerce-register-nonce' ); ?>
		<button type="submit" class="emb-auth__go button woocommerce-form-register__submit" name="register" value="<?php esc_attr_e( 'ثبت‌نام', 'easymakebot' ); ?>"><?php esc_html_e( 'ثبت‌نام', 'easymakebot' ); ?></button>

		<?php do_action( 'woocommerce_register_form_end' ); ?>

	</form>

	<p class="emb-auth__meta">
		<?php esc_html_e( 'قبلاً حساب ساخته‌اید؟', 'easymakebot' ); ?>
		<a class="emb-account-form__switch" href="<?php echo esc_url( $emb_login_url ); ?>"><?php esc_html_e( 'ورود', 'easymakebot' ); ?></a>
	</p>

<?php endif; ?>

</div>

<?php do_action( 'woocommerce_after_customer_login_form' ); ?>
