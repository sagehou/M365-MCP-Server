"""Structured audit events that deliberately exclude message content."""

from __future__ import annotations

import logging
import json
from datetime import datetime, timezone
from collections.abc import Awaitable, Callable
from time import perf_counter
from typing import TypeVar

from ..auth.errors import OboTokenError
from ..auth.models import AuthContext


T = TypeVar("T")
AuditOperation = Callable[[AuthContext], Awaitable[T]]


class AuditJsonFormatter(logging.Formatter):
    """Serialize only allowlisted metadata, including an explicit UTC timestamp."""

    def format(self, record: logging.LogRecord) -> str:
        fields = {name: getattr(record, name) for name in (
            "event", "tenant_id", "user_id", "tool_name", "outcome", "duration_ms",
            "error_type", "client_id", "result", "correlation_id", "event_id",
            "grant_type",
            "oauth_error", "status_code", "entra_error", "entra_suberror",
            "entra_error_code", "provider_size", "content_size",
            "graph_request_id",
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
        *,
        event_id: str | None = None,
    ) -> T:
        """Run an operation and emit one success or failure audit event."""

        started = perf_counter()
        try:
            result = await operation(context)
        except Exception as exc:
            entra_fields: dict[str, str | int] = {}
            if isinstance(exc, OboTokenError):
                entra_fields = {
                    name: value
                    for name, value in {
                        "entra_error": exc.entra_error,
                        "entra_suberror": exc.entra_suberror,
                        "entra_error_code": exc.entra_error_code,
                        "correlation_id": exc.correlation_id,
                    }.items()
                    if value is not None
                }
            self._record(
                context,
                tool_name,
                outcome="error",
                started=started,
                error_type=type(exc).__name__,
                event_id=event_id,
                **entra_fields,
            )
            raise
        self._record(
            context, tool_name, outcome="success", started=started, event_id=event_id
        )
        return result

    def attachment_size_mismatch(
        self,
        context: AuthContext,
        tool_name: str,
        *,
        provider_size: int,
        content_size: int,
        graph_request_id: str | None,
    ) -> None:
        """Record a provider/content size difference without attachment identifiers."""

        fields: dict[str, str | int] = {
            "event": "attachment_size_mismatch",
            "tenant_id": context.identity.tenant_id,
            "user_id": context.identity.user_id,
            "tool_name": tool_name,
            "outcome": "warning",
            "provider_size": provider_size,
            "content_size": content_size,
        }
        if graph_request_id is not None:
            fields["graph_request_id"] = graph_request_id
        self.logger.warning("attachment_size_mismatch", extra=fields)

    def _record(
        self,
        context: AuthContext,
        tool_name: str,
        *,
        outcome: str,
        started: float,
        error_type: str | None = None,
        event_id: str | None = None,
        entra_error: str | None = None,
        entra_suberror: str | None = None,
        entra_error_code: int | None = None,
        correlation_id: str | None = None,
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
        for name, value in {
            "event_id": event_id,
            "entra_error": entra_error,
            "entra_suberror": entra_suberror,
            "entra_error_code": entra_error_code,
            "correlation_id": correlation_id,
        }.items():
            if value is not None:
                fields[name] = value
        self.logger.info("mcp_tool_invocation", extra=fields)
