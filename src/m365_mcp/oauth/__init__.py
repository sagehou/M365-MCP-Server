"""MCP OAuth discovery and dynamic client registration."""

from .authorization import OAuthAuthorizationService, OAuthProtocolError
from .crypto import EphemeralTokenProtector, TokenProtectionError, TokenProtector
from .entra import (
    EntraAuthorizationBroker,
    EntraBrokerError,
    MsalEntraAuthorizationBroker,
)
from .models import OAuthClient, OAuthClientRegistration
from .registry import (
    DynamicClientRegistry,
    OAuthClientRegistry,
    OAuthRegistrationUnavailableError,
)
from .routes import create_oauth_router
from .store import (
    OAuthClientAlreadyExistsError,
    OAuthStore,
    OAuthStoreError,
    SQLiteOAuthStore,
)

__all__ = [
    "DynamicClientRegistry",
    "EntraAuthorizationBroker",
    "EntraBrokerError",
    "EphemeralTokenProtector",
    "MsalEntraAuthorizationBroker",
    "OAuthAuthorizationService",
    "OAuthClient",
    "OAuthClientAlreadyExistsError",
    "OAuthClientRegistration",
    "OAuthClientRegistry",
    "OAuthRegistrationUnavailableError",
    "OAuthProtocolError",
    "OAuthStore",
    "OAuthStoreError",
    "SQLiteOAuthStore",
    "TokenProtectionError",
    "TokenProtector",
    "create_oauth_router",
]
