"""Async supervision of short-lived, resource-limited attachment workers."""

import asyncio
import json
import os
import sys

from .attachment import AttachmentInput, ExtractionResult
from .errors import AttachmentTooLargeError, InvalidAttachmentError, UnsupportedAttachmentError

WORKER_TIMEOUT_SECONDS = 20.0


async def extract_isolated(
    attachment: AttachmentInput, *, max_bytes: int, max_text_chars: int
) -> ExtractionResult:
    if len(attachment.content) > max_bytes or (
        attachment.declared_size is not None and attachment.declared_size > max_bytes
    ):
        raise AttachmentTooLargeError("Attachment exceeds the server byte limit")
    if not sys.platform.startswith("linux"):
        raise InvalidAttachmentError("Isolated extraction requires the Linux container")
    metadata = json.dumps({
        "name": attachment.name, "content_type": attachment.content_type,
        "declared_size": attachment.declared_size,
        "max_bytes": max_bytes, "max_text_chars": max_text_chars,
    }).encode("utf-8")
    if len(metadata) > 8192:
        raise InvalidAttachmentError("Attachment metadata exceeds the server limit")
    process = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "m365_mcp.extractors.worker",
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        # Do not pass Entra credentials or bearer tokens into parser processes.
        env={"PATH": os.defpath, "PYTHONDONTWRITEBYTECODE": "1", "OPENBLAS_NUM_THREADS": "1"},
    )
    try:
        output, _ = await asyncio.wait_for(
            process.communicate(metadata + b"\n" + attachment.content),
            timeout=WORKER_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        raise InvalidAttachmentError("Attachment extraction exceeded its time limit") from None
    finally:
        # Also reap on cancellation; wait_for does not kill a subprocess.
        if process.returncode is None:
            try:
                process.kill()
            except ProcessLookupError:
                pass
        await process.wait()
    if process.returncode != 0:
        raise InvalidAttachmentError("Attachment extraction failed or exceeded resource limits")
    try:
        result = json.loads(output)
        error = result.get("error")
        if error == "too_large":
            raise AttachmentTooLargeError("Attachment exceeds extraction limits")
        if error == "unsupported":
            raise UnsupportedAttachmentError("Attachment format is not supported")
        if error:
            raise InvalidAttachmentError("The attachment could not be parsed")
        return ExtractionResult(**result)
    except (ValueError, TypeError):
        raise InvalidAttachmentError("Attachment worker returned an invalid result") from None
