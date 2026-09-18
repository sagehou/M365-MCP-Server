**English** | [简体中文](README.zh-CN.md)

# M365 MCP Server

Enterprise Microsoft 365 MCP Server based on Microsoft Graph API.

## Overview

This project provides an MCP interface for AI agents (WorkBuddy, Claude, Cursor, etc.) to access Microsoft 365 services securely.

Design goals:

- Self-hosted deployment
- Microsoft Entra ID authentication
- Delegated permission model
- On-Behalf-Of (OBO) flow to Microsoft Graph
- User identity isolation
- No additional SaaS dependency

## Planned capabilities

### Phase 1: Outlook Mail

- Search emails
- Read email content
- List attachments
- Extract attachment text
- Mark read/unread
- Move emails
- Archive emails
- Categories
- Draft management

### Future

- Calendar
- OneDrive
- SharePoint
- Teams

## Architecture

```
MCP Client
   |
   | Entra delegated bearer token
   v
M365 MCP Server
   |
   | OBO Flow
   v
Microsoft Graph
   |
   v
Microsoft 365
```

## Development Status

Tasks 001–007 have implementations and CI coverage, including all eight mail
tools. GitHub Actions is the only build/test environment. The release workflow
can publish reviewed stable version tags; a configured workflow is not evidence
that an image has been released. Select an existing GHCR version before deployment.

The server accepts an Entra delegated bearer token obtained by the client.
OAuth discovery, public-client registration, MSAL-backed interactive sign-in,
S256 PKCE and one-time local authorization-code exchange are available behind
`OAUTH_ENABLED`. Persistent encrypted MSAL cache, opaque local refresh tokens,
one-time rotation, replay rejection and restart-safe SQLite sessions are
implemented. The `workbuddy/` package follows the official connector layout, and
CI exercises a complete mocked WorkBuddy discovery, DCR, authorization-code,
authenticated MCP and refresh flow. The flag remains false until real WorkBuddy
acceptance is complete.
Drafts, OCR, shared mailboxes, RBAC,
rate limiting and other M365 workloads are not implemented. No live-tenant
acceptance is implied by mocked Graph/OBO/OAuth tests.
See [review status](docs/review-status.md), the
[runtime dependency audit](docs/runtime-dependency-audit.md), and the
[WorkBuddy OAuth guide](docs/workbuddy-oauth.md).

## Deploy

Configure Microsoft Entra before deploying. The step-by-step portal guide covers
single-tenant and cross-tenant registration, `access_as_user`, Graph delegated
permissions, OBO credentials, target-tenant consent and an optional test client:

- [Microsoft Entra app registration guide](docs/entra-app-registration.md)

Then follow [the deployment checklist](docs/deployment.md):

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d
```

The application exposes:

- `GET /health` (also available as `/healthz`) for process liveness only
- `/mcp/` for the protected FastMCP Streamable HTTP endpoint

Configure `CLIENT_ID`, exactly one client credential, `ALLOWED_TENANTS`, and
`REQUIRED_SCOPES` before using `/mcp/`. `ALLOWED_TENANTS` accepts a comma-separated
list of tenant IDs or `*` for any valid Microsoft tenant; an empty value fails
closed. `AUDIENCE` is optional and, when omitted, the server accepts the API
client ID and `api://<client-id>` forms. The protected endpoint exposes only the
current user's delegated Outlook mailbox operations.

Tests and the Docker build run in GitHub Actions.
