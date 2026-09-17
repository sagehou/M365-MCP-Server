import asyncio
import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import logging
from pathlib import Path
import sqlite3
from threading import Barrier
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit

from fastapi.testclient import TestClient

from m365_mcp.app import create_app
from m365_mcp.auth import (
    AuthenticationError,
    ConfigurationError,
    Settings,
    UserIdentity,
)
from m365_mcp.oauth.authorization import OAuthAuthorizationService
from m365_mcp.oauth.audit import OAuthAuditLogger
from m365_mcp.oauth.crypto import AesGcmTokenProtector
from m365_mcp.oauth.entra import (
    EntraBrokerError,
    EntraRefreshRejectedError,
    MsalEntraAuthorizationBroker,
)
from m365_mcp.oauth.models import UpstreamAuthorization, UpstreamTokenResult
from m365_mcp.oauth.registry import DynamicClientRegistry
from m365_mcp.oauth.sessions import OAuthSessionService
from m365_mcp.oauth.store import SQLiteOAuthStore


ISSUER = "https://mcp.example.com"
RESOURCE = "https://mcp.example.com/mcp/"
REDIRECT_URI = "workbuddy://workbuddy/mcp/connector%3Aoutlook-mail/oauth/callback"
TENANT_ID = "11111111-1111-1111-1111-111111111111"
API_CLIENT_ID = "22222222-2222-2222-2222-222222222222"
VERIFIER = "v" * 64


def pkce_challenge(verifier: str = VERIFIER) -> str:
    return base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")


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
        "entra_broker_client_id": "33333333-3333-3333-3333-333333333333",
        "entra_broker_client_secret": "test-broker-secret",
        "oauth_encryption_key": base64.b64encode(b"k" * 32).decode("ascii"),
    }
    values.update(overrides)
    return Settings(**values)


class FakeBroker:
    def __init__(self) -> None:
        self.states: list[str] = []
        self.completed_flows: list[dict[str, Any]] = []
        self.refreshed_caches: list[str] = []

    async def begin(self, upstream_state: str) -> UpstreamAuthorization:
        self.states.append(upstream_state)
        flow = {"state": upstream_state, "code_verifier": "upstream-pkce"}
        return UpstreamAuthorization(
            authorization_uri=(
                "https://login.microsoftonline.com/organizations/"
                "oauth2/v2.0/authorize?" + urlencode({"state": upstream_state})
            ),
            flow=flow,
        )

    async def complete(
        self,
        flow: dict[str, Any],
        authorization_response: dict[str, str],
    ) -> UpstreamTokenResult:
        assert authorization_response["state"] == flow["state"]
        self.completed_flows.append(flow)
        return UpstreamTokenResult(
            access_token="validated-token-a",
            expires_in=3600,
            serialized_cache="sensitive-msal-cache",
        )

    async def refresh(self, serialized_cache: str) -> UpstreamTokenResult:
        self.refreshed_caches.append(serialized_cache)
        return UpstreamTokenResult(
            access_token=f"refreshed-token-{len(self.refreshed_caches)}",
            expires_in=3300,
            serialized_cache=f"refreshed-cache-{len(self.refreshed_caches)}",
        )


class FakeValidator:
    def __init__(self) -> None:
        self.tokens: list[str] = []

    async def validate(self, token: str) -> UserIdentity:
        self.tokens.append(token)
        return UserIdentity(
            tenant_id=TENANT_ID,
            user_id="44444444-4444-4444-4444-444444444444",
            subject="subject",
            issuer=f"https://login.microsoftonline.com/{TENANT_ID}/v2.0",
            audience=API_CLIENT_ID,
            scopes=frozenset({"access_as_user"}),
        )


class FailingBroker(FakeBroker):
    async def complete(
        self,
        flow: dict[str, Any],
        authorization_response: dict[str, str],
    ) -> UpstreamTokenResult:
        raise EntraBrokerError("simulated upstream failure")


class RefreshFailingBroker(FakeBroker):
    def __init__(self) -> None:
        super().__init__()
        self.fail_refresh = True

    async def refresh(self, serialized_cache: str) -> UpstreamTokenResult:
        if self.fail_refresh:
            raise EntraBrokerError("simulated refresh outage")
        return await super().refresh(serialized_cache)


class RevokedRefreshBroker(FakeBroker):
    async def refresh(self, serialized_cache: str) -> UpstreamTokenResult:
        raise EntraRefreshRejectedError("simulated Microsoft revocation")


class WrongStateRedirectBroker(FakeBroker):
    async def begin(self, upstream_state: str) -> UpstreamAuthorization:
        self.states.append(upstream_state)
        return UpstreamAuthorization(
            authorization_uri=(
                "https://login.microsoftonline.com/organizations/"
                "oauth2/v2.0/authorize?state=wrong-state"
            ),
            flow={"state": upstream_state, "code_verifier": "upstream-pkce"},
        )


