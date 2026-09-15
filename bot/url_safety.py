"""SSRF guard for outbound HTTP calls to URLs that came from a bot owner
(not the platform operator) — the invoice logo/signature URL and the
"live API call" digital-delivery endpoint are both owner-supplied and are
fetched automatically, server-side, with no human in the loop. Without this,
an owner (or anyone who can edit those settings, e.g. via a compromised
owner account) could point either one at http://169.254.169.254/..., an
internal service on the Docker network, localhost, etc.

This only blocks the common, cheap SSRF path: scheme confusion, literal
private/loopback/link-local IPs, and DNS names that resolve to one. It does
NOT fully close DNS-rebinding (resolve-then-connect race), since aiohttp
doesn't expose a clean way to pin the connection to the IP we validated
without a custom resolver/connector. Callers should treat this as a floor,
not a complete SSRF fix — and MUST also disable redirects
(allow_redirects=False) themselves, since a validated URL can still 302 to
an internal address.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from urllib.parse import urlsplit

_ALLOWED_SCHEMES = {"http", "https"}


def _is_blocked_ip(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return True  # unparseable -> treat as unsafe
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
        or bool(getattr(ip, "is_site_local", False))  # deprecated IPv6 fec0::/10; IPv4 has no such attr
    )


async def check_url_is_safe(url: str) -> str | None:
    """Returns None if the URL looks safe to fetch server-side, or a short
    human-readable reason string if it should be rejected."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return "malformed URL"

    if parts.scheme.lower() not in _ALLOWED_SCHEMES:
        return "only http/https URLs are allowed"

    host = parts.hostname
    if not host:
        return "URL has no host"

    # Literal IP (bracketed IPv6 included via .hostname, which strips brackets)
    try:
        literal_ip = ipaddress.ip_address(host)
    except ValueError:
        literal_ip = None

    if literal_ip is not None:
        if _is_blocked_ip(str(literal_ip)):
            return "URL points at a private/internal address"
        return None

    # Hostname -> resolve and check every A/AAAA result; block if any is unsafe
    # (an attacker-controlled DNS name could otherwise return one public and
    # one private IP and rely on us only checking the first).
    try:
        loop = asyncio.get_running_loop()
        infos = await loop.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return "could not resolve host"
    except Exception:
        return "could not resolve host"

    if not infos:
        return "could not resolve host"

    for info in infos:
        sockaddr = info[4]
        ip_str = sockaddr[0]
        if _is_blocked_ip(ip_str):
            return "host resolves to a private/internal address"

    return None
