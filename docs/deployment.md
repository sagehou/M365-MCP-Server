**English** | [简体中文](zh-CN/deployment.md)

# Deployment

## Supported deployment artifact

The supported delivery artifact is the container image:

    ghcr.io/sagehou/m365-mcp-server:<version>

The image is built as a non-root Python 3.12 container. It exposes port 8000
and provides unauthenticated health endpoints at /health and /healthz for
container and reverse-proxy probes. The MCP endpoint remains protected by
Microsoft Entra bearer-token validation.

## Entra setup first

Before deploying, complete the portal configuration in:

- [Microsoft Entra app registration guide](entra-app-registration.md)

That guide covers the exact application model used by this server, including
multitenant cross-tenant testing, the `access_as_user` API scope, delegated
Microsoft Graph permissions, OBO credentials, target-tenant consent and an
interactive Web callback on the same App Registration.

## Compose deployment

Copy the environment template into the deploy directory, fill in the Entra
and Graph settings, and keep the resulting file out of version control:

    cp deploy/.env.example deploy/.env

Start the image:

    docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d

Check container status and process liveness:

    docker compose --env-file deploy/.env -f deploy/docker-compose.yml ps
    curl --fail http://127.0.0.1:8000/healthz

Set M365_MCP_IMAGE to an existing version or digest. The template intentionally
contains CHANGE_ME. Before starting, run docker compose with the same options
and the pull subcommand; stop if the image is unavailable. Private GHCR packages
also require docker login ghcr.io using a credential with package read access.

For live pre-release validation, the repository can publish the reviewed main
branch as `ghcr.io/sagehou/m365-mcp-server:edge` and a commit-specific
`sha-<commit>` tag. Prefer the SHA tag when recording reproducible test results.
Stable `latest` remains reserved for a versioned release.

## Production network boundary

Terminate TLS and enforce the public hostname at a reverse proxy:

    Traefik -> HTTPS -> M365 MCP Server -> Microsoft Graph

Compose binds to 127.0.0.1 by default. A reverse proxy on another host/container
needs an explicitly configured private interface/network; do not simply expose
all interfaces. MCP_PORT controls both the listener and the health probe.
Configure the external HTTPS endpoint URL in the MCP client and reverse proxy.
Do not expose the container directly to the internet without TLS and the
required Entra configuration.

## OAuth authorization

The OAuth module provides discovery metadata, dynamic public-client registration,
MSAL-backed interactive authorization, S256 PKCE, one-time authorization-code
exchange and persistent local refresh sessions. OAuth remains disabled by default
until live WorkBuddy acceptance is complete:

    OAUTH_ENABLED=false
    MCP_PUBLIC_URL=https://mcp.example.com/mcp/
    OAUTH_ISSUER_URL=https://mcp.example.com
    OAUTH_DATABASE_PATH=/data/oauth.db
    OAUTH_ENCRYPTION_KEY=<base64-encoded-32-random-bytes>
    OAUTH_REFRESH_TOKEN_TTL_DAYS=30
    OAUTH_REFRESH_MAX_ROTATIONS=10000

`CLIENT_ID` and the configured `CLIENT_SECRET` or certificate belong to the one
`M365-MCP-Server` App Registration. The same registration exposes
`api://<CLIENT_ID>/access_as_user`, owns the Web callback and authenticates the
server for both the interactive code exchange and Graph OBO.

When explicitly enabled for integration development, both public URLs are
validated configuration; they are never inferred from Host or forwarded headers.
HTTPS is mandatory except for loopback development. Compose mounts the named
`oauth-data` volume at `/data`, so registered clients and encrypted sessions survive
container recreation. Back up this volume as sensitive authentication state. Store
`OAUTH_ENCRYPTION_KEY` in the deployment secret manager, never in the database,
image, repository or logs. Restores and replacement processes must use the same
database and key. v0.1 does not provide distributed or multi-host session storage.

Route `/.well-known/*`, `/oauth/*` and `/mcp/` through the same fixed public
origin. Register `https://mcp.example.com/oauth/callback` as a Web redirect URI
on the `M365-MCP-Server` App Registration. For loopback development, register
`http://localhost:8000/oauth/callback` separately.
Apply reverse-proxy request-size and rate limits to `/oauth/register`, and rate
plus concurrency limits to `/oauth/token`;
the application deliberately does not add Redis or an enterprise rate limiter.
The production entry point disables Uvicorn request-line access logs because
OAuth authorization and callback query strings contain sensitive transient
values. Configure every reverse proxy and log collector to omit query strings
for `/oauth/*` as well.
Do not set `OAUTH_ENABLED=true` in production until the WorkBuddy end-to-end gate
is complete. See [WorkBuddy OAuth](workbuddy-oauth.md).

