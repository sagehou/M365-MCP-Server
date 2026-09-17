**English** | [简体中文](zh-CN/security.md)

# Security Design

## Identity

Authentication is based on Microsoft Entra ID delegated access tokens.

The server validates the token signature using the OpenID Connect discovery
document and published signing keys before accepting any MCP request.

## Permissions

Preferred Graph permissions:

- User.Read
- Mail.ReadWrite

Avoid:

- Mail.Read.All
- Mail.ReadWrite.All
- Application permissions

## Token validation

The protected `/mcp/` endpoint requires:

- a bearer access token issued for this API audience
- a tenant explicitly present in `ALLOWED_TENANTS`, or `ALLOWED_TENANTS=*`
- an exact issuer derived from the token tenant and Entra metadata
- a delegated `scp` claim containing `REQUIRED_SCOPES`

`ALLOWED_TENANTS=*` removes only the local tenant allowlist restriction. It does
not bypass signature, issuer, audience, expiry, delegated-scope, or user-identity
validation. Personal Microsoft accounts are accepted only when the Entra App
Registration itself supports them; their tokens use the Microsoft consumer tenant.

The server rejects Graph-destined tokens, application-only tokens with only
`roles`, tenants outside an explicit allowlist, invalid signatures, expired tokens,
and mismatched issuers.

## Tenant Isolation

The server validates:

- tenant id
- user object id (or subject when object id is unavailable)
- audience
- issuer
- delegated scopes

Downstream operations must use the validated tenant-qualified identity and must
not accept arbitrary mailbox or user identifiers from MCP tools. Wildcard tenant
admission does not weaken this per-request identity isolation: the tenant ID remains
part of the validated identity and OBO authority.

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

## Logging policy

The audit logger records one event for each MCP mail-tool invocation. The event
is emitted as JSON to stderr and contains an explicit UTC timestamp, tenant ID, user ID,
tool name, success or failure outcome, duration, and safe exception type. It
does not accept or serialize tool arguments, Graph responses, email bodies,
attachment names, attachment bytes, access tokens, or secrets.

The tool boundary replaces exceptions before FastMCP logs them; raw provider or
parser messages are not exposed. Invalid protocol/schema requests that never
reach a registered mail-tool function are not mailbox audit events.
Graph response bytes are bounded before JSON parsing. Attachment base64 length
is checked before decoding; untrusted parsers run in resource-limited Linux
processes without inherited Entra secrets, with timeout/cancellation cleanup.

Email previews, message bodies, and extracted attachment text are returned with
an explicit untrusted-content marker. They are data for the agent to analyze,
not system, developer, user, or tool instructions. The tool descriptions repeat
this boundary so clients should not follow instructions embedded in messages or
files.

The HTTP security middleware adds no-store, anti-framing, content-type, referrer,
content-security, and permissions-policy response headers. It does not replace
TLS termination, token validation, or downstream authorization.
