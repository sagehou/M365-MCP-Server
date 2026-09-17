**English** | [简体中文](zh-CN/workbuddy-oauth.md)

# WorkBuddy OAuth

## Current phase

The server currently implements the discovery and registration foundation:

- `GET /.well-known/oauth-protected-resource`
- a `resource_metadata` link in unauthenticated `/mcp/` bearer challenges
- `GET /.well-known/oauth-authorization-server`
- `POST /oauth/register` for public clients without a client secret
- issuer-bound SQLite persistence at `OAUTH_DATABASE_PATH`

This phase does not yet implement `/oauth/authorize`, `/oauth/token`, Microsoft
interactive login, local authorization codes or refresh sessions. Keep
`OAUTH_ENABLED=false` outside controlled integration development.

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

The existing App A remains the protected resource/OBO application. A later phase
adds App B as the confidential interactive OAuth broker. Do not reuse App A's
client credential for App B and do not add the broker callback to App A.
