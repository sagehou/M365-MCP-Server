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
optional test client registration.

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
MCP_PUBLIC_URL is not a server setting and does not enable OAuth discovery.
Do not expose the container directly to the internet without TLS and the
required Entra configuration.

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
exactly one of CLIENT_SECRET or CLIENT_CERT_PATH, set ALLOWED_TENANTS and
AUDIENCE, and grant only the delegated Graph permissions required by the mail
tools. Secrets must be injected by the deployment environment or secret
management system.

## Entra/client prerequisites and acceptance

1. Register the API application, expose the access_as_user delegated scope and
   configure v2 access tokens. Set CLIENT_ID, AUDIENCE, ALLOWED_TENANTS and
   REQUIRED_SCOPES to the actual API registration. ALLOWED_TENANTS is a comma-
   separated allowlist, not the unused historical TENANT_ID variable.
2. Grant delegated Graph User.Read and Mail.ReadWrite plus the required target-
   tenant consent for the implemented read/update tools. Do not grant application
   mailbox permissions or Mail.Send; there is no send tool.
3. Configure exactly one credential. For a certificate, mount its PEM private key
   read-only into the container, set CLIENT_CERT_PATH to that container path and
   set CLIENT_CERT_THUMBPRINT. Merely setting a host path does not mount the file.
   A Compose override can add ./secrets/client.pem:/run/secrets/client.pem:ro.
4. Register/configure the client to obtain a delegated token for this API scope,
   and send Authorization: Bearer with every /mcp/ request. A Graph access token
   is not accepted. Automatic MCP OAuth discovery/interactive sign-in is not
   implemented; client compatibility must be validated before rollout.
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
