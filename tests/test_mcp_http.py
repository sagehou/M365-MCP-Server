"""Exercise the real Streamable HTTP mount, not a direct tool function call."""

import asyncio
import json
from dataclasses import replace

import httpx

from m365_mcp.app import create_app
from m365_mcp.auth import Settings
from m365_mcp.graph import GraphClient, MailService
from test_graph import make_context


def test_http_initialize_list_and_concurrent_users_call_with_own_assertions():
    calls = []
    class Validator:
        async def validate(self, token):
            return replace(make_context().identity, user_id=token, subject=token)
    class Obo:
        def acquire_graph_token(self, *, user_assertion, tenant_id):
            return "graph-" + user_assertion
    async def handler(request):
        await asyncio.sleep(0)
        calls.append((request.headers["authorization"], request.url.path))
        if request.url.path.endswith("/failure"):
            raise RuntimeError("SECRET_PROVIDER_BODY")
        return httpx.Response(200, json={"id": request.headers["authorization"]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as graph_http:
            graph = GraphClient(Settings(), Obo(), http_client=graph_http)
            app = create_app(settings=Settings(), token_validator=Validator(), mail_service=MailService(graph))
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
                    results = await asyncio.gather(*[
                        rpc(user, "tools/call", {"name": "mail_get", "arguments": {"message_id": "id"}})
                        for user in ("alice", "bob")
                    ])
                    for user, result in zip(("alice", "bob"), results):
                        assert not result.get("isError")
                        payload = json.loads(result["content"][0]["text"])
                        assert payload["message"]["id"] == "Bearer graph-" + user
                    failure = await rpc("alice", "tools/call", {
                        "name": "mail_get", "arguments": {"message_id": "failure"}})
                    assert failure["isError"]
                    assert "SECRET_PROVIDER_BODY" not in json.dumps(failure)
                    missing = await client.post("/mcp/", json={})
                    assert missing.status_code == 401
    asyncio.run(exercise())
    assert ("Bearer graph-alice", "/v1.0/me/messages/id") in calls
    assert ("Bearer graph-bob", "/v1.0/me/messages/id") in calls
