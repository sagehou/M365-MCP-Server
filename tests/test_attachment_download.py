from fastapi import FastAPI
from fastapi.testclient import TestClient

from m365_mcp.mail import (
    AttachmentDownloadStore,
    DownloadPayload,
    create_attachment_download_router,
)


def test_download_ticket_is_short_lived_and_single_use() -> None:
    now = [100.0]
    store = AttachmentDownloadStore(
        ttl_seconds=60,
        max_items=2,
        max_total_bytes=100,
        clock=lambda: now[0],
        token_factory=lambda: "a" * 43,
    )

    ticket = store.issue(DownloadPayload("notes.txt", "text/plain", b"hello"))

    assert ticket.token == "a" * 43
    assert ticket.expires_in_seconds == 60
    assert store.consume(ticket.token) == DownloadPayload(
        "notes.txt", "text/plain", b"hello"
    )
    assert store.consume(ticket.token) is None


def test_download_store_expires_and_evicts_bounded_payloads() -> None:
    now = [100.0]
    tokens = iter(("a" * 43, "b" * 43, "c" * 43))
    store = AttachmentDownloadStore(
        ttl_seconds=30,
        max_items=1,
        max_total_bytes=5,
        clock=lambda: now[0],
        token_factory=lambda: next(tokens),
    )

    first = store.issue(DownloadPayload("one.bin", None, b"1234"))
    second = store.issue(DownloadPayload("two.bin", None, b"5678"))

    assert store.consume(first.token) is None
    now[0] += 31
    assert store.consume(second.token) is None


def test_download_route_returns_bytes_with_safe_headers_once() -> None:
    store = AttachmentDownloadStore(
        ttl_seconds=60,
        max_items=2,
        max_total_bytes=100,
        token_factory=lambda: "d" * 43,
    )
    ticket = store.issue(
        DownloadPayload(
            filename="../résumé\r\n.txt",
            content_type="text/plain; charset=utf-8",
            content=b"downloaded",
        )
    )
    app = FastAPI()
    app.include_router(create_attachment_download_router(store))

    with TestClient(app) as client:
        response = client.get(f"/downloads/{ticket.token}")
        repeated = client.get(f"/downloads/{ticket.token}")

    assert response.status_code == 200
    assert response.content == b"downloaded"
    assert response.headers["content-type"] == "text/plain; charset=utf-8"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["content-disposition"].startswith("attachment;")
    assert "\r" not in response.headers["content-disposition"]
    assert "\n" not in response.headers["content-disposition"]
    assert repeated.status_code == 404


def test_invalid_download_token_does_not_reach_store() -> None:
    store = AttachmentDownloadStore(
        ttl_seconds=60,
        max_items=2,
        max_total_bytes=100,
    )
    app = FastAPI()
    app.include_router(create_attachment_download_router(store))

    with TestClient(app) as client:
        response = client.get("/downloads/not-a-valid-token")

    assert response.status_code == 404
