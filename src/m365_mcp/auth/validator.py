"""Microsoft Entra access-token validation."""

import json
import re
import uuid
from collections.abc import Mapping
from typing import Any

import jwt
from jwt.exceptions import PyJWTError

from .errors import InsufficientScopeError, TokenValidationError
from .models import UserIdentity
from .oidc import OidcDocumentProvider
from .settings import Settings


class JwtValidator:
    """Validate delegated v2.0 JWTs against Entra metadata and JWKS."""

    def __init__(
        self,
        settings: Settings,
        documents: OidcDocumentProvider | None = None,
    ) -> None:
        self.settings = settings
        self.documents = documents or OidcDocumentProvider(settings)

    async def validate(self, token: str) -> UserIdentity:
        self.settings.validate_auth_configuration()
        header = self._read_header(token)
        if header.get("alg") != "RS256":
            raise TokenValidationError("Unsupported access-token algorithm")
        key_id = header.get("kid")
        if not isinstance(key_id, str) or not key_id:
            raise TokenValidationError("Access token has no signing-key id")

        unverified_claims = self._read_unverified_claims(token)
        tenant_id = self._tenant_from_claims(unverified_claims)
        configuration = await self.documents.configuration()
        signing_key = await self._find_key(key_id)
        public_key = self._public_key(signing_key)
        claims = self._decode(token, public_key)

        if claims.get("tid") != tenant_id:
            raise TokenValidationError("Access-token tenant changed during validation")
        issuer = claims.get("iss")
        if issuer != self._expected_issuer(configuration, tenant_id):
            raise TokenValidationError("Access-token issuer is invalid")
        self._validate_key_issuer(signing_key, issuer, tenant_id)

        scopes = self._scopes(claims)
        if not self.settings.required_scopes.issubset(scopes):
            raise InsufficientScopeError(self.settings.required_scopes)

        subject = claims.get("sub")
        user_id = claims.get("oid") or subject
        if not isinstance(subject, str) or not subject:
            raise TokenValidationError("Access token has no subject")
        if not isinstance(user_id, str) or not user_id:
            raise TokenValidationError("Access token has no user object id")

        audience = claims.get("aud")
        if not isinstance(audience, str):
            raise TokenValidationError("Access-token audience is invalid")
        return UserIdentity(
            tenant_id=tenant_id,
            user_id=user_id,
            subject=subject,
            issuer=issuer,
            audience=audience,
            scopes=scopes,
            username=self._optional_string(claims.get("preferred_username")),
            client_id=self._optional_string(claims.get("azp") or claims.get("appid")),
        )

    async def _find_key(self, key_id: str) -> Mapping[str, Any]:
        for refresh in (False, True):
            document = await self.documents.signing_keys(force_refresh=refresh)
            keys = document.get("keys")
            if not isinstance(keys, list):
                raise TokenValidationError("Identity signing-key document is invalid")
            for key in keys:
                if isinstance(key, Mapping) and key.get("kid") == key_id:
                    return key
        raise TokenValidationError("Access-token signing key is not published")

    def _decode(self, token: str, public_key: Any) -> Mapping[str, Any]:
        try:
            claims = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                audience=list(self.settings.expected_audiences),
                options={
                    "require": ["exp", "iss", "aud", "tid"],
                    "verify_iss": False,
                },
                leeway=30,
            )
        except PyJWTError as exc:
            raise TokenValidationError("Access token claims are invalid") from exc
        if not isinstance(claims, Mapping):
            raise TokenValidationError("Access token claims are invalid")
        return claims

    @staticmethod
    def _public_key(signing_key: Mapping[str, Any]) -> Any:
        try:
            return jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(signing_key))
        except (TypeError, ValueError, KeyError) as exc:
            raise TokenValidationError("Identity signing key is invalid") from exc

    def _tenant_from_claims(self, claims: Mapping[str, Any]) -> str:
        tenant_id = claims.get("tid")
        if not isinstance(tenant_id, str) or not tenant_id:
            raise TokenValidationError("Access token has no tenant id")
        try:
            uuid.UUID(tenant_id)
        except ValueError as exc:
            raise TokenValidationError("Access-token tenant id is invalid") from exc
        if not self.settings.is_allowed_tenant(tenant_id):
            raise TokenValidationError("Access-token tenant is not allowlisted")
        return tenant_id

    def _expected_issuer(
        self,
        configuration: Mapping[str, Any],
        tenant_id: str,
    ) -> str:
        issuer_template = configuration.get("issuer")
        if not isinstance(issuer_template, str) or not issuer_template:
            raise TokenValidationError("Identity metadata has no issuer")
        return re.sub(r"\{tenantid\}", tenant_id, issuer_template, flags=re.IGNORECASE)

    @staticmethod
    def _validate_key_issuer(
        signing_key: Mapping[str, Any], issuer: Any, tenant_id: str
    ) -> None:
        key_issuer = signing_key.get("issuer")
        if key_issuer is None:
            return
        if not isinstance(key_issuer, str):
            raise TokenValidationError("Identity signing-key issuer is invalid")
        expected = re.sub(r"\{tenantid\}", tenant_id, key_issuer, flags=re.IGNORECASE)
        if issuer != expected:
            raise TokenValidationError("Identity signing-key issuer does not match")

    def _scopes(self, claims: Mapping[str, Any]) -> frozenset[str]:
        raw_scopes = claims.get("scp")
        if not isinstance(raw_scopes, str):
            raise TokenValidationError("Delegated scope claim is missing")
        scopes = frozenset(item for item in raw_scopes.split() if item)
        if not scopes:
            raise TokenValidationError("Delegated scope claim is empty")
        return scopes

    @staticmethod
    def _read_header(token: str) -> Mapping[str, Any]:
        try:
            header = jwt.get_unverified_header(token)
        except PyJWTError as exc:
            raise TokenValidationError("Access token is malformed") from exc
        if not isinstance(header, Mapping):
            raise TokenValidationError("Access-token header is invalid")
        return header

    @staticmethod
    def _read_unverified_claims(token: str) -> Mapping[str, Any]:
        try:
            claims = jwt.decode(
                token,
                options={
                    "verify_signature": False,
                    "verify_exp": False,
                    "verify_aud": False,
                    "verify_iss": False,
                },
            )
        except PyJWTError as exc:
            raise TokenValidationError("Access token is malformed") from exc
        if not isinstance(claims, Mapping):
            raise TokenValidationError("Access-token claims are invalid")
        return claims

    @staticmethod
    def _optional_string(value: Any) -> str | None:
        return value if isinstance(value, str) and value else None
