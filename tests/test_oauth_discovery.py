import asyncio
import base64
import logging
from pathlib import Path
import sqlite3
from typing import Any

import pytest
from fastapi.testclient import TestClient

from m365_mcp.app import create_app
from m365_mcp.auth import ConfigurationError, Settings
from m365_mcp.oauth.audit import OAuthAuditLogger
from m365_mcp.oauth.registry import DynamicClientRegistry
from m365_mcp.oauth.store import SQLiteOAuthStore


ISSUER = "https://mcp.example.com"
RESOURCE = "https://mcp.example.com/mcp/"
WORKBUDDY_REDIRECT = (
    "workbuddy://workbuddy/mcp/connector%3Aoutlook-mail/oauth/callback"
)
TENANT_ID = "11111111-1111-1111-1111-111111111111"
API_CLIENT_ID = "22222222-2222-2222-2222-222222222222"


class NeverCalledValidator:
    async def validate(self, token: str) -> Any:
        raise AssertionError("metadata and registration routes must remain public")


def make_settings(database_path: Path, **overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "oauth_enabled": True,
        "mcp_public_url": RESOURCE,
        "oauth_issuer_url": ISSUER,
        "oauth_database_path": database_path,
        "required_scopes": {"access_as_user"},
        "client_id": API_CLIENT_ID,
        "client_secret": "test-api-secret",
        "allowed_tenants": {TENANT_ID},
        "oauth_encryption_key": base64.b64encode(b"k" * 32).decode("ascii"),
    }
    values.update(overrides)
    return Settings(**values)


def make_registry(
    database_path: Path,
    *,
    issuer: str = ISSUER,
    audit_logger: OAuthAuditLogger | None = None,
) -> DynamicClientRegistry:
    return DynamicClientRegistry(
        SQLiteOAuthStore(database_path),
        issuer,
        audit_logger=audit_logger,
    )


def make_app(settings: Settings, registry: DynamicClientRegistry | None = None):
    return create_app(
        settings=settings,
        token_validator=NeverCalledValidator(),
        mail_service=object(),
        oauth_registry=registry,
    )


def registration(**overrides: Any) -> dict[str, Any]:
    value: dict[str, Any] = {
        "client_name": "WorkBuddy",
        "redirect_uris": [WORKBUDDY_REDIRECT],
        "application_type": "native",
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
    }
    value.update(overrides)
    return value


