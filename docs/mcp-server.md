**English** | [简体中文](zh-CN/mcp-server.md)

# Remote MCP server

This guide is for the Python server running as a container, not the Windows
stdio connector. The server exposes Streamable HTTP at `/mcp/` and calls
Microsoft Graph with the signed-in user's delegated identity through OBO. It
operates under `/me`; a path on a client's PC is not a path on the server.

## Deploy and connect

1. Configure the server App Registration, delegated Graph permissions and
   target-tenant consent using the [Entra guide](entra-app-registration.md).
2. Configure the container, TLS reverse proxy and secrets using the
   [deployment guide](deployment.md). The v0.1.1 image is
   `ghcr.io/sagehou/m365-mcp-server:v0.1.1`. `/healthz` checks process liveness;
   it does not prove Entra consent or mailbox access.
3. Connect a client to the public HTTPS `/mcp/` URL. The default mode requires
   a validated Entra bearer token for this API. Optional server-managed OAuth
   sign-in for WorkBuddy is described in the [OAuth guide](workbuddy-oauth.md)
   and must be explicitly enabled. The default tool set has 11 mail tools;
   OAuth mode also exposes `mail_download_attachment` and
   `mail_prepare_attachment_push` (13 total). See the [tool contract](tool-spec.md).

The Windows single EXE's local `stdio` mode has its own authentication and
tool contract; see the [Windows guide](windows-local.md).

## Add a file to a remote draft

The remote tool `mail_add_draft_attachment(draft_id, upload_handle)` does not
read a client-side file path. A client must explicitly supply 1 byte to 20 MiB
of raw file bytes through one of these server upload routes, then call the MCP
tool. Uploading or attaching never sends the draft.

### Authenticated binary upload

Use this route when the uploading client can provide the same delegated bearer
token it uses for `/mcp/`:

1. Create a draft with `mail_create_draft`.
2. Send `POST /uploads/attachments` with `Authorization: Bearer <token>`,
   `Content-Type: application/octet-stream`, a percent-encoded UTF-8 plain
   filename in `X-Attachment-Name`, and optionally an ASCII MIME type in
   `X-Attachment-Content-Type`. The body is the raw file bytes, not Base64 or
   multipart form data.
3. Pass the returned `upload_handle` and draft ID to
   `mail_add_draft_attachment`. Verify the returned SHA-256 and
   `mail_list_attachments` before an authorized send.

The upload handle is bound to the authenticated user, expires after five
minutes and can be consumed once. This route is not restricted to Windows;
the client must implement the explicit binary upload.

### OAuth push grant for an unattended client artifact

When server-managed OAuth is enabled and the MCP client does not hand an OAuth
token to a local file uploader, use the grant route:

1. Inspect the completed local artifact to obtain its filename, MIME type,
   exact byte length and SHA-256. Create the draft through the remote MCP
   connector.
2. Call `mail_prepare_attachment_push(draft_id, name, content_length,
   content_sha256, content_type?)`. It returns a fixed HTTPS `upload_url` and a
   short-lived `upload_handle` bound to that user, draft and exact file metadata.
3. Push the raw bytes to that URL with `Content-Type: application/octet-stream`
   and `X-Upload-Handle: <upload_handle>`. This HTTP request uses the grant, not
   a bearer token. The server rejects a different length or SHA-256.
4. After a successful push, call
   `mail_add_draft_attachment(draft_id, upload_handle)` through the same remote
   MCP connector. Check `mail_list_attachments` before sending.

On Windows, the same `m365-mcp.exe` provides `inspect-attachment` and
`push-attachment` commands for steps 1 and 3. WorkBuddy can invoke them through
its compose Skill and Bash tool. Configure a trusted `M365_ATTACHMENT_ROOT`
and fixed HTTPS `M365_ATTACHMENT_PUSH_URL` as described in the
[Windows EXE helper guide](windows-local.md#local-exe-helper-for-a-remote-connector).
This helper is optional: another trusted client can implement the same HTTP
contract. The EXE's file-root restriction does not constrain WorkBuddy's
general Bash permission; apply the client's sandbox and approval policy.

## Operating boundaries

- The filename must be a plain name (at most 255 characters); the optional
  MIME type must be valid ASCII. Each upload is non-empty and at most 20 MiB.
- Grants and staged bytes are held in bounded server process memory for five
  minutes. Grant, upload and attachment calls must reach the same worker;
  multiple workers or replicas need a shared-store design that v0.1.1 does
  not provide. Restarting the worker loses outstanding handles.
- Route `/mcp/`, `/uploads/attachments` and `/uploads/push` through the same
  fixed HTTPS origin. Keep bearer tokens and `X-Upload-Handle` out of logs;
  enforce proxy body-size and rate limits as detailed in the
  [deployment guide](deployment.md#oauth-authorization).
- A push stages a file but does not attach it. Attaching does not authorize
  sending. Interactive sends need separate confirmation; bounded automation
  needs explicit client/agent authorization. If an attachment or send result
  is ambiguous, inspect the draft before retrying.

Graph uses direct attachment creation below 3 MB and a sequential upload
session for larger files. The server never returns the Graph upload URL or
file bytes through MCP. See the [tool contract](tool-spec.md#mail_add_draft_attachment)
for result fields and limits.
