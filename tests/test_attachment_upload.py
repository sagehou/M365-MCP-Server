import asyncio
import hashlib
from dataclasses import replace

import httpx

import pytest

from m365_mcp.auth import AuthContext
from m365_mcp.auth import Settings
from m365_mcp.app import create_app
from m365_mcp.graph.mail import MailService
from m365_mcp.mail.uploads import (
    AttachmentUploadStore,
    StagedAttachment,
    validate_attachment_name,
)
from test_mail import StubGraphClient, make_context


def test_upload_handle_is_one_use_expiring_and_bound_to_user() -> None:
    clock = [0.0]
    store = AttachmentUploadStore(ttl_seconds=5, clock=lambda: clock[0])
    alice = make_context()
    bob = AuthContext(
        identity=replace(alice.identity, user_id="other-user"),
        access_token="other-token",
    )
    payload = StagedAttachment("report.txt", "text/plain", b"hello")
    handle = store.issue(alice, payload)
    assert store.consume(bob, handle) is None
    assert store.consume(alice, handle) == payload
    assert store.consume(alice, handle) is None
    expired = store.issue(alice, payload)
    clock[0] = 5.0
    assert store.consume(alice, expired) is None


def test_upload_store_rejects_invalid_files_and_bounds_capacity() -> None:
    context = make_context()
    store = AttachmentUploadStore(max_items=1, max_total_bytes=10)
    for name in ("../secret.txt", "a/b.txt", "a\x00.txt"):
        with pytest.raises(ValueError):
            validate_attachment_name(name)
    with pytest.raises(ValueError):
        store.issue(context, StagedAttachment("empty.txt", "text/plain", b""))
    with pytest.raises(ValueError):
        store.issue(context, StagedAttachment("big.txt", "text/plain", b"x" * (20 * 1024 * 1024 + 1)))
    store.issue(context, StagedAttachment("one.txt", "text/plain", b"one"))
    with pytest.raises(OverflowError):
        store.issue(context, StagedAttachment("two.txt", "text/plain", b"two"))
    store.clear()
    store.issue(context, StagedAttachment("three.txt", "text/plain", b"three"))


def test_push_grant_binds_exact_content_user_and_draft() -> None:
    clock = [0.0]
    store = AttachmentUploadStore(ttl_seconds=5, clock=lambda: clock[0])
    alice = make_context()
    bob = AuthContext(
        identity=replace(alice.identity, user_id="other-user"),
        access_token="other-token",
    )
    content = b"report bytes"
    sha256 = hashlib.sha256(content).hexdigest()
    handle = store.issue_push_grant(
        alice, "draft-1", "report.docx", "application/octet-stream",
        len(content), sha256,
    )
    assert store.push_grant_size(handle) == len(content)
    with pytest.raises(ValueError):
        store.complete_push_grant(handle, b"wrong bytes!")
    assert store.push_grant_size(handle) == len(content)
    assert store.complete_push_grant(handle, content) == StagedAttachment(
        "report.docx", "application/octet-stream", content
    )
    assert store.complete_push_grant(handle, content) is None
    assert store.consume(bob, handle, "draft-1") is None
    assert store.consume(alice, handle, "draft-2") is None
    assert store.consume(alice, handle, "draft-1") is not None
    assert store.consume(alice, handle, "draft-1") is None
    expired = store.issue_push_grant(
        alice, "draft-1", "report.docx", "application/octet-stream",
        len(content), sha256,
    )
    clock[0] = 5.0
    assert store.push_grant_size(expired) is None


def test_binary_upload_route_rejects_bad_input_and_enforces_capacity() -> None:
    class Validator:
        async def validate(self, token: str):
            return replace(make_context().identity, user_id=token, subject=token)

    async def exercise() -> None:
        store = AttachmentUploadStore(max_items=1)
        app = create_app(
            settings=Settings(),
            token_validator=Validator(),
            mail_service=MailService(StubGraphClient()),  # type: ignore[arg-type]
            attachment_upload_store=store,
        )
        headers = {
            "Authorization": "Bearer alice",
            "Content-Type": "application/octet-stream",
            "X-Attachment-Name": "r%C3%A9sum%C3%A9.txt",
        }
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                url = "/uploads/attachments"
                assert (await client.post(url, content=b"x")).status_code == 401
                assert (await client.post(url, headers={
                    **headers, "Content-Type": "text/plain"
                }, content=b"x")).status_code == 415
                assert (await client.post(url, headers={
                    **headers, "X-Attachment-Content-Type": "not-a-mime-type"
                }, content=b"x")).status_code == 400
                for name in ("%FF", "..%2Fsecret.txt", "bad%00name.txt"):
                    assert (await client.post(url, headers={
                        **headers, "X-Attachment-Name": name
                    }, content=b"x")).status_code == 400
                assert (await client.post(url, headers=headers, content=b"")).status_code == 400
                oversized = await client.post(url, headers={
                    **headers, "Content-Length": str(20 * 1024 * 1024 + 1)
                }, content=b"x")
                assert oversized.status_code == 413
                async def oversized_stream():
                    yield b"x" * (20 * 1024 * 1024)
                    yield b"x"
                streamed = await client.post(url, headers=headers, content=oversized_stream())
                assert streamed.status_code == 413
                uploaded = await client.post(url, headers=headers, content=b"hello")
                assert uploaded.status_code == 201
                assert uploaded.headers["cache-control"] == "no-store"
                assert uploaded.json()["name"] == "résumé.txt"
                assert uploaded.json()["content_length"] == 5
                assert (await client.post(url, headers=headers, content=b"again")).status_code == 429

    asyncio.run(exercise())


def test_push_route_accepts_only_matching_one_use_grant() -> None:
    async def exercise() -> None:
        store = AttachmentUploadStore()
        app = create_app(
            settings=Settings(),
            mail_service=MailService(StubGraphClient()),  # type: ignore[arg-type]
            attachment_upload_store=store,
        )
        content = b"report bytes"
        handle = store.issue_push_grant(
            make_context(), "draft-1", "report.docx", "application/octet-stream",
            len(content), hashlib.sha256(content).hexdigest(),
        )
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                url = "/uploads/push"
                headers = {
                    "X-Upload-Handle": handle,
                    "Content-Type": "application/octet-stream",
                }
                assert (await client.post(url, content=content)).status_code == 404
                assert (await client.post(url, headers=headers, content=b"wrong bytes!")).status_code == 400
                assert (await client.post(url, headers=headers, content=content + b"x")).status_code == 400
                uploaded = await client.post(url, headers=headers, content=content)
                assert uploaded.status_code == 201
                assert uploaded.headers["cache-control"] == "no-store"
                assert uploaded.json()["content_sha256"] == hashlib.sha256(content).hexdigest()
                assert (await client.post(url, headers=headers, content=content)).status_code == 404
                assert store.consume(make_context(), handle, "other-draft") is None
                assert store.consume(make_context(), handle, "draft-1") is not None

    asyncio.run(exercise())
