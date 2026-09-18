"""Deep module for persistent local OAuth refresh sessions."""

from __future__ import annotations

import hashlib
import re
import secrets
from dataclasses import replace
from time import time

from ..auth.errors import AuthenticationError, ConfigurationError
from ..auth.middleware import TokenValidator
from ..auth.settings import Settings
from .audit import OAuthAuditLogger
from .crypto import TokenProtectionError, TokenProtector
from .entra import (
    EntraAuthorizationBroker,
    EntraBrokerError,
    EntraRefreshRejectedError,
)
from .errors import OAuthProtocolError
from .models import (
    OAuthAuthorizationCode,
    OAuthRefreshTokenRequest,
    OAuthSession,
    OAuthTokenResponse,
)
from .store import OAuthStore, OAuthStoreError, RefreshSessionRotationResult


_REFRESH_TOKEN = re.compile(r"^[A-Za-z0-9_-]{43}$")


class OAuthSessionService:
    """Own encrypted cache persistence, refresh and one-time token rotation."""

    def __init__(
        self,
        settings: Settings,
        store: OAuthStore,
        broker: EntraAuthorizationBroker,
        token_validator: TokenValidator,
        token_protector: TokenProtector,
        audit_logger: OAuthAuditLogger | None = None,
    ) -> None:
        self.settings = settings
        self.store = store
        self.broker = broker
        self.token_validator = token_validator
        self.token_protector = token_protector
        self.audit_logger = audit_logger or OAuthAuditLogger()
        self.issuer = settings.normalized_oauth_issuer_url

    async def issue(
        self,
        authorization_code: OAuthAuthorizationCode,
        serialized_cache: str,
        now: int,
    ) -> str:
        """Persist one restart-safe session and return its opaque client handle."""

        if not serialized_cache:
            raise self._unavailable()
        refresh_token = secrets.token_urlsafe(32)
        session_id = secrets.token_urlsafe(24)
        rotation_family = secrets.token_urlsafe(24)
        session = OAuthSession(
            id=session_id,
            issuer=self.issuer,
            client_id=authorization_code.client_id,
            tenant_id=authorization_code.tenant_id,
            user_id=authorization_code.user_id,
            scope=authorization_code.scope,
            resource=authorization_code.resource,
            refresh_token_hash=self._hash_secret(refresh_token),
            encrypted_msal_cache=b"",
            created_at=now,
            updated_at=now,
            expires_at=(now + self.settings.oauth_refresh_token_ttl_days * 86_400),
            revoked_at=None,
            rotation_family=rotation_family,
            rotation_count=0,
        )
        try:
            encrypted_cache = self.token_protector.seal(
                {"serialized_cache": serialized_cache},
                context=self._session_protection_context(session),
            )
            await self.store.create_session(
                replace(session, encrypted_msal_cache=encrypted_cache)
            )
        except (TokenProtectionError, OAuthStoreError) as exc:
            raise self._unavailable() from exc
        return refresh_token

    async def refresh(
        self,
        request: OAuthRefreshTokenRequest,
    ) -> OAuthTokenResponse:
        """Refresh Token A and atomically rotate the local opaque handle."""

        if not _REFRESH_TOKEN.fullmatch(request.refresh_token):
            self.audit_logger.refresh_failed(request.client_id, "InvalidGrant")
            raise self._invalid_grant()
        now = int(time())
        current_hash = self._hash_secret(request.refresh_token)
        try:
            session = await self.store.get_refresh_session(
                self.issuer,
                current_hash,
                request.client_id,
                now,
            )
        except OAuthStoreError as exc:
            raise self._unavailable() from exc
        if session is None:
            replayed = await self._revoke_replayed_session(
                request.client_id,
                current_hash,
                now,
            )
            if not replayed:
                self.audit_logger.refresh_failed(request.client_id, "InvalidGrant")
            raise self._invalid_grant()
        if not self._session_binding_is_valid(session):
            await self._revoke(session, current_hash, now, "InvalidSessionBinding")
            raise self._invalid_grant()
        if request.scope is not None:
            requested_scope = frozenset(request.scope.split())
            stored_scope = frozenset(session.scope.split())
            if requested_scope != stored_scope:
                self.audit_logger.refresh_failed(
                    request.client_id,
                    "InvalidScope",
                    session.id,
                )
                raise OAuthProtocolError(
                    "invalid_scope",
                    "requested scope is not supported",
                )
        if session.rotation_count >= self.settings.oauth_refresh_max_rotations:
            await self._revoke(session, current_hash, now, "RotationLimitReached")
            raise self._invalid_grant()

        try:
            protected_cache = self.token_protector.open(
                session.encrypted_msal_cache,
                context=self._session_protection_context(session),
            )
        except TokenProtectionError:
            await self._revoke(session, current_hash, now, "TokenProtectionError")
            raise self._invalid_grant()
        serialized_cache = protected_cache.get("serialized_cache")
        if not isinstance(serialized_cache, str) or not serialized_cache:
            await self._revoke(session, current_hash, now, "InvalidTokenCache")
            raise self._invalid_grant()

        try:
            token_result = await self.broker.refresh(serialized_cache)
        except EntraRefreshRejectedError:
            await self._revoke(session, current_hash, now, "MicrosoftRevocation")
            raise self._invalid_grant()
        except EntraBrokerError as exc:
            self.audit_logger.refresh_failed(
                request.client_id,
                type(exc).__name__,
                session.id,
            )
            raise self._unavailable() from exc

        try:
            identity = await self.token_validator.validate(token_result.access_token)
        except ConfigurationError as exc:
            self.audit_logger.refresh_failed(
                request.client_id,
                type(exc).__name__,
                session.id,
            )
            raise self._unavailable() from exc
        except AuthenticationError as exc:
            await self._revoke(session, current_hash, now, type(exc).__name__)
            raise self._invalid_grant() from exc
        if (
            identity.tenant_id != session.tenant_id
            or identity.user_id != session.user_id
        ):
            await self._revoke(session, current_hash, now, "IdentityMismatch")
            raise self._invalid_grant()

        new_refresh_token = secrets.token_urlsafe(32)
        new_refresh_token_hash = self._hash_secret(new_refresh_token)
        rotated_session = replace(
            session,
            refresh_token_hash=new_refresh_token_hash,
            rotation_count=session.rotation_count + 1,
        )
        try:
            encrypted_cache = self.token_protector.seal(
                {"serialized_cache": token_result.serialized_cache},
                context=self._session_protection_context(rotated_session),
            )
            rotation_result = await self.store.rotate_refresh_session(
                self.issuer,
                session.id,
                session.client_id,
                current_hash,
                new_refresh_token_hash,
                encrypted_cache,
                self.settings.oauth_refresh_max_rotations,
                now,
            )
        except (TokenProtectionError, OAuthStoreError) as exc:
            raise self._unavailable() from exc
        if rotation_result is RefreshSessionRotationResult.LIMIT_REACHED:
            self.audit_logger.refresh_failed(
                session.client_id,
                "RotationLimitReached",
                session.id,
            )
            self.audit_logger.session_revoked(
                session.client_id,
                session.tenant_id,
                session.user_id,
                session.id,
                "RotationLimitReached",
            )
            raise self._invalid_grant()
        if rotation_result is not RefreshSessionRotationResult.ROTATED:
            replayed = await self._revoke_replayed_session(
                request.client_id,
                current_hash,
                now,
            )
            if not replayed:
                self.audit_logger.refresh_failed(
                    request.client_id,
                    "RefreshReplay",
                    session.id,
                )
            raise self._invalid_grant()

        self.audit_logger.refresh_succeeded(
            session.client_id,
            session.tenant_id,
            session.user_id,
            session.id,
        )
        return OAuthTokenResponse(
            access_token=token_result.access_token,
            expires_in=token_result.expires_in,
            scope=session.scope,
            refresh_token=new_refresh_token,
        )

    async def _revoke(
        self,
        session: OAuthSession,
        current_hash: str,
        now: int,
        error_type: str,
    ) -> None:
        try:
            revoked = await self.store.revoke_refresh_session(
                self.issuer,
                session.id,
                session.client_id,
                current_hash,
                now,
            )
        except OAuthStoreError as exc:
            raise self._unavailable() from exc
        if not revoked:
            replayed = await self._revoke_replayed_session(
                session.client_id,
                current_hash,
                now,
            )
            if replayed:
                return
        self.audit_logger.refresh_failed(
            session.client_id,
            error_type,
            session.id,
        )
        if revoked:
            self.audit_logger.session_revoked(
                session.client_id,
                session.tenant_id,
                session.user_id,
                session.id,
                error_type,
            )

    async def _revoke_replayed_session(
        self,
        client_id: str,
        refresh_token_hash: str,
        now: int,
    ) -> bool:
        try:
            session = await self.store.revoke_refresh_session_by_replay(
                self.issuer,
                refresh_token_hash,
                client_id,
                now,
            )
        except OAuthStoreError as exc:
            raise self._unavailable() from exc
        if session is None:
            return False
        self.audit_logger.refresh_failed(
            session.client_id,
            "RefreshReplay",
            session.id,
        )
        self.audit_logger.session_revoked(
            session.client_id,
            session.tenant_id,
            session.user_id,
            session.id,
            "RefreshReplay",
        )
        return True

    def _session_binding_is_valid(self, session: OAuthSession) -> bool:
        return (
            session.issuer == self.issuer
            and session.resource == self.settings.mcp_public_url
            and frozenset(session.scope.split()) == self.settings.required_scopes
        )

    @staticmethod
    def _session_protection_context(session: OAuthSession) -> dict[str, object]:
        return {
            "artifact": "oauth_session",
            "id": session.id,
            "issuer": session.issuer,
            "client_id": session.client_id,
            "tenant_id": session.tenant_id,
            "user_id": session.user_id,
            "scope": session.scope,
            "resource": session.resource,
            "refresh_token_hash": session.refresh_token_hash,
            "created_at": session.created_at,
            "expires_at": session.expires_at,
            "rotation_family": session.rotation_family,
            "rotation_count": session.rotation_count,
        }

    @staticmethod
    def _hash_secret(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _invalid_grant() -> OAuthProtocolError:
        return OAuthProtocolError("invalid_grant", "refresh token is invalid")

    @staticmethod
    def _unavailable() -> OAuthProtocolError:
        return OAuthProtocolError(
            "temporarily_unavailable",
            "OAuth authorization is temporarily unavailable",
            status_code=503,
        )
