"""Persistent OAuth store seam and SQLite adapter."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sqlite3
from time import time
from typing import Protocol

from .models import OAuthAuthorizationCode, OAuthClient, OAuthSession, OAuthTransaction


_REVOKED_SESSION_RETENTION_SECONDS = 86_400


class OAuthClientAlreadyExistsError(Exception):
    """Raised when an issuer/client identifier pair already exists."""


class OAuthStoreError(Exception):
    """Raised when OAuth persistence is unavailable without exposing internals."""


class OAuthStore(Protocol):
    async def initialize(self) -> None: ...

    async def create_client(self, client: OAuthClient) -> None: ...

    async def get_client(self, issuer: str, client_id: str) -> OAuthClient | None: ...

    async def create_transaction(self, transaction: OAuthTransaction) -> None: ...

    async def consume_transaction(
        self,
        issuer: str,
        entra_state_hash: str,
        now: int,
    ) -> OAuthTransaction | None: ...

    async def create_authorization_code(
        self,
        authorization_code: OAuthAuthorizationCode,
    ) -> None: ...

    async def consume_authorization_code(
        self,
        issuer: str,
        code_hash: str,
        client_id: str,
        redirect_uri: str,
        code_challenge: str,
        now: int,
    ) -> OAuthAuthorizationCode | None: ...

    async def create_session(self, session: OAuthSession) -> None: ...

    async def get_refresh_session(
        self,
        issuer: str,
        refresh_token_hash: str,
        client_id: str,
        now: int,
    ) -> OAuthSession | None: ...

    async def rotate_refresh_session(
        self,
        issuer: str,
        session_id: str,
        client_id: str,
        current_refresh_token_hash: str,
        new_refresh_token_hash: str,
        encrypted_msal_cache: bytes,
        now: int,
    ) -> bool: ...

    async def revoke_refresh_session(
        self,
        issuer: str,
        session_id: str,
        client_id: str,
        current_refresh_token_hash: str,
        now: int,
    ) -> bool: ...


class SQLiteOAuthStore:
    """SQLite persistence with short, isolated transactions per operation."""

    def __init__(self, path: Path) -> None:
        self.path = path

    async def initialize(self) -> None:
        try:
            await asyncio.to_thread(self._initialize_sync)
        except sqlite3.Error as exc:
            raise OAuthStoreError("OAuth persistence initialization failed") from exc

    async def create_client(self, client: OAuthClient) -> None:
        try:
            await asyncio.to_thread(self._create_client_sync, client)
        except sqlite3.IntegrityError as exc:
            raise OAuthClientAlreadyExistsError from exc
        except sqlite3.Error as exc:
            raise OAuthStoreError("OAuth client persistence failed") from exc

    async def get_client(self, issuer: str, client_id: str) -> OAuthClient | None:
        try:
            return await asyncio.to_thread(self._get_client_sync, issuer, client_id)
        except sqlite3.Error as exc:
            raise OAuthStoreError("OAuth client lookup failed") from exc

    async def create_transaction(self, transaction: OAuthTransaction) -> None:
        try:
            await asyncio.to_thread(self._create_transaction_sync, transaction)
        except sqlite3.Error as exc:
            raise OAuthStoreError("OAuth transaction persistence failed") from exc

    async def consume_transaction(
        self,
        issuer: str,
        entra_state_hash: str,
        now: int,
    ) -> OAuthTransaction | None:
        try:
            return await asyncio.to_thread(
                self._consume_transaction_sync,
                issuer,
                entra_state_hash,
                now,
            )
        except sqlite3.Error as exc:
            raise OAuthStoreError("OAuth transaction lookup failed") from exc

    async def create_authorization_code(
        self,
        authorization_code: OAuthAuthorizationCode,
    ) -> None:
        try:
            await asyncio.to_thread(
                self._create_authorization_code_sync,
                authorization_code,
            )
        except sqlite3.Error as exc:
            raise OAuthStoreError("OAuth authorization-code persistence failed") from exc

    async def consume_authorization_code(
        self,
        issuer: str,
        code_hash: str,
        client_id: str,
        redirect_uri: str,
        code_challenge: str,
        now: int,
    ) -> OAuthAuthorizationCode | None:
        try:
            return await asyncio.to_thread(
                self._consume_authorization_code_sync,
                issuer,
                code_hash,
                client_id,
                redirect_uri,
                code_challenge,
                now,
            )
        except sqlite3.Error as exc:
            raise OAuthStoreError("OAuth authorization-code lookup failed") from exc

    async def create_session(self, session: OAuthSession) -> None:
        try:
            await asyncio.to_thread(self._create_session_sync, session)
        except sqlite3.Error as exc:
            raise OAuthStoreError("OAuth session persistence failed") from exc

    async def get_refresh_session(
        self,
        issuer: str,
        refresh_token_hash: str,
        client_id: str,
        now: int,
    ) -> OAuthSession | None:
        try:
            return await asyncio.to_thread(
                self._get_refresh_session_sync,
                issuer,
                refresh_token_hash,
                client_id,
                now,
            )
        except sqlite3.Error as exc:
            raise OAuthStoreError("OAuth session lookup failed") from exc

    async def rotate_refresh_session(
        self,
        issuer: str,
        session_id: str,
        client_id: str,
        current_refresh_token_hash: str,
        new_refresh_token_hash: str,
        encrypted_msal_cache: bytes,
        now: int,
    ) -> bool:
        try:
            return await asyncio.to_thread(
                self._rotate_refresh_session_sync,
                issuer,
                session_id,
                client_id,
                current_refresh_token_hash,
                new_refresh_token_hash,
                encrypted_msal_cache,
                now,
            )
        except sqlite3.Error as exc:
            raise OAuthStoreError("OAuth session rotation failed") from exc

    async def revoke_refresh_session(
        self,
        issuer: str,
        session_id: str,
        client_id: str,
        current_refresh_token_hash: str,
        now: int,
    ) -> bool:
        try:
            return await asyncio.to_thread(
                self._revoke_refresh_session_sync,
                issuer,
                session_id,
                client_id,
                current_refresh_token_hash,
                now,
            )
        except sqlite3.Error as exc:
            raise OAuthStoreError("OAuth session revocation failed") from exc

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize_sync(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS oauth_clients (
                    issuer TEXT NOT NULL,
                    client_id TEXT NOT NULL,
                    client_name TEXT NOT NULL,
                    redirect_uris_json TEXT NOT NULL,
                    application_type TEXT NOT NULL,
                    grant_types_json TEXT NOT NULL,
                    response_types_json TEXT NOT NULL,
                    token_endpoint_auth_method TEXT NOT NULL,
                    scope TEXT,
                    created_at INTEGER NOT NULL,
                    PRIMARY KEY (issuer, client_id)
                );

                CREATE TABLE IF NOT EXISTS oauth_transactions (
                    transaction_id_hash TEXT PRIMARY KEY,
                    issuer TEXT NOT NULL,
                    client_id TEXT NOT NULL,
                    redirect_uri TEXT NOT NULL,
                    workbuddy_state TEXT NOT NULL,
                    entra_state_hash TEXT NOT NULL UNIQUE,
                    code_challenge TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    resource TEXT NOT NULL,
                    protected_upstream_flow BLOB NOT NULL DEFAULT X'',
                    created_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL,
                    completed_at INTEGER
                );

                CREATE TABLE IF NOT EXISTS oauth_codes (
                    code_hash TEXT PRIMARY KEY,
                    issuer TEXT NOT NULL,
                    client_id TEXT NOT NULL,
                    redirect_uri TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    resource TEXT NOT NULL,
                    code_challenge TEXT NOT NULL,
                    encrypted_msal_cache BLOB NOT NULL,
                    tenant_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL,
                    used_at INTEGER
                );

                CREATE TABLE IF NOT EXISTS oauth_sessions (
                    id TEXT PRIMARY KEY,
                    issuer TEXT NOT NULL,
                    client_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    resource TEXT NOT NULL,
                    refresh_token_hash TEXT NOT NULL UNIQUE,
                    encrypted_msal_cache BLOB NOT NULL,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL,
                    revoked_at INTEGER,
                    rotation_family TEXT NOT NULL
                );
                """
            )
            transaction_columns = {
                row[1]
                for row in connection.execute("PRAGMA table_info(oauth_transactions)")
            }
            if "protected_upstream_flow" not in transaction_columns:
                connection.execute(
                    "ALTER TABLE oauth_transactions "
                    "ADD COLUMN protected_upstream_flow BLOB NOT NULL DEFAULT X''"
                )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS oauth_sessions_expires_at_idx "
                "ON oauth_sessions(expires_at)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS oauth_sessions_revoked_at_idx "
                "ON oauth_sessions(revoked_at)"
            )
            self._delete_terminal_oauth_rows(connection, int(time()))
            connection.execute("PRAGMA user_version = 3")

    def _create_client_sync(self, client: OAuthClient) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO oauth_clients (
                    issuer, client_id, client_name, redirect_uris_json,
                    application_type, grant_types_json, response_types_json,
                    token_endpoint_auth_method, scope, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    client.issuer,
                    client.client_id,
                    client.client_name,
                    json.dumps(client.redirect_uris),
                    client.application_type,
                    json.dumps(client.grant_types),
                    json.dumps(client.response_types),
                    client.token_endpoint_auth_method,
                    client.scope,
                    client.created_at,
                ),
            )

    def _get_client_sync(self, issuer: str, client_id: str) -> OAuthClient | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM oauth_clients WHERE issuer = ? AND client_id = ?",
                (issuer, client_id),
            ).fetchone()
        if row is None:
            return None
        return OAuthClient(
            issuer=row["issuer"],
            client_id=row["client_id"],
            client_name=row["client_name"],
            redirect_uris=tuple(json.loads(row["redirect_uris_json"])),
            application_type=row["application_type"],
            grant_types=tuple(json.loads(row["grant_types_json"])),
            response_types=tuple(json.loads(row["response_types_json"])),
            token_endpoint_auth_method=row["token_endpoint_auth_method"],
            scope=row["scope"],
            created_at=row["created_at"],
        )

    def _create_transaction_sync(self, transaction: OAuthTransaction) -> None:
        with self._connect() as connection:
            self._delete_terminal_oauth_rows(
                connection,
                transaction.created_at,
            )
            connection.execute(
                """
                INSERT INTO oauth_transactions (
                    transaction_id_hash, issuer, client_id, redirect_uri,
                    workbuddy_state, entra_state_hash, code_challenge, scope,
                    resource, protected_upstream_flow, created_at, expires_at,
                    completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    transaction.transaction_id_hash,
                    transaction.issuer,
                    transaction.client_id,
                    transaction.redirect_uri,
                    transaction.workbuddy_state,
                    transaction.entra_state_hash,
                    transaction.code_challenge,
                    transaction.scope,
                    transaction.resource,
                    transaction.protected_upstream_flow,
                    transaction.created_at,
                    transaction.expires_at,
                    transaction.completed_at,
                ),
            )

    def _consume_transaction_sync(
        self,
        issuer: str,
        entra_state_hash: str,
        now: int,
    ) -> OAuthTransaction | None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT * FROM oauth_transactions
                WHERE issuer = ? AND entra_state_hash = ?
                  AND completed_at IS NULL AND expires_at > ?
                """,
                (issuer, entra_state_hash, now),
            ).fetchone()
            if row is None:
                return None
            updated = connection.execute(
                """
                UPDATE oauth_transactions SET completed_at = ?
                WHERE transaction_id_hash = ? AND completed_at IS NULL
                """,
                (now, row["transaction_id_hash"]),
            )
            if updated.rowcount != 1:
                return None
            return self._transaction_from_row(row, completed_at=now)

    def _create_authorization_code_sync(
        self,
        authorization_code: OAuthAuthorizationCode,
    ) -> None:
        with self._connect() as connection:
            self._delete_terminal_oauth_rows(
                connection,
                authorization_code.created_at,
            )
            connection.execute(
                """
                INSERT INTO oauth_codes (
                    code_hash, issuer, client_id, redirect_uri, scope,
                    resource, code_challenge, encrypted_msal_cache,
                    tenant_id, user_id, created_at, expires_at, used_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    authorization_code.code_hash,
                    authorization_code.issuer,
                    authorization_code.client_id,
                    authorization_code.redirect_uri,
                    authorization_code.scope,
                    authorization_code.resource,
                    authorization_code.code_challenge,
                    authorization_code.encrypted_msal_cache,
                    authorization_code.tenant_id,
                    authorization_code.user_id,
                    authorization_code.created_at,
                    authorization_code.expires_at,
                    authorization_code.used_at,
                ),
            )

    def _consume_authorization_code_sync(
        self,
        issuer: str,
        code_hash: str,
        client_id: str,
        redirect_uri: str,
        code_challenge: str,
        now: int,
    ) -> OAuthAuthorizationCode | None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT * FROM oauth_codes
                WHERE issuer = ? AND code_hash = ?
                  AND client_id = ? AND redirect_uri = ?
                  AND code_challenge = ?
                  AND used_at IS NULL AND expires_at > ?
                """,
                (
                    issuer,
                    code_hash,
                    client_id,
                    redirect_uri,
                    code_challenge,
                    now,
                ),
            ).fetchone()
            if row is None:
                return None
            updated = connection.execute(
                """
                UPDATE oauth_codes SET used_at = ?
                WHERE code_hash = ? AND used_at IS NULL
                """,
                (now, code_hash),
            )
            if updated.rowcount != 1:
                return None
            return self._authorization_code_from_row(row, used_at=now)

    def _create_session_sync(self, session: OAuthSession) -> None:
        with self._connect() as connection:
            self._delete_terminal_oauth_rows(connection, session.created_at)
            connection.execute(
                """
                INSERT INTO oauth_sessions (
                    id, issuer, client_id, tenant_id, user_id, scope,
                    resource, refresh_token_hash, encrypted_msal_cache,
                    created_at, updated_at, expires_at, revoked_at,
                    rotation_family
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session.id,
                    session.issuer,
                    session.client_id,
                    session.tenant_id,
                    session.user_id,
                    session.scope,
                    session.resource,
                    session.refresh_token_hash,
                    session.encrypted_msal_cache,
                    session.created_at,
                    session.updated_at,
                    session.expires_at,
                    session.revoked_at,
                    session.rotation_family,
                ),
            )

    def _get_refresh_session_sync(
        self,
        issuer: str,
        refresh_token_hash: str,
        client_id: str,
        now: int,
    ) -> OAuthSession | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM oauth_sessions
                WHERE issuer = ? AND refresh_token_hash = ?
                  AND client_id = ? AND revoked_at IS NULL
                  AND expires_at > ?
                """,
                (issuer, refresh_token_hash, client_id, now),
            ).fetchone()
        return self._session_from_row(row) if row is not None else None

    def _rotate_refresh_session_sync(
        self,
        issuer: str,
        session_id: str,
        client_id: str,
        current_refresh_token_hash: str,
        new_refresh_token_hash: str,
        encrypted_msal_cache: bytes,
        now: int,
    ) -> bool:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            updated = connection.execute(
                """
                UPDATE oauth_sessions
                SET refresh_token_hash = ?, encrypted_msal_cache = ?,
                    updated_at = ?
                WHERE issuer = ? AND id = ? AND client_id = ?
                  AND refresh_token_hash = ? AND revoked_at IS NULL
                  AND expires_at > ?
                """,
                (
                    new_refresh_token_hash,
                    encrypted_msal_cache,
                    now,
                    issuer,
                    session_id,
                    client_id,
                    current_refresh_token_hash,
                    now,
                ),
            )
            self._delete_terminal_oauth_rows(connection, now)
            return updated.rowcount == 1

    def _revoke_refresh_session_sync(
        self,
        issuer: str,
        session_id: str,
        client_id: str,
        current_refresh_token_hash: str,
        now: int,
    ) -> bool:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            updated = connection.execute(
                """
                UPDATE oauth_sessions SET revoked_at = ?, updated_at = ?
                WHERE issuer = ? AND id = ? AND client_id = ?
                  AND refresh_token_hash = ? AND revoked_at IS NULL
                """,
                (
                    now,
                    now,
                    issuer,
                    session_id,
                    client_id,
                    current_refresh_token_hash,
                ),
            )
            return updated.rowcount == 1

    @staticmethod
    def _delete_terminal_oauth_rows(
        connection: sqlite3.Connection,
        now: int,
    ) -> None:
        """Reclaim terminal rows opportunistically during normal OAuth traffic."""

        connection.execute(
            """
            DELETE FROM oauth_transactions
            WHERE expires_at <= ? OR completed_at IS NOT NULL
            """,
            (now,),
        )
        connection.execute(
            """
            DELETE FROM oauth_sessions
            WHERE expires_at <= ?
               OR (revoked_at IS NOT NULL AND revoked_at <= ?)
            """,
            (now, now - _REVOKED_SESSION_RETENTION_SECONDS),
        )
        connection.execute(
            """
            DELETE FROM oauth_codes
            WHERE expires_at <= ? OR used_at IS NOT NULL
            """,
            (now,),
        )

    @staticmethod
    def _transaction_from_row(
        row: sqlite3.Row,
        *,
        completed_at: int | None = None,
    ) -> OAuthTransaction:
        return OAuthTransaction(
            transaction_id_hash=row["transaction_id_hash"],
            issuer=row["issuer"],
            client_id=row["client_id"],
            redirect_uri=row["redirect_uri"],
            workbuddy_state=row["workbuddy_state"],
            entra_state_hash=row["entra_state_hash"],
            code_challenge=row["code_challenge"],
            scope=row["scope"],
            resource=row["resource"],
            protected_upstream_flow=row["protected_upstream_flow"],
            created_at=row["created_at"],
            expires_at=row["expires_at"],
            completed_at=(
                completed_at if completed_at is not None else row["completed_at"]
            ),
        )

    @staticmethod
    def _authorization_code_from_row(
        row: sqlite3.Row,
        *,
        used_at: int | None = None,
    ) -> OAuthAuthorizationCode:
        return OAuthAuthorizationCode(
            code_hash=row["code_hash"],
            issuer=row["issuer"],
            client_id=row["client_id"],
            redirect_uri=row["redirect_uri"],
            scope=row["scope"],
            resource=row["resource"],
            code_challenge=row["code_challenge"],
            encrypted_msal_cache=row["encrypted_msal_cache"],
            tenant_id=row["tenant_id"],
            user_id=row["user_id"],
            created_at=row["created_at"],
            expires_at=row["expires_at"],
            used_at=used_at if used_at is not None else row["used_at"],
        )

    @staticmethod
    def _session_from_row(row: sqlite3.Row) -> OAuthSession:
        return OAuthSession(
            id=row["id"],
            issuer=row["issuer"],
            client_id=row["client_id"],
            tenant_id=row["tenant_id"],
            user_id=row["user_id"],
            scope=row["scope"],
            resource=row["resource"],
            refresh_token_hash=row["refresh_token_hash"],
            encrypted_msal_cache=row["encrypted_msal_cache"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            expires_at=row["expires_at"],
            revoked_at=row["revoked_at"],
            rotation_family=row["rotation_family"],
        )
