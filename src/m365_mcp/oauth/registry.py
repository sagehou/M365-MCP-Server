"""Deep module for dynamic public-client registration."""

from __future__ import annotations

import secrets
from time import time
from typing import Protocol

from .audit import OAuthAuditLogger
from .models import OAuthClient, OAuthClientRegistration
from .redirects import validate_redirect_uri
from .store import OAuthClientAlreadyExistsError, OAuthStore, OAuthStoreError


class OAuthClientRegistry(Protocol):
    async def initialize(self) -> None: ...

    async def register(self, registration: OAuthClientRegistration) -> OAuthClient: ...

    async def get(self, client_id: str) -> OAuthClient | None: ...

    async def validate_redirect(self, client_id: str, redirect_uri: str) -> bool: ...


class OAuthRegistrationUnavailableError(Exception):
    """Raised when a public client cannot be registered safely."""


class DynamicClientRegistry:
    """Validate, persist and query issuer-bound public OAuth clients."""

    def __init__(
        self,
        store: OAuthStore,
        issuer: str,
        *,
        audit_logger: OAuthAuditLogger | None = None,
    ) -> None:
        self.store = store
        self.issuer = issuer.rstrip("/")
        self.audit_logger = audit_logger or OAuthAuditLogger()

    async def initialize(self) -> None:
        await self.store.initialize()

    async def register(self, registration: OAuthClientRegistration) -> OAuthClient:
        redirects = tuple(validate_redirect_uri(value) for value in registration.redirect_uris)
        for _ in range(3):
            client = OAuthClient(
                issuer=self.issuer,
                client_id="mcp_" + secrets.token_urlsafe(32),
                client_name=registration.client_name,
                redirect_uris=redirects,
                application_type=registration.application_type,
                grant_types=tuple(registration.grant_types),
                response_types=tuple(registration.response_types),
                token_endpoint_auth_method=registration.token_endpoint_auth_method,
                scope=registration.scope,
                created_at=int(time()),
            )
            try:
                await self.store.create_client(client)
            except OAuthClientAlreadyExistsError:
                continue
            except OAuthStoreError:
                raise OAuthRegistrationUnavailableError from None
            self.audit_logger.client_registered(client.client_id)
            return client
        raise OAuthRegistrationUnavailableError from None

    async def get(self, client_id: str) -> OAuthClient | None:
        return await self.store.get_client(self.issuer, client_id)

    async def validate_redirect(self, client_id: str, redirect_uri: str) -> bool:
        client = await self.get(client_id)
        return client is not None and redirect_uri in client.redirect_uris
