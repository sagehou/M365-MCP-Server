"""Deep module implementing the MCP authorization-code flow."""

from __future__ import annotations

import base64
import hashlib
import re
import secrets
from collections.abc import Mapping
from dataclasses import replace
from time import time
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from ..auth.errors import AuthenticationError, ConfigurationError
from ..auth.middleware import TokenValidator
from ..auth.settings import Settings
from .audit import OAuthAuditLogger
from .crypto import TokenProtectionError, TokenProtector
from .entra import EntraAuthorizationClient, EntraAuthorizationError
from .errors import OAuthProtocolError
from .models import (
    OAuthAuthorizationCode,
    OAuthAuthorizationCodeTokenRequest,
    OAuthAuthorizationRequest,
    OAuthClient,
    OAuthRefreshTokenRequest,
    OAuthTokenResponse,
    OAuthTransaction,
)
from .registry import OAuthClientRegistry
from .sessions import OAuthSessionService
from .store import OAuthStore, OAuthStoreError


_PKCE_CHALLENGE = re.compile(r"^[A-Za-z0-9_-]{43}$")
_PKCE_VERIFIER = re.compile(r"^[A-Za-z0-9._~-]{43,128}$")
_RESERVED_REDIRECT_PARAMETERS = frozenset({"code", "state", "error"})


