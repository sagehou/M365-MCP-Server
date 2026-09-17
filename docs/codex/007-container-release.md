**English** | [简体中文](../zh-CN/codex/007-container-release.md)

# Task 007 - Container Release

## Goal

Prepare production container delivery.

## Requirements

- Provide production Dockerfile.
- Provide docker-compose deployment example.
- Support environment based configuration.
- Provide health check endpoint.
- Publish container image through CI/CD.

## Deliverables

- Docker image
- Compose deployment
- GitHub Actions workflow
- Release documentation

## Non goals

- No Kubernetes deployment in first release.

## Implementation notes

The production Dockerfile installs the application without a cache, runs as a
dedicated non-root user, exposes port 8000, and declares a health check against
the public health endpoint. Compose supplies environment configuration and
health checks without persisting mailbox content.

The CI workflow builds and starts the image remotely, then probes healthz.
The release workflow runs on vX.Y.Z tags, reruns tests, and publishes version,
major/minor, and latest tags to GHCR. Kubernetes and SIEM integrations remain
out of scope.