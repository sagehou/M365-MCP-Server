#!/usr/bin/env bash
# Run only in GitHub Actions after building the image.
set -euo pipefail
image="${1:?image tag required}"
container="m365-mcp-smoke"
port="${MCP_PORT:-8123}"
docker run --detach --name "$container" --publish "127.0.0.1:18000:$port" \
  --env "MCP_PORT=$port" --health-interval=1s --health-start-period=1s "$image"
trap 'docker rm --force "$container" >/dev/null' EXIT
ready=false
for attempt in $(seq 1 45); do
  if [ "$(docker inspect --format '{{.State.Health.Status}}' "$container")" = healthy ]; then
    ready=true
    break
  fi
  sleep 1
done
if [ "$ready" != true ]; then
  docker logs "$container"
  exit 1
fi
curl --fail --silent http://127.0.0.1:18000/healthz
test "$(curl --silent --output /dev/null --write-out '%{http_code}' http://127.0.0.1:18000/mcp/)" = 401
test "$(docker exec "$container" id -u)" != 0
# Exercise the installed worker from the non-root production image.
docker exec "$container" python -c '
import asyncio
from m365_mcp.extractors import AttachmentExtractorRegistry, AttachmentInput
result = asyncio.run(AttachmentExtractorRegistry().extract_async(
    AttachmentInput(name="smoke.txt", content=b"container worker works")))
assert result.content == "container worker works"
'