class RejectingValidator(FakeValidator):
    async def validate(self, token: str) -> UserIdentity:
        self.tokens.append(token)
        raise AuthenticationError("simulated invalid token")


class MismatchedRefreshValidator(FakeValidator):
    async def validate(self, token: str) -> UserIdentity:
        if not self.tokens:
            return await super().validate(token)
        self.tokens.append(token)
        return UserIdentity(
            tenant_id=TENANT_ID,
            user_id="55555555-5555-5555-5555-555555555555",
            subject="other-subject",
            issuer=f"https://login.microsoftonline.com/{TENANT_ID}/v2.0",
            audience=API_CLIENT_ID,
            scopes=frozenset({"access_as_user"}),
        )


def make_app(
    database_path: Path,
    *,
    audit_logger: OAuthAuditLogger | None = None,
    broker: Any | None = None,
    validator: Any | None = None,
):
    settings = make_settings(database_path)
    store = SQLiteOAuthStore(database_path)
    registry = DynamicClientRegistry(store, ISSUER, audit_logger=audit_logger)
    selected_broker = broker if broker is not None else FakeBroker()
    selected_validator = validator if validator is not None else FakeValidator()
    token_protector = AesGcmTokenProtector(settings.oauth_encryption_key_bytes)
    session_service = OAuthSessionService(
        settings,
        store,
        selected_broker,
        selected_validator,
        token_protector,
        audit_logger=audit_logger,
    )
    service = OAuthAuthorizationService(
        settings,
        registry,
        store,
        selected_broker,
        selected_validator,
        token_protector,
        session_service,
        audit_logger=audit_logger,
    )
    app = create_app(
        settings=settings,
        token_validator=selected_validator,
        mail_service=object(),
        oauth_registry=registry,
        oauth_store=store,
        oauth_authorization_service=service,
    )
    return app, selected_broker, selected_validator


def register_client(client: TestClient) -> str:
    response = client.post(
        "/oauth/register",
        json={
            "client_name": "WorkBuddy",
            "redirect_uris": [REDIRECT_URI],
            "application_type": "native",
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",
        },
    )
    assert response.status_code == 201
    return response.json()["client_id"]


def authorization_parameters(client_id: str, **overrides: str) -> dict[str, str]:
    parameters: dict[str, str] = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "access_as_user",
        "state": "workbuddy-state",
        "code_challenge": pkce_challenge(),
        "code_challenge_method": "S256",
        "resource": RESOURCE,
    }
    parameters.update(overrides)
    return parameters


def begin_authorization(client: TestClient, client_id: str, **overrides: str):
    parameters = authorization_parameters(client_id, **overrides)
    return client.get("/oauth/authorize", params=parameters, follow_redirects=False)


def complete_authorization(client: TestClient, upstream_state: str):
    return client.get(
        "/oauth/callback/entra",
        params={"code": "entra-code", "state": upstream_state},
        follow_redirects=False,
    )


def local_code_from_redirect(location: str) -> str:
    parsed = urlsplit(location)
    assert parsed.scheme == "workbuddy"
    query = parse_qs(parsed.query)
    assert query["state"] == ["workbuddy-state"]
    assert "access_token" not in query
    assert "refresh_token" not in query
    return query["code"][0]


def redeem_code(
    client: TestClient,
    client_id: str,
    code: str,
    *,
    verifier: str = VERIFIER,
    redirect_uri: str = REDIRECT_URI,
):
    return client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "code_verifier": verifier,
        },
    )


def refresh_token(
    client: TestClient,
    client_id: str,
    token: str,
    *,
    scope: str | None = None,
):
    data = {
        "grant_type": "refresh_token",
        "refresh_token": token,
        "client_id": client_id,
    }
    if scope is not None:
        data["scope"] = scope
    return client.post("/oauth/token", data=data)


def authorize_and_redeem(
    client: TestClient,
    client_id: str,
) -> dict[str, Any]:
    authorization = begin_authorization(client, client_id)
    assert authorization.status_code == 302
    upstream_state = parse_qs(urlsplit(authorization.headers["location"]).query)[
        "state"
    ][0]
    callback = complete_authorization(client, upstream_state)
    assert callback.status_code == 302
    local_code = local_code_from_redirect(callback.headers["location"])
    token = redeem_code(client, client_id, local_code)
    assert token.status_code == 200
    return token.json()


