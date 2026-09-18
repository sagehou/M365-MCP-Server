"""MCP OAuth discovery and dynamic client registration."""

from .authorization import OAuthAuthorizationService
from .crypto import (
    AesGcmTokenProtector,
    EphemeralTokenProtector,
    TokenProtectionError,
    TokenProtector,
)
from .entra import (
    EntraAuthorizationClient,
    EntraAuthorizationError,
    EntraRefreshRejectedError,
    MsalEntraAuthorizationClient,
)
from .errors import OAuthProtocolError
from .models import OAuthClient, OAuthClientRegistration
from .registry import (
    DynamicClientRegistry,
    OAuthClientRegistry,
    OAuthRegistrationUnavailableError,
)
from .routes import create_oauth_router
from .sessions import OAuthSessionService
from .store import (
    OAuthClientAlreadyExistsError,
    OAuthStore,
    OAuthStoreError,
    RefreshSessionRotationResult,
    SQLiteOAuthStore,
)

__all__ = [
    "AesGcmTokenProtector",
    "DynamicClientRegistry",
    "EntraAuthorizationClient",
    "EntraAuthorizationError",
    "EntraRefreshRejectedError",
    "EphemeralTokenProtector",
    "MsalEntraAuthorizationClient",
    "OAuthAuthorizationService",
    "OAuthClient",
    "OAuthClientAlreadyExistsError",
    "OAuthClientRegistration",
    "OAuthClientRegistry",
    "OAuthRegistrationUnavailableError",
    "OAuthSessionService",
    "OAuthProtocolError",
    "OAuthStore",
    "OAuthStoreError",
    "RefreshSessionRotationResult",
    "SQLiteOAuthStore",
    "TokenProtectionError",
    "TokenProtector",
    "create_oauth_router",
]
