"""MSAL adapter for the upstream Microsoft Entra authorization flow."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Protocol

import msal

from ..auth.settings import Settings
from .models import UpstreamAuthorization, UpstreamTokenResult


class EntraBrokerError(Exception):
    """Raised when Entra authorization cannot be completed safely."""


class EntraAuthorizationBroker(Protocol):
    async def begin(self, upstream_state: str) -> UpstreamAuthorization: ...

    async def complete(
        self,
        flow: Mapping[str, Any],
        authorization_response: Mapping[str, str],
    ) -> UpstreamTokenResult: ...


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


class MsalEntraAuthorizationBroker:
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

    def _begin_sync(self, upstream_state: str) -> UpstreamAuthorization:
        try:
            cache = self._cache_factory()
            application = self._new_application(cache)
            flow = application.initiate_auth_code_flow(
                scopes=list(self.settings.entra_broker_scopes),
                redirect_uri=self.settings.entra_broker_redirect_uri,
                state=upstream_state,
            )
        except Exception as exc:
            raise EntraBrokerError("Microsoft authorization is unavailable") from exc
        authorization_uri = flow.get("auth_uri") if isinstance(flow, dict) else None
        if not isinstance(authorization_uri, str) or not authorization_uri:
            raise EntraBrokerError("Microsoft authorization is unavailable")
        if flow.get("state") != upstream_state:
            raise EntraBrokerError("Microsoft authorization state is invalid")
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
                scopes=list(self.settings.entra_broker_scopes),
            )
            serialized_cache = cache.serialize()
        except Exception as exc:
            raise EntraBrokerError(
                "Microsoft authorization response is invalid"
            ) from exc
        access_token = result.get("access_token") if isinstance(result, dict) else None
        expires_in = result.get("expires_in") if isinstance(result, dict) else None
        if not isinstance(access_token, str) or not access_token:
            raise EntraBrokerError("Microsoft authorization did not return a token")
        try:
            normalized_expires_in = int(expires_in)
        except (TypeError, ValueError) as exc:
            raise EntraBrokerError("Microsoft token lifetime is invalid") from exc
        if normalized_expires_in <= 0:
            raise EntraBrokerError("Microsoft token lifetime is invalid")
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
            client_id=self.settings.entra_broker_client_id,
            client_credential=self.settings.entra_broker_client_credential(),
            authority=self.settings.entra_broker_authority,
            token_cache=cache,
            timeout=self.settings.http_timeout_seconds,
        )
