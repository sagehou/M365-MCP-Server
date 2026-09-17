"""Validated OAuth discovery and registration models."""

from __future__ import annotations

from dataclasses import dataclass

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
