"""Microsoft Authentication Library On-Behalf-Of service."""

from collections.abc import Callable, Sequence
from typing import Any, Protocol
from threading import Lock

import msal

from .errors import ConfigurationError, OboTokenError
from .settings import Settings


class MsalApplication(Protocol):
    def acquire_token_on_behalf_of(
        self, user_assertion: str, scopes: list[str]
    ) -> dict[str, Any]: ...


class MsalOboService:
    """Acquire Microsoft Graph delegated tokens without accepting user IDs."""

    def __init__(
        self,
        settings: Settings,
        client_factory: Callable[..., MsalApplication]
        | None = None,
    ) -> None:
        self.settings = settings
        self._client_factory = client_factory or msal.ConfidentialClientApplication
        self._clients: dict[str, MsalApplication] = {}
        self._client_lock = Lock()

    def acquire_graph_token(
        self,
        *,
        user_assertion: str,
        tenant_id: str,
        scopes: Sequence[str] | None = None,
    ) -> str:
        """Exchange the validated inbound assertion for a Graph token."""

        if not user_assertion:
            raise OboTokenError("The inbound user assertion is empty")
        if not self.settings.is_allowed_tenant(tenant_id):
            raise ConfigurationError("The OBO tenant is not allowlisted")
        selected_scopes = tuple(scopes or self.settings.graph_scopes)
        if not selected_scopes:
            raise ConfigurationError("No downstream Graph scopes are configured")

        client = self._client_for_tenant(tenant_id)
        result = client.acquire_token_on_behalf_of(
            user_assertion=user_assertion,
            scopes=list(selected_scopes),
        )
        access_token = result.get("access_token") if isinstance(result, dict) else None
        if isinstance(access_token, str) and access_token:
            return access_token
        raise OboTokenError("Microsoft Entra rejected the OBO token request")

    def _client_for_tenant(self, tenant_id: str) -> MsalApplication:
        with self._client_lock:
            return self._get_or_create_client(tenant_id)

    def _get_or_create_client(self, tenant_id: str) -> MsalApplication:
        existing = self._clients.get(tenant_id)
        if existing is not None:
            return existing
        self.settings.validate_auth_configuration()
        client = self._client_factory(
            client_id=self.settings.client_id,
            authority=self.settings.authority_for_tenant(tenant_id),
            client_credential=self.settings.client_credential(),
            timeout=self.settings.http_timeout_seconds,
        )
        self._clients[tenant_id] = client
        return client
