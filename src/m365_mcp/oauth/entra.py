"""MSAL adapter for the upstream Microsoft Entra authorization flow."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Protocol

import msal

from ..auth.settings import Settings
from .models import UpstreamAuthorization, UpstreamTokenResult


class EntraAuthorizationError(Exception):
    """Raised when Entra authorization cannot be completed safely."""


class EntraRefreshRejectedError(EntraAuthorizationError):
    """Raised when Microsoft requires a new interactive authorization."""


class EntraAuthorizationClient(Protocol):
    async def begin(self, upstream_state: str) -> UpstreamAuthorization: ...

    async def complete(
        self,
        flow: Mapping[str, Any],
        authorization_response: Mapping[str, str],
    ) -> UpstreamTokenResult: ...

    async def refresh(self, serialized_cache: str) -> UpstreamTokenResult: ...


class MsalAuthorizationApplication(Protocol):
    def initiate_auth_code_flow(
        self,
        scopes: Sequence[str],
        redirect_uri: str | None = None,
        state: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]: ...

    def acquire_token_by_auth_code_flow(
        self,
        auth_code_flow: Mapping[str, Any],
        auth_response: Mapping[str, str],
        scopes: Sequence[str] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]: ...

    def get_accounts(self, **kwargs: Any) -> list[dict[str, Any]]: ...

    def acquire_token_silent_with_error(
        self,
        scopes: Sequence[str],
        account: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any] | None: ...


class MsalEntraAuthorizationClient:
    """Hide MSAL flow construction and token exchange behind one small interface."""

    def __init__(
        self,
        settings: Settings,
        application_factory: Callable[..., MsalAuthorizationApplication] | None = None,
        cache_factory: Callable[[], msal.SerializableTokenCache] | None = None,
    ) -> None:
        self.settings = settings
        self._application_factory = (
            application_factory or msal.ConfidentialClientApplication
        )
        self._cache_factory = cache_factory or msal.SerializableTokenCache

    async def begin(self, upstream_state: str) -> UpstreamAuthorization:
        return await asyncio.to_thread(self._begin_sync, upstream_state)

    async def complete(
        self,
        flow: Mapping[str, Any],
        authorization_response: Mapping[str, str],
    ) -> UpstreamTokenResult:
        return await asyncio.to_thread(
            self._complete_sync,
            dict(flow),
            dict(authorization_response),
        )

    async def refresh(self, serialized_cache: str) -> UpstreamTokenResult:
        return await asyncio.to_thread(self._refresh_sync, serialized_cache)

    def _begin_sync(self, upstream_state: str) -> UpstreamAuthorization:
        try:
            cache = self._cache_factory()
            application = self._new_application(cache)
            flow = application.initiate_auth_code_flow(
                scopes=list(self.settings.entra_authorization_scopes),
                redirect_uri=self.settings.oauth_callback_uri,
                state=upstream_state,
            )
        except Exception as exc:
            raise EntraAuthorizationError(
                "Microsoft authorization is unavailable"
            ) from exc
        authorization_uri = flow.get("auth_uri") if isinstance(flow, dict) else None
        if not isinstance(authorization_uri, str) or not authorization_uri:
            raise EntraAuthorizationError("Microsoft authorization is unavailable")
        if flow.get("state") != upstream_state:
            raise EntraAuthorizationError("Microsoft authorization state is invalid")
        return UpstreamAuthorization(authorization_uri=authorization_uri, flow=flow)

    def _complete_sync(
        self,
        flow: Mapping[str, Any],
        authorization_response: Mapping[str, str],
    ) -> UpstreamTokenResult:
        try:
            cache = self._cache_factory()
            application = self._new_application(cache)
            result = application.acquire_token_by_auth_code_flow(
                auth_code_flow=flow,
                auth_response=authorization_response,
                scopes=list(self.settings.entra_token_scopes),
            )
            serialized_cache = cache.serialize()
        except Exception as exc:
            raise EntraAuthorizationError(
                "Microsoft authorization response is invalid"
            ) from exc
        return self._token_result(result, serialized_cache)

    def _refresh_sync(self, serialized_cache: str) -> UpstreamTokenResult:
        if not serialized_cache:
            raise EntraRefreshRejectedError("Microsoft session is unavailable")
        try:
            cache = self._cache_factory()
            try:
                cache.deserialize(serialized_cache)
            except Exception as exc:
                raise EntraRefreshRejectedError(
                    "Microsoft session cache is invalid"
                ) from exc
            application = self._new_application(cache)
            accounts = application.get_accounts()
            if len(accounts) != 1:
                raise EntraRefreshRejectedError(
                    "Microsoft session requires interactive authorization"
                )
            result = application.acquire_token_silent_with_error(
                scopes=list(self.settings.entra_token_scopes),
                account=accounts[0],
                force_refresh=True,
            )
            refreshed_cache = cache.serialize()
        except EntraRefreshRejectedError:
            raise
        except Exception as exc:
            raise EntraAuthorizationError(
                "Microsoft token refresh is unavailable"
            ) from exc
        if not isinstance(result, dict) or not result.get("access_token"):
            error = result.get("error") if isinstance(result, dict) else None
            if error in {
                "invalid_grant",
                "interaction_required",
                "no_tokens_found",
            } or result is None:
                raise EntraRefreshRejectedError(
                    "Microsoft session requires interactive authorization"
                )
            raise EntraAuthorizationError("Microsoft token refresh is unavailable")
        return self._token_result(result, refreshed_cache)

    @staticmethod
    def _token_result(
        result: Mapping[str, Any],
        serialized_cache: str,
    ) -> UpstreamTokenResult:
        if not isinstance(serialized_cache, str) or not serialized_cache:
            raise EntraAuthorizationError("Microsoft token cache is invalid")
        access_token = result.get("access_token")
        expires_in = result.get("expires_in")
        if not isinstance(access_token, str) or not access_token:
            raise EntraAuthorizationError(
                "Microsoft authorization did not return a token"
            )
        try:
            normalized_expires_in = int(expires_in)
        except (TypeError, ValueError) as exc:
            raise EntraAuthorizationError(
                "Microsoft token lifetime is invalid"
            ) from exc
        if normalized_expires_in <= 0:
            raise EntraAuthorizationError("Microsoft token lifetime is invalid")
        return UpstreamTokenResult(
            access_token=access_token,
            expires_in=normalized_expires_in,
            serialized_cache=serialized_cache,
        )

    def _new_application(
        self,
        cache: msal.SerializableTokenCache,
    ) -> MsalAuthorizationApplication:
        return self._application_factory(
            client_id=self.settings.client_id,
            client_credential=self.settings.client_credential(),
            authority=self.settings.entra_authority,
            token_cache=cache,
            timeout=self.settings.http_timeout_seconds,
        )
