"""Redirect URI policy for public MCP OAuth clients."""

from __future__ import annotations

from urllib.parse import parse_qsl, urlsplit


_RESERVED_QUERY_PARAMETERS = frozenset({"code", "state", "error"})
_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


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
            parsed.hostname is None
            or parsed.hostname.casefold() != "workbuddy"
            or parsed.port is not None
            or parsed.query
            or not parsed.path
            or parsed.path == "/"
        ):
            raise ValueError("invalid WorkBuddy redirect_uri")
        return value

    if scheme == "http":
        host = parsed.hostname
        if host is None or host.casefold() not in _LOOPBACK_HOSTS:
            raise ValueError("public HTTP redirect_uri is not allowed")
        if parsed.port is None:
            raise ValueError("loopback redirect_uri requires an explicit port")
        if parsed.query or not parsed.path or parsed.path == "/":
            raise ValueError("loopback redirect_uri requires a callback path")
        return value

    if scheme == "https" and parsed.hostname:
        if any(
            name in _RESERVED_QUERY_PARAMETERS
            for name, _ in parse_qsl(parsed.query, keep_blank_values=True)
        ):
            raise ValueError("redirect_uri contains reserved OAuth parameters")
        return value

    raise ValueError("unsupported redirect_uri scheme")
