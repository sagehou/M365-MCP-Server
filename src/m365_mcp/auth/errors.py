"""Errors raised by the authentication boundary."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any
from uuid import UUID


_SAFE_ENTRA_VALUE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


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

    def __init__(
        self,
        message: str,
        *,
        entra_error: str | None = None,
        entra_suberror: str | None = None,
        entra_error_code: int | None = None,
        correlation_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.entra_error = self._safe_value(entra_error)
        self.entra_suberror = self._safe_value(entra_suberror)
        self.entra_error_code = self._safe_error_code(entra_error_code)
        self.correlation_id = self._safe_correlation_id(correlation_id)

    @classmethod
    def from_msal_result(cls, result: Mapping[str, Any] | None) -> OboTokenError:
        """Keep only non-sensitive Entra classifications from an MSAL failure."""

        if result is None:
            return cls("Microsoft Entra rejected the OBO token request")
        error_codes = result.get("error_codes")
        error_code = None
        if isinstance(error_codes, Sequence) and not isinstance(
            error_codes, (str, bytes)
        ):
            error_code = next(
                (
                    value
                    for value in error_codes
                    if (
                        isinstance(value, int)
                        and not isinstance(value, bool)
                        and 0 < value <= 999_999_999
                    )
                ),
                None,
            )
        return cls(
            "Microsoft Entra rejected the OBO token request",
            entra_error=result.get("error"),
            entra_suberror=result.get("suberror"),
            entra_error_code=error_code,
            correlation_id=result.get("correlation_id"),
        )

    @staticmethod
    def _safe_value(value: object) -> str | None:
        if isinstance(value, str) and _SAFE_ENTRA_VALUE.fullmatch(value):
            return value
        return None

    @staticmethod
    def _safe_error_code(value: object) -> int | None:
        if (
            isinstance(value, int)
            and not isinstance(value, bool)
            and 0 < value <= 999_999_999
        ):
            return value
        return None

    @staticmethod
    def _safe_correlation_id(value: object) -> str | None:
        if not isinstance(value, str):
            return None
        try:
            return str(UUID(value))
        except ValueError:
            return None
