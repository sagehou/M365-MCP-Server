"""Persistent OAuth store seam and SQLite adapter."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sqlite3
from typing import Protocol

from .models import OAuthAuthorizationCode, OAuthClient, OAuthTransaction


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
            connection.execute("PRAGMA user_version = 2")

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
            self._delete_terminal_authorization_rows(
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
            self._delete_terminal_authorization_rows(
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

    @staticmethod
    def _delete_terminal_authorization_rows(
        connection: sqlite3.Connection,
        now: int,
    ) -> None:
        """Reclaim terminal short-lived rows before each new persisted flow."""

        connection.execute(
            """
            DELETE FROM oauth_transactions
            WHERE expires_at <= ? OR completed_at IS NOT NULL
            """,
            (now,),
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
