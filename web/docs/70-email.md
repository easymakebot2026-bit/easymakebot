# Email — ParsPack cPanel mailbox

Transactional + contact email for `easymakebot.com` runs through a **ParsPack
shared cPanel hosting** account, separate from the site VPS.

## Accounts / servers

| Thing | Value |
|---|---|
| cPanel account | `h419862` |
| Mail server (HELO) | `s438.bitcommand.com` |
| Shared IP | `89.44.243.103` |
| Outgoing mail IP | `89.44.243.102` |
| cPanel login | ParsPack panel → هاست ابری → easymakebot.com → کنترل پنل |
| Mailbox | `info@easymakebot.com` (shown on the Contact page) |
| Webmail | `https://s438.bitcommand.com:2096` (Roundcube) |

`pspk@easymakebot.com` was a throwaway mailbox created while debugging with
ParsPack support — safe to delete.

## WP Mail SMTP settings (wp-admin → WP Mail SMTP → Settings → Other SMTP)

| Field | Value |
|---|---|
| SMTP Host | `mail.easymakebot.com` (or `s438.bitcommand.com`) |
| Encryption / Port | SSL `465` — or STARTTLS `587`; both work |
| Auth | on, username `info@easymakebot.com`, password = the mailbox password |
| From Email | `info@easymakebot.com`, Force From Email on |
| Return Path | on |

Two workarounds are in the repo, both because the mail host's TLS cert is
**self-signed** and its hostname is not publicly resolvable from Iran:

1. **`docker-compose.prod.yml`** — `extra_hosts` on the `wordpress` service pins
   `s438.bitcommand.com` → `89.44.243.103` (ParsPack resolvers return NXDOMAIN
   for it).
2. **`wp-content/mu-plugins/emb-smtp-tls.php`** — disables SMTP peer-cert
   verification via `phpmailer_init`.

Drop both once `mail.easymakebot.com` gets a real AutoSSL cert.

## DNS records (ParsPack panel → CDN → easymakebot.com → رکوردهای DNS, all "DNS فقط")

| Type | Name | Value |
|---|---|---|
| A | `mail` | `89.44.243.103` |
| MX | `@` | `mail.easymakebot.com` (priority 10) |
| TXT | `@` | `v=spf1 +mx +a +ip4:89.44.243.102 ~all` |
| TXT | `_dmarc` | `v=DMARC1; p=none;` |
| TXT | `default._domainkey` | `v=DKIM1; k=rsa; p=…` (from cPanel → Email Deliverability) |

## History (2026-09-01)

Sending + receiving were both dead for hours: `MAIL FROM` was silently rejected
(Email Routing stuck on "Remote" because the domain's A record points at the
VPS, not the cPanel box), then external sending bounced with
`550 relay not permitted` at ParsPack's outbound relay `imailgw4.getway.biz`.
Both were fixed server-side by ParsPack support (tickets #55578053 / #88962047).
PTR for `89.44.243.102` → `s438.bitcommand.com` was also requested.
