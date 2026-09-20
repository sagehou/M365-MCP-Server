import asyncio
import json
import logging
from typing import Any

import pytest

from m365_mcp.auth import AuthContext, OboTokenError, UserIdentity
from m365_mcp.security import AuditLogger, SecurityHeadersMiddleware
from m365_mcp.security.audit import AuditJsonFormatter


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
        access_token="inbound-token-must-not-be-logged",
    )


def test_audit_logger_records_identity_without_operation_payload(caplog: Any) -> None:
    logger = logging.getLogger("test.audit.success")
    audit = AuditLogger(logger)

    async def operation(context: AuthContext) -> dict[str, str]:
        assert context.identity.user_id == "user-1"
        return {"body": "email body must not be logged"}

    with caplog.at_level(logging.INFO, logger=logger.name):
        result = asyncio.run(audit.invoke(make_context(), "mail_get", operation))

    assert result["body"] == "email body must not be logged"
    record = caplog.records[-1]
    assert record.event == "mcp_tool_invocation"
    assert record.tenant_id == TENANT_ID
    assert record.user_id == "user-1"
    assert record.tool_name == "mail_get"
    assert record.outcome == "success"
    assert "email body" not in caplog.text
    assert "inbound-token" not in caplog.text


def test_audit_logger_records_safe_failure_type_only(caplog: Any) -> None:
    logger = logging.getLogger("test.audit.failure")
    audit = AuditLogger(logger)

    async def operation(context: AuthContext) -> None:
        raise ValueError("attachment bytes must not be logged")

    with caplog.at_level(logging.INFO, logger=logger.name):
        with pytest.raises(ValueError):
            asyncio.run(audit.invoke(make_context(), "mail_read_attachment", operation))

    record = caplog.records[-1]
    assert record.outcome == "error"
    assert record.error_type == "ValueError"
    assert "attachment bytes" not in caplog.text


def test_audit_logger_records_safe_obo_failure_classification(caplog: Any) -> None:
    logger = logging.getLogger("test.audit.obo_failure")
    audit = AuditLogger(logger)
    correlation_id = "11111111-2222-3333-4444-555555555555"

    async def operation(context: AuthContext) -> None:
        raise OboTokenError.from_msal_result(
            {
                "error": "invalid_grant",
                "suberror": "consent_required",
                "error_codes": [65001],
                "correlation_id": correlation_id,
                "error_description": "sensitive provider detail",
            }
        )

    with caplog.at_level(logging.INFO, logger=logger.name):
        with pytest.raises(OboTokenError):
            asyncio.run(audit.invoke(make_context(), "mail_search", operation))

    record = caplog.records[-1]
    assert record.error_type == "OboTokenError"
    assert record.entra_error == "invalid_grant"
    assert record.entra_suberror == "consent_required"
    assert record.entra_error_code == 65001
    assert record.correlation_id == correlation_id
    formatted = json.loads(AuditJsonFormatter().format(record))
    assert formatted["entra_error"] == "invalid_grant"
    assert formatted["entra_suberror"] == "consent_required"
    assert formatted["entra_error_code"] == 65001
    assert formatted["correlation_id"] == correlation_id
    assert "sensitive provider detail" not in caplog.text
    assert "inbound-token" not in caplog.text


def test_audit_logger_records_attachment_size_mismatch_without_identifiers(
    caplog: Any,
) -> None:
    logger = logging.getLogger("test.audit.attachment_size_mismatch")
    audit = AuditLogger(logger)

    with caplog.at_level(logging.WARNING, logger=logger.name):
        audit.attachment_size_mismatch(
            make_context(),
            "mail_download_attachment",
            provider_size=42_710,
            content_size=42_326,
            graph_request_id="graph-request-1",
        )

    record = caplog.records[-1]
    assert record.event == "attachment_size_mismatch"
    assert record.outcome == "warning"
    assert record.provider_size == 42_710
    assert record.content_size == 42_326
    assert record.graph_request_id == "graph-request-1"
    formatted = json.loads(AuditJsonFormatter().format(record))
    assert formatted["provider_size"] == 42_710
    assert formatted["content_size"] == 42_326
    assert formatted["graph_request_id"] == "graph-request-1"
    assert "attachment-1" not in caplog.text
    assert "implementation-plan.md" not in caplog.text
    assert "inbound-token" not in caplog.text


def test_security_headers_are_added_to_http_responses() -> None:
    messages: list[dict[str, Any]] = []

    async def downstream(scope: Any, receive: Any, send: Any) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send({"type": "http.response.body", "body": b"{}"})

    async def send(message: dict[str, Any]) -> None:
        messages.append(message)

    asyncio.run(
        SecurityHeadersMiddleware(downstream)(
            {"type": "http"},
            None,
            send,
        )
    )

    headers = dict(messages[0]["headers"])
    assert headers[b"cache-control"] == b"no-store"
    assert headers[b"content-security-policy"] == (
        b"default-src 'none'; frame-ancestors 'none'"
    )
    assert headers[b"x-content-type-options"] == b"nosniff"
    assert headers[b"x-frame-options"] == b"DENY"
