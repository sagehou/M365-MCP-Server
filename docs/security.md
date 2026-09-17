# Security Design

## Identity

Authentication is based on Microsoft Entra ID.

## Permissions

Preferred Graph permissions:

- User.Read
- Mail.ReadWrite
- Mail.Send (optional)

Avoid:

- Mail.Read.All
- Mail.ReadWrite.All
- Application permissions

## Tenant Isolation

The server validates:

- tenant id
- user id
- audience
- scopes

## Audit

Record:

- timestamp
- tenant
- user
- MCP tool
- operation result

Do not store:

- email body
- attachment content
- secrets
