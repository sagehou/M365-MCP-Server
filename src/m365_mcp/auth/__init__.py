"""Authentication and delegated-token services."""

from .context import get_auth_context
from .errors import (
    AuthenticationError,
    ConfigurationError,
    IdentityProviderUnavailableError,
    InsufficientScopeError,
    OboTokenError,
    TokenValidationError,
)
from .middleware import BearerAuthMiddleware
from .models import AuthContext, UserIdentity
from .obo import MsalOboService
from .settings import Settings
from .validator import JwtValidator

__all__ = [
    "AuthContext",
    "AuthenticationError",
    "BearerAuthMiddleware",
    "ConfigurationError",
    "IdentityProviderUnavailableError",
    "InsufficientScopeError",
    "JwtValidator",
    "MsalOboService",
    "OboTokenError",
    "Settings",
    "TokenValidationError",
    "UserIdentity",
    "get_auth_context",
]