def test_authorization_code_flow_uses_separate_state_and_one_time_code(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "oauth.db"
    app, broker, validator = make_app(database_path)
    with TestClient(app) as client:
        client_id = register_client(client)
        authorization = begin_authorization(client, client_id)
        assert authorization.status_code == 302
        upstream_state = parse_qs(urlsplit(authorization.headers["location"]).query)[
            "state"
        ][0]
        assert upstream_state != "workbuddy-state"
        with sqlite3.connect(database_path) as connection:
            protected_flow = connection.execute(
                "SELECT protected_upstream_flow FROM oauth_transactions"
            ).fetchone()[0]
        callback = complete_authorization(client, upstream_state)
        assert callback.status_code == 302
        local_code = local_code_from_redirect(callback.headers["location"])
        with sqlite3.connect(database_path) as connection:
            protected = connection.execute(
                "SELECT encrypted_msal_cache FROM oauth_codes"
            ).fetchone()[0]

        token = redeem_code(client, client_id, local_code)
        replay = redeem_code(client, client_id, local_code)

    assert token.status_code == 200
    assert token.json()["access_token"] == "validated-token-a"
    assert token.json()["token_type"] == "Bearer"
    assert 1 <= token.json()["expires_in"] <= 3600
    assert token.json()["scope"] == "access_as_user"
    assert token.json()["refresh_token"]
    assert replay.status_code == 400
    assert replay.json()["error"] == "invalid_grant"
    assert broker.states == [upstream_state]
    assert validator.tokens == ["validated-token-a"]

    with sqlite3.connect(database_path) as connection:
        protected_session = connection.execute(
            "SELECT encrypted_msal_cache FROM oauth_sessions"
        ).fetchone()[0]
    assert b"validated-token-a" not in protected
    assert b"sensitive-msal-cache" not in protected
    assert b"sensitive-msal-cache" not in protected_session
    assert b"upstream-pkce" not in protected_flow


def test_wrong_pkce_or_client_does_not_consume_valid_code(tmp_path: Path) -> None:
    app, broker, _ = make_app(tmp_path / "oauth.db")
    with TestClient(app) as client:
        client_id = register_client(client)
        authorization = begin_authorization(client, client_id)
        upstream_state = parse_qs(urlsplit(authorization.headers["location"]).query)[
            "state"
        ][0]
        callback = complete_authorization(client, upstream_state)
        local_code = local_code_from_redirect(callback.headers["location"])

        wrong_pkce = redeem_code(client, client_id, local_code, verifier="x" * 64)
        wrong_client = redeem_code(client, "other-client", local_code)
        wrong_redirect = redeem_code(
            client,
            client_id,
            local_code,
            redirect_uri="https://client.example/wrong",
        )
        valid = redeem_code(client, client_id, local_code)

    assert wrong_pkce.status_code == 400
    assert wrong_pkce.json()["error"] == "invalid_grant"
    assert wrong_client.status_code == 400
    assert wrong_client.json()["error"] == "invalid_grant"
    assert wrong_redirect.status_code == 400
    assert wrong_redirect.json()["error"] == "invalid_grant"
    assert valid.status_code == 200
    assert len(broker.completed_flows) == 1


def test_new_authorization_reclaims_terminal_transaction_and_code_rows(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "oauth.db"
    app, _, _ = make_app(database_path)
    with TestClient(app) as client:
        client_id = register_client(client)
        first_authorization = begin_authorization(client, client_id)
        first_upstream_state = parse_qs(
            urlsplit(first_authorization.headers["location"]).query
        )["state"][0]
        first_callback = complete_authorization(client, first_upstream_state)
        first_local_code = local_code_from_redirect(
            first_callback.headers["location"]
        )
        assert redeem_code(client, client_id, first_local_code).status_code == 200

        second_authorization = begin_authorization(client, client_id)
        assert second_authorization.status_code == 302

    with sqlite3.connect(database_path) as connection:
        transactions = connection.execute(
            "SELECT completed_at FROM oauth_transactions"
        ).fetchall()
        code_count = connection.execute(
            "SELECT COUNT(*) FROM oauth_codes"
        ).fetchone()[0]

    assert transactions == [(None,)]
    assert code_count == 0


def test_authorize_rejects_unsafe_parameters_before_upstream_redirect(
    tmp_path: Path,
) -> None:
    app, broker, _ = make_app(tmp_path / "oauth.db")
    with TestClient(app) as client:
        client_id = register_client(client)
        responses = [
            begin_authorization(client, client_id, code_challenge_method="plain"),
            begin_authorization(client, client_id, code_challenge="malformed"),
            begin_authorization(client, client_id, scope="access_as_user extra"),
            begin_authorization(
                client,
                client_id,
                resource="https://evil.example/mcp/",
            ),
            begin_authorization(
                client,
                client_id,
                redirect_uri="https://evil.example/callback",
            ),
            begin_authorization(client, "unregistered-client"),
            begin_authorization(client, client_id, response_type="token"),
            client.get(
                "/oauth/authorize",
                params={
                    name: value
                    for name, value in authorization_parameters(client_id).items()
                    if name != "state"
                },
                follow_redirects=False,
            ),
            client.get(
                "/oauth/authorize",
                params={
                    name: value
                    for name, value in authorization_parameters(client_id).items()
                    if name != "code_challenge"
                },
                follow_redirects=False,
            ),
        ]

    assert all(response.status_code == 400 for response in responses)
    assert broker.states == []


def test_upstream_state_is_single_use(tmp_path: Path) -> None:
    app, _, _ = make_app(tmp_path / "oauth.db")
    with TestClient(app) as client:
        client_id = register_client(client)
        authorization = begin_authorization(client, client_id)
        upstream_state = parse_qs(urlsplit(authorization.headers["location"]).query)[
            "state"
        ][0]
        first = complete_authorization(client, upstream_state)
        replay = complete_authorization(client, upstream_state)

    assert first.status_code == 302
    assert replay.status_code == 400
    assert replay.json()["error"] == "invalid_request"


def test_expired_transaction_is_rejected(tmp_path: Path) -> None:
    database_path = tmp_path / "oauth.db"
    app, _, _ = make_app(database_path)
    with TestClient(app) as client:
        client_id = register_client(client)
        authorization = begin_authorization(client, client_id)
        upstream_state = parse_qs(
            urlsplit(authorization.headers["location"]).query
        )["state"][0]
        with sqlite3.connect(database_path) as connection:
            connection.execute("UPDATE oauth_transactions SET expires_at = 0")
        callback = complete_authorization(client, upstream_state)

    assert callback.status_code == 400
    assert callback.json()["error"] == "invalid_request"


def test_upstream_denial_returns_safe_error_to_registered_redirect(
    tmp_path: Path,
    caplog: Any,
) -> None:
    logger = logging.getLogger("test.oauth.denial.audit")
    app, broker, validator = make_app(
        tmp_path / "oauth.db",
        audit_logger=OAuthAuditLogger(logger),
    )
    with caplog.at_level(logging.INFO, logger=logger.name):
        with TestClient(app) as client:
            client_id = register_client(client)
            authorization = begin_authorization(client, client_id)
            upstream_state = parse_qs(
                urlsplit(authorization.headers["location"]).query
            )["state"][0]
            callback = client.get(
                "/oauth/callback/entra",
                params={
                    "error": "access_denied",
                    "error_description": "untrusted upstream text",
                    "state": upstream_state,
                },
                follow_redirects=False,
            )

    assert callback.status_code == 302
    query = parse_qs(urlsplit(callback.headers["location"]).query)
    assert query == {"error": ["access_denied"], "state": ["workbuddy-state"]}
    assert broker.completed_flows == []
    assert validator.tokens == []
    records = [record for record in caplog.records if record.name == logger.name]
    failure = records[-1]
    assert failure.event == "entra_authorization_failed"
    assert failure.client_id == client_id
    assert failure.error_type == "AccessDenied"
    assert "untrusted upstream text" not in caplog.text


def test_upstream_or_token_validation_failure_returns_safe_error(
    tmp_path: Path,
) -> None:
    cases = (
        (FailingBroker(), FakeValidator()),
        (FakeBroker(), RejectingValidator()),
    )
    for index, (broker, validator) in enumerate(cases):
        app, _, _ = make_app(
            tmp_path / f"oauth-{index}.db",
            broker=broker,
            validator=validator,
        )
        with TestClient(app) as client:
            client_id = register_client(client)
            authorization = begin_authorization(client, client_id)
            upstream_state = parse_qs(
                urlsplit(authorization.headers["location"]).query
            )["state"][0]
            callback = complete_authorization(client, upstream_state)

        assert callback.status_code == 302
        query = parse_qs(urlsplit(callback.headers["location"]).query)
        assert query == {
            "error": ["server_error"],
            "state": ["workbuddy-state"],
        }


def test_expired_or_unknown_authorization_code_is_rejected(tmp_path: Path) -> None:
    database_path = tmp_path / "oauth.db"
    app, _, _ = make_app(database_path)
    with TestClient(app) as client:
        client_id = register_client(client)
        authorization = begin_authorization(client, client_id)
        upstream_state = parse_qs(
            urlsplit(authorization.headers["location"]).query
        )["state"][0]
        callback = complete_authorization(client, upstream_state)
        local_code = local_code_from_redirect(callback.headers["location"])
        with sqlite3.connect(database_path) as connection:
            connection.execute("UPDATE oauth_codes SET expires_at = 0")
        expired = redeem_code(client, client_id, local_code)
        unknown = redeem_code(client, client_id, "unknown-code")

    assert expired.status_code == 400
    assert expired.json()["error"] == "invalid_grant"
    assert unknown.status_code == 400
    assert unknown.json()["error"] == "invalid_grant"


def test_corrupt_authorization_code_bundle_is_rejected(tmp_path: Path) -> None:
    database_path = tmp_path / "oauth.db"
    app, _, _ = make_app(database_path)
    with TestClient(app) as client:
        client_id = register_client(client)
        authorization = begin_authorization(client, client_id)
        upstream_state = parse_qs(
            urlsplit(authorization.headers["location"]).query
        )["state"][0]
        callback = complete_authorization(client, upstream_state)
        local_code = local_code_from_redirect(callback.headers["location"])
        with sqlite3.connect(database_path) as connection:
            connection.execute(
                "UPDATE oauth_codes SET encrypted_msal_cache = ?",
                (sqlite3.Binary(b"\x01" + b"0" * 29),),
            )
        response = redeem_code(client, client_id, local_code)

    assert response.status_code == 400
    assert response.json()["error"] == "invalid_grant"


def test_authorize_rejects_upstream_redirect_with_wrong_state(
    tmp_path: Path,
) -> None:
    broker = WrongStateRedirectBroker()
    app, _, _ = make_app(tmp_path / "oauth.db", broker=broker)
    with TestClient(app) as client:
        client_id = register_client(client)
        response = begin_authorization(client, client_id)

    assert response.status_code == 503
    assert response.json()["error"] == "temporarily_unavailable"


def test_token_endpoint_requires_form_encoding_and_rejects_duplicates(
    tmp_path: Path,
) -> None:
    app, _, _ = make_app(tmp_path / "oauth.db")
    with TestClient(app) as client:
        json_response = client.post(
            "/oauth/token",
            json={"grant_type": "authorization_code"},
        )
        duplicate_response = client.post(
            "/oauth/token",
            content="grant_type=authorization_code&grant_type=authorization_code",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    assert json_response.status_code == 400
    assert json_response.json()["error"] == "invalid_request"
    assert duplicate_response.status_code == 400
    assert duplicate_response.json()["error"] == "invalid_request"


def test_msal_broker_uses_separate_app_b_and_app_a_scope(tmp_path: Path) -> None:
    settings = make_settings(tmp_path / "oauth.db")
    created: list[dict[str, Any]] = []

    class FakeCache:
        def serialize(self) -> str:
            return "serialized-cache"

    class FakeApplication:
        def __init__(self, **kwargs: Any) -> None:
            created.append(kwargs)

        def initiate_auth_code_flow(
            self,
            scopes: list[str],
            redirect_uri: str | None = None,
            state: str | None = None,
            **kwargs: Any,
        ) -> dict[str, Any]:
            assert scopes == [f"api://{API_CLIENT_ID}/access_as_user"]
            assert redirect_uri == f"{ISSUER}/oauth/callback/entra"
            return {
                "auth_uri": f"https://login.microsoftonline.com/auth?state={state}",
                "state": state,
                "code_verifier": "upstream-verifier",
            }

        def acquire_token_by_auth_code_flow(
            self,
            auth_code_flow: dict[str, Any],
            auth_response: dict[str, str],
            scopes: list[str] | None = None,
            **kwargs: Any,
        ) -> dict[str, Any]:
            assert auth_code_flow["state"] == auth_response["state"]
            assert scopes == [f"api://{API_CLIENT_ID}/access_as_user"]
            return {"access_token": "token-a", "expires_in": 3210}

    broker = MsalEntraAuthorizationBroker(
        settings,
        application_factory=FakeApplication,
        cache_factory=FakeCache,
    )
    authorization = asyncio.run(broker.begin("upstream-state"))
    token = asyncio.run(
        broker.complete(
            authorization.flow,
            {"code": "entra-code", "state": "upstream-state"},
        )
    )

    assert token.access_token == "token-a"
    assert token.expires_in == 3210
    assert token.serialized_cache == "serialized-cache"
    assert len(created) == 2
    assert all(
        values["client_id"]
        == "33333333-3333-3333-3333-333333333333"
        for values in created
    )
    assert all(
        values["client_credential"] == "test-broker-secret"
        for values in created
    )
    assert all(
        values["authority"]
        == "https://login.microsoftonline.com/organizations"
        for values in created
    )


def test_oauth_enabled_fails_closed_without_broker_configuration(
    tmp_path: Path,
) -> None:
    settings = make_settings(
        tmp_path / "oauth.db",
        entra_broker_client_id=None,
        entra_broker_client_secret=None,
    )
    try:
        create_app(settings=settings, mail_service=object())
    except ConfigurationError as exc:
        assert "ENTRA_BROKER_CLIENT_ID" in str(exc)
        assert "ENTRA_BROKER_CLIENT_SECRET" in str(exc)
    else:
        raise AssertionError("OAuth must fail closed without App B configuration")


def test_sqlite_store_migrates_pr2_transaction_schema(tmp_path: Path) -> None:
    database_path = tmp_path / "oauth.db"
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE oauth_transactions (
                transaction_id_hash TEXT PRIMARY KEY,
                issuer TEXT NOT NULL,
                client_id TEXT NOT NULL,
                redirect_uri TEXT NOT NULL,
                workbuddy_state TEXT NOT NULL,
                entra_state_hash TEXT NOT NULL UNIQUE,
                code_challenge TEXT NOT NULL,
                scope TEXT NOT NULL,
                resource TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                completed_at INTEGER
            );
            PRAGMA user_version = 1;
            """
        )

    asyncio.run(SQLiteOAuthStore(database_path).initialize())

    with sqlite3.connect(database_path) as connection:
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(oauth_transactions)")
        }
        user_version = connection.execute("PRAGMA user_version").fetchone()[0]
    assert "protected_upstream_flow" in columns
    assert user_version == 3


def test_authorization_flow_emits_safe_audit_metadata(
    tmp_path: Path,
    caplog: Any,
) -> None:
    logger = logging.getLogger("test.oauth.authorization.audit")
    audit_logger = OAuthAuditLogger(logger)
    app, _, _ = make_app(
        tmp_path / "oauth.db",
        audit_logger=audit_logger,
    )

    with caplog.at_level(logging.INFO, logger=logger.name):
        with TestClient(app) as client:
            client_id = register_client(client)
            authorization = begin_authorization(client, client_id)
            upstream_state = parse_qs(
                urlsplit(authorization.headers["location"]).query
            )["state"][0]
            callback = complete_authorization(client, upstream_state)
            local_code = local_code_from_redirect(callback.headers["location"])
            token = redeem_code(client, client_id, local_code)

    assert token.status_code == 200
    records = [record for record in caplog.records if record.name == logger.name]
    assert [record.event for record in records] == [
        "oauth_client_registered",
        "oauth_authorization_started",
        "entra_authorization_succeeded",
        "oauth_code_redeemed",
    ]
    assert all(record.client_id == client_id for record in records)
    assert records[2].tenant_id == TENANT_ID
    assert records[2].user_id == "44444444-4444-4444-4444-444444444444"
    for secret in (
        "workbuddy-state",
        upstream_state,
        VERIFIER,
        pkce_challenge(),
        local_code,
        "validated-token-a",
        "sensitive-msal-cache",
        token.json()["refresh_token"],
    ):
        assert secret not in caplog.text


def test_refresh_succeeds_rotates_and_rejects_old_token_replay(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "oauth.db"
    app, broker, validator = make_app(database_path)
    with TestClient(app) as client:
        client_id = register_client(client)
        initial = authorize_and_redeem(client, client_id)
        old_refresh_token = initial["refresh_token"]

        refreshed = refresh_token(client, client_id, old_refresh_token)
        replay = refresh_token(client, client_id, old_refresh_token)
        second_refresh = refresh_token(
            client,
            client_id,
            refreshed.json()["refresh_token"],
            scope="access_as_user",
        )

    assert refreshed.status_code == 200
    assert refreshed.json()["access_token"] == "refreshed-token-1"
    assert refreshed.json()["expires_in"] == 3300
    assert refreshed.json()["refresh_token"] != old_refresh_token
    assert replay.status_code == 400
    assert replay.json()["error"] == "invalid_grant"
    assert second_refresh.status_code == 200
    assert broker.refreshed_caches == [
        "sensitive-msal-cache",
        "refreshed-cache-1",
    ]
    assert validator.tokens == [
        "validated-token-a",
        "refreshed-token-1",
        "refreshed-token-2",
    ]

    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            "SELECT refresh_token_hash, encrypted_msal_cache, rotation_family "
            "FROM oauth_sessions"
        ).fetchone()
    assert row is not None
    assert row[0] == hashlib.sha256(
        second_refresh.json()["refresh_token"].encode("utf-8")
    ).hexdigest()
    assert old_refresh_token.encode("utf-8") not in row[1]
    assert b"refreshed-cache" not in row[1]
    assert row[2]


def test_wrong_client_or_scope_does_not_consume_refresh_token(
    tmp_path: Path,
) -> None:
    app, _, _ = make_app(tmp_path / "oauth.db")
    with TestClient(app) as client:
        client_id = register_client(client)
        initial = authorize_and_redeem(client, client_id)
        local_refresh_token = initial["refresh_token"]

        wrong_client = refresh_token(client, "other-client", local_refresh_token)
        wrong_scope = refresh_token(
            client,
            client_id,
            local_refresh_token,
            scope="access_as_user extra",
        )
        valid = refresh_token(client, client_id, local_refresh_token)

    assert wrong_client.status_code == 400
    assert wrong_client.json()["error"] == "invalid_grant"
    assert wrong_scope.status_code == 400
    assert wrong_scope.json()["error"] == "invalid_scope"
    assert valid.status_code == 200


def test_expired_and_revoked_refresh_sessions_are_rejected(tmp_path: Path) -> None:
    database_path = tmp_path / "oauth.db"
    app, _, _ = make_app(database_path)
    with TestClient(app) as client:
        client_id = register_client(client)
        expired_token = authorize_and_redeem(client, client_id)["refresh_token"]
        with sqlite3.connect(database_path) as connection:
            connection.execute("UPDATE oauth_sessions SET expires_at = 0")
        expired = refresh_token(client, client_id, expired_token)

        revoked_token = authorize_and_redeem(client, client_id)["refresh_token"]
        with sqlite3.connect(database_path) as connection:
            connection.execute(
                "UPDATE oauth_sessions SET revoked_at = 1 "
                "WHERE refresh_token_hash = ?",
                (hashlib.sha256(revoked_token.encode("utf-8")).hexdigest(),),
            )
        revoked = refresh_token(client, client_id, revoked_token)

    assert expired.status_code == 400
    assert expired.json()["error"] == "invalid_grant"
    assert revoked.status_code == 400
    assert revoked.json()["error"] == "invalid_grant"


def test_corrupt_encrypted_cache_revokes_session(tmp_path: Path) -> None:
    database_path = tmp_path / "oauth.db"
    app, _, _ = make_app(database_path)
    with TestClient(app) as client:
        client_id = register_client(client)
        local_refresh_token = authorize_and_redeem(client, client_id)[
            "refresh_token"
        ]
        with sqlite3.connect(database_path) as connection:
            connection.execute(
                "UPDATE oauth_sessions SET encrypted_msal_cache = ?",
                (sqlite3.Binary(b"\x01" + b"0" * 29),),
            )
        response = refresh_token(client, client_id, local_refresh_token)

    assert response.status_code == 400
    assert response.json()["error"] == "invalid_grant"
    with sqlite3.connect(database_path) as connection:
        revoked_at = connection.execute(
            "SELECT revoked_at FROM oauth_sessions"
        ).fetchone()[0]
    assert revoked_at is not None


def test_transient_msal_refresh_failure_keeps_current_token_retryable(
    tmp_path: Path,
) -> None:
    broker = RefreshFailingBroker()
    app, _, _ = make_app(tmp_path / "oauth.db", broker=broker)
    with TestClient(app) as client:
        client_id = register_client(client)
        local_refresh_token = authorize_and_redeem(client, client_id)[
            "refresh_token"
        ]
        unavailable = refresh_token(client, client_id, local_refresh_token)
        broker.fail_refresh = False
        retried = refresh_token(client, client_id, local_refresh_token)

    assert unavailable.status_code == 503
    assert unavailable.json()["error"] == "temporarily_unavailable"
    assert retried.status_code == 200


def test_microsoft_revocation_revokes_local_session(tmp_path: Path) -> None:
    database_path = tmp_path / "oauth.db"
    app, _, _ = make_app(database_path, broker=RevokedRefreshBroker())
    with TestClient(app) as client:
        client_id = register_client(client)
        local_refresh_token = authorize_and_redeem(client, client_id)[
            "refresh_token"
        ]
        response = refresh_token(client, client_id, local_refresh_token)
        replay = refresh_token(client, client_id, local_refresh_token)

    assert response.status_code == 400
    assert response.json()["error"] == "invalid_grant"
    assert replay.status_code == 400
    with sqlite3.connect(database_path) as connection:
        revoked_at = connection.execute(
            "SELECT revoked_at FROM oauth_sessions"
        ).fetchone()[0]
    assert revoked_at is not None


def test_refresh_identity_mismatch_revokes_local_session(tmp_path: Path) -> None:
    database_path = tmp_path / "oauth.db"
    app, _, _ = make_app(
        database_path,
        validator=MismatchedRefreshValidator(),
    )
    with TestClient(app) as client:
        client_id = register_client(client)
        local_refresh_token = authorize_and_redeem(client, client_id)[
            "refresh_token"
        ]
        response = refresh_token(client, client_id, local_refresh_token)

    assert response.status_code == 400
    assert response.json()["error"] == "invalid_grant"
    with sqlite3.connect(database_path) as connection:
        revoked_at = connection.execute(
            "SELECT revoked_at FROM oauth_sessions"
        ).fetchone()[0]
    assert revoked_at is not None


def test_refresh_audit_contains_metadata_but_no_token_material(
    tmp_path: Path,
    caplog: Any,
) -> None:
    logger = logging.getLogger("test.oauth.refresh.audit")
    audit_logger = OAuthAuditLogger(logger)
    app, _, _ = make_app(
        tmp_path / "oauth.db",
        audit_logger=audit_logger,
    )
    with caplog.at_level(logging.INFO, logger=logger.name):
        with TestClient(app) as client:
            client_id = register_client(client)
            initial = authorize_and_redeem(client, client_id)
            refreshed = refresh_token(
                client,
                client_id,
                initial["refresh_token"],
            )

    assert refreshed.status_code == 200
    records = [record for record in caplog.records if record.name == logger.name]
    assert records[-1].event == "oauth_refresh_succeeded"
    assert records[-1].client_id == client_id
    assert records[-1].tenant_id == TENANT_ID
    for secret in (
        initial["access_token"],
        initial["refresh_token"],
        refreshed.json()["access_token"],
        refreshed.json()["refresh_token"],
        "sensitive-msal-cache",
        "refreshed-cache-1",
    ):
        assert secret not in caplog.text


def test_refresh_session_survives_application_restart(tmp_path: Path) -> None:
    database_path = tmp_path / "oauth.db"
    first_app, _, _ = make_app(database_path)
    with TestClient(first_app) as first_client:
        client_id = register_client(first_client)
        local_refresh_token = authorize_and_redeem(first_client, client_id)[
            "refresh_token"
        ]

    restarted_app, restarted_broker, _ = make_app(database_path)
    with TestClient(restarted_app) as restarted_client:
        response = refresh_token(
            restarted_client,
            client_id,
            local_refresh_token,
        )

    assert response.status_code == 200
    assert restarted_broker.refreshed_caches == ["sensitive-msal-cache"]


def test_concurrent_refresh_allows_only_one_rotation(tmp_path: Path) -> None:
    class ConcurrentBroker(FakeBroker):
        def __init__(self) -> None:
            super().__init__()
            self.barrier = Barrier(2)

        async def refresh(self, serialized_cache: str) -> UpstreamTokenResult:
            await asyncio.to_thread(self.barrier.wait, 10)
            return await super().refresh(serialized_cache)

    database_path = tmp_path / "oauth.db"
    broker = ConcurrentBroker()
    first_app, _, _ = make_app(database_path, broker=broker)
    second_app, _, _ = make_app(database_path, broker=broker)
    with TestClient(first_app) as first_client, TestClient(second_app) as second_client:
        client_id = register_client(first_client)
        local_refresh_token = authorize_and_redeem(first_client, client_id)[
            "refresh_token"
        ]
        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(
                refresh_token,
                first_client,
                client_id,
                local_refresh_token,
            )
            second = executor.submit(
                refresh_token,
                second_client,
                client_id,
                local_refresh_token,
            )
            responses = [first.result(timeout=20), second.result(timeout=20)]

    assert sorted(response.status_code for response in responses) == [200, 400]
    assert [
        response.json()["error"]
        for response in responses
        if response.status_code == 400
    ] == ["invalid_grant"]


def test_oauth_enabled_requires_valid_persistent_encryption_key(
    tmp_path: Path,
) -> None:
    for value in (None, "not-base64", base64.b64encode(b"short").decode("ascii")):
        settings = make_settings(
            tmp_path / f"oauth-{value is None}.db",
            oauth_encryption_key=value,
        )
        try:
            create_app(settings=settings, mail_service=object())
        except ConfigurationError as exc:
            assert "OAUTH_ENCRYPTION_KEY" in str(exc)
        else:
            raise AssertionError("OAuth must fail closed without a valid AEAD key")


def test_msal_broker_restores_cache_and_forces_silent_refresh(
    tmp_path: Path,
) -> None:
    settings = make_settings(tmp_path / "oauth.db")
    calls: list[dict[str, Any]] = []

    class RefreshCache:
        def __init__(self) -> None:
            self.serialized = ""

        def deserialize(self, value: str) -> None:
            self.serialized = value

        def serialize(self) -> str:
            return "updated-cache"

    class RefreshApplication:
        def __init__(self, **kwargs: Any) -> None:
            calls.append(kwargs)

        def get_accounts(self, **kwargs: Any) -> list[dict[str, Any]]:
            return [{"home_account_id": "account"}]

        def acquire_token_silent_with_error(
            self,
            scopes: list[str],
            account: dict[str, Any] | None = None,
            **kwargs: Any,
        ) -> dict[str, Any]:
            assert scopes == [f"api://{API_CLIENT_ID}/access_as_user"]
            assert account == {"home_account_id": "account"}
            assert kwargs["force_refresh"] is True
            return {"access_token": "refreshed-token", "expires_in": 2700}

    broker = MsalEntraAuthorizationBroker(
        settings,
        application_factory=RefreshApplication,
        cache_factory=RefreshCache,
    )
    result = asyncio.run(broker.refresh("persisted-cache"))

    assert result.access_token == "refreshed-token"
    assert result.expires_in == 2700
    assert result.serialized_cache == "updated-cache"
    assert len(calls) == 1


def test_msal_broker_distinguishes_reauth_from_transient_refresh_error(
    tmp_path: Path,
) -> None:
    settings = make_settings(tmp_path / "oauth.db")

    class ErrorCache:
        def deserialize(self, value: str) -> None:
            assert value == "persisted-cache"

        def serialize(self) -> str:
            return "unchanged-cache"

    class ErrorApplication:
        next_error = "invalid_grant"

        def __init__(self, **kwargs: Any) -> None:
            pass

        def get_accounts(self, **kwargs: Any) -> list[dict[str, Any]]:
            return [{"home_account_id": "account"}]

        def acquire_token_silent_with_error(
            self,
            scopes: list[str],
            account: dict[str, Any] | None = None,
            **kwargs: Any,
        ) -> dict[str, Any]:
            return {"error": self.next_error}

    broker = MsalEntraAuthorizationBroker(
        settings,
        application_factory=ErrorApplication,
        cache_factory=ErrorCache,
    )
    try:
        asyncio.run(broker.refresh("persisted-cache"))
    except EntraRefreshRejectedError:
        pass
    else:
        raise AssertionError("invalid_grant must require interactive authorization")

    ErrorApplication.next_error = "temporarily_unavailable"
    try:
        asyncio.run(broker.refresh("persisted-cache"))
    except EntraBrokerError as exc:
        assert not isinstance(exc, EntraRefreshRejectedError)
    else:
        raise AssertionError("transient errors must remain retryable")
