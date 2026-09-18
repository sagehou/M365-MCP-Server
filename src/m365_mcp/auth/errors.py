"""Errors raised by the authentication boundary."""


class AuthenticationError(Exception):
    """Base error for an access token that must not be accepted."""


class TokenValidationError(AuthenticationError):
    """The token is malformed, expired, or fails claim validation."""


class InsufficientScopeError(AuthenticationError):
    """The token is valid but does not carry the required delegated scope."""

    def __init__(self, required_scopes: frozenset[str]) -> None:
        self.required_scopes = required_scopes
        super().__init__("The access token does not contain the required scopes")


class ConfigurationError(Exception):
    """Authentication cannot run because server configuration is incomplete."""


class IdentityProviderUnavailableError(ConfigurationError):
    """Identity-provider metadata or signing keys are temporarily unavailable."""


class OboTokenError(Exception):
    """Microsoft Entra rejected an on-behalf-of token request."""
