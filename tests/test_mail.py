import asyncio
from typing import Any

from m365_mcp.auth import AuthContext, UserIdentity
from m365_mcp.graph.client import GraphResponse
from m365_mcp.graph.mail import MailService
from m365_mcp.mail import MailToolService


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
