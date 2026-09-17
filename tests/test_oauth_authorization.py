import asyncio
import base64
import hashlib
import logging
from pathlib import Path
import sqlite3
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
from m365_mcp.oauth.crypto import EphemeralTokenProtector
from m365_mcp.oauth.entra import EntraBrokerError, MsalEntraAuthorizationBroker
from m365_mcp.oauth.models import UpstreamAuthorization, UpstreamTokenResult
from m365_mcp.oauth.registry import DynamicClientRegistry
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
    }
    values.update(overrides)
    return Settings(**values)


class FakeBroker:
    def __init__(self) -> None:
        self.states: list[str] = []
        self.completed_flows: list[dict[str, Any]] = []

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
    service = OAuthAuthorizationService(
        settings,
        registry,
        store,
        selected_broker,
        selected_validator,
        EphemeralTokenProtector(key=b"k" * 32),
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
        callback = complete_authorization(client, upstream_state)
        assert callback.status_code == 302
        local_code = local_code_from_redirect(callback.headers["location"])

        token = redeem_code(client, client_id, local_code)
        replay = redeem_code(client, client_id, local_code)

    assert token.status_code == 200
    assert token.json()["access_token"] == "validated-token-a"
    assert token.json()["token_type"] == "Bearer"
    assert 1 <= token.json()["expires_in"] <= 3600
    assert token.json()["scope"] == "access_as_user"
    assert "refresh_token" not in token.json()
    assert replay.status_code == 400
    assert replay.json()["error"] == "invalid_grant"
    assert broker.states == [upstream_state]
    assert validator.tokens == ["validated-token-a"]

    with sqlite3.connect(database_path) as connection:
        protected = connection.execute(
            "SELECT encrypted_msal_cache FROM oauth_codes"
        ).fetchone()[0]
        protected_flow = connection.execute(
            "SELECT protected_upstream_flow FROM oauth_transactions"
        ).fetchone()[0]
    assert b"validated-token-a" not in protected
    assert b"sensitive-msal-cache" not in protected
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
    assert user_version == 2


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
    ):
        assert secret not in caplog.text
