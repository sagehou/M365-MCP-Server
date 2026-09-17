"""Reusable Microsoft Graph HTTP client with delegated-token handling."""

import asyncio
import math
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import unquote, urlsplit

import httpx

from ..auth.models import AuthContext
from ..auth.obo import MsalOboService
from ..auth.settings import Settings
from .errors import GraphApiError, GraphPathError, GraphTransportError


@dataclass(frozen=True, slots=True)
class GraphResponse:
    """Response data returned to a service layer, not directly to MCP clients."""

    status_code: int
    data: Any
    request_id: str | None
    headers: Mapping[str, str]


class GraphClient:
    """Call Microsoft Graph only in the context of a validated user identity."""

    RETRYABLE_STATUS_CODES = frozenset({408, 429, 500, 502, 503, 504})

    def __init__(
        self,
        settings: Settings,
        obo_service: MsalOboService,
        http_client: httpx.AsyncClient | None = None,
        sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.settings = settings
        self.obo_service = obo_service
        self._client = http_client or httpx.AsyncClient(timeout=settings.http_timeout_seconds)
        self._owns_client = http_client is None
        self._sleeper = sleeper
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    async def __aenter__(self) -> "GraphClient":
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def request(
        self,
        context: AuthContext,
        method: str,
        path: str,
        *,
        params: Mapping[str, str | int | float | bool] | None = None,
        json_body: Any = None,
        headers: Mapping[str, str] | None = None,
    ) -> GraphResponse:
        """Send a delegated Graph request under the validated caller identity."""

        url = self._url(path)
        request_headers = self._headers(headers)
        method = method.upper()
        retry_safe = method in {"GET", "HEAD", "OPTIONS"}
        graph_token = await asyncio.to_thread(
            self.obo_service.acquire_graph_token,
            user_assertion=context.access_token,
            tenant_id=context.identity.tenant_id,
        )
        request_headers["Authorization"] = f"Bearer {graph_token}"

        for attempt in range(self.settings.graph_max_retries + 1):
            try:
                response = await self._request_bounded(
                    method,
                    url,
                    params=params,
                    json=json_body,
                    headers=request_headers,
                )
            except httpx.RequestError as exc:
                if not retry_safe or attempt >= self.settings.graph_max_retries:
                    raise GraphTransportError(
                        "Microsoft Graph transport failed; write outcome may be unknown"
                    ) from None
                await self._sleeper(self._backoff(attempt))
                continue

            if (
                response.status_code in self.RETRYABLE_STATUS_CODES
                and (retry_safe or response.status_code == 429)
                and attempt < self.settings.graph_max_retries
            ):
                delay = self._retry_delay(response, attempt)
                if delay > self.settings.graph_max_retry_delay_seconds:
                    raise self._api_error(response)
                await self._sleeper(delay)
                continue

            if response.status_code >= 300:
                raise self._api_error(response)
            return GraphResponse(
                status_code=response.status_code,
                data=self._response_data(response),
                request_id=self._request_id(response),
                headers=dict(response.headers),
            )

        raise GraphTransportError("Microsoft Graph request exhausted retries")

    async def _request_bounded(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        # Bound decoded bytes even for chunked or compressed responses, before JSON parsing.
        async with self._client.stream(method, url, **kwargs) as response:
            content = bytearray()
            async for chunk in response.aiter_bytes():
                if len(content) + len(chunk) > self.settings.graph_max_response_bytes:
                    raise GraphTransportError("Microsoft Graph response exceeds the server limit")
                content.extend(chunk)
            return httpx.Response(
                response.status_code, headers={
                    key: value for key, value in response.headers.items()
                    if key not in {"content-encoding", "content-length"}
                },
                content=bytes(content), request=response.request,
            )

    def _url(self, path: str) -> str:
        if not isinstance(path, str) or not path:
            raise GraphPathError("A relative Graph path is required")
        parsed = urlsplit(path)
        if parsed.scheme or parsed.netloc or not parsed.path or parsed.query or parsed.fragment:
            raise GraphPathError("Absolute Graph URLs are not accepted")
        if any(segment in {".", ".."} for segment in unquote(parsed.path).split("/")):
            raise GraphPathError("Graph path traversal is not accepted")
        if parsed.path != "/me" and not parsed.path.startswith("/me/"):
            raise GraphPathError("Graph operations must use the delegated /me path")
        return f"{self.settings.graph_base_url.rstrip('/')}{path}"

    @staticmethod
    def _headers(headers: Mapping[str, str] | None) -> dict[str, str]:
        result = {
            "Accept": "application/json",
        }
        for name, value in (headers or {}).items():
            if name.casefold() == "authorization":
                raise GraphPathError("Authorization is managed by the Graph client")
            result[name] = value
        return result

    def _retry_delay(self, response: httpx.Response, attempt: int) -> float:
        retry_after = self._retry_after(response.headers.get("retry-after"))
        if retry_after is not None:
            return retry_after
        return self._backoff(attempt)

    def _backoff(self, attempt: int) -> float:
        delay = self.settings.graph_retry_backoff_seconds * (2**attempt)
        return min(delay, self.settings.graph_max_retry_delay_seconds)

    def _retry_after(self, value: str | None) -> float | None:
        if not value:
            return None
        try:
            number = float(value)
            return max(0.0, number) if math.isfinite(number) else None
        except ValueError:
            pass
        try:
            retry_at = parsedate_to_datetime(value)
        except (TypeError, ValueError, OverflowError):
            return None
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=timezone.utc)
        return max(0.0, (retry_at - self._clock()).total_seconds())

    @classmethod
    def _api_error(cls, response: httpx.Response) -> GraphApiError:
        payload = cls._response_data(response)
        error = payload.get("error") if isinstance(payload, Mapping) else None
        code = error.get("code") if isinstance(error, Mapping) else None
        if not isinstance(code, str) or not code:
            code = f"http_{response.status_code}"
        return GraphApiError(
            status_code=response.status_code,
            code=code,
            request_id=cls._request_id(response),
            retry_after=cls._retry_after_header(response),
        )

    @staticmethod
    def _response_data(response: httpx.Response) -> Any:
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            return None

    @staticmethod
    def _request_id(response: httpx.Response) -> str | None:
        return response.headers.get("request-id") or response.headers.get(
            "client-request-id"
        )

    @classmethod
    def _retry_after_header(cls, response: httpx.Response) -> float | None:
        value = response.headers.get("retry-after")
        if value is None:
            return None
        try:
            return max(0.0, float(value))
        except ValueError:
            return None
