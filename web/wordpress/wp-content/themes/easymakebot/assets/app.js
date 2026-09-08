/* easymakebot theme — progressive enhancement only. The site is fully usable
   with JS disabled. */
(function () {
	"use strict";
	var root = document.documentElement;

	/* ── Theme toggle: auto → light → dark → auto ──────────────────────── */
	var ICONS = { auto: "◐", light: "☀", dark: "☾" };
	function currentMode() {
		var a = root.getAttribute("data-theme");
		return a === "dark" || a === "light" ? a : "auto";
	}
	function applyMode(mode) {
		if (mode === "auto") {
			root.removeAttribute("data-theme");
			try { localStorage.removeItem("emb-theme"); } catch (e) {}
		} else {
			root.setAttribute("data-theme", mode);
			try { localStorage.setItem("emb-theme", mode); } catch (e) {}
		}
		var btns = document.querySelectorAll("[data-emb-theme-toggle]");
		for (var i = 0; i < btns.length; i++) {
			var icon = btns[i].querySelector(".emb-theme-toggle__i");
			if (icon) { icon.textContent = ICONS[mode]; }
			btns[i].setAttribute("data-mode", mode);
		}
	}
	applyMode(currentMode());
	var toggles = document.querySelectorAll("[data-emb-theme-toggle]");
	for (var t = 0; t < toggles.length; t++) {
		toggles[t].addEventListener("click", function () {
			applyMode({ auto: "light", light: "dark", dark: "auto" }[currentMode()]);
		});
	}

	/* ── Sticky header: drop a shadow once the page has scrolled ───────── */
	var header = document.querySelector(".site-header");
	if (header) {
		var onScroll = function () {
			header.classList.toggle("is-stuck", (window.scrollY || document.documentElement.scrollTop) > 8);
		};
		onScroll();
		window.addEventListener("scroll", onScroll, { passive: true });
	}

	/* ── Accounts: shared REST helper ─────────────────────────────────── */
	var AUTH = window.embAuth || {};
	var EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
	var OTP_MSG = {
		bad_email: "That email address looks invalid.",
		tos_required: "Please accept the Terms of Service to continue.",
		rate_limited: "Too many attempts — please wait a few minutes.",
		too_soon: "Please wait a minute before requesting another code.",
		too_many_sends: "Too many code requests. Try again in an hour.",
		send_failed: "Couldn't send the code. Please try again shortly.",
		no_pending: "No code pending — request a new one.",
		expired: "That code expired — request a new one.",
		too_many: "Too many tries — request a new code.",
		mismatch: "That code isn't right.",
		no_target: "No phone or email on file to send a code to.",
		server: "Something went wrong. Please try again."
	};
	function embApi(path, body) {
		var payload = body || {};
		if (AUTH.lang && payload.lang === undefined) { payload.lang = AUTH.lang; }
		return fetch((AUTH.restBase || "/wp-json/emb/v1/") + path, {
			method: "POST",
			headers: { "Content-Type": "application/json", "X-WP-Nonce": AUTH.nonce || "" },
			body: JSON.stringify(payload)
		}).then(function (r) { return r.json(); });
	}
	function embMsg(d, fallback) { return (d && OTP_MSG[d.error]) || fallback || OTP_MSG.server; }

	/* ── /en/ plan purchase: inline TON / USDT panel ──────────────────── */
	var panel = document.getElementById("emb-buy-panel");
	if (panel) {
		var slot = function (n) { return panel.querySelector('[data-emb-slot="' + n + '"]'); };
		var stepEl = function (n) { return panel.querySelector('[data-emb-step="' + n + '"]'); };
		var errBox = panel.querySelector(".emb-buy-panel__err");
		var result = panel.querySelector(".emb-buy-panel__result");
		var goBtn = panel.querySelector(".emb-buy-panel__go");
		var sendBtn = panel.querySelector(".emb-buy-panel__send");
		var verifyBtn = panel.querySelector(".emb-buy-panel__verify");
		var scrim = document.createElement("div");
		scrim.className = "emb-buy-scrim";
		scrim.hidden = true;
		document.body.appendChild(scrim);
		panel.hidden = true;
		var pollTimer = null, curPid = 0, verified = !!AUTH.verified, authEmail = "";

		var showStep = function (name) {
			["email", "code", "pay"].forEach(function (s) {
				var el = stepEl(s); if (el) { el.hidden = s !== name; }
			});
		};
		var showErr = function (m) { errBox.textContent = m; errBox.hidden = false; };
		var clrErr = function () { errBox.hidden = true; errBox.textContent = ""; };
		var reset = function (b) {
			[goBtn, sendBtn, verifyBtn].forEach(function (x) { if (x) { x.disabled = false; } });
			if (goBtn) { goBtn.textContent = "Get payment details"; }
		};

		var close = function () {
			panel.hidden = true; scrim.hidden = true;
			if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
		};
		var open = function (btn) {
			curPid = btn.getAttribute("data-emb-buy");
			slot("name").textContent = btn.getAttribute("data-emb-name") || "";
			slot("usd").textContent = "$" + (btn.getAttribute("data-emb-usd") || "");
			clrErr(); reset();
			if (slot("tos")) { slot("tos").checked = false; }
			result.hidden = true; result.innerHTML = "";
			showStep(verified ? "pay" : "email");
			panel.hidden = false; scrim.hidden = false;
			setTimeout(function () {
				var f = verified ? goBtn : slot("email");
				if (f && f.focus) { f.focus(); }
			}, 40);
		};

		document.querySelectorAll(".emb-buy").forEach(function (b) {
			b.addEventListener("click", function () { open(b); });
		});
		panel.querySelector(".emb-buy-panel__x").addEventListener("click", close);
		scrim.addEventListener("click", close);
		document.addEventListener("keydown", function (e) { if (e.key === "Escape" && !panel.hidden) close(); });

		if (sendBtn) {
			sendBtn.addEventListener("click", function () {
				var email = (slot("email").value || "").trim();
				var tos = slot("tos") && slot("tos").checked;
				if (!EMAIL_RE.test(email)) { showErr("Please enter a valid email address."); return; }
				if (!tos) { showErr("Please accept the Terms of Service."); return; }
				clrErr(); sendBtn.disabled = true; sendBtn.textContent = "Sending…";
				embApi("auth-start", { email: email, tos: true }).then(function (d) {
					sendBtn.textContent = "Email me a code";
					if (!d || !d.ok) { sendBtn.disabled = false; showErr(embMsg(d)); return; }
					authEmail = email;
					showStep("code");
					setTimeout(function () { slot("code").focus(); }, 40);
				}).catch(function () { sendBtn.disabled = false; sendBtn.textContent = "Email me a code"; showErr("Network error. Please try again."); });
			});
		}
		if (verifyBtn) {
			verifyBtn.addEventListener("click", function () {
				var code = (slot("code").value || "").replace(/\D/g, "");
				if (code.length < 4) { showErr("Enter the 6-digit code."); return; }
				clrErr(); verifyBtn.disabled = true; verifyBtn.textContent = "Verifying…";
				embApi("auth-verify", { email: authEmail, code: code }).then(function (d) {
					verifyBtn.disabled = false; verifyBtn.textContent = "Verify & continue";
					if (!d || !d.ok) { showErr(embMsg(d)); return; }
					if (d.nonce) { AUTH.nonce = d.nonce; }  // fresh nonce for the now-logged-in session
					verified = true;
					showStep("pay");
					setTimeout(function () { goBtn.focus(); }, 40);
				}).catch(function () { verifyBtn.disabled = false; verifyBtn.textContent = "Verify & continue"; showErr("Network error. Please try again."); });
			});
		}
		var restart = panel.querySelector('[data-emb-slot="restart"]');
		if (restart) { restart.addEventListener("click", function (e) { e.preventDefault(); clrErr(); showStep("email"); slot("email").focus(); }); }

		var startPolling = function (orderId, key) {
			var check = function () {
				fetch((AUTH.restBase || "/wp-json/emb/v1/") + "ton-status?order_id=" + orderId + "&key=" + encodeURIComponent(key))
					.then(function (r) { return r.json(); })
					.then(function (d) {
						if (d && d.status === "paid") {
							clearInterval(pollTimer); pollTimer = null;
							var codes = (d.codes && d.codes.length) ? d.codes.join(", ") : "(sent by email)";
							result.innerHTML =
								'<div class="emb-ton-box is-paid"><p>✅ <strong>Payment confirmed.</strong></p>' +
								'<p>Your activation code: <code>' + codes + '</code><br>' +
								'It was emailed to ' + (d.email || "you") + '. Open <strong>@easymakebot</strong>, pick your bot, ' +
								'choose “Activate with a code” and paste it.</p>' +
								'<p><a class="button" href="https://t.me/easymakebot" target="_blank" rel="noopener">Open the bot</a></p></div>';
						}
					})
					.catch(function () {});
			};
			pollTimer = setInterval(check, 15000);
		};

		goBtn.addEventListener("click", function () {
			clrErr();
			goBtn.disabled = true; goBtn.textContent = "Creating order…";
			embApi("ton-order", { product_id: curPid }).then(function (d) {
				if (!d || !d.ok) {
					goBtn.disabled = false; goBtn.textContent = "Get payment details";
					if (d && d.error === "login_required") { verified = false; showStep("email"); showErr("Please verify your email first."); return; }
					showErr(embMsg(d, {
						bad_product: "That plan is unavailable — please reload.",
						not_configured: "Crypto payment isn't set up yet — contact support."
					}[d && d.error]));
					return;
				}
				stepEl("pay").hidden = true;
				result.hidden = false;
				result.innerHTML = d.pay_html;
				startPolling(d.order_id, d.key);
			}).catch(function () { goBtn.disabled = false; goBtn.textContent = "Get payment details"; showErr("Network error. Please try again."); });
		});
	}

	/* ── [emb_auth]: /en/ passwordless sign-in widget ─────────────────── */
	var authBox = document.querySelector("[data-emb-auth]");
	if (authBox) {
		var aStep = function (n) { return authBox.querySelector('[data-emb-auth-step="' + n + '"]'); };
		var aErr = authBox.querySelector(".emb-auth__err");
		var aEmailIn = authBox.querySelector("[data-emb-auth-email]");
		var aCodeIn = authBox.querySelector("[data-emb-auth-code]");
		var aSend = authBox.querySelector("[data-emb-auth-send]");
		var aVerify = authBox.querySelector("[data-emb-auth-verify]");
		var aRestart = authBox.querySelector("[data-emb-auth-restart]");
		var aEmail = "";
		var aShowErr = function (m) { aErr.textContent = m; aErr.hidden = false; };
		var aTos = authBox.querySelector("[data-emb-auth-tos]");
		if (aSend) {
			aSend.addEventListener("click", function () {
				var v = (aEmailIn.value || "").trim();
				if (!EMAIL_RE.test(v)) { aShowErr("Please enter a valid email address."); return; }
				if (aTos && !aTos.checked) { aShowErr("Please accept the Terms of Service."); return; }
				aErr.hidden = true; aSend.disabled = true; aSend.textContent = "Sending…";
				embApi("auth-start", { email: v, tos: true }).then(function (d) {
					aSend.disabled = false; aSend.textContent = "Email me a code";
					if (!d || !d.ok) { aShowErr(embMsg(d)); return; }
					aEmail = v; aStep("email").hidden = true; aStep("code").hidden = false; aCodeIn.focus();
				}).catch(function () { aSend.disabled = false; aSend.textContent = "Email me a code"; aShowErr("Network error."); });
			});
		}
		if (aVerify) {
			aVerify.addEventListener("click", function () {
				var c = (aCodeIn.value || "").replace(/\D/g, "");
				if (c.length < 4) { aShowErr("Enter the 6-digit code."); return; }
				aErr.hidden = true; aVerify.disabled = true; aVerify.textContent = "Verifying…";
				embApi("auth-verify", { email: aEmail, code: c }).then(function (d) {
					if (d && d.ok) { location.reload(); return; }
					aVerify.disabled = false; aVerify.textContent = "Verify & sign in"; aShowErr(embMsg(d));
				}).catch(function () { aVerify.disabled = false; aVerify.textContent = "Verify & sign in"; aShowErr("Network error."); });
			});
		}
		if (aRestart) { aRestart.addEventListener("click", function (e) { e.preventDefault(); aErr.hidden = true; aStep("code").hidden = true; aStep("email").hidden = false; aEmailIn.focus(); }); }
	}

	/* ── [emb_verify] / My Account: logged-in verify form ─────────────── */
	var vBox = document.querySelector("[data-emb-verify]");
	if (vBox) {
		var vCode = vBox.querySelector("[data-emb-code]");
		var vGo = vBox.querySelector(".emb-verify__go");
		var vErr = vBox.querySelector(".emb-verify__err");
		var vResend = vBox.querySelector("[data-emb-resend]");
		var vShowErr = function (m) { vErr.textContent = m; vErr.hidden = false; };
		if (vGo) {
			vGo.addEventListener("click", function () {
				var c = (vCode.value || "").replace(/\D/g, "");
				if (c.length < 4) { vShowErr("Enter the 6-digit code."); return; }
				vErr.hidden = true; vGo.disabled = true;
				embApi("otp-verify", { code: c }).then(function (d) {
					if (d && d.ok) { location.reload(); return; }
					vGo.disabled = false; vShowErr(embMsg(d));
				}).catch(function () { vGo.disabled = false; vShowErr("Network error."); });
			});
		}
		if (vResend) {
			vResend.addEventListener("click", function (e) {
				e.preventDefault(); vErr.hidden = true; vResend.textContent = "…";
				embApi("otp-resend", {}).then(function (d) {
					vResend.textContent = (d && d.ok) ? "Code sent ✓" : "Resend";
					if (!d || !d.ok) { vShowErr(embMsg(d)); }
				}).catch(function () { vResend.textContent = "Resend"; vShowErr("Network error."); });
			});
		}
	}
})();
