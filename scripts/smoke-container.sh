#!/usr/bin/env bash
# Run only in GitHub Actions after building the image.
set -euo pipefail
image="${1:?image tag required}"
container="m365-mcp-smoke"
oauth_container="m365-mcp-oauth-smoke"
oauth_volume="m365-mcp-oauth-smoke-data"
port="${MCP_PORT:-8123}"
cleanup() {
  docker rm --force "$container" "$oauth_container" >/dev/null 2>&1 || true
  docker volume rm "$oauth_volume" >/dev/null 2>&1 || true
}
trap cleanup EXIT
docker run --detach --name "$container" --publish "127.0.0.1:18000:$port" \
  --env "MCP_PORT=$port" --health-interval=1s --health-start-period=1s "$image"
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
startup_logs="$(docker logs "$container" 2>&1)"
for forbidden in \
  'AuthlibDeprecationWarning' \
  'authlib.jose module is deprecated' \
  'please use joserfc instead' \
  'The httpx module is deprecated' \
  'please use httpx2 instead'; do
  if grep --fixed-strings --quiet "$forbidden" <<< "$startup_logs"; then
    printf '%s\n' "$startup_logs"
    printf 'Forbidden runtime warning found: %s\n' "$forbidden" >&2
    exit 1
  fi
done
# Exercise the installed worker from the non-root production image.
docker exec "$container" python -c '
import asyncio
from m365_mcp.extractors import AttachmentExtractorRegistry, AttachmentInput
result = asyncio.run(AttachmentExtractorRegistry().extract_async(
    AttachmentInput(name="smoke.txt", content=b"container worker works")))
assert result.content == "container worker works"
'

docker run --detach --name "$oauth_container" --publish "127.0.0.1:18001:$port" \
  --mount "type=volume,src=$oauth_volume,dst=/data" \
  --env "MCP_PORT=$port" \
  --env "OAUTH_ENABLED=true" \
  --env "MCP_PUBLIC_URL=https://mcp.example.com/mcp/" \
  --env "OAUTH_ISSUER_URL=https://mcp.example.com" \
  --env "CLIENT_ID=22222222-2222-2222-2222-222222222222" \
  --env "CLIENT_SECRET=ci-api-secret" \
  --env "ALLOWED_TENANTS=11111111-1111-1111-1111-111111111111" \
  --env "ENTRA_BROKER_CLIENT_ID=33333333-3333-3333-3333-333333333333" \
  --env "ENTRA_BROKER_CLIENT_SECRET=ci-broker-secret" \
  --health-interval=1s --health-start-period=1s "$image"
oauth_ready=false
for attempt in $(seq 1 45); do
  if [ "$(docker inspect --format '{{.State.Health.Status}}' "$oauth_container")" = healthy ]; then
    oauth_ready=true
    break
  fi
  sleep 1
done
if [ "$oauth_ready" != true ]; then
  docker logs "$oauth_container"
  exit 1
fi
resource_metadata="$(curl --fail --silent http://127.0.0.1:18001/.well-known/oauth-protected-resource)"
python -c '
import json, sys
metadata = json.load(sys.stdin)
assert metadata["resource"] == "https://mcp.example.com/mcp/"
assert metadata["authorization_servers"] == ["https://mcp.example.com"]
' <<< "$resource_metadata"
challenge_headers="$(curl --silent --dump-header - --output /dev/null http://127.0.0.1:18001/mcp/)"
grep --ignore-case --fixed-strings \
  'www-authenticate: Bearer resource_metadata="https://mcp.example.com/.well-known/oauth-protected-resource"' \
  <<< "$challenge_headers"
registration="$(curl --fail --silent \
  --header 'Content-Type: application/json' \
  --data '{"client_name":"CI","redirect_uris":["http://127.0.0.1:43123/oauth/callback"],"application_type":"native","grant_types":["authorization_code","refresh_token"],"response_types":["code"],"token_endpoint_auth_method":"none"}' \
  http://127.0.0.1:18001/oauth/register)"
python -c '
import json, sys
registration = json.load(sys.stdin)
assert registration["client_id"].startswith("mcp_")
assert "client_secret" not in registration
' <<< "$registration"
docker exec "$oauth_container" test -s /data/oauth.db
test "$(curl --silent --output /dev/null --write-out '%{http_code}' \
  --get \
  --data-urlencode 'client_id=unregistered-client' \
  --data-urlencode 'redirect_uri=http://127.0.0.1:43123/oauth/callback' \
  --data-urlencode 'response_type=code' \
  --data-urlencode 'scope=access_as_user' \
  --data-urlencode 'state=ci-state' \
  --data-urlencode 'code_challenge=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA' \
  --data-urlencode 'code_challenge_method=S256' \
  --data-urlencode 'resource=https://mcp.example.com/mcp/' \
  http://127.0.0.1:18001/oauth/authorize)" = 400
oauth_startup_logs="$(docker logs "$oauth_container" 2>&1)"
for forbidden in \
  'AuthlibDeprecationWarning' \
  'authlib.jose module is deprecated' \
  'please use joserfc instead' \
  'The httpx module is deprecated' \
  'please use httpx2 instead'; do
  if grep --fixed-strings --quiet "$forbidden" <<< "$oauth_startup_logs"; then
    printf '%s\n' "$oauth_startup_logs"
    printf 'Forbidden OAuth runtime warning found: %s\n' "$forbidden" >&2
    exit 1
  fi
done
