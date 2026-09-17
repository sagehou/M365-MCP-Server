import asyncio
from typing import Any

import httpx
import pytest

from m365_mcp.auth import AuthContext, Settings, UserIdentity
from m365_mcp.graph import (
    GraphApiError,
    GraphClient,
    GraphPathError,
    MailService,
)


TENANT_ID = "00000000-0000-0000-0000-000000000001"


def make_context() -> AuthContext:
    return AuthContext(
        identity=UserIdentity(
            tenant_id=TENANT_ID,
            user_id="user-1",
            subject="subject-1",
            issuer="https://login.microsoftonline.com/tenant/v2.0",
            audience="api://client",
            scopes=frozenset({"access_as_user"}),
        ),
        access_token="inbound-token",
    )


class StubObo:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def acquire_graph_token(self, *, user_assertion: str, tenant_id: str) -> str:
        self.calls.append(
            {"user_assertion": user_assertion, "tenant_id": tenant_id}
        )
        return "graph-token"


def make_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "graph_max_retries": 2,
        "graph_retry_backoff_seconds": 0,
        "graph_max_retry_delay_seconds": 1,
    }
    values.update(overrides)
    return Settings(**values)


def test_graph_client_honors_retry_after_and_uses_delegated_token() -> None:
    attempts: list[httpx.Request] = []
    responses = [
        httpx.Response(
            429,
            headers={"Retry-After": "0"},
            json={"error": {"code": "TooManyRequests"}},
        ),
        httpx.Response(
            200,
            headers={"request-id": "request-1"},
            json={"value": []},
        ),
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(request)
        return responses.pop(0)

    sleeps: list[float] = []

    async def sleeper(delay: float) -> None:
        sleeps.append(delay)

    obo = StubObo()

    async def exercise() -> Any:
        http_client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
        )
        graph = GraphClient(
            make_settings(),
            obo,  # type: ignore[arg-type]
            http_client=http_client,
            sleeper=sleeper,
        )
        try:
            return await graph.request(make_context(), "GET", "/me/messages")
        finally:
            await http_client.aclose()

    response = asyncio.run(exercise())

    assert response.status_code == 200
    assert response.data == {"value": []}
    assert len(attempts) == 2
    assert attempts[0].url.path == "/v1.0/me/messages"
    assert attempts[0].headers["authorization"] == "Bearer graph-token"
    assert obo.calls == [
        {"user_assertion": "inbound-token", "tenant_id": TENANT_ID}
    ]
    assert sleeps == [0.0]


def test_graph_client_rejects_arbitrary_user_paths() -> None:
    obo = StubObo()

    async def exercise() -> None:
        http_client = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200)))
        graph = GraphClient(make_settings(), obo, http_client=http_client)  # type: ignore[arg-type]
        try:
            with pytest.raises(GraphPathError):
                await graph.request(make_context(), "GET", "/users/user-1/messages")
        finally:
            await http_client.aclose()

    asyncio.run(exercise())
    assert obo.calls == []


def test_graph_error_does_not_expose_response_message() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            headers={"request-id": "request-2"},
            json={
                "error": {
                    "code": "ErrorAccessDenied",
                    "message": "mail body must not appear in an exception",
                }
            },
        )

    async def exercise() -> None:
        http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        graph = GraphClient(make_settings(), StubObo(), http_client=http_client)  # type: ignore[arg-type]
        try:
            with pytest.raises(GraphApiError) as error:
                await graph.request(make_context(), "GET", "/me/messages/message-1")
        finally:
            await http_client.aclose()
        assert error.value.status_code == 403
        assert error.value.code == "ErrorAccessDenied"
        assert error.value.request_id == "request-2"
        assert "mail body" not in str(error.value)

    asyncio.run(exercise())


def test_mail_service_encodes_resource_ids_and_stays_on_me() -> None:
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.raw_path.decode())
        return httpx.Response(200, json={"id": "message-1"})

    async def exercise() -> None:
        http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        graph = GraphClient(make_settings(), StubObo(), http_client=http_client)  # type: ignore[arg-type]
        try:
            service = MailService(graph)
            response = await service.get_message(
                make_context(),
                "id/with secret",
            )
            assert response.data == {"id": "message-1"}
        finally:
            await http_client.aclose()

    asyncio.run(exercise())
    assert paths == ["/v1.0/me/messages/id%2Fwith%20secret"]
