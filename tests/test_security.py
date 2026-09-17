import asyncio
import logging
from typing import Any

import pytest

from m365_mcp.auth import AuthContext, UserIdentity
from m365_mcp.security import AuditLogger, SecurityHeadersMiddleware


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
