**English** | [简体中文](../zh-CN/codex/002-entra-auth-obo.md)

# Task 002 - Entra Authentication and OBO

## Goal

Implement Microsoft Entra ID authentication and Microsoft Graph On-Behalf-Of flow.

## Requirements

- Validate incoming JWT access tokens.
- Support tenant allowlist validation.
- Implement OBO token exchange.
- Acquire Microsoft Graph delegated tokens.
- Keep user identity from the original request.

## Security requirements

- Do not implement Application Permission mailbox access.
- Do not accept arbitrary user IDs from MCP tools.
- Validate tenant, audience, issuer, scopes.

## Deliverables

- Auth middleware
- OBO service
- Configuration model
- Authentication tests

## Non goals

- No mail tools implementation.
- No attachment processing.
