import asyncio
import json
import time
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from pydantic import ValidationError

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
OTHER_TENANT_ID = "00000000-0000-0000-0000-000000000003"
MSA_TENANT_ID = "9188040d-6c67-4c5b-b112-36a304b66dad"
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


def make_token(*, tenant_id: str = TENANT_ID, scope: str = "access_as_user",
               kid: str = "test-key", claims_override: dict[str, Any] | None = None) -> tuple[str, dict[str, Any]]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key()))
    public_jwk.update({"kid": kid, "issuer": ISSUER_TEMPLATE})
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
    claims.update(claims_override or {})
    token = jwt.encode(
        claims,
        private_key,
        algorithm="RS256",
        headers={"kid": kid},
    )
    return token, {
        "configuration": {
            "issuer": ISSUER_TEMPLATE,
            "jwks_uri": "https://login.microsoftonline.com/common/discovery/v2.0/keys",
        },
        "jwks": {"keys": [public_jwk]},
    }


def make_validator(
    token_documents: dict[str, dict[str, Any]],
    *,
    settings: Settings | None = None,
) -> JwtValidator:
    configured_settings = settings or make_settings()
    fetcher = FakeFetcher(
        {
            configured_settings.discovery_url: token_documents["configuration"],
            token_documents["configuration"]["jwks_uri"]: token_documents["jwks"],
        }
    )
    return JwtValidator(
        configured_settings,
        OidcDocumentProvider(configured_settings, fetcher=fetcher),
    )


def test_valid_delegated_token_returns_tenant_qualified_identity() -> None:
    token, documents = make_token()

    identity = asyncio.run(make_validator(documents).validate(token))

    assert identity.tenant_id == TENANT_ID
    assert identity.user_id == "00000000-0000-0000-0000-000000000002"
    assert identity.tenant_user_key == f"{TENANT_ID}:00000000-0000-0000-0000-000000000002"
    assert identity.scopes == frozenset({"access_as_user"})


def test_validator_rejects_wrong_tenant_and_scope() -> None:
    token, documents = make_token(tenant_id=OTHER_TENANT_ID)
    validator = make_validator(documents)

    with pytest.raises(TokenValidationError):
        asyncio.run(validator.validate(token))

    token, documents = make_token(scope="User.Read")
    validator = make_validator(documents)
    with pytest.raises(InsufficientScopeError):
        asyncio.run(validator.validate(token))


@pytest.mark.parametrize("tenant_id", [OTHER_TENANT_ID, MSA_TENANT_ID])
def test_wildcard_allows_any_valid_microsoft_tenant(tenant_id: str) -> None:
    token, documents = make_token(tenant_id=tenant_id)
    settings = make_settings(allowed_tenants={"*"})

    identity = asyncio.run(make_validator(documents, settings=settings).validate(token))

    assert identity.tenant_id == tenant_id
    assert settings.authority_for_tenant(tenant_id).endswith(f"/{tenant_id}")


def test_wildcard_cannot_be_combined_with_explicit_tenant_ids() -> None:
    with pytest.raises(ValidationError):
        make_settings(allowed_tenants={"*", TENANT_ID})


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
    correlation_id = "11111111-2222-3333-4444-555555555555"

    class FailingMsalClient:
        def acquire_token_on_behalf_of(
            self, user_assertion: str, scopes: list[str]
        ) -> dict[str, Any]:
            return {
                "error": "invalid_grant",
                "suberror": "consent_required",
                "error_codes": [65001],
                "correlation_id": correlation_id,
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
    assert error.value.entra_error == "invalid_grant"
    assert error.value.entra_suberror == "consent_required"
    assert error.value.entra_error_code == 65001
    assert error.value.correlation_id == correlation_id


def test_obo_discards_unsafe_provider_diagnostic_values() -> None:
    error = OboTokenError.from_msal_result(
        {
            "error": "invalid_grant\nforged-log-entry",
            "suberror": "x" * 65,
            "error_codes": [True, -1, 1_000_000_000],
            "correlation_id": "not-a-uuid",
            "error_description": "secret bearer token",
        }
    )

    assert error.entra_error is None
    assert error.entra_suberror is None
    assert error.entra_error_code is None
    assert error.correlation_id is None
    assert "secret bearer token" not in str(error)


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
