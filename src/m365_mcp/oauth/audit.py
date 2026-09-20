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

    def authorization_started(self, client_id: str, correlation_id: str) -> None:
        self._record(
            "oauth_authorization_started",
            client_id=client_id,
            correlation_id=correlation_id,
            result="success",
        )

    def entra_authorization_succeeded(
        self,
        client_id: str,
        tenant_id: str,
        user_id: str,
        correlation_id: str,
    ) -> None:
        self._record(
            "entra_authorization_succeeded",
            client_id=client_id,
            tenant_id=tenant_id,
            user_id=user_id,
            correlation_id=correlation_id,
            result="success",
        )

    def entra_authorization_failed(
        self,
        client_id: str,
        correlation_id: str,
        error_type: str,
    ) -> None:
        self._record(
            "entra_authorization_failed",
            client_id=client_id,
            correlation_id=correlation_id,
            error_type=error_type,
            result="error",
        )

    def authorization_code_issued(
        self,
        client_id: str,
        correlation_id: str,
    ) -> None:
        self._record(
            "oauth_authorization_code_issued",
            client_id=client_id,
            correlation_id=correlation_id,
            result="success",
        )

    def token_failed(
        self,
        grant_type: str,
        error_type: str,
        oauth_error: str,
        status_code: int,
    ) -> None:
        self._record(
            "oauth_token_failed",
            grant_type=grant_type,
            error_type=error_type,
            oauth_error=oauth_error,
            status_code=status_code,
            result="error",
        )

    def code_redeemed(
        self,
        client_id: str,
        tenant_id: str,
        user_id: str,
        correlation_id: str,
    ) -> None:
        self._record(
            "oauth_code_redeemed",
            client_id=client_id,
            tenant_id=tenant_id,
            user_id=user_id,
            correlation_id=correlation_id,
            result="success",
        )

    def refresh_succeeded(
        self,
        client_id: str,
        tenant_id: str,
        user_id: str,
        correlation_id: str,
    ) -> None:
        self._record(
            "oauth_refresh_succeeded",
            client_id=client_id,
            tenant_id=tenant_id,
            user_id=user_id,
            correlation_id=correlation_id,
            result="success",
        )

    def refresh_failed(
        self,
        client_id: str,
        error_type: str,
        correlation_id: str | None = None,
    ) -> None:
        fields = {
            "client_id": client_id,
            "error_type": error_type,
            "result": "error",
        }
        if correlation_id is not None:
            fields["correlation_id"] = correlation_id
        self._record("oauth_refresh_failed", **fields)

    def session_revoked(
        self,
        client_id: str,
        tenant_id: str,
        user_id: str,
        correlation_id: str,
        error_type: str,
    ) -> None:
        self._record(
            "oauth_session_revoked",
            client_id=client_id,
            tenant_id=tenant_id,
            user_id=user_id,
            correlation_id=correlation_id,
            error_type=error_type,
            result="success",
        )

    def _record(self, event: str, **fields: str | int) -> None:
        self.logger.info(event, extra={"event": event, **fields})
