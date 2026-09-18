"""Environment-backed authentication configuration."""

import base64
import binascii
from pathlib import Path
from typing import Any
from ipaddress import ip_address
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .errors import ConfigurationError


def _split_values(value: Any) -> Any:
    if value is None or isinstance(value, (set, frozenset, tuple, list)):
        return value
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return value


class Settings(BaseSettings):
    """Settings required to validate inbound tokens and perform OBO."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        env_prefix="",
        extra="ignore",
        enable_decoding=False,
    )

    tenant_id: str | None = None
    client_id: str | None = None
    client_secret: SecretStr | None = None
    client_cert_path: Path | None = None
    client_cert_thumbprint: str | None = None

    authority_host: str = "https://login.microsoftonline.com"
    audience: str | None = None
    allowed_tenants: frozenset[str] = Field(default_factory=frozenset)
    required_scopes: frozenset[str] = Field(
        default_factory=lambda: frozenset({"access_as_user"})
    )
    graph_scopes: tuple[str, ...] = (
        "https://graph.microsoft.com/.default",
    )
    graph_base_url: str = "https://graph.microsoft.com/v1.0"
    graph_max_retries: int = Field(default=3, ge=0, le=5)
    graph_retry_backoff_seconds: float = Field(default=0.5, ge=0, allow_inf_nan=False)
    graph_max_retry_delay_seconds: float = Field(default=30.0, gt=0, allow_inf_nan=False)
    graph_max_response_bytes: int = Field(default=16 * 1024 * 1024, gt=0)

    oidc_cache_ttl_seconds: int = Field(default=86_400, gt=0)
    http_timeout_seconds: float = Field(default=10.0, gt=0, allow_inf_nan=False)
    attachment_max_bytes: int = Field(default=10 * 1024 * 1024, gt=0, le=50 * 1024 * 1024)
    attachment_max_text_chars: int = Field(default=100_000, gt=0, le=1_000_000)

    oauth_enabled: bool = False
    mcp_public_url: str | None = None
    oauth_issuer_url: str | None = None
    oauth_database_path: Path = Path("/data/oauth.db")
    oauth_transaction_ttl_seconds: int = Field(default=600, ge=60, le=900)
    oauth_authorization_code_ttl_seconds: int = Field(default=600, ge=60, le=600)
    oauth_refresh_token_ttl_days: int = Field(default=30, ge=1, le=365)
    oauth_refresh_max_rotations: int = Field(default=10_000, ge=1, le=10_000)
    oauth_encryption_key: SecretStr | None = None

    @field_validator("allowed_tenants", "required_scopes", mode="before")
    @classmethod
    def normalize_sets(cls, value: Any) -> frozenset[str]:
        return frozenset(_split_values(value) or ())

    @field_validator("allowed_tenants")
    @classmethod
    def validate_allowed_tenants(cls, value: frozenset[str]) -> frozenset[str]:
        if "*" in value and len(value) != 1:
            raise ValueError("ALLOWED_TENANTS '*' cannot be combined with tenant IDs")
        return value

    @field_validator("graph_scopes", mode="before")
    @classmethod
    def normalize_scopes(cls, value: Any) -> tuple[str, ...]:
        return tuple(_split_values(value) or ())

    @field_validator("authority_host")
    @classmethod
    def normalize_authority_host(cls, value: str) -> str:
        return value.rstrip("/")

    @field_validator("mcp_public_url", "oauth_issuer_url")
    @classmethod
    def validate_oauth_public_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value.isascii():
            raise ValueError("OAuth public URLs must use their ASCII representation")
        if any(ord(character) < 0x21 for character in value) or any(
            character in value for character in ('"', "\\")
        ):
            raise ValueError("OAuth public URLs contain unsafe characters")
        parsed = urlsplit(value)
        if not parsed.scheme or not parsed.hostname:
            raise ValueError("OAuth public URLs must be absolute")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("OAuth public URLs must not contain user information")
        if parsed.query or parsed.fragment:
            raise ValueError("OAuth public URLs must not contain query or fragment parts")
        host = parsed.hostname.casefold()
        try:
            loopback = ip_address(host).is_loopback
        except ValueError:
            loopback = host == "localhost"
        if parsed.scheme.casefold() != "https" and not (
            parsed.scheme.casefold() == "http" and loopback
        ):
            raise ValueError("OAuth public URLs require HTTPS except on loopback")
        return value

    @field_validator("oauth_issuer_url")
    @classmethod
    def validate_oauth_issuer_origin(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parsed = urlsplit(value)
        if parsed.path not in {"", "/"}:
            raise ValueError("OAUTH_ISSUER_URL must be an origin without a path")
        return value.rstrip("/")

    @field_validator("mcp_public_url")
    @classmethod
    def validate_mcp_resource_path(cls, value: str | None) -> str | None:
        if value is not None and not urlsplit(value).path.endswith("/mcp/"):
            raise ValueError("MCP_PUBLIC_URL must identify the public /mcp/ endpoint")
        return value

    @property
    def expected_audiences(self) -> frozenset[str]:
        """Return accepted API audiences, never a downstream Graph audience."""

        if self.audience:
            return frozenset({self.audience})
        if not self.client_id:
            return frozenset()
        return frozenset({self.client_id, f"api://{self.client_id}"})

    @property
    def discovery_url(self) -> str:
        """Return tenant-independent v2.0 metadata for key validation."""

        return (
            f"{self.authority_host}/common/v2.0/"
            ".well-known/openid-configuration"
        )

    def is_allowed_tenant(self, tenant_id: str) -> bool:
        allowed = {item.casefold() for item in self.allowed_tenants}
        return "*" in allowed or tenant_id.casefold() in allowed

    def authority_for_tenant(self, tenant_id: str) -> str:
        if not self.is_allowed_tenant(tenant_id):
            raise ConfigurationError("The token tenant is not allowlisted")
        return f"{self.authority_host}/{tenant_id}"

    @property
    def normalized_oauth_issuer_url(self) -> str:
        if not self.oauth_issuer_url:
            raise ConfigurationError("OAUTH_ISSUER_URL is not configured")
        return self.oauth_issuer_url.rstrip("/")

    @property
    def protected_resource_metadata_url(self) -> str:
        return (
            f"{self.normalized_oauth_issuer_url}/"
            ".well-known/oauth-protected-resource"
        )

    @property
    def oauth_callback_uri(self) -> str:
        return f"{self.normalized_oauth_issuer_url}/oauth/callback"

    @property
    def entra_authorization_scopes(self) -> tuple[str, ...]:
        if not self.client_id:
            raise ConfigurationError("CLIENT_ID is not configured")
        return tuple(
            f"api://{self.client_id}/{scope}"
            for scope in sorted(self.required_scopes)
        )

    @property
    def entra_authority(self) -> str:
        """Use one upstream authority that supports every configured account type."""

        return f"{self.authority_host}/common"

    @property
    def oauth_encryption_key_bytes(self) -> bytes:
        """Decode the configured 256-bit AEAD key without exposing it."""

        if self.oauth_encryption_key is None:
            raise ConfigurationError("OAUTH_ENCRYPTION_KEY is not configured")
        try:
            decoded = base64.b64decode(
                self.oauth_encryption_key.get_secret_value().encode("ascii"),
                altchars=b"-_",
                validate=True,
            )
        except (UnicodeEncodeError, binascii.Error, ValueError) as exc:
            raise ConfigurationError(
                "OAUTH_ENCRYPTION_KEY must be valid base64"
            ) from exc
        if len(decoded) != 32:
            raise ConfigurationError(
                "OAUTH_ENCRYPTION_KEY must decode to exactly 32 bytes"
            )
        return decoded

    def validate_oauth_discovery_configuration(self) -> None:
        """Fail closed when the optional OAuth discovery surface is enabled."""

        if not self.oauth_enabled:
            return
        missing: list[str] = []
        if not self.mcp_public_url:
            missing.append("MCP_PUBLIC_URL")
        if not self.oauth_issuer_url:
            missing.append("OAUTH_ISSUER_URL")
        if not self.required_scopes:
            missing.append("REQUIRED_SCOPES")
        if missing:
            raise ConfigurationError(
                "OAuth discovery configuration is incomplete: " + ", ".join(missing)
            )

    def validate_oauth_authorization_configuration(self) -> None:
        """Fail closed before exposing interactive OAuth authorization."""

        self.validate_oauth_discovery_configuration()
        if not self.oauth_enabled:
            return
        self.validate_auth_configuration()
        missing: list[str] = []
        if self.oauth_encryption_key is None:
            missing.append("OAUTH_ENCRYPTION_KEY")
        if missing:
            raise ConfigurationError(
                "OAuth authorization configuration is incomplete: "
                + ", ".join(missing)
            )
        self.oauth_encryption_key_bytes

    def validate_auth_configuration(self) -> None:
        """Fail closed when the authentication boundary is not configured."""

        missing: list[str] = []
        if not self.client_id:
            missing.append("CLIENT_ID")
        if not self.allowed_tenants:
            missing.append("ALLOWED_TENANTS")
        if not self.required_scopes:
            missing.append("REQUIRED_SCOPES")
        if not self.expected_audiences:
            missing.append("AUDIENCE or CLIENT_ID")

        has_secret = self.client_secret is not None
        has_certificate = self.client_cert_path is not None
        if has_secret == has_certificate:
            missing.append("exactly one of CLIENT_SECRET or CLIENT_CERT_PATH")
        if has_certificate and not self.client_cert_thumbprint:
            missing.append("CLIENT_CERT_THUMBPRINT")

        if missing:
            raise ConfigurationError(
                "Authentication configuration is incomplete: " + ", ".join(missing)
            )

    def client_credential(self) -> str | dict[str, str]:
        """Load the configured MSAL client credential without logging it."""

        self.validate_auth_configuration()
        if self.client_secret is not None:
            return self.client_secret.get_secret_value()

        if self.client_cert_path is None or self.client_cert_thumbprint is None:
            raise ConfigurationError("The client certificate is not configured")
        try:
            private_key = self.client_cert_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ConfigurationError("The client certificate could not be read") from exc
        return {
            "private_key": private_key,
            "thumbprint": self.client_cert_thumbprint,
        }