class OAuthAuthorizationService:
    """Own validation, state binding, Entra exchange and one-time code redemption."""

    def __init__(
        self,
        settings: Settings,
        registry: OAuthClientRegistry,
        store: OAuthStore,
        entra_client: EntraAuthorizationClient,
        token_validator: TokenValidator,
        token_protector: TokenProtector,
        session_service: OAuthSessionService,
        audit_logger: OAuthAuditLogger | None = None,
    ) -> None:
        self.settings = settings
        self.registry = registry
        self.store = store
        self.entra_client = entra_client
        self.token_validator = token_validator
        self.token_protector = token_protector
        self.session_service = session_service
        self.audit_logger = audit_logger or OAuthAuditLogger()
        self.issuer = settings.normalized_oauth_issuer_url

    async def authorize(self, request: OAuthAuthorizationRequest) -> str:
        if request.response_type != "code":
            raise OAuthProtocolError(
                "unsupported_response_type",
                "response_type must be code",
            )
        if request.code_challenge_method != "S256":
            raise OAuthProtocolError(
                "invalid_request",
                "code_challenge_method must be S256",
            )
        if not _PKCE_CHALLENGE.fullmatch(request.code_challenge):
            raise OAuthProtocolError(
                "invalid_request",
                "code_challenge is malformed",
            )
        scope = self._validated_scope(request.scope)
        resource = request.resource or self.settings.mcp_public_url
        if resource != self.settings.mcp_public_url:
            raise OAuthProtocolError("invalid_target", "resource is not supported")

        client = await self._registered_client_for_grant(
            request.client_id,
            "authorization_code",
        )
        if request.redirect_uri not in client.redirect_uris:
            raise OAuthProtocolError(
                "invalid_request",
                "redirect_uri is not registered for this client",
            )

        upstream_state = secrets.token_urlsafe(32)
        transaction_id = secrets.token_urlsafe(32)
        try:
            upstream = await self.entra_client.begin(upstream_state)
        except EntraAuthorizationError as exc:
            raise self._unavailable() from exc
        self._validate_upstream_authorization_uri(
            upstream.authorization_uri,
            upstream_state,
        )
        now = int(time())
        transaction = OAuthTransaction(
            transaction_id_hash=self._hash_secret(transaction_id),
            issuer=self.issuer,
            client_id=request.client_id,
            redirect_uri=request.redirect_uri,
            workbuddy_state=request.state,
            entra_state_hash=self._hash_secret(upstream_state),
            code_challenge=request.code_challenge,
            scope=scope,
            resource=resource,
            protected_upstream_flow=b"",
            created_at=now,
            expires_at=now + self.settings.oauth_transaction_ttl_seconds,
        )
        try:
            protected_upstream_flow = self.token_protector.seal(
                {"flow": dict(upstream.flow)},
                context=self._transaction_protection_context(transaction),
            )
        except TokenProtectionError as exc:
            raise self._unavailable() from exc
        transaction = replace(
            transaction,
            protected_upstream_flow=protected_upstream_flow,
        )
        try:
            await self.store.create_transaction(transaction)
        except OAuthStoreError as exc:
            raise self._unavailable() from exc
        self.audit_logger.authorization_started(
            request.client_id,
            transaction.transaction_id_hash,
        )
        return upstream.authorization_uri

    async def complete(
        self,
        authorization_response: Mapping[str, str],
    ) -> str:
        upstream_state = authorization_response.get("state")
        if not isinstance(upstream_state, str) or not upstream_state:
            raise OAuthProtocolError("invalid_request", "upstream state is missing")
        now = int(time())
        try:
            transaction = await self.store.consume_transaction(
                self.issuer,
                self._hash_secret(upstream_state),
                now,
            )
        except OAuthStoreError as exc:
            raise self._unavailable() from exc
        if transaction is None:
            raise OAuthProtocolError(
                "invalid_request",
                "authorization transaction is invalid or expired",
            )
        if authorization_response.get("error"):
            self.audit_logger.entra_authorization_failed(
                transaction.client_id,
                transaction.transaction_id_hash,
                "AccessDenied",
            )
            return self._append_redirect_parameters(
                transaction.redirect_uri,
                [("error", "access_denied"), ("state", transaction.workbuddy_state)],
            )
        try:
            protected_transaction = self.token_protector.open(
                transaction.protected_upstream_flow,
                context=self._transaction_protection_context(transaction),
            )
        except TokenProtectionError:
            self.audit_logger.entra_authorization_failed(
                transaction.client_id,
                transaction.transaction_id_hash,
                "TokenProtectionError",
            )
            return self._callback_error_redirect(transaction, "server_error")
        upstream_flow = protected_transaction.get("flow")
        if not isinstance(upstream_flow, dict):
            self.audit_logger.entra_authorization_failed(
                transaction.client_id,
                transaction.transaction_id_hash,
                "InvalidAuthorizationFlow",
            )
            return self._callback_error_redirect(transaction, "server_error")
        try:
            token_result = await self.entra_client.complete(
                upstream_flow,
                authorization_response,
            )
            access_token_expires_at = int(time()) + token_result.expires_in
            identity = await self.token_validator.validate(token_result.access_token)
        except (
            EntraAuthorizationError,
            AuthenticationError,
            ConfigurationError,
        ) as exc:
            self.audit_logger.entra_authorization_failed(
                transaction.client_id,
                transaction.transaction_id_hash,
                type(exc).__name__,
            )
            return self._callback_error_redirect(transaction, "server_error")

        self.audit_logger.entra_authorization_succeeded(
            transaction.client_id,
            identity.tenant_id,
            identity.user_id,
            transaction.transaction_id_hash,
        )

        now = int(time())
        local_code = secrets.token_urlsafe(32)
        authorization_code = OAuthAuthorizationCode(
            code_hash=self._hash_secret(local_code),
            issuer=self.issuer,
            client_id=transaction.client_id,
            redirect_uri=transaction.redirect_uri,
            scope=transaction.scope,
            resource=transaction.resource,
            code_challenge=transaction.code_challenge,
            encrypted_msal_cache=b"",
            tenant_id=identity.tenant_id,
            user_id=identity.user_id,
            created_at=now,
            expires_at=now + self.settings.oauth_authorization_code_ttl_seconds,
        )
        try:
            protected_bundle = self.token_protector.seal(
                {
                    "access_token": token_result.access_token,
                    "access_token_expires_at": access_token_expires_at,
                    "serialized_cache": token_result.serialized_cache,
                },
                context=self._authorization_code_protection_context(
                    authorization_code
                ),
            )
        except TokenProtectionError:
            return self._callback_error_redirect(transaction, "server_error")
        authorization_code = replace(
            authorization_code,
            encrypted_msal_cache=protected_bundle,
        )
        try:
            await self.store.create_authorization_code(authorization_code)
        except OAuthStoreError:
            return self._callback_error_redirect(
                transaction,
                "temporarily_unavailable",
            )
        return self._append_authorization_result(
            transaction.redirect_uri,
            local_code,
            transaction.workbuddy_state,
        )

    async def exchange(
        self,
        request: OAuthAuthorizationCodeTokenRequest,
    ) -> OAuthTokenResponse:
        if not _PKCE_VERIFIER.fullmatch(request.code_verifier):
            raise OAuthProtocolError("invalid_grant", "authorization code is invalid")
        verifier_challenge = self._pkce_challenge(request.code_verifier)
        now = int(time())
        try:
            authorization_code = await self.store.consume_authorization_code(
                self.issuer,
                self._hash_secret(request.code),
                request.client_id,
                request.redirect_uri,
                verifier_challenge,
                now,
            )
        except OAuthStoreError as exc:
            raise self._unavailable() from exc
        if authorization_code is None:
            raise OAuthProtocolError("invalid_grant", "authorization code is invalid")
        if not self._authorization_code_binding_is_valid(authorization_code):
            raise OAuthProtocolError("invalid_grant", "authorization code is invalid")
        client = await self._registered_client_for_grant(
            request.client_id,
            "authorization_code",
        )
        try:
            bundle = self.token_protector.open(
                authorization_code.encrypted_msal_cache,
                context=self._authorization_code_protection_context(
                    authorization_code
                ),
            )
        except TokenProtectionError as exc:
            raise OAuthProtocolError(
                "invalid_grant",
                "authorization code is invalid",
            ) from exc
        access_token = bundle.get("access_token")
        access_token_expires_at = bundle.get("access_token_expires_at")
        serialized_cache = bundle.get("serialized_cache")
        if not isinstance(access_token, str) or not access_token:
            raise OAuthProtocolError("invalid_grant", "authorization code is invalid")
        if not isinstance(access_token_expires_at, int):
            raise OAuthProtocolError("invalid_grant", "authorization code is invalid")
        if not isinstance(serialized_cache, str) or not serialized_cache:
            raise OAuthProtocolError("invalid_grant", "authorization code is invalid")
        expires_in = access_token_expires_at - now
        if expires_in <= 0:
            raise OAuthProtocolError("invalid_grant", "authorization code is invalid")
        refresh_token = None
        if "refresh_token" in client.grant_types:
            refresh_token = await self.session_service.issue(
                authorization_code,
                serialized_cache,
                now,
            )
        self.audit_logger.code_redeemed(
            authorization_code.client_id,
            authorization_code.tenant_id,
            authorization_code.user_id,
            authorization_code.code_hash,
        )
        return OAuthTokenResponse(
            access_token=access_token,
            expires_in=expires_in,
            scope=authorization_code.scope,
            refresh_token=refresh_token,
        )

    async def refresh(
        self,
        request: OAuthRefreshTokenRequest,
    ) -> OAuthTokenResponse:
        await self._registered_client_for_grant(
            request.client_id,
            "refresh_token",
            hide_unknown_client=True,
        )
        return await self.session_service.refresh(request)

    async def _registered_client_for_grant(
        self,
        client_id: str,
        grant_type: str,
        *,
        hide_unknown_client: bool = False,
    ) -> OAuthClient:
        try:
            client = await self.registry.get(client_id)
        except OAuthStoreError as exc:
            raise self._unavailable() from exc
        if client is None:
            if hide_unknown_client:
                raise OAuthProtocolError(
                    "invalid_grant",
                    "refresh token is invalid",
                )
            raise OAuthProtocolError("invalid_client", "client_id is not registered")
        if grant_type not in client.grant_types:
            raise OAuthProtocolError(
                "unauthorized_client",
                "client is not registered for this grant type",
            )
        return client

    def _validated_scope(self, raw_scope: str) -> str:
        requested = frozenset(item for item in raw_scope.split() if item)
        if requested != self.settings.required_scopes:
            raise OAuthProtocolError(
                "invalid_scope",
                "requested scope is not supported",
            )
        return " ".join(sorted(requested))

    @staticmethod
    def _hash_secret(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _pkce_challenge(verifier: str) -> str:
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

    def _authorization_code_binding_is_valid(
        self,
        authorization_code: OAuthAuthorizationCode,
    ) -> bool:
        stored_scope = frozenset(
            item for item in authorization_code.scope.split() if item
        )
        return (
            authorization_code.resource == self.settings.mcp_public_url
            and stored_scope == self.settings.required_scopes
        )

    @staticmethod
    def _transaction_protection_context(
        transaction: OAuthTransaction,
    ) -> dict[str, object]:
        return {
            "artifact": "oauth_transaction",
            "issuer": transaction.issuer,
            "transaction_id_hash": transaction.transaction_id_hash,
            "client_id": transaction.client_id,
            "redirect_uri": transaction.redirect_uri,
            "workbuddy_state": transaction.workbuddy_state,
            "entra_state_hash": transaction.entra_state_hash,
            "code_challenge": transaction.code_challenge,
            "scope": transaction.scope,
            "resource": transaction.resource,
            "created_at": transaction.created_at,
            "expires_at": transaction.expires_at,
        }

    @staticmethod
    def _authorization_code_protection_context(
        authorization_code: OAuthAuthorizationCode,
    ) -> dict[str, object]:
        return {
            "artifact": "oauth_authorization_code",
            "issuer": authorization_code.issuer,
            "code_hash": authorization_code.code_hash,
            "client_id": authorization_code.client_id,
            "redirect_uri": authorization_code.redirect_uri,
            "scope": authorization_code.scope,
            "resource": authorization_code.resource,
            "code_challenge": authorization_code.code_challenge,
            "tenant_id": authorization_code.tenant_id,
            "user_id": authorization_code.user_id,
            "created_at": authorization_code.created_at,
            "expires_at": authorization_code.expires_at,
        }

    def _validate_upstream_authorization_uri(
        self,
        value: str,
        upstream_state: str,
    ) -> None:
        parsed = urlsplit(value)
        configured_authority = urlsplit(self.settings.entra_authority)
        try:
            parsed_port = parsed.port
            configured_port = configured_authority.port
        except ValueError:
            parsed_port = object()
            configured_port = None
        state_values = [
            query_value
            for query_name, query_value in parse_qsl(
                parsed.query,
                keep_blank_values=True,
            )
            if query_name == "state"
        ]
        if (
            parsed.scheme.casefold() != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.fragment
            or parsed.hostname.casefold()
            != (configured_authority.hostname or "").casefold()
            or parsed_port != configured_port
            or state_values != [upstream_state]
        ):
            raise OAuthProtocolError(
                "temporarily_unavailable",
                "Microsoft authorization is unavailable",
                status_code=503,
            )

    @staticmethod
    def _append_authorization_result(
        redirect_uri: str,
        code: str,
        state: str,
    ) -> str:
        return OAuthAuthorizationService._append_redirect_parameters(
            redirect_uri,
            [("code", code), ("state", state)],
        )

    def _callback_error_redirect(
        self,
        transaction: OAuthTransaction,
        error: str,
    ) -> str:
        return self._append_redirect_parameters(
            transaction.redirect_uri,
            [("error", error), ("state", transaction.workbuddy_state)],
        )

    @staticmethod
    def _append_redirect_parameters(
        redirect_uri: str,
        result_parameters: list[tuple[str, str]],
    ) -> str:
        parsed = urlsplit(redirect_uri)
        query = parse_qsl(parsed.query, keep_blank_values=True)
        if any(name in _RESERVED_REDIRECT_PARAMETERS for name, _ in query):
            raise OAuthProtocolError(
                "invalid_request",
                "registered redirect_uri contains reserved parameters",
            )
        query.extend(result_parameters)
        return urlunsplit(
            (
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                urlencode(query),
                "",
            )
        )

    @staticmethod
    def _unavailable() -> OAuthProtocolError:
        return OAuthProtocolError(
            "temporarily_unavailable",
            "OAuth authorization is temporarily unavailable",
            status_code=503,
        )
