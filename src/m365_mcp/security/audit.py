"""Structured audit events that deliberately exclude message content."""

from __future__ import annotations

import logging
import json
from datetime import datetime, timezone
from collections.abc import Awaitable, Callable
from time import perf_counter
from typing import TypeVar

from ..auth.models import AuthContext


T = TypeVar("T")
AuditOperation = Callable[[AuthContext], Awaitable[T]]


class AuditJsonFormatter(logging.Formatter):
    """Serialize only allowlisted metadata, including an explicit UTC timestamp."""

    def format(self, record: logging.LogRecord) -> str:
        fields = {name: getattr(record, name) for name in (
            "event", "tenant_id", "user_id", "tool_name", "outcome", "duration_ms",
            "error_type",
        ) if hasattr(record, name)}
        fields["timestamp"] = datetime.fromtimestamp(
            record.created, timezone.utc
        ).isoformat()
        return json.dumps(fields, ensure_ascii=True)


def configure_audit_logger() -> logging.Logger:
    logger = logging.getLogger("m365_mcp.audit")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(AuditJsonFormatter())
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


class AuditLogger:
    """Record safe MCP operation metadata without accepting arbitrary payloads."""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self.logger = logger if logger is not None else configure_audit_logger()

    async def invoke(
        self,
        context: AuthContext,
        tool_name: str,
        operation: AuditOperation[T],
    ) -> T:
        """Run an operation and emit one success or failure audit event."""

        started = perf_counter()
        try:
            result = await operation(context)
        except Exception as exc:
            self._record(
                context,
                tool_name,
                outcome="error",
                started=started,
                error_type=type(exc).__name__,
            )
            raise
        self._record(context, tool_name, outcome="success", started=started)
        return result

    def _record(
        self,
        context: AuthContext,
        tool_name: str,
        *,
        outcome: str,
        started: float,
        error_type: str | None = None,
    ) -> None:
        fields: dict[str, str | int] = {
            "event": "mcp_tool_invocation",
            "tenant_id": context.identity.tenant_id,
            "user_id": context.identity.user_id,
            "tool_name": tool_name,
            "outcome": outcome,
            "duration_ms": max(0, round((perf_counter() - started) * 1000)),
        }
        if error_type is not None:
            fields["error_type"] = error_type
        self.logger.info("mcp_tool_invocation", extra=fields)
