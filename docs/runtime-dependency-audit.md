**English** | [简体中文](zh-CN/runtime-dependency-audit.md)

# Runtime dependency audit

This audit records the FastMCP 4 migration dependency boundary. The versions
are the packages actually resolved by GitHub Actions on 2026-09-17, not an
estimate derived from version ranges.

## Resolved versions

| Package | Relationship | Before | After |
| --- | --- | ---: | ---: |
| `fastmcp` | direct MCP runtime | 2.14.7 | 4.0.4 |
| `fastmcp-slim` | transitive via `fastmcp` | not installed | 4.0.4 |
| `mcp` | transitive via `fastmcp` | 1.30.0 | 2.2.0 |
| `mcp-types` | transitive via MCP/FastMCP | not installed | 2.2.0 |
| `authlib` | transitive via FastMCP | 1.8.0 | 1.8.0 |
| `joserfc` | transitive via FastMCP | 1.7.5 | 1.7.5 |
| `httpx` | direct Graph/OIDC client | 0.28.1 | 0.28.1 |
| `httpx2` | transitive FastMCP HTTP stack | not installed | 2.13.0 |
| `msal` | direct Entra OBO client | 1.38.0 | 1.38.0 |
| `PyJWT` | direct JWT validation | 2.14.0 | 2.14.0 |
| `fastapi` | direct ASGI application | 0.141.1 | 0.141.1 |
| `starlette` | transitive via FastAPI/FastMCP | 1.6.0 | 1.6.0 |
| `pydantic` | direct models/settings | 2.13.5 | 2.13.5 |

The project intentionally contains both HTTP client families. Application-owned
Graph and OpenID Connect traffic continues to use the direct `httpx` dependency.
FastMCP 4 and MCP SDK v2 use the separate, transitive `httpx2` stack internally.
They have different owners and neither dependency is an accidental duplicate.

The accepted dependency constraints are `fastmcp==4.0.4`,
`fastapi>=0.133,<1`, and `pydantic>=2.12,<3`. The exact FastMCP pin keeps the
runtime migration reproducible while other existing ranges continue to receive
compatible maintenance releases.

## Compatibility evidence

The migration audit found no project use of removed FastMCP APIs. The existing
ASGI mount, stateless HTTP configuration, tool error boundary and request
dependency helper remain exercised through the production application factory.

GitHub Actions covers both protocol eras on that same endpoint:

- Legacy `2025-03-26`: initialize, tools/list, every one of the eleven mail tools,
  sanitized failures and concurrent Alice/Bob identity isolation.
- Modern `2026-07-28`: server/discover, tools/list and tools/call with request
  metadata and no MCP session identifier.
- The full unit/integration suite, production Docker image, health endpoint,
  non-root worker startup and Docker Compose smoke path.

The container smoke test also rejects production startup logs containing the
known Authlib JOSE and HTTPX migration warnings. It does not hide warnings,
downgrade Authlib, patch installed packages or retain FastMCP 2.

The before snapshot is [GitHub Actions run 35195153651](https://github.com/sagehou/M365-MCP-Server/actions/runs/35195153651).
The successful migrated snapshot is [GitHub Actions run 35195810661](https://github.com/sagehou/M365-MCP-Server/actions/runs/35195810661).

## Scope boundary

This phase changes the MCP runtime only. Authentication still requires a bearer
token supplied by the client, followed by the existing Entra OBO exchange.
OAuth discovery, dynamic client registration and browser sign-in are not added
by this migration.
