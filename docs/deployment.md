# Deployment

## Supported deployment target

The official delivery artifact is a container image.

Example:

```
ghcr.io/sagehou/m365-mcp-server:<version>
```

## Docker

The image must:

- run without interactive setup
- expose health endpoint
- receive configuration through environment variables
- support reverse proxy deployment

## Production

Recommended:

Traefik -> HTTPS -> M365 MCP Server -> Microsoft Graph

## Configuration

Secrets must not be committed. Use environment injection or secret management.
