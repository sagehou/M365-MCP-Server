"""Exercise the real Streamable HTTP mount, not a direct tool function call."""

import asyncio
import base64
import json
import logging
import re
from dataclasses import replace

import httpx

from m365_mcp.app import create_app
from m365_mcp.auth import Settings
from m365_mcp.graph import GraphClient, MailService
from m365_mcp.security import AuditLogger
from test_graph import make_context


def test_http_initialize_list_and_concurrent_users_call_with_own_assertions(capfd, caplog):
    calls = []
    writes = []
    failure_refs = []
    audit_log = logging.getLogger("test.mcp_http.audit")
    audit_log.setLevel(logging.INFO)
    class Validator:
        async def validate(self, token):
            return replace(make_context().identity, user_id=token, subject=token)
    class Obo:
        def acquire_token(self, context):
            return "graph-" + context.access_token
    async def handler(request):
        await asyncio.sleep(0)
        calls.append((request.headers["authorization"], request.url.path))
        if request.url.path.endswith("/failure"):
            raise RuntimeError("SECRET_PROVIDER_BODY")
        if request.method in {"POST", "PATCH"}:
            writes.append((request.method, request.url.path, json.loads(request.content)))
        if request.url.path.endswith("/attachments/attachment"):
            return httpx.Response(200, json={
                "@odata.type": "#microsoft.graph.fileAttachment", "id": "attachment",
                "name": "notes.txt", "size": 5,
                "contentBytes": base64.b64encode(b"hello").decode(),
            })
        if request.url.path.endswith("/attachments"):
            return httpx.Response(200, json={"value": [{"id": "attachment", "name": "notes.txt"}]})
        if request.url.path == "/v1.0/me/messages":
            assert "$search" in request.url.params
            assert "$filter" not in request.url.params and "$orderby" not in request.url.params
            return httpx.Response(200, json={"value": [{"id": "id", "subject": "test"}]})
        if request.url.path.endswith("/move"):
            return httpx.Response(201, json={"id": "moved-id"})
        return httpx.Response(200, json={"id": request.headers["authorization"]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as graph_http:
            graph = GraphClient(Settings(), Obo(), http_client=graph_http)
            app = create_app(
                settings=Settings(),
                token_validator=Validator(),
                mail_service=MailService(graph),
                audit_logger=AuditLogger(audit_log),
            )
            async with app.router.lifespan_context(app):
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app), base_url="http://test"
                ) as client:
                    async def rpc(token, method, params):
                        response = await client.post("/mcp/", headers={
                            "Authorization": "Bearer " + token,
                            "Accept": "application/json, text/event-stream",
                            "MCP-Protocol-Version": "2025-03-26",
                        }, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
                        assert response.status_code == 200, response.text
                        assert "mcp-session-id" not in response.headers
                        return response.json()["result"]
                    initialized = await rpc("alice", "initialize", {
                        "protocolVersion": "2025-03-26", "capabilities": {},
                        "clientInfo": {"name": "ci-regression", "version": "1"},
                    })
                    assert initialized["serverInfo"]["name"] == "M365 MCP Server"
                    listed = await rpc("alice", "tools/list", {})
                    assert {tool["name"] for tool in listed["tools"]} == {
                        "mail_search", "mail_get", "mail_list_attachments", "mail_read_attachment",
                        "mail_mark_read", "mail_archive", "mail_move", "mail_set_category",
                    }
                    search_schema = next(
                        tool["inputSchema"]["properties"]
                        for tool in listed["tools"]
                        if tool["name"] == "mail_search"
                    )
                    assert search_schema["date_from"].get("format") == "date-time"
                    assert search_schema["date_to"].get("format") == "date-time"
                    results = await asyncio.gather(*[
                        rpc(user, "tools/call", {"name": "mail_get", "arguments": {"message_id": "id"}})
                        for user in ("alice", "bob")
                    ])
                    for user, result in zip(("alice", "bob"), results):
                        assert not result.get("isError")
                        payload = json.loads(result["content"][0]["text"])
                        assert payload["message"]["id"] == "Bearer graph-" + user
                    cases = [
                        ("mail_search", {"query": "test"}, "messages"),
                        ("mail_list_attachments", {"message_id": "id"}, "attachments"),
                        ("mail_read_attachment", {"message_id": "id", "attachment_id": "attachment"}, "content"),
                        ("mail_mark_read", {"message_id": "id", "is_read": False}, "is_read"),
                        ("mail_archive", {"message_id": "id"}, "archived"),
                        ("mail_move", {"message_id": "id", "destination_folder_id": "folder"}, "destination_folder_id"),
                        ("mail_set_category", {"message_id": "id", "categories": ["Reviewed"]}, "categories"),
                    ]
                    for name, arguments, field in cases:
                        result = await rpc("alice", "tools/call", {"name": name, "arguments": arguments})
                        assert not result.get("isError"), result
                        payload = json.loads(result["content"][0]["text"])
                        assert field in payload
                        if name in {"mail_archive", "mail_move"}:
                            assert payload["message_id"] == "moved-id"
                        if name == "mail_read_attachment":
                            assert payload["content"] == "hello"
                    bad_date = await rpc("alice", "tools/call", {
                        "name": "mail_search",
                        "arguments": {"query": "test", "date_from": "2026-13-45"},
                    })
                    assert bad_date["isError"]
                    bad_text = json.dumps(bad_date)
                    assert "date_from" in bad_text
                    assert "invalid_date_format" in bad_text
                    assert "consult the audit event" not in bad_text
                    failure = await rpc("alice", "tools/call", {
                        "name": "mail_get", "arguments": {"message_id": "failure"}})
                    assert failure["isError"]
                    failure_text = json.dumps(failure)
                    assert "SECRET_PROVIDER_BODY" not in failure_text
                    assert "consult the audit event" in failure_text
                    match = re.search(r"\(ref ([0-9a-f]{16})\)", failure_text)
                    assert match is not None
                    failure_refs.append(match.group(1))
                    assert "verify mailbox state before retrying" not in failure_text
                    write_failure = await rpc("alice", "tools/call", {
                        "name": "mail_mark_read",
                        "arguments": {"message_id": "failure", "is_read": True},
                    })
                    assert write_failure["isError"]
                    assert "Verify mailbox state before retrying" in json.dumps(write_failure)
                    missing = await client.post("/mcp/", json={})
                    assert missing.status_code == 401

                    modern_meta = {
                        "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                        "io.modelcontextprotocol/clientCapabilities": {},
                        "io.modelcontextprotocol/clientInfo": {
                            "name": "ci-modern-regression",
                            "version": "1",
                        },
                    }

                    async def modern_rpc(token, method, params, name=None):
                        headers = {
                            "Authorization": "Bearer " + token,
                            "Accept": "application/json, text/event-stream",
                            "MCP-Protocol-Version": "2026-07-28",
                            "Mcp-Method": method,
                        }
                        if name is not None:
                            headers["Mcp-Name"] = name
                        response = await client.post(
                            "/mcp/",
                            headers=headers,
                            json={"jsonrpc": "2.0", "id": 2, "method": method, "params": params},
                        )
                        assert response.status_code == 200, response.text
                        assert "mcp-session-id" not in response.headers
                        return response.json()["result"]

                    discovered = await modern_rpc(
                        "alice", "server/discover", {"_meta": modern_meta}
                    )
                    assert discovered["resultType"] == "complete"
                    assert "2026-07-28" in discovered["supportedVersions"]
                    modern_tools = await modern_rpc(
                        "alice", "tools/list", {"_meta": modern_meta}
                    )
                    assert len(modern_tools["tools"]) == 8
                    modern_result = await modern_rpc(
                        "bob",
                        "tools/call",
                        {"name": "mail_get", "arguments": {"message_id": "id"}, "_meta": modern_meta},
                        name="mail_get",
                    )
                    assert not modern_result.get("isError")
                    modern_payload = json.loads(modern_result["content"][0]["text"])
                    assert modern_payload["message"]["id"] == "Bearer graph-bob"
    asyncio.run(exercise())
    assert len(failure_refs) == 1
    matching_audit_records = [
        record
        for record in caplog.records
        if getattr(record, "event_id", None) == failure_refs[0]
    ]
    assert len(matching_audit_records) == 1
    assert matching_audit_records[0].event == "mcp_tool_invocation"
    assert matching_audit_records[0].outcome == "error"
    assert matching_audit_records[0].tool_name == "mail_get"
    assert ("Bearer graph-alice", "/v1.0/me/messages/id") in calls
    assert ("Bearer graph-bob", "/v1.0/me/messages/id") in calls
    assert writes == [
        ("PATCH", "/v1.0/me/messages/id", {"isRead": False}),
        ("POST", "/v1.0/me/messages/id/move", {"destinationId": "archive"}),
        ("POST", "/v1.0/me/messages/id/move", {"destinationId": "folder"}),
        ("PATCH", "/v1.0/me/messages/id", {"categories": ["Reviewed"]}),
    ]
    captured = capfd.readouterr()
    assert "SECRET_PROVIDER_BODY" not in captured.out + captured.err + caplog.text
