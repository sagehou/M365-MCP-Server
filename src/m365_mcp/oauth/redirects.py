"""Redirect URI policy for public MCP OAuth clients."""

from __future__ import annotations

from ipaddress import ip_address
import re
from urllib.parse import parse_qsl, urlsplit


_WORKBUDDY_PATH = re.compile(
    r"^/mcp/connector%3a[A-Za-z0-9._~-]+/oauth/callback$",
    re.IGNORECASE,
)
_RESERVED_QUERY_PARAMETERS = frozenset({"code", "state", "error"})


def validate_redirect_uri(value: str) -> str:
    """Return a safe redirect URI or raise ValueError."""

    if not value or any(character.isspace() for character in value):
        raise ValueError("redirect_uri is malformed")
    parsed = urlsplit(value)
    if not parsed.scheme or parsed.fragment:
        raise ValueError("redirect_uri must be absolute and must not contain a fragment")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("redirect_uri must not contain user information")
    try:
        parsed.port
    except ValueError as exc:
        raise ValueError("redirect_uri port is invalid") from exc

    scheme = parsed.scheme.casefold()
    if scheme == "workbuddy":
        if (
            parsed.hostname != "workbuddy"
            or parsed.port is not None
            or parsed.query
            or not _WORKBUDDY_PATH.fullmatch(parsed.path)
        ):
            raise ValueError("invalid WorkBuddy redirect_uri")
        return value

    if scheme == "http":
        if parsed.path != "/oauth/callback" or parsed.query:
            raise ValueError("loopback redirect_uri must use /oauth/callback")
        host = parsed.hostname
        if host is None:
            raise ValueError("loopback redirect_uri requires a host")
        try:
            loopback = ip_address(host).is_loopback
        except ValueError:
            loopback = host.casefold() == "localhost"
        if not loopback:
            raise ValueError("public HTTP redirect_uri is not allowed")
        return value

    if scheme == "https" and parsed.hostname:
        if any(
            name in _RESERVED_QUERY_PARAMETERS
            for name, _ in parse_qsl(parsed.query, keep_blank_values=True)
        ):
            raise ValueError("redirect_uri contains reserved OAuth parameters")
        return value

    raise ValueError("unsupported redirect_uri scheme")
