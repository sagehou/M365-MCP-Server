**English** | [简体中文](zh-CN/review-status.md)

# Implementation review follow-up

## Corrected gaps

- Configuration: empty alternative credentials from the environment template;
  positive/bounded runtime limits and non-empty required scopes.
- Authentication: signing-key rollover refresh with a one-minute miss cooldown;
  negative signature/audience/issuer/expiry/application-token tests.
- Runtime: stateless MCP HTTP identity per request; off-thread OBO; initialize,
  tools/list and concurrent two-user tools/call integration tests.
- Graph/mail: separate KQL search and OData filtering, preserve new IDs after
  move/archive, do not replay ambiguous writes, do not shorten Retry-After,
  reject path traversal and bound response bytes.
- Audit: actual JSON events with timestamp and identity under default logging;
  sanitize errors before framework handling.
- Attachments: metadata-only listings, pre-decode/expanded archive limits and
  supervised parser processes with resource, timeout and cancellation limits.
- Delivery: exclude credentials from Docker contexts, test configurable-port
  health checks/non-root worker startup, bind Compose privately and smoke-test
  the exact image before publishing it.

## What CI proves

Unit and integration tests exercise the real ASGI/FastMCP stack with mocked
Entra metadata, OBO and Graph transport. Docker smoke tests use the installed
non-root production image. Builds and tests run exclusively in GitHub Actions.
The mocked WorkBuddy client flow follows the 401 discovery challenge through
DCR, S256 authorization, an Entra callback, local token exchange, authenticated
MCP initialization, refresh-token rotation and another authenticated MCP call.
Connector-package tests also enforce the official directory shape, OAuth mode
without embedded credentials and the three scoped Skills. No production mailbox
data is read or changed by those tests.

## Still required before production

- Choose and publish the first approved release version; verify GHCR visibility
  and pull access. A passing Docker build is not a published release.
- Configure Entra applications/consent and validate two real users, supported
  MCP clients, certificate or secret credentials, and representative attachments.
- OAuth discovery, dynamic public-client registration, MSAL-backed interactive
  authorization, S256 PKCE, one-time local authorization-code exchange and
  persistent encrypted refresh sessions with rotation/replay prevention are
  implemented behind a default-off feature flag. The WorkBuddy connector and CI
  client-flow coverage are present. Live WorkBuddy automatic sign-in/refresh,
  restart, real-mailbox and cross-tenant acceptance remain release blockers for
  a WorkBuddy-compatible v0.1.
- Search returns one bounded page and a next_link hint, not an exhaustive mailbox
  export. The tool does not yet accept continuation cursors. Keyword search obeys
  Graph's search ordering/result limits; date-only queries use received time.
- OCR, drafts, shared mailboxes, enterprise RBAC/rate limiting/observability,
  Calendar, Drive, SharePoint and Teams remain roadmap items.

These pending items are not marked complete by tasks 001–007 or by this review.
