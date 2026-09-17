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
- `POST /oauth/token` for `grant_type=authorization_code`
- issuer-bound SQLite persistence at `OAUTH_DATABASE_PATH`

The token endpoint returns the validated Entra access token for App A so the
existing JWT validator and OBO path remain authoritative. It does not mint a new
MCP JWT. The Entra authorization-flow object, Token A and the transient MSAL
cache are encrypted under a process-local key while bound to the short-lived
transaction or local authorization code; they never appear in the browser
redirect.

Persistent encryption keys, opaque local refresh tokens, rotation, replay
protection and restart-safe refresh sessions are implemented in the next phase.
Until that phase and real WorkBuddy acceptance are complete, keep
`OAUTH_ENABLED=false` outside controlled integration development.
Controlled PR3 integration must use one server process and one replica because
the temporary key is process-local. PR4 removes this restriction.

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
   and PKCE verification. A second redemption returns `invalid_grant`.

## Public URL configuration

Set the externally reachable URLs explicitly:

    MCP_PUBLIC_URL=https://mcp.example.com/mcp/
    OAUTH_ISSUER_URL=https://mcp.example.com

They must match the reverse-proxy routes exactly. The application does not derive
them from request headers. Production values require HTTPS; HTTP is accepted only
for loopback development.

## Dynamic registration policy

Registration accepts RFC 7591-style public-client metadata and returns a generated
client ID plus the exact registered redirect list. It never returns a client
secret. Supported redirect forms are:

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
