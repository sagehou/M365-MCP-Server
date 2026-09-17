"""Validated OAuth discovery and registration models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


SUPPORTED_GRANT_TYPES = frozenset({"authorization_code", "refresh_token"})
SUPPORTED_RESPONSE_TYPES = frozenset({"code"})


class OAuthClientRegistration(BaseModel):
    """Public-client metadata accepted by the dynamic registration endpoint."""

    model_config = ConfigDict(extra="ignore")

    redirect_uris: list[str] = Field(min_length=1, max_length=10)
    client_name: str = Field(default="MCP OAuth Client", min_length=1, max_length=200)
    application_type: str = "native"
    grant_types: list[str] = Field(
        default_factory=lambda: ["authorization_code", "refresh_token"]
    )
    response_types: list[str] = Field(default_factory=lambda: ["code"])
    token_endpoint_auth_method: str = "none"
    scope: str | None = Field(default=None, max_length=500)

    @field_validator("redirect_uris", "grant_types", "response_types")
    @classmethod
    def reject_duplicates(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("duplicate values are not allowed")
        return value

    @model_validator(mode="after")
    def validate_public_client_metadata(self) -> "OAuthClientRegistration":
        if self.application_type not in {"native", "web"}:
            raise ValueError("unsupported application_type")
        if not self.grant_types or not set(self.grant_types) <= SUPPORTED_GRANT_TYPES:
            raise ValueError("unsupported grant_types")
        if "authorization_code" not in self.grant_types:
            raise ValueError("authorization_code grant is required")
        if not self.response_types or not set(self.response_types) <= SUPPORTED_RESPONSE_TYPES:
            raise ValueError("unsupported response_types")
        if self.token_endpoint_auth_method != "none":
            raise ValueError("only public clients are supported")
        return self


class OAuthAuthorizationRequest(BaseModel):
    """Validated shape of an MCP authorization request."""

    model_config = ConfigDict(extra="forbid")

    client_id: str = Field(min_length=1, max_length=200)
    redirect_uri: str = Field(min_length=1, max_length=2048)
    response_type: str = Field(min_length=1, max_length=50)
    scope: str = Field(min_length=1, max_length=500)
    state: str = Field(min_length=1, max_length=1024)
    code_challenge: str = Field(min_length=1, max_length=128)
    code_challenge_method: str = Field(min_length=1, max_length=20)
    resource: str | None = Field(default=None, max_length=2048)


class OAuthTokenRequest(BaseModel):
    """Validated shape of an authorization-code token request."""

    model_config = ConfigDict(extra="forbid")

    grant_type: str = Field(min_length=1, max_length=50)
    code: str = Field(min_length=1, max_length=512)
    client_id: str = Field(min_length=1, max_length=200)
    redirect_uri: str = Field(min_length=1, max_length=2048)
    code_verifier: str = Field(min_length=1, max_length=256)


@dataclass(frozen=True, slots=True)
class OAuthClient:
    """Persisted public OAuth client bound to one issuer."""

    issuer: str
    client_id: str
    client_name: str
    redirect_uris: tuple[str, ...]
    application_type: str
    grant_types: tuple[str, ...]
    response_types: tuple[str, ...]
    token_endpoint_auth_method: str
    scope: str | None
    created_at: int

    def registration_response(self) -> dict[str, object]:
        response: dict[str, object] = {
            "client_id": self.client_id,
            "client_name": self.client_name,
            "redirect_uris": list(self.redirect_uris),
            "application_type": self.application_type,
            "grant_types": list(self.grant_types),
            "response_types": list(self.response_types),
            "token_endpoint_auth_method": self.token_endpoint_auth_method,
            "client_id_issued_at": self.created_at,
        }
        if self.scope is not None:
            response["scope"] = self.scope
        return response


@dataclass(frozen=True, slots=True)
class OAuthTransaction:
    """Persisted binding between an MCP request and one Entra authorization."""

    transaction_id_hash: str
    issuer: str
    client_id: str
    redirect_uri: str
    workbuddy_state: str
    entra_state_hash: str
    code_challenge: str
    scope: str
    resource: str
    protected_upstream_flow: bytes
    created_at: int
    expires_at: int
    completed_at: int | None = None


@dataclass(frozen=True, slots=True)
class OAuthAuthorizationCode:
    """One-time local authorization code with an encrypted token bundle."""

    code_hash: str
    issuer: str
    client_id: str
    redirect_uri: str
    scope: str
    resource: str
    code_challenge: str
    encrypted_msal_cache: bytes
    tenant_id: str
    user_id: str
    created_at: int
    expires_at: int
    used_at: int | None = None


@dataclass(frozen=True, slots=True)
class UpstreamAuthorization:
    """Authorization URI and opaque MSAL flow state returned by the broker."""

    authorization_uri: str
    flow: dict[str, Any]


@dataclass(frozen=True, slots=True)
class UpstreamTokenResult:
    """Validated shape of the token material returned by MSAL."""

    access_token: str
    expires_in: int
    serialized_cache: str


@dataclass(frozen=True, slots=True)
class OAuthTokenResponse:
    """Local token response returned to the registered public client."""

    access_token: str
    expires_in: int
    scope: str

    def as_dict(self) -> dict[str, object]:
        return {
            "access_token": self.access_token,
            "token_type": "Bearer",
            "expires_in": self.expires_in,
            "scope": self.scope,
        }
