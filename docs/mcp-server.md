**English** | [简体中文](zh-CN/mcp-server.md)

# Server edition

| Item | Configuration |
| --- | --- |
| Runtime | Python 3.12 in a non-root container |
| Image | `ghcr.io/sagehou/m365-mcp-server:v0.1.4` |
| MCP endpoint | Streamable HTTP at `https://<your-host>/mcp/` |
| Identity | Microsoft Entra delegated user identity; Graph access through OBO and `/me` |
| Entra application | One self-managed confidential application for the API and browser sign-in |

## Register the Entra application

1. Open the [Microsoft Entra admin center](https://entra.microsoft.com/), select
   the tenant that will own the application, and open **Entra ID > App
   registrations > New registration**.
2. Name it `M365-MCP-Server`. Select the supported account types using the table
   below. Add a **Web** redirect URI of `https://<your-host>/oauth/callback`,
   then select **Register**.
3. Copy **Application (client) ID** and **Directory (tenant) ID** from
   **Overview**. `CLIENT_ID` uses the application ID, not **Object ID**.
4. Under **Expose an API**, set the Application ID URI to `api://<CLIENT_ID>`
   and add the following enabled scope.
5. In **Manifest**, set `api.requestedAccessTokenVersion` to `2` so the API
   receives v2 access tokens.
6. Under **API permissions > Add a permission > Microsoft Graph > Delegated
   permissions**, add `User.Read`, `Mail.ReadWrite`, and `Mail.Send`.
7. Under **Certificates & secrets**, create the server credential as described
   below. The same application and credential are used for browser sign-in
   and Graph OBO.

| Supported account types | `ALLOWED_TENANTS` |
| --- | --- |
| Accounts in this organizational directory only | That tenant's GUID; recommended for an internal deployment |
| Accounts in any organizational directory | Approved tenant GUIDs separated by commas, or deliberately use `*` |
| Organizational and personal Microsoft accounts | Approved tenant GUIDs including the consumer tenant, or deliberately use `*` |

| Expose an API setting | Value |
| --- | --- |
| Scope name | `access_as_user` |
| Who can consent | Admins and users, subject to tenant policy |
| Admin consent display name | Access M365 MCP Server as the signed-in user |
| Admin consent description | Allows a client to call M365 MCP Server on behalf of the signed-in user. |
| User consent display name | Access M365 MCP Server |
| User consent description | Allows this client to use M365 MCP Server on your behalf. |
| State | Enabled |

The resulting scope is `api://<CLIENT_ID>/access_as_user`.

<details>
<summary>ⓘ Delegated permissions and administrator consent</summary>

| Graph delegated permission | Purpose | Admin consent required by the permission itself |
| --- | --- | --- |
| `User.Read` | Included in the current default consent request | No |
| `Mail.ReadWrite` | Read and modify mail, drafts, and attachments | No |
| `Mail.Send` | Send as the signed-in user | No |

`User.Read` is not required by the mail endpoints, but the current default
`GRAPH_CONSENT_SCOPES` still requests it. These are **delegated** permissions;
mailbox **Application permissions** are not part of this implementation.

When the target tenant permits user consent, sign-in displays the permissions
and the user can approve them. A blank permission **Status** does not require
admin approval. Tenant policy can still disable user consent, require a verified
publisher, or restrict consent to selected low-impact permissions.

If policy requires approval, use the target tenant's admin-consent workflow.
For an app registered there, an authorized administrator can review **App
registrations > your app > API permissions > Grant admin consent**. For a
multitenant app, an authorized target-tenant administrator can use:

```text
https://login.microsoftonline.com/<TARGET-TENANT-ID>/adminconsent?client_id=<CLIENT_ID>
```

Verify the delegated grants under **Enterprise applications > your app >
Security > Permissions** in that tenant. Consent in the app's home tenant does
not approve it for other tenants. Added permissions or revoked grants require
new consent. Personal accounts use their own consent flow.

References: [Graph permissions](https://learn.microsoft.com/en-us/graph/permissions-reference),
[user-consent policy](https://learn.microsoft.com/en-us/entra/identity/enterprise-apps/configure-user-consent),
and [OBO](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-on-behalf-of-flow).

</details>

<details>
<summary>ⓘ Token audience, tenant admission, and cloud endpoints</summary>

The client sends an MCP API token: `aud` matches `CLIENT_ID` or an explicitly
accepted API audience, `scp` includes `access_as_user`, and `tid` plus `oid/sub`
identify the user. A Microsoft Graph token or an app-only token cannot replace
this token. The server validates it, then requests
`https://graph.microsoft.com/.default` through OBO using that validated user's
tenant. Every mail request uses `/me`; callers cannot select another mailbox.

`ALLOWED_TENANTS` must be non-empty. Use tenant GUIDs separated by commas or `*`
on its own. The wildcard widens tenant admission while preserving signature,
issuer, audience, expiry, scope, and identity checks. It does not change the
registration's supported account types. The personal-account consumer tenant is
`9188040d-6c67-4c5b-b112-36a304b66dad`. Leave `AUDIENCE` empty to accept the
configured `CLIENT_ID` and `api://<CLIENT_ID>` forms.

Defaults target the global Microsoft cloud:
`https://login.microsoftonline.com` and `https://graph.microsoft.com/v1.0`.
Microsoft 365 operated by 21Vianet and other national clouds require separate
registrations, endpoints, and deployment validation.

</details>

## Configure and deploy

From a checkout on the deployment host:

```bash
cp deploy/.env.example deploy/.env
```

Edit `deploy/.env`. For server-managed browser sign-in, including WorkBuddy:

```dotenv
M365_MCP_IMAGE=ghcr.io/sagehou/m365-mcp-server:v0.1.4
CLIENT_ID=<application-client-id>
CLIENT_SECRET=<client-secret-value>
CLIENT_CERT_PATH=
CLIENT_CERT_THUMBPRINT=
AUDIENCE=
ALLOWED_TENANTS=<approved-tenant-guid>
REQUIRED_SCOPES=access_as_user
GRAPH_SCOPES=https://graph.microsoft.com/.default
GRAPH_CONSENT_SCOPES=https://graph.microsoft.com/User.Read,https://graph.microsoft.com/Mail.ReadWrite,https://graph.microsoft.com/Mail.Send
OAUTH_ENABLED=true
MCP_PUBLIC_URL=https://mcp.example.com/mcp/
OAUTH_ISSUER_URL=https://mcp.example.com
OAUTH_DATABASE_PATH=/data/oauth.db
OAUTH_ENCRYPTION_KEY=<base64-encoded-32-random-bytes>
OAUTH_REFRESH_TOKEN_TTL_DAYS=30
OAUTH_REFRESH_MAX_ROTATIONS=10000
MCP_BIND_ADDRESS=127.0.0.1
MCP_PORT=8000
```

Replace every placeholder and hostname. For a secret credential, copy the
secret **Value**, not its ID. Generate the OAuth encryption key on the deployment
host, for example with `openssl rand -base64 32`, and retain it in the deployment
secret manager. Keep `deploy/.env` out of version control.

The template defaults to `OAUTH_ENABLED=false`. Keep it false only when the MCP
client already obtains a valid Entra token for this API and can refresh it.
Server-managed discovery, browser sign-in, downloads, and push grants require
`true` and the associated OAuth settings above.

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml pull
docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d
docker compose --env-file deploy/.env -f deploy/docker-compose.yml ps
curl --fail http://127.0.0.1:8000/healthz
curl -i http://127.0.0.1:8000/mcp/
```

Expect health status `200` and an unauthenticated MCP response of `401`. If the
image cannot be pulled, resolve the version or registry access before starting.
Private GHCR packages require `docker login ghcr.io` with package-read access.

<details>
<summary>ⓘ Certificate credentials and reproducible image selection</summary>

Configure exactly one of `CLIENT_SECRET` or `CLIENT_CERT_PATH`. For production,
prefer a certificate: upload its public certificate under **Certificates &
secrets > Certificates**, retain the PEM private key in the deployment secret
store, clear `CLIENT_SECRET`, and set:

```dotenv
CLIENT_CERT_PATH=/run/secrets/m365-client.pem
CLIENT_CERT_THUMBPRINT=<certificate-thumbprint>
```

Mount the private key read-only. For example, create `deploy/compose.cert.yml`:

```yaml
services:
  m365-mcp:
    volumes:
      - ./secrets/m365-client.pem:/run/secrets/m365-client.pem:ro
```

Place the protected key at `deploy/secrets/m365-client.pem`. Add
`-f deploy/compose.cert.yml` after `-f deploy/docker-compose.yml` to every Compose
command. A host path in `CLIENT_CERT_PATH` alone does not mount the file.
Rotate the credential before expiry.

Pin a published image version or digest. `edge` and `sha-<commit>` are integration
images published from reviewed `main`; use the commit tag for reproducible
acceptance. Version-tag releases publish stable image tags after CI succeeds.

</details>

## Configure the HTTPS reverse proxy

Terminate TLS on a fixed public hostname and route the following to the same
server process:

| Route | Access |
| --- | --- |
| `/mcp/`, `/uploads/attachments` | Valid delegated bearer token |
| `/.well-known/*`, `/oauth/*` | OAuth discovery and browser/token flow |
| `/uploads/push` | Exact short-lived `X-Upload-Handle` capability |
| `/downloads/*` | Short-lived, single-use download capability |
| `/health`, `/healthz` | Unauthenticated process probes; restrict exposure as appropriate |

Set `MCP_PUBLIC_URL` and `OAUTH_ISSUER_URL` to the exact public routes; the
application does not derive them from Host or forwarded headers. Production
URLs require HTTPS. The Entra **Web** callback must be exactly
`OAUTH_ISSUER_URL` plus `/oauth/callback`. WorkBuddy's private callback is
registered with this server, not with Entra.

<details>
<summary>ⓘ Proxy limits, logging, and persistence</summary>

Compose binds the published port to `127.0.0.1` by default. A proxy in another
container or host needs an explicitly configured private network/interface.
`MCP_PORT` controls the listener, published port, and health probe.

Limit binary uploads to 20 MiB plus HTTP framing overhead. Apply request-size,
rate, and concurrency limits to uploads, `/oauth/register`, and `/oauth/token`.
Do not log authorization headers, `X-Upload-Handle`, OAuth query strings, or
`/downloads/*` capability paths. The application disables request-line access
logs; configure proxies and log collectors consistently.

Compose persists registered clients and encrypted OAuth sessions in the
`oauth-data` volume mounted at `/data`. Back up the database as sensitive
identity state and retain the same `OAUTH_ENCRYPTION_KEY` for restores or
replacement processes. Token/cache material is encrypted; refresh handles are
stored as hashes, rotated on use, and their family is revoked on replay.

Upload handles, staged bytes, and downloads are held in bounded process memory.
Their creation and use must reach the same worker. Restarting loses them; the
current implementation has no shared store for multi-worker or multi-host
routing of these capabilities.

</details>

## Connect an MCP client

### Browser sign-in and WorkBuddy

With OAuth enabled, configure a client supporting MCP OAuth discovery and
public-client registration:

```json
{
  "mcpServers": {
    "m365": {
      "type": "streamableHttp",
      "url": "https://mcp.example.com/mcp/",
      "timeout": 30000
    }
  }
}
```

Complete browser sign-in and delegated consent when the client connects.
The client uses S256 PKCE and receives an MCP API token plus a rotating refresh
token when registered for refresh. The server then uses OBO to access Graph.

For WorkBuddy 4.24.0 or later, use the package template in `workbuddy/`. Replace
`${M365_MCP_URL}` in `mcp.json` with the exact `MCP_PUBLIC_URL`, then ZIP the
folder's **contents** so `connector-meta.json`, `mcp.json`, `icon.svg`, and
`skills/` are at the archive root. Keep its OAuth-discovery configuration;
do not add token fields, authorization headers, or the Entra client secret.

<details>
<summary>ⓘ OAuth redirect and refresh behavior</summary>

Dynamic registration accepts exact HTTPS redirects,
`workbuddy://workbuddy/<non-empty-path>`, and explicit-port loopback redirects
with a non-empty path (`localhost`, `127.0.0.1`, or `[::1]`). Wildcards,
fragments, public HTTP redirects, and unregistered values are rejected.

Discovery uses `/.well-known/oauth-protected-resource` and
`/.well-known/oauth-authorization-server`. Registration, authorization,
callback, and token routes are `/oauth/register`, `/oauth/authorize`,
`/oauth/callback`, and `/oauth/token`. The browser handoff contains only a
single-use local code and the client's original state. WorkBuddy receives a
completion page that opens its registered private URI; HTTPS and loopback
clients receive a redirect.

Code exchange verifies the client, exact redirect, resource, and S256 verifier.
Local codes expire within ten minutes and can be redeemed once. Refresh
requires a client registered with the `refresh_token` grant. It revalidates the
same tenant/user identity, rotates the local handle atomically, and revokes the
rotation family on replay. Transient upstream outages return
`temporarily_unavailable` without consuming the current refresh token.

</details>

### Clients managing their own Entra token

With `OAUTH_ENABLED=false`, obtain a delegated token for
`api://<CLIENT_ID>/access_as_user` and send it in
`Authorization: Bearer <MCP-API-access-token>` on MCP requests. The client must
handle acquisition, consent, expiry, and refresh. A Graph access token has the
wrong audience. This mode exposes 11 mail tools; enabling server-managed OAuth
adds the two tools marked below.

## Mail tools

| Tools | Use |
| --- | --- |
| `mail_search`, `mail_get` | Search one bounded page and read messages |
| `mail_create_draft`, `mail_send_draft` | Create plain-text drafts and send an existing draft |
| `mail_add_draft_attachment` | Attach an explicitly uploaded file to a draft |
| `mail_list_attachments`, `mail_read_attachment` | List attachments and extract bounded text |
| `mail_mark_read`, `mail_archive`, `mail_move`, `mail_set_category` | Modify the signed-in user's messages |
| `mail_download_attachment` | Single-use download URL; requires server-managed OAuth |
| `mail_prepare_attachment_push` | Draft/file-bound upload grant; requires server-managed OAuth |

Creating or attaching does not send. Before `mail_send_draft`, the client must
obtain per-message confirmation or enforce the user's explicit bounded
automation authorization, including recipients, trusted content/attachment
sources, volume, and expiry. The server cannot verify that client-side approval.
Graph acceptance does not prove delivery. Inspect the draft after an ambiguous
write or send failure before deciding whether to retry.

## Add a file to a remote draft

### Authenticated binary upload

1. Create the draft with `mail_create_draft`.
2. Send `POST /uploads/attachments` using the same delegated bearer token as
   `/mcp/`, `Content-Type: application/octet-stream`, a percent-encoded UTF-8
   plain filename in `X-Attachment-Name`, and optionally an ASCII MIME type in
   `X-Attachment-Content-Type`. Send 1 byte to 20 MiB of raw bytes, not Base64
   or multipart data.
3. Call `mail_add_draft_attachment(draft_id, upload_handle)` with the returned
   handle. Verify its SHA-256 and `mail_list_attachments` before sending.

Handles are user-bound, expire after five minutes, and can be consumed once.
A path on the client's PC is not a file upload to the server.

### OAuth push grant for an unattended client artifact

1. Inspect the finished artifact for its filename, MIME type, exact byte
   length, and SHA-256. Create the draft through the remote MCP connector.
2. Call `mail_prepare_attachment_push(draft_id, name, content_length,
   content_sha256, content_type?)` through that connector.
3. POST the raw bytes to its fixed HTTPS `upload_url` with
   `Content-Type: application/octet-stream` and
   `X-Upload-Handle: <upload_handle>`. This request uses the grant rather than
   an OAuth bearer token; the exact length and SHA-256 must match.
4. Call `mail_add_draft_attachment(draft_id, upload_handle)` through the same
   connector, then inspect the attachment list before authorizing a send.

<details>
<summary>ⓘ Optional Windows .NET uploader for a remote connector</summary>

The .NET NativeAOT EXE provides `inspect-attachment` and `push-attachment`
without a local Entra login or a second MCP connector. Configure a trusted
artifact directory and fixed server upload endpoint:

```powershell
$env:M365_ATTACHMENT_ROOT = 'C:\Automation\Output'
$env:M365_ATTACHMENT_PUSH_URL = 'https://mcp.example.com/uploads/push'
& 'C:\Tools\m365-mcp-windows-local-amd64.exe' inspect-attachment 'reports\weekly.docx'
$grantJson | & 'C:\Tools\m365-mcp-windows-local-amd64.exe' push-attachment 'reports\weekly.docx'
```

`$grantJson` is the complete grant returned by `mail_prepare_attachment_push`.
The helper accepts relative paths beneath the configured root and non-empty
PDF/DOCX/XLSX/PPTX/ZIP files up to 20 MiB, verifies the opened file, and writes
no temporary attachment. Pass grants through stdin, not command arguments or
logs. Re-inspect and request a new grant if the file changes.

WorkBuddy's compose Skill may invoke these commands through its Bash tool.
The helper's file-root check constrains that EXE operation; configure the
client's own sandbox and authorization for its general Bash access. Other
trusted uploaders can implement the same HTTP contract.

</details>

## Attachment limits and operations

| Operation | Default boundary |
| --- | --- |
| Upload to a draft | Non-empty file up to 20 MiB; plain filename up to 255 characters |
| Extract attachment text | File up to 10 MiB; output up to 100,000 characters |
| Extraction worker | 512 MiB address space, 15 CPU seconds, 20 seconds wall time; two active workers |
| Office expansion | 64 MiB and 2,048 entries |
| Download URLs | Five minutes, single use; at most 16 items and 64 MiB in memory |

PDF, DOCX, XLSX, PPTX, TXT, and Markdown extraction is supported; XLSX reads
cached formula results and image-only PDFs need external OCR. Graph attachment
uploads below 3,000,000 bytes use direct creation; larger files use a sequential
upload session. Graph upload URLs and file bytes are not exposed through MCP.

<details>
<summary>ⓘ Adjusting limits and diagnosing failures</summary>

Extraction is bounded by `ATTACHMENT_MAX_BYTES` and
`ATTACHMENT_MAX_TEXT_CHARS`. If increasing the byte limit, also increase
`GRAPH_MAX_RESPONSE_BYTES` for Base64-expanded JSON: at least 4/3 of the file
limit plus metadata. Downloads use `ATTACHMENT_DOWNLOAD_TTL_SECONDS`,
`ATTACHMENT_DOWNLOAD_MAX_ITEMS`, and `ATTACHMENT_DOWNLOAD_MAX_TOTAL_BYTES`; the
total must be at least `ATTACHMENT_MAX_BYTES`. Worker resource limits are not
a filesystem/network sandbox; use container memory/PID and proxy limits too.

| Message or symptom | Check or action |
| --- | --- |
| `AADSTS50011` | Register the exact server `/oauth/callback` under **Web**; the client's private callback belongs to MCP DCR. |
| `AADSTS65001` / `consent_required` / admin approval | Check `access_as_user`, explicit `GRAPH_CONSENT_SCOPES`, and the target tenant's grants/policy; reconnect to complete user consent when allowed. |
| `AADSTS70011` | Keep `GRAPH_SCOPES` as Graph `.default`; do not mix it with explicit scopes. |
| API rejects the bearer token | Check the MCP API audience, delegated `scp`, tenant allowlist, issuer, and expiry. |
| External-tenant OBO fails | Check multitenant registration, target-tenant admission, Enterprise Application, and delegated grants there. |
| Personal account cannot sign in | Check supported account types and admission of the consumer tenant; `*` does not override the registration. |
| Graph `403` | Check delegated consent, signed-in identity, and the account's Outlook/Exchange mailbox availability. |
| Refresh fails after replacing the container | Restore the same SQLite volume and encryption key; inspect expiry/revocation and reconnect when needed. |

For OBO failures, correlate safe audit fields `entra_error`, `entra_suberror`,
`entra_error_code`, and `correlation_id` with Entra diagnostics. Keep token,
message, filename, grant, and attachment payload logging disabled.

</details>

## Deployment acceptance

1. Verify public health and the unauthenticated MCP `401` response.
2. Complete real client sign-in, initialize MCP, and verify the expected 11 or
   13 tools. For WorkBuddy, confirm there is no manual token form.
3. With two users, search/read known messages and confirm each cannot access
   the other's mailbox. Test supported external tenants and personal accounts
   separately when the deployment enables them.
4. Create a draft, attach a known file, and send only after the required
   approval to a controlled recipient. Check mutations on disposable messages
   and use the new IDs returned after moving/archiving.
5. In OAuth mode, check refresh after token expiry and a container restart,
   keeping the database/key. Check download expiry and single-use redemption.
6. Confirm application and proxy logs omit credentials and mail content. Record
   the exact image digest and connector archive in the deployment's records.

---

GitHub Actions runs the repository's builds and tests; the editing environment
must not run local tests or install test dependencies. CI uses mocked identity
flows and does not replace target-tenant/client acceptance. Updated: 2026-11-12.
