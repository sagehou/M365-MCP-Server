"""OpenID Connect discovery and signing-key retrieval with bounded caching."""

import asyncio
import time
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

import httpx

from .errors import IdentityProviderUnavailableError
from .settings import Settings

JsonFetcher = Callable[[str], Awaitable[Mapping[str, Any]]]


class HttpJsonFetcher:
    """Fetch JSON documents without retaining bearer tokens or response bodies."""

    def __init__(self, timeout_seconds: float) -> None:
        self.timeout_seconds = timeout_seconds

    async def __call__(self, url: str) -> Mapping[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(url)
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise IdentityProviderUnavailableError(
                "Identity metadata is unavailable"
            ) from exc
        if not isinstance(payload, Mapping):
            raise IdentityProviderUnavailableError(
                "Identity metadata has an invalid shape"
            )
        return payload


class OidcDocumentProvider:
    """Cache discovery metadata and JWKS for the configured TTL."""

    def __init__(
        self,
        settings: Settings,
        fetcher: JsonFetcher | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.settings = settings
        self._fetcher = fetcher or HttpJsonFetcher(settings.http_timeout_seconds)
        self._clock = clock
        self._lock = asyncio.Lock()
        self._configuration: tuple[float, Mapping[str, Any]] | None = None
        self._jwks: tuple[float, Mapping[str, Any]] | None = None
        self._last_forced_refresh = float("-inf")

    async def configuration(self) -> Mapping[str, Any]:
        if self._configuration_is_fresh():
            assert self._configuration is not None
            return self._configuration[1]
        async with self._lock:
            if self._configuration_is_fresh():
                assert self._configuration is not None
                return self._configuration[1]
            document = await self._fetcher(self.settings.discovery_url)
            self._configuration = (self._clock(), document)
            return document

    async def signing_keys(self, *, force_refresh: bool = False) -> Mapping[str, Any]:
        if self._jwks_is_fresh() and not force_refresh:
            assert self._jwks is not None
            return self._jwks[1]
        configuration = await self.configuration()
        jwks_url = configuration.get("jwks_uri")
        if not isinstance(jwks_url, str) or not jwks_url:
            raise IdentityProviderUnavailableError(
                "Identity metadata has no signing-key URL"
            )
        async with self._lock:
            refresh_allowed = force_refresh and self._clock() - self._last_forced_refresh >= 60
            if self._jwks_is_fresh() and not refresh_allowed:
                assert self._jwks is not None
                return self._jwks[1]
            if force_refresh:
                # Rate-limit misses, including failed fetches, across all unknown kids.
                self._last_forced_refresh = self._clock()
            document = await self._fetcher(jwks_url)
            self._jwks = (self._clock(), document)
            return document

    def _configuration_is_fresh(self) -> bool:
        return self._is_fresh(self._configuration)

    def _jwks_is_fresh(self) -> bool:
        return self._is_fresh(self._jwks)

    def _is_fresh(self, cached: tuple[float, Mapping[str, Any]] | None) -> bool:
        return bool(
            cached
            and self._clock() - cached[0] < self.settings.oidc_cache_ttl_seconds
        )
