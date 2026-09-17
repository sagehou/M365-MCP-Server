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
No production mailbox data is read or changed by those tests.

## Still required before production

- Choose and publish the first approved release version; verify GHCR visibility
  and pull access. A passing Docker build is not a published release.
- Configure Entra applications/consent and validate two real users, supported
  MCP clients, certificate or secret credentials, and representative attachments.
- Client-side sign-in/token acquisition remains external; automatic MCP OAuth
  discovery and dynamic registration are not implemented.
- Search returns one bounded page and a next_link hint, not an exhaustive mailbox
  export. The tool does not yet accept continuation cursors. Keyword search obeys
  Graph's search ordering/result limits; date-only queries use received time.
- OCR, drafts, shared mailboxes, enterprise RBAC/rate limiting/observability,
  Calendar, Drive, SharePoint and Teams remain roadmap items.

These pending items are not marked complete by tasks 001–007 or by this review.
