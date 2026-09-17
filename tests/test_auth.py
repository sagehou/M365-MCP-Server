import asyncio
import json
import time
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from m365_mcp.app import create_app
from m365_mcp.auth import (
    InsufficientScopeError,
    MsalOboService,
    OboTokenError,
    Settings,
    TokenValidationError,
    UserIdentity,
)
from m365_mcp.auth.oidc import OidcDocumentProvider
from m365_mcp.auth.validator import JwtValidator


TENANT_ID = "00000000-0000-0000-0000-000000000001"
ISSUER = f"https://login.microsoftonline.com/{TENANT_ID}/v2.0"
ISSUER_TEMPLATE = "https://login.microsoftonline.com/{tenantid}/v2.0"


class FakeFetcher:
    def __init__(self, documents: dict[str, dict[str, Any]]) -> None:
        self.documents = documents

    async def __call__(self, url: str) -> dict[str, Any]:
        return self.documents[url]


def make_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "client_id": "api-client-id",
        "client_secret": "client-secret",
        "audience": "api://api-client-id",
        "allowed_tenants": {TENANT_ID},
        "required_scopes": {"access_as_user"},
    }
    values.update(overrides)
    return Settings(**values)


def make_token(*, tenant_id: str = TENANT_ID, scope: str = "access_as_user") -> tuple[str, dict[str, Any]]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key()))
    public_jwk.update({"kid": "test-key", "issuer": ISSUER_TEMPLATE})
    now = int(time.time())
    claims = {
        "aud": "api://api-client-id",
        "exp": now + 300,
        "iat": now,
        "iss": f"https://login.microsoftonline.com/{tenant_id}/v2.0",
        "nbf": now - 1,
        "oid": "00000000-0000-0000-0000-000000000002",
        "preferred_username": "user@example.com",
        "scp": scope,
        "sub": "subject-1",
        "tid": tenant_id,
    }
    token = jwt.encode(
        claims,
        private_key,
        algorithm="RS256",
        headers={"kid": "test-key"},
    )
    return token, {
        "configuration": {
            "issuer": ISSUER_TEMPLATE,
            "jwks_uri": "https://login.microsoftonline.com/common/discovery/v2.0/keys",
        },
        "jwks": {"keys": [public_jwk]},
    }


def make_validator(token_documents: dict[str, dict[str, Any]]) -> JwtValidator:
    settings = make_settings()
    fetcher = FakeFetcher(
        {
            settings.discovery_url: token_documents["configuration"],
            token_documents["configuration"]["jwks_uri"]: token_documents["jwks"],
        }
    )
    return JwtValidator(settings, OidcDocumentProvider(settings, fetcher=fetcher))


def test_valid_delegated_token_returns_tenant_qualified_identity() -> None:
    token, documents = make_token()

    identity = asyncio.run(make_validator(documents).validate(token))

    assert identity.tenant_id == TENANT_ID
    assert identity.user_id == "00000000-0000-0000-0000-000000000002"
    assert identity.tenant_user_key == f"{TENANT_ID}:00000000-0000-0000-0000-000000000002"
    assert identity.scopes == frozenset({"access_as_user"})


def test_validator_rejects_wrong_tenant_and_scope() -> None:
    token, documents = make_token(tenant_id="00000000-0000-0000-0000-000000000003")
    validator = make_validator(documents)

    with pytest.raises(TokenValidationError):
        asyncio.run(validator.validate(token))

    token, documents = make_token(scope="User.Read")
    validator = make_validator(documents)
    with pytest.raises(InsufficientScopeError):
        asyncio.run(validator.validate(token))


def test_obo_uses_allowlisted_tenant_and_configured_graph_scope() -> None:
    calls: list[dict[str, Any]] = []

    class FakeMsalClient:
        def acquire_token_on_behalf_of(
            self, user_assertion: str, scopes: list[str]
        ) -> dict[str, Any]:
            calls.append({"user_assertion": user_assertion, "scopes": scopes})
            return {"access_token": "graph-access-token"}

    def factory(**kwargs: Any) -> FakeMsalClient:
        calls.append(kwargs)
        return FakeMsalClient()

    service = MsalOboService(make_settings(), client_factory=factory)

    assert (
        service.acquire_graph_token(
            user_assertion="inbound-access-token",
            tenant_id=TENANT_ID,
        )
        == "graph-access-token"
    )
    assert calls[0]["authority"].endswith(f"/{TENANT_ID}")
    assert calls[1] == {
        "user_assertion": "inbound-access-token",
        "scopes": ["https://graph.microsoft.com/.default"],
    }


def test_obo_does_not_return_identity_provider_error_details() -> None:
    class FailingMsalClient:
        def acquire_token_on_behalf_of(
            self, user_assertion: str, scopes: list[str]
        ) -> dict[str, Any]:
            return {
                "error": "invalid_grant",
                "error_description": "sensitive provider detail",
            }

    service = MsalOboService(
        make_settings(), client_factory=lambda **kwargs: FailingMsalClient()
    )

    with pytest.raises(OboTokenError) as error:
        service.acquire_graph_token(
            user_assertion="inbound-access-token",
            tenant_id=TENANT_ID,
        )
    assert "sensitive provider detail" not in str(error.value)


def test_mcp_requires_bearer_auth_but_health_remains_public() -> None:
    class StubValidator:
        received_token: str | None = None

        async def validate(self, token: str) -> UserIdentity:
            self.received_token = token
            return UserIdentity(
                tenant_id=TENANT_ID,
                user_id="user-1",
                subject="subject-1",
                issuer=ISSUER,
                audience="api://api-client-id",
                scopes=frozenset({"access_as_user"}),
            )

    validator = StubValidator()
    test_app = create_app(settings=Settings(), token_validator=validator)

    with TestClient(test_app) as client:
        assert client.get("/health").status_code == 200
        unauthenticated = client.get("/mcp/")
        authenticated = client.get(
            "/mcp/",
            headers={"Authorization": "Bearer inbound-token"},
        )

    assert unauthenticated.status_code == 401
    assert unauthenticated.headers["www-authenticate"] == "Bearer"
    assert authenticated.status_code != 401
    assert validator.received_token == "inbound-token"
