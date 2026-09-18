import base64
import hashlib
import re
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit

from fastapi.testclient import TestClient

from m365_mcp.app import create_app
from m365_mcp.auth import Settings, UserIdentity
from m365_mcp.oauth.authorization import OAuthAuthorizationService
from m365_mcp.oauth.crypto import AesGcmTokenProtector
from m365_mcp.oauth.models import UpstreamAuthorization, UpstreamTokenResult
from m365_mcp.oauth.registry import DynamicClientRegistry
from m365_mcp.oauth.sessions import OAuthSessionService
from m365_mcp.oauth.store import SQLiteOAuthStore


ISSUER = "https://mcp.example.com"
RESOURCE = f"{ISSUER}/mcp/"
WORKBUDDY_REDIRECT = (
    "workbuddy://workbuddy/mcp/connector%3Asagehou-m365-mcp-server/oauth/callback"
)
TENANT_ID = "11111111-1111-1111-1111-111111111111"
API_CLIENT_ID = "22222222-2222-2222-2222-222222222222"
VERIFIER = "workbuddy-" + "v" * 54


def _pkce_challenge() -> str:
    digest = hashlib.sha256(VERIFIER.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _local_path(url: str) -> str:
    parsed = urlsplit(url)
    assert f"{parsed.scheme}://{parsed.netloc}" == ISSUER
    return parsed.path


class MockEntraBroker:
    def __init__(self) -> None:
        self.upstream_state: str | None = None
        self.refresh_count = 0

    async def begin(self, upstream_state: str) -> UpstreamAuthorization:
        self.upstream_state = upstream_state
        return UpstreamAuthorization(
            authorization_uri=(
                "https://login.microsoftonline.com/organizations/oauth2/v2.0/authorize?"
                + urlencode({"state": upstream_state})
            ),
            flow={"state": upstream_state, "code_verifier": "mock-upstream-pkce"},
        )

    async def complete(
        self,
        flow: dict[str, Any],
        authorization_response: dict[str, str],
    ) -> UpstreamTokenResult:
        assert authorization_response == {
            "code": "mock-entra-code",
            "state": flow["state"],
        }
        return UpstreamTokenResult(
            access_token="mock-token-a-1",
            expires_in=3600,
            serialized_cache="mock-msal-cache-1",
        )

    async def refresh(self, serialized_cache: str) -> UpstreamTokenResult:
        assert serialized_cache == "mock-msal-cache-1"
        self.refresh_count += 1
        return UpstreamTokenResult(
            access_token=f"mock-token-a-{self.refresh_count + 1}",
            expires_in=3300,
            serialized_cache=f"mock-msal-cache-{self.refresh_count + 1}",
        )


class MockTokenValidator:
    def __init__(self) -> None:
        self.validated_tokens: list[str] = []

    async def validate(self, token: str) -> UserIdentity:
        assert token in {"mock-token-a-1", "mock-token-a-2"}
        self.validated_tokens.append(token)
        return UserIdentity(
            tenant_id=TENANT_ID,
            user_id="44444444-4444-4444-4444-444444444444",
            subject="workbuddy-user",
            issuer=f"https://login.microsoftonline.com/{TENANT_ID}/v2.0",
            audience=API_CLIENT_ID,
            scopes=frozenset({"access_as_user"}),
        )


def _make_app(database_path: Path):
    settings = Settings(
        oauth_enabled=True,
        mcp_public_url=RESOURCE,
        oauth_issuer_url=ISSUER,
        oauth_database_path=database_path,
        required_scopes={"access_as_user"},
        client_id=API_CLIENT_ID,
        client_secret="test-api-secret",
        allowed_tenants={TENANT_ID},
        entra_broker_client_id="33333333-3333-3333-3333-333333333333",
        entra_broker_client_secret="test-broker-secret",
        oauth_encryption_key=base64.b64encode(b"k" * 32).decode("ascii"),
    )
    store = SQLiteOAuthStore(database_path)
    registry = DynamicClientRegistry(store, ISSUER)
    broker = MockEntraBroker()
    validator = MockTokenValidator()
    protector = AesGcmTokenProtector(settings.oauth_encryption_key_bytes)
    sessions = OAuthSessionService(
        settings,
        store,
        broker,
        validator,
        protector,
    )
    authorization = OAuthAuthorizationService(
        settings,
        registry,
        store,
        broker,
        validator,
        protector,
        sessions,
    )
    app = create_app(
        settings=settings,
        token_validator=validator,
        mail_service=object(),
        oauth_registry=registry,
        oauth_store=store,
        oauth_authorization_service=authorization,
    )
    return app, broker, validator


def _mcp_rpc(
    client: TestClient,
    access_token: str,
    method: str,
    params: dict[str, Any],
) -> dict[str, Any]:
    response = client.post(
        "/mcp/",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": "2025-03-26",
        },
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
    )
    assert response.status_code == 200, response.text
    return response.json()["result"]


