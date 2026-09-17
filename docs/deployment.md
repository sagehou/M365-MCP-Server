# Deployment

## Supported deployment artifact

The supported delivery artifact is the container image:

    ghcr.io/sagehou/m365-mcp-server:<version>

The image is built as a non-root Python 3.12 container. It exposes port 8000
and provides unauthenticated health endpoints at /health and /healthz for
container and reverse-proxy probes. The MCP endpoint remains protected by
Microsoft Entra bearer-token validation.

## Compose deployment

Copy the environment template into the deploy directory, fill in the Entra
and Graph settings, and keep the resulting file out of version control:

    cp deploy/.env.example deploy/.env

Start the image:

    docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d

Check container status and readiness:

    docker compose --env-file deploy/.env -f deploy/docker-compose.yml ps
    curl --fail http://127.0.0.1:8000/healthz

The Compose example uses the latest GHCR image by default. Set
M365_MCP_IMAGE in the environment file to pin a different image tag.

## Production network boundary

Terminate TLS and enforce the public hostname at a reverse proxy:

    Traefik -> HTTPS -> M365 MCP Server -> Microsoft Graph

Keep port 8000 on a private network or host firewall boundary. Set
MCP_PUBLIC_URL to the externally reachable HTTPS URL used by the MCP client.
Do not expose the container directly to the internet without TLS and the
required Entra configuration.

## Container release

The release workflow is triggered only by a version tag matching vX.Y.Z. It
runs the test suite, builds the production Dockerfile, and publishes:

    git tag v0.1.0
    git push origin v0.1.0

For a v0.1.0 tag, the workflow publishes the version, major/minor, and latest
GHCR tags. The workflow uses the repository GitHub token for package publishing;
no registry secret is committed.

## Configuration

All runtime settings are supplied through environment variables. Configure
exactly one of CLIENT_SECRET or CLIENT_CERT_PATH, set ALLOWED_TENANTS and
AUDIENCE, and grant only the delegated Graph permissions required by the mail
tools. Secrets must be injected by the deployment environment or secret
management system.
