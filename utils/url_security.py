# utils/url_security.py
from __future__ import annotations

import ipaddress
import logging
import socket
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Return True if an IP address is in a range we must never call.

    Blocks loopback, private, link-local (cloud metadata lives at the
    link-local 169.254.169.254), reserved, multicast, and unspecified
    ranges — the full set of SSRF-relevant destinations.

    Args:
        ip: A parsed IPv4 or IPv6 address.

    Returns:
        True if the address is unsafe to connect to.
    """
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def is_safe_outbound_url(url: str) -> tuple[bool, str]:
    """Validate a customer-supplied URL is safe for the server to call.

    Enforces HTTPS, then resolves the hostname and rejects the request
    if any resolved address falls in a private, loopback, link-local,
    or otherwise reserved range. This prevents SSRF against the cloud
    metadata server (169.254.169.254), localhost, and internal VPC hosts.

    Args:
        url: The URL to validate.

    Returns:
        A (is_safe, reason) tuple. reason explains the rejection when
        is_safe is False, and is "ok" when it passes.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return False, "URL could not be parsed"

    if parsed.scheme != "https":
        return False, f"URL must use https (got {parsed.scheme or 'no scheme'!r})"

    host = parsed.hostname
    if not host:
        return False, "URL has no hostname"

    # If the host is a literal IP, check it directly — no DNS needed.
    try:
        literal_ip = ipaddress.ip_address(host)
        if _is_blocked_ip(literal_ip):
            return False, f"host IP {host} is in a blocked range"
        return True, "ok"
    except ValueError:
        pass  # not a literal IP — it's a hostname, resolve it below

    # Resolve the hostname and check every address it maps to. A hostname
    # like localhost or metadata.google.internal only reveals its danger
    # after resolution, so DNS resolution here is mandatory, not optional.
    try:
        addr_infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False, f"DNS resolution failed for {host}"

    for _family, _type, _proto, _canon, sockaddr in addr_infos:
        try:
            ip = ipaddress.ip_address(sockaddr[0])
        except ValueError:
            continue
        if _is_blocked_ip(ip):
            return False, f"{host} resolves to blocked IP {ip}"

    return True, "ok"