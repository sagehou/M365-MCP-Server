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