## Container release

The stable release workflow is triggered only by a version tag matching vX.Y.Z.
It runs the test suite, verifies that the tagged commit is in main, builds the
production Dockerfile, smoke-tests that exact image, and only then publishes.
For an approved release version, tag the reviewed main commit (example only):

    git tag v0.1.0
    git push origin v0.1.0

For a v0.1.0 tag, the workflow publishes the version, major/minor, and latest
GHCR tags. The workflow uses the repository GitHub token for package publishing;
no registry secret is committed.

The separate test-image workflow publishes `edge` and a commit-specific SHA tag
from main after tests, Docker build and smoke tests succeed. Test tags do not
replace `latest`.

## Configuration

All runtime settings are supplied through environment variables. Configure
exactly one of CLIENT_SECRET or CLIENT_CERT_PATH, set ALLOWED_TENANTS and grant
only the delegated Graph permissions required by the mail tools. Secrets must be
injected by the deployment environment or secret management system.

`ALLOWED_TENANTS` supports two modes:

- comma-separated tenant GUIDs for an explicit allowlist;
- `*` to accept any valid Microsoft tenant represented by a correctly validated
  token. This includes the Microsoft consumer tenant when the App Registration's
  Supported account types also allow personal Microsoft accounts.

An empty `ALLOWED_TENANTS` remains invalid and fails closed. Do not combine `*`
with explicit tenant IDs. For private enterprise deployments, an explicit tenant
allowlist remains the narrower security boundary; `*` is intended for deliberately
open multitenant deployments.

`AUDIENCE` is optional. If omitted, the server accepts the configured `CLIENT_ID`
and `api://<CLIENT_ID>` audience forms.

## Entra/client prerequisites and acceptance

1. Register one application named `M365-MCP-Server`, expose the `access_as_user`
   delegated scope and
   configure v2 access tokens. Set CLIENT_ID, ALLOWED_TENANTS and REQUIRED_SCOPES
   to the actual API registration. Use a comma-separated tenant allowlist or `*`
   intentionally. Leave AUDIENCE empty unless an explicit audience override is
   required.
2. Grant delegated Graph User.Read and Mail.ReadWrite plus the required target-
   tenant consent for the implemented read/update tools. Do not grant application
   mailbox permissions or Mail.Send; there is no send tool.
3. Configure exactly one credential. For a certificate, mount its PEM private key
   read-only into the container, set CLIENT_CERT_PATH to that container path and
   set CLIENT_CERT_THUMBPRINT. Merely setting a host path does not mount the file.
   A Compose override can add ./secrets/client.pem:/run/secrets/client.pem:ro.
4. On the same App Registration, add the Web callback
   `https://<your-host>/oauth/callback`. The existing `CLIENT_ID` and client
   credential are reused for interactive sign-in; no second registration or
   second credential set exists. Interactive sign-in, local
   authorization-code exchange and encrypted refresh sessions remain behind the
   disabled feature flag; live acceptance remains a release blocker.
5. Confirm /healthz returns 200 and /mcp/ without a bearer token returns 401.
   These checks do not validate tenant credentials, Graph consent or OBO.
6. With two test users, initialize MCP, list the eight tools and read a known
   message from each mailbox. Verify cross-user message access is denied.
   Exercise updates only on disposable test messages and verify moved IDs.
7. Read representative attachments; verify JSON audit events contain identity,
   tool, outcome and timestamp but no message text, filenames or tokens.
   If OBO/tool calls fail, inspect audit error type and Entra sign-in diagnostics;
   do not enable payload/token logging.

Attachment workers have a 512 MiB address-space ceiling, 15 CPU seconds,
20 seconds wall time and two active workers per server process. Office archives
are limited to 64 MiB expanded data and 2048 entries. Worker limits are resource
containment, not a filesystem/network security sandbox. Apply reverse-proxy
request size/concurrency limits and container memory/PID limits for production.
If increasing ATTACHMENT_MAX_BYTES, also size GRAPH_MAX_RESPONSE_BYTES for its
base64-expanded JSON representation (at least 4/3 of the byte limit plus metadata).
