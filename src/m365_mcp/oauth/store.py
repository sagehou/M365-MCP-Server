"""Persistent OAuth store seam and SQLite adapter."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sqlite3
from typing import Protocol

from .models import OAuthClient


class OAuthClientAlreadyExistsError(Exception):
    """Raised when an issuer/client identifier pair already exists."""


class OAuthStoreError(Exception):
    """Raised when OAuth persistence is unavailable without exposing internals."""


class OAuthStore(Protocol):
    async def initialize(self) -> None: ...

    async def create_client(self, client: OAuthClient) -> None: ...

    async def get_client(self, issuer: str, client_id: str) -> OAuthClient | None: ...


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
                PRAGMA user_version = 1;
                """
            )

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
