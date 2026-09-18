"""Security-minimal OAuth audit events."""

from __future__ import annotations

import logging

from ..security.audit import AuditJsonFormatter


def configure_oauth_audit_logger() -> logging.Logger:
    logger = logging.getLogger("m365_mcp.oauth.audit")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(AuditJsonFormatter())
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


class OAuthAuditLogger:
    def __init__(self, logger: logging.Logger | None = None) -> None:
        self.logger = logger if logger is not None else configure_oauth_audit_logger()

    def client_registered(self, client_id: str) -> None:
        self.logger.info(
            "oauth_client_registered",
            extra={
                "event": "oauth_client_registered",
                "client_id": client_id,
                "result": "success",
            },
        )
