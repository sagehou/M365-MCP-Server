"""ASGI middleware for protecting the MCP endpoint with bearer tokens."""

import json
from collections.abc import Awaitable, Callable, Mapping
from typing import Any, Protocol

from starlette.datastructures import Headers

from .context import ACCESS_TOKEN_STATE_KEY, IDENTITY_STATE_KEY
from .errors import (
    AuthenticationError,
    ConfigurationError,
    InsufficientScopeError,
)
from .models import UserIdentity


class TokenValidator(Protocol):
    async def validate(self, token: str) -> UserIdentity: ...


class BearerAuthMiddleware:
    """Validate only the protected MCP path and attach identity to ASGI state."""

    def __init__(
        self,
        app: Callable[..., Awaitable[None]],
        validator: TokenValidator,
        protected_prefix: str = "/mcp",
    ) -> None:
        self.app = app
        self.validator = validator
        self.protected_prefix = protected_prefix.rstrip("/") or "/"

    async def __call__(self, scope: Mapping[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http" or not self._is_protected(scope):
            await self.app(scope, receive, send)
            return

        token = self._bearer_token(scope)
        if token is None:
            await self._json_response(
                send,
                401,
                {"detail": "Authentication required"},
                ((b"www-authenticate", b"Bearer"),),
            )
            return

        try:
            identity = await self.validator.validate(token)
        except InsufficientScopeError as exc:
            required = " ".join(sorted(exc.required_scopes))
            await self._json_response(
                send,
                403,
                {"detail": "Insufficient delegated scope"},
                ((b"www-authenticate", f'Bearer error="insufficient_scope", scope="{required}"'.encode()),),
            )
            return
        except ConfigurationError:
            await self._json_response(send, 503, {"detail": "Authentication unavailable"})
            return
        except AuthenticationError:
            await self._json_response(
                send,
                401,
                {"detail": "Invalid access token"},
                ((b"www-authenticate", b"Bearer"),),
            )
            return

        authenticated_scope = dict(scope)
        state = dict(authenticated_scope.get("state") or {})
        state[IDENTITY_STATE_KEY] = identity
        state[ACCESS_TOKEN_STATE_KEY] = token
        authenticated_scope["state"] = state
        await self.app(authenticated_scope, receive, send)

    def _is_protected(self, scope: Mapping[str, Any]) -> bool:
        path = scope.get("path")
        if not isinstance(path, str):
            return False
        return path == self.protected_prefix or path.startswith(
            f"{self.protected_prefix}/"
        )

    @staticmethod
    def _bearer_token(scope: Mapping[str, Any]) -> str | None:
        authorization = Headers(scope=scope).get("authorization")
        if not authorization:
            return None
        parts = authorization.strip().split()
        if len(parts) != 2 or parts[0].casefold() != "bearer":
            return None
        return parts[1]

    @staticmethod
    async def _json_response(
        send: Any,
        status: int,
        payload: Mapping[str, str],
        extra_headers: tuple[tuple[bytes, bytes], ...] = (),
    ) -> None:
        body = json.dumps(payload).encode("utf-8")
        headers = (
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode("ascii")),
            *extra_headers,
        )
        await send({"type": "http.response.start", "status": status, "headers": headers})
        await send({"type": "http.response.body", "body": body})
