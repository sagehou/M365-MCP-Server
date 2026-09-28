"""Bounded, user-bound staging for binary draft attachment uploads."""

import asyncio
import hashlib
import re
import secrets
import time
from contextlib import suppress
from dataclasses import dataclass
from threading import Lock
from typing import Callable
from urllib.parse import unquote_to_bytes

from fastapi import APIRouter, HTTPException, Request

from ..auth.context import get_auth_context
from ..auth.models import AuthContext
from ..graph.mail import MAX_SEND_ATTACHMENT_BYTES


_HANDLE_PATTERN = re.compile(r"[A-Za-z0-9_-]{43}")


@dataclass(frozen=True, slots=True)
class StagedAttachment:
    name: str
    content_type: str
    content: bytes


@dataclass(frozen=True, slots=True)
class _Entry:
    owner: tuple[str, str, str]
    payload: StagedAttachment
    expires_at: float


def validate_attachment_name(name: str) -> str:
    if (
        not name
        or len(name) > 255
        or any(ord(char) < 32 or ord(char) == 127 or char in "/\\" for char in name)
    ):
        raise ValueError("name must be a plain filename of at most 255 characters")
    return name


def validate_content_type(content_type: str) -> str:
    if (
        not content_type
        or len(content_type) > 127
        or not content_type.isascii()
        or any(ord(char) < 33 or ord(char) > 126 for char in content_type)
    ):
        raise ValueError("content type must be an ASCII MIME type")
    return content_type


class AttachmentUploadStore:
    """Retain at most four 20 MiB files in RAM; never write staged bytes to disk."""

    def __init__(
        self,
        *,
        ttl_seconds: int = 300,
        max_items: int = 4,
        max_total_bytes: int = 80 * 1024 * 1024,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if ttl_seconds <= 0 or max_items <= 0 or max_total_bytes <= 0:
            raise ValueError("upload store limits must be positive")
        self.ttl_seconds = ttl_seconds
        self.max_items = max_items
        self.max_total_bytes = max_total_bytes
        self._clock = clock
        self._entries: dict[bytes, _Entry] = {}
        self._total_bytes = 0
        self._lock = Lock()
        self._cleanup_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(
                self._cleanup_loop(), name="attachment-upload-cleanup"
            )

    async def aclose(self) -> None:
        task = self._cleanup_task
        self._cleanup_task = None
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        self.clear()

    def issue(self, context: AuthContext, payload: StagedAttachment) -> str:
        validate_attachment_name(payload.name)
        validate_content_type(payload.content_type)
        size = len(payload.content)
        if not 1 <= size <= MAX_SEND_ATTACHMENT_BYTES:
            raise ValueError("attachment must be 1 byte to 20 MiB")
        with self._lock:
            self._prune()
            if len(self._entries) >= self.max_items or self._total_bytes + size > self.max_total_bytes:
                raise OverflowError("temporary upload capacity is full")
            token = secrets.token_urlsafe(32)
            digest = self._digest(token)
            self._entries[digest] = _Entry(
                owner=self._owner(context),
                payload=payload,
                expires_at=self._clock() + self.ttl_seconds,
            )
            self._total_bytes += size
            return token

    def consume(self, context: AuthContext, token: str) -> StagedAttachment | None:
        if not isinstance(token, str) or _HANDLE_PATTERN.fullmatch(token) is None:
            return None
        with self._lock:
            self._prune()
            digest = self._digest(token)
            entry = self._entries.get(digest)
            if entry is None or entry.owner != self._owner(context):
                return None
            del self._entries[digest]
            self._total_bytes -= len(entry.payload.content)
            return entry.payload

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._total_bytes = 0

    def purge_expired(self) -> None:
        with self._lock:
            self._prune()

    async def _cleanup_loop(self) -> None:
        while True:
            await asyncio.sleep(min(60.0, max(1.0, self.ttl_seconds / 2)))
            self.purge_expired()

    def _prune(self) -> None:
        now = self._clock()
        for digest, entry in list(self._entries.items()):
            if entry.expires_at <= now:
                del self._entries[digest]
                self._total_bytes -= len(entry.payload.content)

    @staticmethod
    def _digest(token: str) -> bytes:
        return hashlib.sha256(token.encode("ascii")).digest()

    @staticmethod
    def _owner(context: AuthContext) -> tuple[str, str, str]:
        identity = context.identity
        return (identity.tenant_id, identity.user_id, identity.subject)


def create_attachment_upload_router(store: AttachmentUploadStore) -> APIRouter:
    router = APIRouter(include_in_schema=False)
    upload_slots = asyncio.Semaphore(4)

    @router.post("/uploads/attachments", status_code=201)
    async def stage_attachment(request: Request) -> dict[str, object]:
        context = get_auth_context(request)
        encoded_name = request.headers.get("x-attachment-name")
        if encoded_name is None or len(encoded_name) > 1024:
            raise HTTPException(400, "X-Attachment-Name is required")
        try:
            name = validate_attachment_name(unquote_to_bytes(encoded_name).decode("utf-8"))
            content_type = validate_content_type(
                request.headers.get("x-attachment-content-type", "application/octet-stream")
            )
        except (UnicodeDecodeError, ValueError):
            raise HTTPException(400, "Invalid attachment metadata") from None
        media_type = request.headers.get("content-type", "").split(";", 1)[0].strip().casefold()
        if media_type != "application/octet-stream":
            raise HTTPException(415, "Use application/octet-stream")
        declared = request.headers.get("content-length")
        if declared is not None and (
            len(declared) > 8
            or not declared.isascii()
            or not declared.isdigit()
            or int(declared) > MAX_SEND_ATTACHMENT_BYTES
        ):
            raise HTTPException(413, "Attachment exceeds 20 MiB")
        async with upload_slots:
            content = bytearray()
            async for chunk in request.stream():
                if len(content) + len(chunk) > MAX_SEND_ATTACHMENT_BYTES:
                    raise HTTPException(413, "Attachment exceeds 20 MiB")
                content.extend(chunk)
        if not content:
            raise HTTPException(400, "Attachment must not be empty")
        payload = StagedAttachment(name, content_type, bytes(content))
        try:
            handle = store.issue(context, payload)
        except OverflowError:
            raise HTTPException(429, "Temporary upload capacity is full") from None
        return {
            "upload_handle": handle,
            "expires_in_seconds": store.ttl_seconds,
            "name": name,
            "content_type": content_type,
            "content_length": len(payload.content),
            "content_sha256": hashlib.sha256(payload.content).hexdigest(),
        }

    return router