def test_mock_workbuddy_oauth_discovery_authorization_refresh_and_mcp(
    tmp_path: Path,
) -> None:
    app, broker, validator = _make_app(tmp_path / "oauth.db")
    with TestClient(app, base_url=ISSUER) as client:
        challenge = client.get("/mcp/")
        assert challenge.status_code == 401
        match = re.search(
            r'resource_metadata="(?P<url>[^"]+)"',
            challenge.headers["www-authenticate"],
        )
        assert match is not None

        protected_resource = client.get(_local_path(match.group("url")))
        assert protected_resource.status_code == 200
        resource_metadata = protected_resource.json()
        assert resource_metadata["resource"] == RESOURCE
        assert resource_metadata["authorization_servers"] == [ISSUER]

        authorization_server = client.get(
            _local_path(
                resource_metadata["authorization_servers"][0]
                + "/.well-known/oauth-authorization-server"
            )
        )
        assert authorization_server.status_code == 200
        oauth_metadata = authorization_server.json()
        assert oauth_metadata["code_challenge_methods_supported"] == ["S256"]
        assert "refresh_token" in oauth_metadata["grant_types_supported"]

        registration = client.post(
            _local_path(oauth_metadata["registration_endpoint"]),
            json={
                "client_name": "WorkBuddy",
                "redirect_uris": [WORKBUDDY_REDIRECT],
                "application_type": "native",
                "grant_types": ["authorization_code", "refresh_token"],
                "response_types": ["code"],
                "token_endpoint_auth_method": "none",
            },
        )
        assert registration.status_code == 201
        registered = registration.json()
        assert registered["redirect_uris"] == [WORKBUDDY_REDIRECT]
        assert "client_secret" not in registered

        workbuddy_state = "workbuddy-e2e-state"
        authorization = client.get(
            _local_path(oauth_metadata["authorization_endpoint"]),
            params={
                "client_id": registered["client_id"],
                "redirect_uri": WORKBUDDY_REDIRECT,
                "response_type": "code",
                "scope": "access_as_user",
                "state": workbuddy_state,
                "code_challenge": _pkce_challenge(),
                "code_challenge_method": "S256",
                "resource": RESOURCE,
            },
            follow_redirects=False,
        )
        assert authorization.status_code == 302
        entra_state = parse_qs(urlsplit(authorization.headers["location"]).query)[
            "state"
        ][0]
        assert entra_state == broker.upstream_state
        assert entra_state != workbuddy_state

        callback = client.get(
            "/oauth/callback/entra",
            params={"code": "mock-entra-code", "state": entra_state},
            follow_redirects=False,
        )
        assert callback.status_code == 302
        workbuddy_callback = urlsplit(callback.headers["location"])
        assert f"{workbuddy_callback.scheme}://{workbuddy_callback.netloc}{workbuddy_callback.path}" == WORKBUDDY_REDIRECT
        callback_parameters = parse_qs(workbuddy_callback.query)
        assert callback_parameters["state"] == [workbuddy_state]
        assert "access_token" not in callback_parameters
        assert "refresh_token" not in callback_parameters

        token = client.post(
            _local_path(oauth_metadata["token_endpoint"]),
            data={
                "grant_type": "authorization_code",
                "code": callback_parameters["code"][0],
                "client_id": registered["client_id"],
                "redirect_uri": WORKBUDDY_REDIRECT,
                "code_verifier": VERIFIER,
            },
        )
        assert token.status_code == 200
        first_tokens = token.json()
        assert first_tokens["access_token"] == "mock-token-a-1"
        assert first_tokens["token_type"] == "Bearer"
        assert first_tokens["refresh_token"]

        initialized = _mcp_rpc(
            client,
            first_tokens["access_token"],
            "initialize",
            {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "workbuddy-e2e", "version": "0.1"},
            },
        )
        assert initialized["serverInfo"]["name"] == "M365 MCP Server"

        refresh = client.post(
            _local_path(oauth_metadata["token_endpoint"]),
            data={
                "grant_type": "refresh_token",
                "refresh_token": first_tokens["refresh_token"],
                "client_id": registered["client_id"],
            },
        )
        assert refresh.status_code == 200
        refreshed_tokens = refresh.json()
        assert refreshed_tokens["access_token"] == "mock-token-a-2"
        assert refreshed_tokens["refresh_token"] != first_tokens["refresh_token"]

        tools = _mcp_rpc(
            client,
            refreshed_tokens["access_token"],
            "tools/list",
            {},
        )
        assert {tool["name"] for tool in tools["tools"]} == {
            "mail_search",
            "mail_get",
            "mail_list_attachments",
            "mail_read_attachment",
            "mail_mark_read",
            "mail_archive",
            "mail_move",
            "mail_set_category",
        }

    assert broker.refresh_count == 1
    assert "mock-token-a-1" in validator.validated_tokens
    assert "mock-token-a-2" in validator.validated_tokens
