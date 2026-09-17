"""Identity models shared by authentication and downstream services."""

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class UserIdentity:
    """Validated identity from a delegated Microsoft Entra access token."""

    tenant_id: str
    user_id: str
    subject: str
    issuer: str
    audience: str
    scopes: frozenset[str]
    username: str | None = None
    client_id: str | None = None

    @property
    def tenant_user_key(self) -> str:
        """Return a tenant-qualified key suitable for identity isolation."""

        return f"{self.tenant_id}:{self.user_id}"


@dataclass(frozen=True, slots=True)
class AuthContext:
    """Validated identity plus the short-lived inbound assertion for OBO."""

    identity: UserIdentity
    access_token: str = field(repr=False)
