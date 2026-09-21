import asyncio
from typing import Any

import pytest
from fastmcp import Client, FastMCP

from m365_mcp.auth import AuthContext, UserIdentity
from m365_mcp.errors import InvalidToolInputError
from m365_mcp.graph.client import GraphResponse
from m365_mcp.graph.mail import MailService
from m365_mcp.mail import MailToolService, register_mail_tools
from m365_mcp.security import untrusted_content_metadata


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


class StubGraphClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def request(self, context: AuthContext, method: str, path: str, **kwargs: Any) -> GraphResponse:
        self.calls.append(
            {"context": context, "method": method, "path": path, **kwargs}
        )
        return GraphResponse(
            status_code=200,
            data={"value": []},
            request_id=None,
            headers={},
        )


def test_mail_search_builds_agent_friendly_graph_query() -> None:
    graph = StubGraphClient()
    service = MailService(graph)  # type: ignore[arg-type]

    asyncio.run(
        service.search_messages(
            make_context(),
            query='quarterly "results"',
            limit=10,
            date_from="2026-01-01T00:00:00Z",
            date_to="2026-01-31T23:59:59Z",
        )
    )

    call = graph.calls[0]
    assert call["path"] == "/me/messages"
    assert call["params"]["$top"] == 10
    assert call["params"]["$search"] == (
        '"(quarterly  results) AND received>=2026-01-01T00:00:00Z'
        ' AND received<=2026-01-31T23:59:59Z"'
    )
    assert "$filter" not in call["params"]
    assert "$orderby" not in call["params"]


def test_mail_tool_service_omits_attachment_bytes() -> None:
    class StubMailService:
        async def list_attachments(
            self, context: AuthContext, message_id: str
        ) -> GraphResponse:
            return GraphResponse(
                status_code=200,
                data={
                    "value": [
                        {
                            "id": "attachment-1",
                            "name": "report.txt",
                            "contentBytes": "large-base64-payload",
                        }
                    ],
                    "@odata.nextLink": "https://example.invalid/next",
                },
                request_id=None,
                headers={},
            )

    service = MailToolService(StubMailService())  # type: ignore[arg-type]

    result = asyncio.run(service.list_attachments(make_context(), "message-1"))

    assert result == {
        "attachments": [
            {
                "id": "attachment-1",
                "name": "report.txt",
                "has_content": True,
            }
        ],
        "next_link": "https://example.invalid/next",
    }


def test_registered_mail_tools_accept_an_injected_context_without_http() -> None:
    expected_context = make_context()
    received_contexts: list[AuthContext] = []

    class StubMailService:
        async def get_message(
            self, context: AuthContext, message_id: str
        ) -> GraphResponse:
            received_contexts.append(context)
            return GraphResponse(
                status_code=200,
                data={"id": message_id},
                request_id=None,
                headers={},
            )

    mcp = FastMCP("Local mail tools")
    register_mail_tools(
        mcp,
        MailToolService(StubMailService()),  # type: ignore[arg-type]
        context_provider=lambda: expected_context,
    )

    async def exercise() -> Any:
        async with Client(mcp) as client:
            result = await client.call_tool(
                "mail_get", {"message_id": "message-1"}
            )
            return result.data

    assert asyncio.run(exercise()) == {
        "message": {"id": "message-1"},
        "content_metadata": untrusted_content_metadata("email_message"),
    }
    assert received_contexts == [expected_context]


@pytest.mark.parametrize(
    "kwargs, param, code",
    [
        ({"date_from": "not-a-date"}, "date_from", "invalid_date_format"),
        ({"date_to": "2026-01-01"}, "date_to", "missing_timezone"),
        ({"limit": 0}, "limit", "out_of_range"),
        ({"limit": 500}, "limit", "out_of_range"),
        ({"query": "x" * 2049}, "query", "too_long"),
        (
            {
                "date_from": "2026-02-01T00:00:00Z",
                "date_to": "2026-01-01T00:00:00Z",
            },
            "date_from",
            "invalid_range",
        ),
    ],
)
def test_search_validation_echoes_param_and_code(
    kwargs: dict[str, Any], param: str, code: str
) -> None:
    graph = StubGraphClient()
    service = MailService(graph)  # type: ignore[arg-type]

    with pytest.raises(InvalidToolInputError) as raised:
        asyncio.run(service.search_messages(make_context(), **kwargs))

    assert raised.value.param == param
    assert raised.value.code == code
    assert isinstance(raised.value, ValueError)
    # Validation must fail before any Graph request is attempted.
    assert graph.calls == []
