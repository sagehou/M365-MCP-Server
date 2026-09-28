from dataclasses import replace

import pytest

from m365_mcp.auth import AuthContext
from m365_mcp.mail.uploads import (
    AttachmentUploadStore,
    StagedAttachment,
    validate_attachment_name,
)
from test_mail import make_context


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
