**English** | [简体中文](zh-CN/workbuddy-oauth.md)

# WorkBuddy OAuth

## Current phase

The server currently implements discovery, registration and the interactive
authorization-code flow:

- `GET /.well-known/oauth-protected-resource`
- a `resource_metadata` link in unauthenticated `/mcp/` bearer challenges
- `GET /.well-known/oauth-authorization-server`
- `POST /oauth/register` for public clients without a client secret
- `GET /oauth/authorize` with exact client/redirect/resource binding and S256 PKCE
- `GET /oauth/callback/entra` backed by MSAL Python and a separate upstream state
- one-time local authorization codes with a maximum ten-minute lifetime
- `POST /oauth/token` for `grant_type=authorization_code` and `refresh_token`
- opaque local refresh tokens stored only as SHA-256 hashes
- encrypted persistent MSAL cache with one-time token rotation and family replay revocation
- restart-safe sessions in the configured SQLite database
- issuer-bound SQLite persistence at `OAUTH_DATABASE_PATH`

The token endpoint returns the validated Entra access token for App A so the
existing JWT validator and OBO path remain authoritative. It does not mint a new
MCP JWT. The Entra authorization-flow object, Token A and MSAL cache are encrypted
with AES-256-GCM under `OAUTH_ENCRYPTION_KEY`; record-specific authenticated
context binds each ciphertext to immutable OAuth metadata. Sensitive token
material never appears in the browser redirect or plaintext SQLite columns.

Keep `OAUTH_ENABLED=false` outside controlled integration development until the
real WorkBuddy acceptance gate is complete. Restarted or replacement processes
must use the same SQLite database and encryption key. Distributed or multi-host
session storage is outside the v0.1 scope.

## Authorization flow

1. WorkBuddy dynamically registers an exact redirect URI.
2. `/oauth/authorize` validates the client, redirect, requested scope, resource,
   response type and S256 challenge.
3. The server stores WorkBuddy state and generates a different cryptographically
   random Entra state before starting MSAL authorization.
4. `/oauth/callback/entra` atomically consumes the transaction, lets MSAL exchange
   the Microsoft code, then re-validates Token A through the existing
   `JwtValidator`.
5. The browser receives only `code=<local-code>&state=<original-state>` at the
   exact registered redirect.
6. `/oauth/token` atomically redeems the local code after exact client, redirect
   and PKCE verification. It returns Token A plus a random local refresh token;
   a second code redemption returns `invalid_grant`.

## Refresh flow

1. WorkBuddy sends `grant_type=refresh_token`, its public `client_id` and the
   current opaque local refresh token.
2. The server hashes the handle and resolves an unexpired, non-revoked session
   bound to the configured issuer and client.
3. The encrypted MSAL cache is opened and MSAL performs a forced silent token
   acquisition. The resulting Token A is revalidated and must identify the same
   tenant and user as the original session.
4. SQLite compare-and-swap replaces the old handle hash and encrypted cache with
   the new values. The consumed hash remains linked to the rotation family.
5. WorkBuddy receives Token A and a new opaque refresh token. Reuse of any
   consumed value returns `invalid_grant` and revokes the active family, including
   an attacker-first successor.

Microsoft revocation, an unusable cache or identity mismatch revokes the local
session. A transient upstream or identity-metadata outage returns
`temporarily_unavailable` without consuming the current local refresh token.

## Public URL configuration

Set the externally reachable URLs explicitly:

    MCP_PUBLIC_URL=https://mcp.example.com/mcp/
    OAUTH_ISSUER_URL=https://mcp.example.com
    OAUTH_DATABASE_PATH=/data/oauth.db
    OAUTH_ENCRYPTION_KEY=<base64-encoded-32-random-bytes>
    OAUTH_REFRESH_TOKEN_TTL_DAYS=30
    OAUTH_REFRESH_MAX_ROTATIONS=10000

The public URLs must match the reverse-proxy routes exactly. The application does
not derive them from request headers. Production values require HTTPS; HTTP is
accepted only for loopback development. The encryption key must remain outside
the database, image, repository and logs; losing it invalidates stored sessions.
The rotation limit bounds replay-history growth for one session; reaching it
revokes the session and requires interactive authorization again.

## Dynamic registration policy

Registration accepts RFC 7591-style public-client metadata and returns a generated
client ID plus the exact registered redirect list. It never returns a client
secret. Authorization-code clients receive a refresh token only when
`refresh_token` is present in their registered `grant_types`; refresh requests
from other clients return `unauthorized_client`. Supported redirect forms are:

- `workbuddy://workbuddy/mcp/connector%3A<source>/oauth/callback`
- `http://localhost:<port>/oauth/callback`
- `http://127.0.0.1:<port>/oauth/callback`
- `http://[::1]:<port>/oauth/callback`
- explicitly registered HTTPS redirects

Public HTTP redirects, malformed private schemes, fragments, wildcard matching,
prefix matching and unregistered redirects are rejected. Registration state is
bound to the configured issuer and persists in the `/data` Compose volume.

## Entra application separation

The existing App A remains the protected resource/OBO application. App B is the
separate confidential interactive OAuth broker:

    ENTRA_BROKER_CLIENT_ID=<app-b-client-id>
    ENTRA_BROKER_CLIENT_SECRET=<app-b-secret>
    ENTRA_BROKER_AUTHORITY=https://login.microsoftonline.com/organizations

Register exactly this App B redirect URI:

    https://mcp.example.com/oauth/callback/entra

App B requests App A's `api://<CLIENT_ID>/access_as_user` scope. MSAL adds its
reserved OpenID scopes as required. The broker does not request a Graph token;
the MCP API performs the existing OBO exchange after accepting Token A. Do not
reuse App A's client credential for App B and do not add the broker callback to
App A.
