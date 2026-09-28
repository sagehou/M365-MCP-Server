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
_MEDIA_TYPE_PATTERN = re.compile(r"[A-Za-z0-9!#$&^_.+-]+/[A-Za-z0-9!#$&^_.+-]+")


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
    draft_id: str | None = None


@dataclass(frozen=True, slots=True)
class _PushGrant:
    owner: tuple[str, str, str]
    draft_id: str
    name: str
    content_type: str
    size: int
    sha256: str
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
        or _MEDIA_TYPE_PATTERN.fullmatch(content_type) is None
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
        max_push_grants: int = 8,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if ttl_seconds <= 0 or max_items <= 0 or max_total_bytes <= 0 or max_push_grants <= 0:
            raise ValueError("upload store limits must be positive")
        self.ttl_seconds = ttl_seconds
        self.max_items = max_items
        self.max_total_bytes = max_total_bytes
        self.max_push_grants = max_push_grants
        self._clock = clock
        self._entries: dict[bytes, _Entry] = {}
        self._push_grants: dict[bytes, _PushGrant] = {}
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

    def issue_push_grant(
        self,
        context: AuthContext,
        draft_id: str,
        name: str,
        content_type: str,
        size: int,
        sha256: str,
    ) -> str:
        if not isinstance(draft_id, str) or not 1 <= len(draft_id) <= 1024:
            raise ValueError("draft_id must contain 1 to 1024 characters")
        validate_attachment_name(name)
        validate_content_type(content_type)
        if not isinstance(size, int) or isinstance(size, bool) or not 1 <= size <= MAX_SEND_ATTACHMENT_BYTES:
            raise ValueError("attachment must be 1 byte to 20 MiB")
        if not isinstance(sha256, str) or re.fullmatch(r"[0-9a-fA-F]{64}", sha256) is None:
            raise ValueError("content_sha256 must be a SHA-256 hex digest")
        with self._lock:
            self._prune()
            if len(self._push_grants) >= self.max_push_grants:
                raise OverflowError("temporary upload grant capacity is full")
            token = secrets.token_urlsafe(32)
            digest = self._digest(token)
            self._push_grants[digest] = _PushGrant(
                owner=self._owner(context),
                draft_id=draft_id,
                name=name,
                content_type=content_type,
                size=size,
                sha256=sha256.lower(),
                expires_at=self._clock() + self.ttl_seconds,
            )
            return token

    def push_grant_size(self, token: str | None) -> int | None:
        if not isinstance(token, str) or _HANDLE_PATTERN.fullmatch(token) is None:
            return None
        with self._lock:
            self._prune()
            grant = self._push_grants.get(self._digest(token))
            return grant.size if grant is not None else None

    def complete_push_grant(self, token: str, content: bytes) -> StagedAttachment | None:
        if not isinstance(token, str) or _HANDLE_PATTERN.fullmatch(token) is None:
            return None
        with self._lock:
            self._prune()
            digest = self._digest(token)
            grant = self._push_grants.get(digest)
            if grant is None:
                return None
            if len(content) != grant.size or hashlib.sha256(content).hexdigest() != grant.sha256:
                raise ValueError("attachment content does not match the upload grant")
            if len(self._entries) >= self.max_items or self._total_bytes + grant.size > self.max_total_bytes:
                raise OverflowError("temporary upload capacity is full")
            payload = StagedAttachment(grant.name, grant.content_type, content)
            del self._push_grants[digest]
            self._entries[digest] = _Entry(
                owner=grant.owner,
                payload=payload,
                expires_at=self._clock() + self.ttl_seconds,
                draft_id=grant.draft_id,
            )
            self._total_bytes += grant.size
            return payload

    def consume(
        self, context: AuthContext, token: str, draft_id: str | None = None
    ) -> StagedAttachment | None:
        if not isinstance(token, str) or _HANDLE_PATTERN.fullmatch(token) is None:
            return None
        with self._lock:
            self._prune()
            digest = self._digest(token)
            entry = self._entries.get(digest)
            if (
                entry is None
                or entry.owner != self._owner(context)
                or (entry.draft_id is not None and entry.draft_id != draft_id)
            ):
                return None
            del self._entries[digest]
            self._total_bytes -= len(entry.payload.content)
            return entry.payload

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._push_grants.clear()
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
        for digest, grant in list(self._push_grants.items()):
            if grant.expires_at <= now:
                del self._push_grants[digest]

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

    @router.post("/uploads/push", status_code=201)
    async def push_attachment(request: Request) -> dict[str, object]:
        token = request.headers.get("x-upload-handle")
        expected_size = store.push_grant_size(token)
        if expected_size is None:
            raise HTTPException(404, "Upload grant not found")
        media_type = request.headers.get("content-type", "").split(";", 1)[0].strip().casefold()
        if media_type != "application/octet-stream":
            raise HTTPException(415, "Use application/octet-stream")
        declared = request.headers.get("content-length")
        if declared is not None and (
            len(declared) > 8 or not declared.isascii() or not declared.isdigit()
            or int(declared) != expected_size
        ):
            raise HTTPException(400, "Upload length does not match the grant")
        async with upload_slots:
            content = bytearray()
            async for chunk in request.stream():
                if len(content) + len(chunk) > expected_size:
                    raise HTTPException(413, "Attachment exceeds the granted size")
                content.extend(chunk)
        try:
            payload = store.complete_push_grant(token, bytes(content))
        except ValueError:
            raise HTTPException(400, "Upload content does not match the grant") from None
        except OverflowError:
            raise HTTPException(429, "Temporary upload capacity is full") from None
        if payload is None:
            raise HTTPException(404, "Upload grant not found")
        return {
            "upload_handle": token,
            "name": payload.name,
            "content_type": payload.content_type,
            "content_length": len(payload.content),
            "content_sha256": hashlib.sha256(payload.content).hexdigest(),
        }

    return router
