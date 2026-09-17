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
   | OAuth 2.1
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

Task 004 is implemented: the MCP endpoint exposes identity-scoped Outlook
mail tools for search, read, attachment metadata, read state, archive, move, and
categories. Attachment content extraction remains in the next task.

## Run locally

Install the package with Python 3.12 and start the HTTP server:

```bash
python -m pip install -e ".[dev]"
python -m m365_mcp
```

The application exposes:

- `GET /health` (also available as `/healthz`) for readiness checks
- `/mcp/` for the protected FastMCP Streamable HTTP endpoint

Configure `CLIENT_ID`, exactly one client credential, `ALLOWED_TENANTS`,
`AUDIENCE`, and `REQUIRED_SCOPES` before using `/mcp/`. Task 002 does not
expose Microsoft Graph or mailbox operations.

Tests and the Docker build run in GitHub Actions.
