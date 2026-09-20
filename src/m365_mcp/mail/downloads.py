"""Short-lived capability URLs for bounded attachment downloads."""

from __future__ import annotations

import asyncio
import hashlib
import re
import secrets
import time
from collections import OrderedDict
from contextlib import suppress
from dataclasses import dataclass
from threading import Lock
from typing import Callable
from urllib.parse import quote

from fastapi import APIRouter, HTTPException
from starlette.responses import Response


_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]{43}")
_MEDIA_TYPE_PATTERN = re.compile(
    r"[A-Za-z0-9!#$&^_.+-]+/[A-Za-z0-9!#$&^_.+-]+"
)


@dataclass(frozen=True, slots=True)
class DownloadPayload:
    """Attachment bytes and response metadata retained until download."""

    filename: str
    content_type: str | None
    content: bytes


@dataclass(frozen=True, slots=True)
class DownloadTicket:
    """Opaque single-use ticket returned to the mail tool."""

    token: str
    expires_in_seconds: int


@dataclass(frozen=True, slots=True)
class _StoredDownload:
    payload: DownloadPayload
    expires_at: float


class AttachmentDownloadStore:
    """Keep bounded attachment bytes behind opaque, expiring, single-use tokens."""

    def __init__(
        self,
        *,
        ttl_seconds: int,
        max_items: int,
        max_total_bytes: int,
        clock: Callable[[], float] = time.monotonic,
        token_factory: Callable[[], str] | None = None,
    ) -> None:
        if ttl_seconds <= 0 or max_items <= 0 or max_total_bytes <= 0:
            raise ValueError("Download store limits must be positive")
        self.ttl_seconds = ttl_seconds
        self.max_items = max_items
        self.max_total_bytes = max_total_bytes
        self._clock = clock
        self._token_factory = token_factory or (lambda: secrets.token_urlsafe(32))
        self._entries: OrderedDict[bytes, _StoredDownload] = OrderedDict()
        self._total_bytes = 0
        self._lock = Lock()
        self._cleanup_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start periodic expiry cleanup for unclaimed downloads."""

        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(
                self._cleanup_loop(), name="attachment-download-cleanup"
            )

    async def aclose(self) -> None:
        """Stop cleanup and release every retained attachment byte."""

        task = self._cleanup_task
        self._cleanup_task = None
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        with self._lock:
            self._entries.clear()
            self._total_bytes = 0

    def issue(self, payload: DownloadPayload) -> DownloadTicket:
        """Retain one payload and return a cryptographically random capability."""

        payload_size = len(payload.content)
        if payload_size > self.max_total_bytes:
            raise ValueError("Attachment exceeds temporary download capacity")
        with self._lock:
            now = self._clock()
            self._prune_locked(now)
            while self._entries and (
                len(self._entries) >= self.max_items
                or self._total_bytes + payload_size > self.max_total_bytes
            ):
                self._remove_oldest_locked()

            for _ in range(5):
                token = self._token_factory()
                if _TOKEN_PATTERN.fullmatch(token) is None:
                    raise RuntimeError("Download token generator returned an invalid token")
                token_hash = self._token_hash(token)
                if token_hash not in self._entries:
                    break
            else:
                raise RuntimeError("Could not allocate a unique download token")

            self._entries[token_hash] = _StoredDownload(
                payload=payload,
                expires_at=now + self.ttl_seconds,
            )
            self._total_bytes += payload_size
        return DownloadTicket(token=token, expires_in_seconds=self.ttl_seconds)

    def consume(self, token: str) -> DownloadPayload | None:
        """Atomically redeem one valid ticket; invalid and expired tickets look absent."""

        if _TOKEN_PATTERN.fullmatch(token) is None:
            return None
        with self._lock:
            now = self._clock()
            self._prune_locked(now)
            entry = self._entries.pop(self._token_hash(token), None)
            if entry is None:
                return None
            self._total_bytes -= len(entry.payload.content)
            if entry.expires_at <= now:
                return None
            return entry.payload

    def purge_expired(self) -> None:
        with self._lock:
            self._prune_locked(self._clock())

    async def _cleanup_loop(self) -> None:
        interval = min(60.0, max(1.0, self.ttl_seconds / 2))
        while True:
            await asyncio.sleep(interval)
            self.purge_expired()

    def _prune_locked(self, now: float) -> None:
        while self._entries:
            _, entry = next(iter(self._entries.items()))
            if entry.expires_at > now:
                break
            self._remove_oldest_locked()

    def _remove_oldest_locked(self) -> None:
        _, entry = self._entries.popitem(last=False)
        self._total_bytes -= len(entry.payload.content)

    @staticmethod
    def _token_hash(token: str) -> bytes:
        return hashlib.sha256(token.encode("ascii")).digest()


def create_attachment_download_router(store: AttachmentDownloadStore) -> APIRouter:
    """Expose a bearerless route protected only by the short-lived capability."""

    router = APIRouter(include_in_schema=False)

    @router.get("/downloads/{token}")
    async def download_attachment(token: str) -> Response:
        payload = store.consume(token)
        if payload is None:
            raise HTTPException(status_code=404, detail="Download not found")
        return Response(
            content=payload.content,
            media_type=_safe_media_type(payload.content_type),
            headers={
                "Cache-Control": "no-store",
                "Content-Disposition": _content_disposition(payload.filename),
                "Pragma": "no-cache",
                "X-Download-Options": "noopen",
            },
        )

    return router


def _safe_media_type(value: str | None) -> str:
    media_type = (value or "").split(";", 1)[0].strip().casefold()
    if _MEDIA_TYPE_PATTERN.fullmatch(media_type) is None:
        return "application/octet-stream"
    return media_type


def _content_disposition(filename: str) -> str:
    basename = filename.replace("\\", "/").rsplit("/", 1)[-1]
    cleaned = "".join(
        character
        for character in basename
        if 0x20 <= ord(character) != 0x7F
    )[:180]
    if not cleaned:
        cleaned = "attachment"
    fallback = re.sub(r"[^A-Za-z0-9._-]", "_", cleaned).strip(".")
    if not fallback:
        fallback = "attachment"
    encoded = quote(cleaned, safe="")
    return f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{encoded}"
