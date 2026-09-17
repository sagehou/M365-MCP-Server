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

Project initialization stage.
