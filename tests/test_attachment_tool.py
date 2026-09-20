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
from m365_mcp.mail import AttachmentDownloadStore, MailToolService
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


def test_mail_read_attachment_extracts_markdown() -> None:
    payload = b"# Incident notes\n\nAttachment body"
    service_stub = StubMailService(
        {
            "@odata.type": "#microsoft.graph.fileAttachment",
            "id": "attachment-1",
            "name": "notes.md",
            "contentType": "text/markdown; charset=utf-8",
            "size": len(payload),
            "contentBytes": base64.b64encode(payload).decode("ascii"),
        }
    )
    service = MailToolService(service_stub)  # type: ignore[arg-type]

    result = asyncio.run(service.read_attachment(make_context(), "message-1", "attachment-1"))

    assert result["attachment"]["format"] == "markdown"
    assert result["content"] == "# Incident notes\n\nAttachment body"


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


def test_mail_download_attachment_returns_ticket_without_file_bytes() -> None:
    payload = b"original attachment bytes"
    service_stub = StubMailService(
        {
            "@odata.type": "#microsoft.graph.fileAttachment",
            "id": "attachment-1",
            "name": "archive.bin",
            "contentType": "application/octet-stream",
            "size": len(payload),
            "contentBytes": base64.b64encode(payload).decode("ascii"),
        }
    )
    store = AttachmentDownloadStore(
        ttl_seconds=300,
        max_items=2,
        max_total_bytes=1024,
        token_factory=lambda: "e" * 43,
    )
    service = MailToolService(
        service_stub,  # type: ignore[arg-type]
        attachment_download_store=store,
        attachment_download_url_prefix="https://mcp.example.com/downloads",
    )

    result = asyncio.run(
        service.download_attachment(make_context(), "message-1", "attachment-1")
    )
    retained = store.consume("e" * 43)

    assert service_stub.calls == [("message-1", "attachment-1")]
    assert result == {
        "attachment": {
            "id": "attachment-1",
            "name": "archive.bin",
            "content_type": "application/octet-stream",
            "size": len(payload),
        },
        "download_url": "https://mcp.example.com/downloads/" + "e" * 43,
        "expires_in_seconds": 300,
        "single_use": True,
    }
    assert retained is not None
    assert retained.content == payload
    assert "content" not in result
    assert "contentBytes" not in result


def test_attachment_tools_distinguish_actual_and_graph_reported_size() -> None:
    payload = b"x" * 42_326
    reported_size = 42_710
    attachment = {
        "@odata.type": "#microsoft.graph.fileAttachment",
        "id": "attachment-1",
        "name": "implementation-plan.md",
        "contentType": "text/markdown; charset=utf-8",
        "size": reported_size,
        "contentBytes": base64.b64encode(payload).decode("ascii"),
    }

    class SizeMismatchMailService(StubMailService):
        async def list_attachments(
            self,
            context: AuthContext,
            message_id: str,
        ) -> GraphResponse:
            return GraphResponse(
                status_code=200,
                data={"value": [self.data]},
                request_id=None,
                headers={},
            )

    service_stub = SizeMismatchMailService(attachment)
    store = AttachmentDownloadStore(
        ttl_seconds=300,
        max_items=2,
        max_total_bytes=100_000,
        token_factory=lambda: "f" * 43,
    )
    service = MailToolService(
        service_stub,  # type: ignore[arg-type]
        attachment_download_store=store,
        attachment_download_url_prefix="https://mcp.example.com/downloads",
    )

    listed = asyncio.run(service.list_attachments(make_context(), "message-1"))
    downloaded = asyncio.run(
        service.download_attachment(make_context(), "message-1", "attachment-1")
    )

    assert listed["attachments"][0]["size"] == len(payload)
    assert listed["attachments"][0]["reported_size"] == reported_size
    assert downloaded["attachment"]["size"] == len(payload)
    assert downloaded["attachment"]["reported_size"] == reported_size

