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
- `GET /oauth/callback` backed by MSAL Python and a separate upstream state
- one-time local authorization codes with a maximum ten-minute lifetime
- `POST /oauth/token` for `grant_type=authorization_code` and `refresh_token`
- opaque local refresh tokens stored only as SHA-256 hashes
- encrypted persistent MSAL cache with one-time token rotation and family replay revocation
- restart-safe sessions in the configured SQLite database
- issuer-bound SQLite persistence at `OAUTH_DATABASE_PATH`

The token endpoint returns the validated Entra access token for the single
`M365-MCP-Server` App Registration so the
existing JWT validator and OBO path remain authoritative. It does not mint a new
MCP JWT. The Entra authorization-flow object, Token A and MSAL cache are encrypted
with AES-256-GCM under `OAUTH_ENCRYPTION_KEY`; record-specific authenticated
context binds each ciphertext to immutable OAuth metadata. Sensitive token
material never appears in the browser redirect or plaintext SQLite columns.

Keep `OAUTH_ENABLED=false` outside controlled integration development until the
real WorkBuddy acceptance gate is complete. Restarted or replacement processes
must use the same SQLite database and encryption key. Distributed or multi-host
session storage is outside the v0.1 scope.

## Connector package

The repository includes the package template under `workbuddy/` using the
[official WorkBuddy connector structure](https://open.workbuddy.cn/en/docs/connector):

    workbuddy/
    |-- connector-meta.json
    |-- mcp.json
    |-- icon.svg
    `-- skills/
        |-- outlook-mail/SKILL.md
        |-- outlook-attachments/SKILL.md
        `-- outlook-mail-management/SKILL.md

The package deliberately omits `auth_mode`, request headers, token fields and a
`token-schema.json`. WorkBuddy must discover and complete the server's standard
MCP OAuth flow as a public client; users must not paste access tokens or receive
an Entra client secret. The metadata requires WorkBuddy 4.24.0 because it uses
the current bilingual name and example fields. Each Skill uses the current
[WorkBuddy Skill format](https://open.workbuddy.cn/en/docs/skill) and exposes
only its required tools.

`workbuddy/mcp.json` is a source-controlled deployment template. Before creating
the submission archive, replace `${M365_MCP_URL}` with the exact production HTTPS
`/mcp/` URL used by `MCP_PUBLIC_URL`. Do not add an Authorization header or switch
the connector to user-supplied token mode. Zip the contents of `workbuddy/` so
`connector-meta.json`, `mcp.json`, `icon.svg` and `skills/` are at the archive
root.

## Authorization flow

1. WorkBuddy dynamically registers an exact redirect URI.
2. `/oauth/authorize` validates the client, redirect, requested scope, resource,
   response type and S256 challenge.
3. The server stores WorkBuddy state and generates a different cryptographically
   random Entra state before starting MSAL authorization.
4. `/oauth/callback` atomically consumes the transaction, lets MSAL exchange
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

- `workbuddy://workbuddy/<non-empty-path>` such as
  `workbuddy://workbuddy/mcp/test/oauth/callback`
- `http://localhost:<port>/<non-empty-path>`
- `http://127.0.0.1:<port>/<non-empty-path>`
- `http://[::1]:<port>/<non-empty-path>`
- explicitly registered HTTPS redirects

Public HTTP redirects, malformed private schemes, fragments, wildcard matching,
prefix matching and unregistered redirects are rejected. Loopback HTTP redirects
must include an explicit port. Every authorization request must exactly match a
stored redirect URI. Registration state is bound to the configured issuer and
persists in the `/data` Compose volume.

## Single Entra application

Create only one App Registration named `M365-MCP-Server`. It serves both as the
protected resource/OBO middle tier and as the confidential interactive OAuth
client:

    CLIENT_ID=<m365-mcp-server-client-id>
    CLIENT_SECRET=<m365-mcp-server-secret>

Register this production Web redirect URI on that app:

    https://mcp.example.com/oauth/callback

For local development, register this separate loopback Web redirect URI:

    http://localhost:8000/oauth/callback

MSAL requests the same app's `api://<CLIENT_ID>/access_as_user` scope and adds
its reserved OpenID scopes as required. The interactive client does not request
a Graph token directly; after Token A is accepted, the MCP API performs the
existing OBO exchange. There is no second Entra app or second credential set.

## Automated and live acceptance boundary

GitHub Actions runs a mocked WorkBuddy end-to-end test against the real
ASGI/FastMCP application. It parses the 401 `resource_metadata` challenge,
discovers both metadata documents, dynamically registers the WorkBuddy private
callback, completes S256 authorization through a mocked Entra callback, exchanges
the local code, initializes MCP, rotates the refresh token and lists tools with
the refreshed access token. This proves the repository flow without contacting a
tenant or changing a mailbox.

Before enabling OAuth in production or calling v0.1 ready, perform and record all
of these live checks with the exact release image and connector archive:

1. Install the connector in WorkBuddy 4.24.0 or later and verify that no token
   entry form appears.
2. Connect from a clean WorkBuddy profile. Verify browser launch, Microsoft login
   and consent, then return to WorkBuddy through
   `workbuddy://workbuddy/mcp/connector%3Asagehou-m365-mcp-server/oauth/callback`.
3. Initialize MCP, list exactly eight tools, then exercise search, single-message
   read, attachment extraction and deliberate mutations on disposable messages.
   Verify the new IDs returned by move and archive are used afterward.
4. Repeat with a second user and verify that neither user can access the other's
   mailbox content.
5. Let Token A expire (or use an approved short-lived test policy), then verify
   WorkBuddy refreshes and retries transparently without another token prompt.
6. Restart the server while preserving `OAUTH_DATABASE_PATH` and
   `OAUTH_ENCRYPTION_KEY`; verify the WorkBuddy session can refresh afterward.
7. Complete the same flow in an allowed second tenant and record consent, issuer,
   audience and OBO results. Test consumer accounts separately only if the
   deployment intentionally supports them.
8. Confirm application, proxy and platform logs contain no authorization codes,
   access/refresh tokens, MSAL cache, client secrets, code verifiers, message
   bodies or attachment contents.

These live checks are manual release gates. Passing the mocked CI flow does not
mark them complete.
