"""Regression coverage for deployment, transport and authentication review gaps."""

import asyncio
import gzip
import io
import json
import logging
import threading
import time

import httpx
import pytest
from pydantic import ValidationError

from m365_mcp.auth import Settings, TokenValidationError
from m365_mcp.auth.errors import ConfigurationError
from m365_mcp.auth.oidc import OidcDocumentProvider
from m365_mcp.auth.validator import JwtValidator
from m365_mcp.graph import GraphApiError, GraphClient, GraphPathError, MailService
from m365_mcp.graph.errors import GraphTransportError
from m365_mcp.graph.client import GraphResponse
from m365_mcp.mail import MailToolService
from m365_mcp.security.audit import AuditLogger, AuditJsonFormatter
from test_auth import make_settings, make_token, make_validator
from test_graph import StubObo, make_context


@pytest.mark.parametrize("credential", ["secret", "certificate"])
def test_env_template_empty_alternate_credential(tmp_path, credential):
    path = tmp_path / ".env"
    path.write_text(
        "CLIENT_ID=client\nALLOWED_TENANTS=tenant\nAUDIENCE=api://client\n"
        + ("CLIENT_SECRET=secret\nCLIENT_CERT_PATH=\nCLIENT_CERT_THUMBPRINT=\n"
           if credential == "secret" else
           "CLIENT_SECRET=\nCLIENT_CERT_PATH=/run/secrets/key.pem\nCLIENT_CERT_THUMBPRINT=abc\n"),
        encoding="utf-8",
    )
    settings = Settings(_env_file=path)
    settings.validate_auth_configuration()
    assert (settings.client_secret is None) == (credential == "certificate")
    assert (settings.client_cert_path is None) == (credential == "secret")


@pytest.mark.parametrize("field,value", [
    ("graph_max_retries", -1), ("graph_max_retries", 6),
    ("http_timeout_seconds", 0), ("graph_max_response_bytes", 0),
    ("attachment_max_bytes", -1), ("attachment_max_text_chars", 0),
    ("graph_retry_backoff_seconds", float("nan")),
])
def test_configuration_rejects_invalid_limits(field, value):
    with pytest.raises(ValidationError):
        Settings(**{field: value})


def test_download_capacity_covers_one_maximum_attachment():
    with pytest.raises(ValidationError):
        Settings(
            attachment_max_bytes=1024,
            attachment_download_max_total_bytes=512,
        )


def test_required_scope_cannot_be_disabled():
    with pytest.raises(ConfigurationError):
        make_settings(required_scopes=[]).validate_auth_configuration()


@pytest.mark.parametrize("claims", [
    {"aud": "https://graph.microsoft.com"},
    {"exp": int(time.time()) - 1000},
    {"iss": "https://attacker.invalid/"},
    {"scp": None, "roles": ["Mail.ReadWrite"]},
])
def test_auth_negative_claims(claims):
    token, documents = make_token(claims_override=claims)
    with pytest.raises(TokenValidationError):
        asyncio.run(make_validator(documents).validate(token))


def test_wrong_signature_rejected():
    token, _ = make_token()
    _, documents = make_token()
    with pytest.raises(TokenValidationError):
        asyncio.run(make_validator(documents).validate(token))


def test_jwks_rollover_refreshes_once_and_rate_limits_unknown_keys():
    old_token, old = make_token(kid="old")
    new_token, new = make_token(kid="new")
    unknown, _ = make_token(kid="unknown")
    settings = make_settings()
    calls = []

    async def fetch(url):
        if url == settings.discovery_url:
            return old["configuration"]
        calls.append(url)
        return old["jwks"] if len(calls) == 1 else new["jwks"]

    async def exercise():
        validator = JwtValidator(settings, OidcDocumentProvider(settings, fetcher=fetch))
        await validator.validate(old_token)
        await validator.validate(new_token)
        for _ in range(5):
            with pytest.raises(TokenValidationError):
                await validator.validate(unknown)
    asyncio.run(exercise())
    assert len(calls) == 2


@pytest.mark.parametrize("failure", ["timeout", "503"])
def test_move_is_not_replayed_after_ambiguous_failure(failure):
    calls = []
    def handler(request):
        calls.append(request)
        if failure == "timeout":
            raise httpx.ReadTimeout("sensitive provider detail", request=request)
        return httpx.Response(503)

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            graph = GraphClient(Settings(), StubObo(), http_client=client)
            with pytest.raises((GraphTransportError, GraphApiError)):
                await graph.request(make_context(), "POST", "/me/messages/id/move")
    asyncio.run(exercise())
    assert len(calls) == 1