def test_metadata_and_challenge_use_configured_urls_not_request_host(tmp_path: Path) -> None:
    settings = make_settings(tmp_path / "oauth.db")
    with TestClient(make_app(settings)) as client:
        resource = client.get(
            "/.well-known/oauth-protected-resource",
            headers={"Host": "attacker.example", "X-Forwarded-Host": "attacker.example"},
        )
        server = client.get(
            "/.well-known/oauth-authorization-server",
            headers={"Host": "attacker.example", "X-Forwarded-Host": "attacker.example"},
        )
        challenge = client.get(
            "/mcp/",
            headers={"Host": "attacker.example", "X-Forwarded-Host": "attacker.example"},
        )

    assert resource.status_code == 200
    assert resource.json() == {
        "resource": RESOURCE,
        "authorization_servers": [ISSUER],
        "scopes_supported": ["access_as_user"],
    }
    assert server.status_code == 200
    assert server.json() == {
        "issuer": ISSUER,
        "authorization_endpoint": f"{ISSUER}/oauth/authorize",
        "token_endpoint": f"{ISSUER}/oauth/token",
        "registration_endpoint": f"{ISSUER}/oauth/register",
        "scopes_supported": ["access_as_user"],
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none"],
    }
    assert challenge.status_code == 401
    assert challenge.headers["www-authenticate"] == (
        f'Bearer resource_metadata="{ISSUER}/.well-known/oauth-protected-resource"'
    )
    assert "attacker.example" not in challenge.headers["www-authenticate"]
    assert resource.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    "redirect_uris",
    [
        [WORKBUDDY_REDIRECT],
        ["http://localhost:43123/oauth/callback"],
        ["http://127.0.0.1:43123/oauth/callback"],
        ["http://[::1]:43123/oauth/callback"],
        ["https://client.example/oauth/callback"],
        [WORKBUDDY_REDIRECT, "http://127.0.0.1:43123/oauth/callback"],
    ],
)
def test_dcr_accepts_supported_redirects_and_persists_exact_values(
    tmp_path: Path,
    redirect_uris: list[str],
) -> None:
    database_path = tmp_path / "oauth.db"
    registry = make_registry(database_path)
    with TestClient(make_app(make_settings(database_path), registry)) as client:
        response = client.post(
            "/oauth/register",
            json=registration(redirect_uris=redirect_uris),
        )

    assert response.status_code == 201
    body = response.json()
    assert body["client_id"].startswith("mcp_")
    assert body["redirect_uris"] == redirect_uris
    assert body["token_endpoint_auth_method"] == "none"
    assert "client_secret" not in body

    restarted = make_registry(database_path)
    asyncio.run(restarted.initialize())
    with sqlite3.connect(database_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    assert {
        "oauth_clients",
        "oauth_transactions",
        "oauth_codes",
        "oauth_sessions",
        "oauth_refresh_token_history",
    } <= tables
    persisted = asyncio.run(restarted.get(body["client_id"]))
    assert persisted is not None
    assert persisted.redirect_uris == tuple(redirect_uris)
    assert asyncio.run(restarted.validate_redirect(body["client_id"], redirect_uris[0]))
    assert not asyncio.run(
        restarted.validate_redirect(body["client_id"], redirect_uris[0] + "/extra")
    )


def test_dcr_accepts_workbuddy_private_scheme_registration(tmp_path: Path) -> None:
    redirect_uri = "workbuddy://workbuddy/mcp/test/oauth/callback"
    with TestClient(make_app(make_settings(tmp_path / "oauth.db"))) as client:
        response = client.post(
            "/oauth/register",
            json={
                "client_name": "WorkBuddy",
                "redirect_uris": [redirect_uri],
                "grant_types": ["authorization_code", "refresh_token"],
                "response_types": ["code"],
                "token_endpoint_auth_method": "none",
            },
        )

    assert response.status_code == 201
    assert response.json()["client_id"].startswith("mcp_")
    assert response.json()["client_name"] == "WorkBuddy"
    assert response.json()["redirect_uris"] == [redirect_uri]
    assert response.json()["token_endpoint_auth_method"] == "none"


@pytest.mark.parametrize(
    "redirect_uri",
    [
        "http://localhost:12345/callback",
        "http://127.0.0.1:52341/oauth/callback",
        "http://[::1]:43123/workbuddy/return",
    ],
)
def test_dcr_accepts_loopback_redirect_with_arbitrary_path(
    tmp_path: Path,
    redirect_uri: str,
) -> None:
    with TestClient(make_app(make_settings(tmp_path / "oauth.db"))) as client:
        response = client.post(
            "/oauth/register",
            json={
                "client_name": "WorkBuddy",
                "redirect_uris": [redirect_uri],
            },
        )

    assert response.status_code == 201
    assert response.json()["redirect_uris"] == [redirect_uri]
    assert response.json()["token_endpoint_auth_method"] == "none"


@pytest.mark.parametrize(
    ("payload", "raw_body"),
    [
        (registration(redirect_uris=["http://public.example.com/oauth/callback"]), None),
        (registration(redirect_uris=["http://8.8.8.8/callback"]), None),
        (registration(redirect_uris=["workbuddy://evil/oauth/callback"]), None),
        (registration(redirect_uris=["https://client.example/callback?code=chosen"]), None),
        (registration(redirect_uris=["*"]), None),
        (registration(redirect_uris=[]), None),
        ({"client_name": "Missing redirect"}, None),
        (registration(application_type="desktop"), None),
        (registration(token_endpoint_auth_method="client_secret_post"), None),
        (None, "not-json"),
    ],
)
def test_dcr_rejects_invalid_or_malformed_client_metadata(
    tmp_path: Path,
    payload: dict[str, Any] | None,
    raw_body: str | None,
) -> None:
    with TestClient(make_app(make_settings(tmp_path / "oauth.db"))) as client:
        if raw_body is None:
            response = client.post("/oauth/register", json=payload)
        else:
            response = client.post(
                "/oauth/register",
                content=raw_body,
                headers={"Content-Type": "application/json"},
            )

    assert response.status_code == 400
    assert response.json()["error"] == "invalid_client_metadata"


def test_dcr_rejection_logs_safe_structured_reason(
    tmp_path: Path,
    caplog: Any,
) -> None:
    redirect_uri = "workbuddy://evil/private/oauth/callback"
    logger_name = "m365_mcp.oauth.routes"
    with caplog.at_level(logging.WARNING, logger=logger_name):
        with TestClient(make_app(make_settings(tmp_path / "oauth.db"))) as client:
            response = client.post(
                "/oauth/register",
                json=registration(redirect_uris=[redirect_uri]),
            )

    assert response.status_code == 400
    records = [record for record in caplog.records if record.name == logger_name]
    assert len(records) == 1
    record = records[0]
    assert record.message == "OAuth client registration rejected"
    assert record.error_type == "ValueError"
    assert record.error == "invalid WorkBuddy redirect_uri"
    assert record.redirect_uri_count == 1
    assert redirect_uri not in caplog.text


def test_registry_binds_clients_to_issuer_and_emits_safe_audit(
    tmp_path: Path,
    caplog: Any,
) -> None:
    database_path = tmp_path / "oauth.db"
    logger = logging.getLogger("test.oauth.audit")
    registry = make_registry(
        database_path,
        audit_logger=OAuthAuditLogger(logger),
    )
    with caplog.at_level(logging.INFO, logger=logger.name):
        with TestClient(make_app(make_settings(database_path), registry)) as client:
            response = client.post("/oauth/register", json=registration())

    client_id = response.json()["client_id"]
    other_issuer = make_registry(database_path, issuer="https://other.example")
    asyncio.run(other_issuer.initialize())
    assert asyncio.run(other_issuer.get(client_id)) is None
    record = caplog.records[-1]
    assert record.event == "oauth_client_registered"
    assert record.client_id == client_id
    assert record.result == "success"
    assert WORKBUDDY_REDIRECT not in caplog.text


def test_dcr_applies_public_client_defaults_and_ignores_optional_metadata(
    tmp_path: Path,
) -> None:
    with TestClient(make_app(make_settings(tmp_path / "oauth.db"))) as client:
        response = client.post(
            "/oauth/register",
            json={
                "redirect_uris": [WORKBUDDY_REDIRECT],
                "scope": "access_as_user",
                "software_id": "workbuddy-desktop",
            },
        )

    assert response.status_code == 201
    body = response.json()
    assert body["application_type"] == "native"
    assert body["grant_types"] == ["authorization_code", "refresh_token"]
    assert body["response_types"] == ["code"]
    assert body["token_endpoint_auth_method"] == "none"
    assert body["scope"] == "access_as_user"
    assert "software_id" not in body


def test_oauth_feature_flag_defaults_off_and_requires_explicit_urls(tmp_path: Path) -> None:
    with TestClient(make_app(Settings(oauth_enabled=False))) as client:
        assert client.get("/.well-known/oauth-protected-resource").status_code == 404
        challenge = client.get("/mcp/")
    assert challenge.status_code == 401
    assert challenge.headers["www-authenticate"] == "Bearer"

    with pytest.raises(ConfigurationError):
        make_app(Settings(oauth_enabled=True, oauth_database_path=tmp_path / "oauth.db"))


@pytest.mark.parametrize(
    "field_value",
    [
        "http://public.example.com",
        "https://user:password@mcp.example.com",
        "https://mcp.example.com?issuer=attacker",
        "https://mcp.example.com/issuer-path",
        'https://mcp.example.com/"broken',
        "//mcp.example.com",
    ],
)
def test_oauth_public_urls_reject_unsafe_values(field_value: str) -> None:
    with pytest.raises(ValueError):
        Settings(oauth_issuer_url=field_value)
