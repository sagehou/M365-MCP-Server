"""Persistent AEAD protection for OAuth token material."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from typing import Any, Protocol

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


_AAD_PREFIX = b"m365-mcp-oauth-v2\x00"
_VERSION = b"\x02"


class TokenProtectionError(Exception):
    """Raised when protected OAuth token material cannot be opened safely."""


class TokenProtector(Protocol):
    def seal(
        self,
        payload: Mapping[str, object],
        *,
        context: Mapping[str, object],
    ) -> bytes: ...

    def open(
        self,
        protected: bytes,
        *,
        context: Mapping[str, object],
    ) -> dict[str, Any]: ...


class AesGcmTokenProtector:
    """Encrypt OAuth material with the configured restart-stable key."""

    def __init__(self, key: bytes | None = None) -> None:
        selected_key = key if key is not None else AESGCM.generate_key(bit_length=256)
        if len(selected_key) != 32:
            raise ValueError("OAuth token protection key must be 256 bits")
        self._cipher = AESGCM(selected_key)

    def seal(
        self,
        payload: Mapping[str, object],
        *,
        context: Mapping[str, object],
    ) -> bytes:
        try:
            plaintext = json.dumps(
                dict(payload),
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
            nonce = os.urandom(12)
            return _VERSION + nonce + self._cipher.encrypt(
                nonce,
                plaintext,
                self._aad(context),
            )
        except Exception as exc:
            raise TokenProtectionError("OAuth token material is invalid") from exc

    def open(
        self,
        protected: bytes,
        *,
        context: Mapping[str, object],
    ) -> dict[str, Any]:
        if len(protected) < 30 or protected[:1] != _VERSION:
            raise TokenProtectionError("OAuth token material is invalid")
        nonce = protected[1:13]
        try:
            plaintext = self._cipher.decrypt(
                nonce,
                protected[13:],
                self._aad(context),
            )
            payload = json.loads(plaintext)
        except (
            InvalidTag,
            TypeError,
            ValueError,
            json.JSONDecodeError,
            UnicodeDecodeError,
        ) as exc:
            raise TokenProtectionError("OAuth token material is invalid") from exc
        if not isinstance(payload, dict):
            raise TokenProtectionError("OAuth token material is invalid")
        return payload

    @staticmethod
    def _aad(context: Mapping[str, object]) -> bytes:
        return _AAD_PREFIX + json.dumps(
            dict(context),
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")


class EphemeralTokenProtector(AesGcmTokenProtector):
    """Test/development adapter that generates a process-local key by default."""
