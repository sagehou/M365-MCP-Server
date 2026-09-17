"""Environment-backed authentication configuration."""

from pathlib import Path
from typing import Any

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

    oidc_cache_ttl_seconds: int = 86_400
    http_timeout_seconds: float = 10.0

    @field_validator("allowed_tenants", "required_scopes", mode="before")
    @classmethod
    def normalize_sets(cls, value: Any) -> frozenset[str]:
        return frozenset(_split_values(value) or ())

    @field_validator("graph_scopes", mode="before")
    @classmethod
    def normalize_scopes(cls, value: Any) -> tuple[str, ...]:
        return tuple(_split_values(value) or ())

    @field_validator("authority_host")
    @classmethod
    def normalize_authority_host(cls, value: str) -> str:
        return value.rstrip("/")

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
        return tenant_id.casefold() in allowed

    def authority_for_tenant(self, tenant_id: str) -> str:
        if not self.is_allowed_tenant(tenant_id):
            raise ConfigurationError("The token tenant is not allowlisted")
        return f"{self.authority_host}/{tenant_id}"

    def validate_auth_configuration(self) -> None:
        """Fail closed when the authentication boundary is not configured."""

        missing: list[str] = []
        if not self.client_id:
            missing.append("CLIENT_ID")
        if not self.allowed_tenants:
            missing.append("ALLOWED_TENANTS")
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