def test_retry_after_beyond_budget_is_returned_without_early_retry():
    calls, sleeps = [], []
    def handler(request):
        calls.append(request)
        return httpx.Response(429, headers={"Retry-After": "90"})
    async def sleep(delay):
        sleeps.append(delay)
    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            graph = GraphClient(Settings(), StubObo(), http_client=client, sleeper=sleep)
            with pytest.raises(GraphApiError) as error:
                await graph.request(make_context(), "GET", "/me/messages")
            assert error.value.retry_after == 90
    asyncio.run(exercise())
    assert len(calls) == 1
    assert sleeps == []


def test_streaming_response_limit_and_compressed_success():
    class Chunks(httpx.AsyncByteStream):
        consumed = 0
        async def __aiter__(self):
            for _ in range(100):
                self.consumed += 1
                yield b"x" * 16
    stream = Chunks()
    responses = [
        httpx.Response(200, content=gzip.compress(b'{"value":[]}'),
                       headers={"Content-Encoding": "gzip"}),
        httpx.Response(200, stream=stream),
    ]
    async def exercise():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda request: responses.pop(0))
        ) as client:
            graph = GraphClient(Settings(graph_max_response_bytes=32), StubObo(), http_client=client)
            assert (await graph.request(make_context(), "GET", "/me/messages")).data == {"value": []}
            with pytest.raises(GraphTransportError):
                await graph.request(make_context(), "GET", "/me/messages")
    asyncio.run(exercise())
    assert stream.consumed == 3


@pytest.mark.parametrize("path", [
    "/me/../users/id", "/me/%2e%2e/users/id", "/me/messages?secret=value",
    "/me/messages#fragment", "https://graph.microsoft.com/v1.0/me",
])
def test_graph_rejects_noncanonical_paths_before_obo(path):
    obo = StubObo()
    async def exercise():
        async with GraphClient(Settings(), obo) as graph:
            with pytest.raises(GraphPathError):
                await graph.request(make_context(), "GET", path)
    asyncio.run(exercise())
    assert obo.calls == []


def test_obo_runs_outside_the_event_loop_thread():
    event_thread = threading.get_ident()
    class ThreadCheckedObo(StubObo):
        def acquire_token(self, context):
            assert threading.get_ident() != event_thread
            return super().acquire_token(context)
    async def exercise():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json={}))
        ) as client:
            await GraphClient(Settings(), ThreadCheckedObo(), http_client=client).request(
                make_context(), "GET", "/me/messages"
            )
    asyncio.run(exercise())


def test_search_without_keywords_uses_odata_and_validates_range():
    from test_mail import StubGraphClient
    graph = StubGraphClient()
    service = MailService(graph)
    asyncio.run(service.search_messages(make_context(), date_from="2026-01-01T08:00:00+08:00"))
    assert graph.calls[0]["params"]["$filter"] == "receivedDateTime ge 2026-01-01T00:00:00Z"
    assert "$search" not in graph.calls[0]["params"]
    with pytest.raises(ValueError):
        asyncio.run(service.search_messages(
            make_context(), date_from="2026-02-01T00:00:00Z", date_to="2026-01-01T00:00:00Z"))
    assert len(graph.calls) == 1


@pytest.mark.parametrize("operation", ["archive", "move"])
def test_move_returns_destination_identifier(operation):
    class Mail:
        async def move_message(self, *args, **kwargs):
            return GraphResponse(201, {"id": "new-id"}, None, {})
        archive_message = move_message
    service = MailToolService(Mail())
    args = [make_context(), "old-id"] + (["folder-id"] if operation == "move" else [])
    result = asyncio.run(getattr(service, operation)(*args))
    assert result["message_id"] == "new-id"
    assert result["source_message_id"] == "old-id"


def test_attachment_listing_requests_metadata_only():
    from test_mail import StubGraphClient
    graph = StubGraphClient()
    asyncio.run(MailService(graph).list_attachments(make_context(), "message-id"))
    assert graph.calls[0]["params"]["$select"] == "id,name,contentType,size,isInline,lastModifiedDateTime"
    with pytest.raises(ValueError):
        asyncio.run(MailService(graph).get_message(make_context(), ".."))


def test_default_audit_emits_parseable_json_even_when_root_is_warning():
    audit = AuditLogger()
    handler = audit.logger.handlers[0]
    original_stream = handler.stream
    stream = io.StringIO()
    root = logging.getLogger()
    original_level = root.level
    async def operation(context):
        return {"body": "SECRET_BODY"}
    try:
        root.setLevel(logging.WARNING)
        handler.setStream(stream)
        asyncio.run(audit.invoke(make_context(), "mail_get", operation))
    finally:
        handler.setStream(original_stream)
        root.setLevel(original_level)
    record = json.loads(stream.getvalue())
    assert record["timestamp"]
    assert record["user_id"] == "user-1"
    assert record["outcome"] == "success"
    assert "SECRET_BODY" not in stream.getvalue()
    assert "inbound-token" not in stream.getvalue()
