"""Linux-only parser worker. Receives bytes via stdin and returns bounded JSON."""

import contextlib
import json
import os
import resource
import sys
from dataclasses import asdict

from .attachment import AttachmentExtractorRegistry, AttachmentInput
from .errors import AttachmentTooLargeError, UnsupportedAttachmentError


def apply_limits() -> None:
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_CPU, (15, 15))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))


def main() -> None:
    apply_limits()
    try:
        header = sys.stdin.buffer.readline(8194)
        if not header.endswith(b"\n") or len(header) > 8193:
            raise ValueError("Invalid metadata")
        metadata = json.loads(header)
        max_bytes = metadata.pop("max_bytes")
        max_chars = metadata.pop("max_text_chars")
        if not 0 < max_bytes <= 50 * 1024 * 1024 or not 0 < max_chars <= 1_000_000:
            raise ValueError("Invalid limits")
        content = sys.stdin.buffer.read(max_bytes + 1)
        with open(os.devnull, "w") as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            registry = AttachmentExtractorRegistry(max_bytes=max_bytes, max_text_chars=max_chars)
            result = registry.extract(AttachmentInput(content=content, **metadata))
        response = asdict(result)
    except AttachmentTooLargeError:
        response = {"error": "too_large"}
    except UnsupportedAttachmentError:
        response = {"error": "unsupported"}
    except Exception:
        response = {"error": "invalid"}
    sys.stdout.write(json.dumps(response, ensure_ascii=True))


if __name__ == "__main__":
    main()
