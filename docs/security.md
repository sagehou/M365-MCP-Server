# Security Design

## Identity

Authentication is based on Microsoft Entra ID delegated access tokens.

The server validates the token signature using the OpenID Connect discovery
document and published signing keys before accepting any MCP request.

## Permissions

Preferred Graph permissions:

- User.Read
- Mail.ReadWrite
- Mail.Send (optional)

Avoid:

- Mail.Read.All
- Mail.ReadWrite.All
- Application permissions

## Token validation

The protected `/mcp/` endpoint requires:

- a bearer access token issued for this API audience
- a tenant present in `ALLOWED_TENANTS`
- an exact issuer derived from the token tenant and Entra metadata
- a delegated `scp` claim containing `REQUIRED_SCOPES`

The server rejects Graph-destined tokens, application-only tokens with only
`roles`, unknown tenants, invalid signatures, expired tokens, and mismatched
issuers.

## Tenant Isolation

The server validates:

- tenant id
- user object id (or subject when object id is unavailable)
- audience
- issuer
- delegated scopes

Downstream operations must use the validated tenant-qualified identity and must
not accept arbitrary mailbox or user identifiers from MCP tools.

## On-Behalf-Of

Graph tokens are acquired with MSAL's On-Behalf-Of flow from the validated
inbound assertion. The service never exchanges a caller-supplied user ID and
does not use Graph application permissions for mailbox access.

## Audit

Record:

- timestamp
- tenant
- user
- MCP tool
- operation result

Mail attachment listing removes `contentBytes` before returning data to
MCP clients. The mail_read_attachment tool decodes file attachments only on
the server, applies byte and extracted-text limits, and returns metadata plus
text for PDF, DOCX, XLSX, PPTX, and TXT files. It never returns the Graph
contentBytes base64 field to an MCP client.

Do not store:

- email body in logs
- attachment content in logs
- access tokens
- secrets
