**English** | [简体中文](zh-CN/architecture.md)

# Architecture

## Overview

M365 MCP Server is a self-hosted MCP gateway for Microsoft 365.

Goals:

- Enterprise multi-user support
- Microsoft Entra ID authentication
- Delegated permissions
- OAuth 2.0 / OAuth 2.1 compatible integration
- Microsoft Graph OBO flow

## Request Flow

```
MCP Client
    |
    | User token
    v
M365 MCP Server
    |
    | Validate token
    |
    | OBO exchange
    v
Microsoft Graph
    |
    v
User mailbox
```

## Security Principles

- Never use Graph Application permissions for mailbox access
- Never accept arbitrary mailbox/user identifiers from tools
- Always operate with /me unless explicitly implementing shared mailbox support
- Validate tenant and user identity from token claims
## Integration Boundaries

The Graph client accepts a validated `AuthContext`, obtains a delegated
Microsoft Graph token through the Entra OBO service, and only permits relative
paths under `/me`. It handles Graph throttling and transient failures before
returning a sanitized response or error to the service layer.

The mail service is an internal layer behind eight registered MCP mail tools.
The HTTP transport is stateless: every call carries and validates its own token,
and no MCP session stores a caller identity. MSAL runs off the ASGI event loop.
Attachment parsing runs in short-lived Linux workers, with resource limits.
Graph transport, mailbox policy and HTTP integration have separate tests.

## OAuth authorization broker

OAuth is a separate deep module in front of the existing resource server. Its
interface exposes discovery, public-client registration and authorization-code
operations while hiding redirect policy, state binding, PKCE, MSAL and SQLite
details. `DynamicClientRegistry` owns redirect validation and issuer binding;
`OAuthAuthorizationService` owns the interactive flow; routes are HTTP adapters
and do not know the SQLite schema.

`SQLiteOAuthStore` is the persistence adapter at the internal store seam. It
persists registered clients, atomically consumes Entra transactions and local
authorization codes, and compare-and-swap rotates issuer-bound refresh sessions.
Spent handle hashes remain linked to each rotation family so replay atomically
revokes the active successor instead of only rejecting the stale request. Unknown
handles take a read-only rejection path, while an atomically enforced per-session
rotation counter bounds retained replay history.
`MsalEntraAuthorizationBroker` is the true-external adapter for App B, while the
existing `JwtValidator` revalidates Token A for App A before any local code is
created. `OAuthSessionService` hides opaque-token hashing, encrypted MSAL cache
persistence, silent refresh, identity rebinding checks, revocation and one-time
rotation behind a small interface. The authorization-flow object, Token A and
MSAL cache use AES-256-GCM under the configured restart-stable key, with
record-specific authenticated context that binds ciphertext to OAuth metadata,
including the current local-handle hash and rotation count.

The public resource and issuer URLs come only from `MCP_PUBLIC_URL` and
`OAUTH_ISSUER_URL`; request Host and forwarded-host headers never define this
security metadata. The module remains disabled by default until real WorkBuddy
acceptance is complete.
