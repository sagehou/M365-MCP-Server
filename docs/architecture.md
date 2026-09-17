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
