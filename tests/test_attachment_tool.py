import asyncio
import base64
from typing import Any

import pytest

from m365_mcp.auth import AuthContext, UserIdentity
from m365_mcp.extractors import (
    AttachmentExtractorRegistry,
    AttachmentTooLargeError,
    UnsupportedAttachmentError,
)
from m365_mcp.graph.client import GraphResponse
from m365_mcp.mail import MailToolService
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


class StubMailService:
    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data
        self.calls: list[tuple[str, str]] = []

    async def get_attachment(
        self,
        context: AuthContext,
        message_id: str,
        attachment_id: str,
    ) -> GraphResponse:
        self.calls.append((message_id, attachment_id))
        return GraphResponse(
            status_code=200,
            data=self.data,
            request_id=None,
            headers={},
        )


def test_mail_read_attachment_extracts_text_without_returning_base64() -> None:
    payload = b"hello from attachment"
    service_stub = StubMailService(
        {
            "@odata.type": "#microsoft.graph.fileAttachment",
            "id": "attachment-1",
            "name": "notes.txt",
            "contentType": "text/plain",
            "size": len(payload),
            "contentBytes": base64.b64encode(payload).decode("ascii"),
        }
    )
    service = MailToolService(service_stub)  # type: ignore[arg-type]

    result = asyncio.run(service.read_attachment(make_context(), "message-1", "attachment-1"))

    assert service_stub.calls == [("message-1", "attachment-1")]
    assert result == {
        "attachment": {
            "id": "attachment-1",
            "name": "notes.txt",
            "content_type": "text/plain",
            "size": len(payload),
            "format": "txt",
            "truncated": False,
        },
        "content": "hello from attachment",
        "content_metadata": untrusted_content_metadata("email_attachment"),
    }
    assert "contentBytes" not in result


def test_mail_read_attachment_rejects_item_attachments() -> None:
    service_stub = StubMailService(
        {
            "@odata.type": "#microsoft.graph.itemAttachment",
            "id": "attachment-1",
            "name": "nested-message.eml",
        }
    )
    service = MailToolService(service_stub)  # type: ignore[arg-type]

    with pytest.raises(UnsupportedAttachmentError):
        asyncio.run(service.read_attachment(make_context(), "message-1", "attachment-1"))


def test_mail_read_attachment_uses_configured_size_limit() -> None:
    payload = b"12345"
    service_stub = StubMailService(
        {
            "id": "attachment-1",
            "name": "notes.txt",
            "contentBytes": base64.b64encode(payload).decode("ascii"),
        }
    )
    service = MailToolService(
        service_stub,  # type: ignore[arg-type]
        attachment_extractor=AttachmentExtractorRegistry(max_bytes=4),
    )

    with pytest.raises(AttachmentTooLargeError):
        asyncio.run(service.read_attachment(make_context(), "message-1", "attachment-1"))

