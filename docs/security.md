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

## OAuth discovery and client registration

OAuth issuer and resource metadata are generated only from explicit validated
configuration. Host, `X-Forwarded-Host`, prefix matches and wildcard redirect
matching are not trusted. Public HTTP redirects are rejected; HTTP is accepted
only for loopback callbacks. The WorkBuddy private scheme is shape-validated,
and every later authorization request must match the registered redirect string
exactly for the same client and issuer.

Dynamic registration creates public clients only and never issues a client
secret. Client records are stored in SQLite under an issuer-qualified key.
Registration audit events contain the generated client ID and result, but not
redirect URIs or request bodies. The OAuth module is guarded by a default-off
feature flag until live end-to-end acceptance is complete.

Interactive authorization requires `response_type=code`, exact client and
redirect binding, the configured MCP resource, the configured public scope and
S256 PKCE. WorkBuddy state is stored separately from a newly generated Entra
state; the latter is atomically consumed before MSAL completes the callback.
Token A is revalidated by the existing `JwtValidator` before a random, hashed,
single-use local code is created. Browser redirects contain only that local code
and the original WorkBuddy state. The Entra authorization-flow object, Token A
and MSAL cache are encrypted with AES-256-GCM before being written to SQLite.
`OAUTH_ENCRYPTION_KEY` must decode from base64 to exactly 32 bytes and is required
whenever OAuth is enabled. The key is not stored in SQLite.

WorkBuddy receives a random 256-bit-equivalent local handle, never an Entra
refresh token. SQLite stores only its SHA-256 hash and the encrypted MSAL cache.
Refresh restores the cache, forces MSAL silent acquisition, revalidates Token A,
checks that tenant and user still match the session, then compare-and-swap rotates
the local handle. Concurrent or replayed use of the old handle returns
`invalid_grant`; Microsoft revocation, corrupt cache or identity mismatch revokes
the local session. Transient Microsoft failures do not consume the current handle.

During initialization and normal OAuth writes, the SQLite adapter reclaims
expired/completed transactions, expired/used codes, expired sessions and old
revoked sessions so terminal OAuth state does not grow without bound. The
production Uvicorn request-line access log is
disabled; reverse proxies must also omit `/oauth/*` query strings so Entra
codes, state, and PKCE values are not retained outside the allowlisted audit log.
