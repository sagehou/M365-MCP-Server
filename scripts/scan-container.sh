#!/usr/bin/env bash
# Run on GitHub Actions against the exact candidate image before publishing.
set -euo pipefail
image="${1:?image tag required}"
docker run --rm \
  --volume /var/run/docker.sock:/var/run/docker.sock:ro \
  ghcr.io/aquasecurity/trivy:0.76.2 image \
  --scanners vuln --severity HIGH,CRITICAL --exit-code 1 "$image"
