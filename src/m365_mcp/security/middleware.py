"""HTTP security headers for the MCP gateway."""

from collections.abc import Awaitable, Callable, Mapping
from typing import Any


class SecurityHeadersMiddleware:
    """Add non-invasive response headers, including to auth failures."""

    HEADERS = (
        (b"cache-control", b"no-store"),
        (b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'"),
        (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
        (b"referrer-policy", b"no-referrer"),
        (b"x-content-type-options", b"nosniff"),
        (b"x-frame-options", b"DENY"),
    )

    def __init__(self, app: Callable[..., Awaitable[None]]) -> None:
        self.app = app

    async def __call__(self, scope: Mapping[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Mapping[str, Any]) -> None:
            if message.get("type") != "http.response.start":
                await send(message)
                return
            headers = list(message.get("headers") or ())
            existing = {
                name.casefold() for name, _ in headers if isinstance(name, bytes)
            }
            headers.extend(
                (name, value) for name, value in self.HEADERS if name not in existing
            )
            updated = dict(message)
            updated["headers"] = headers
            await send(updated)

        await self.app(scope, receive, send_with_headers)
