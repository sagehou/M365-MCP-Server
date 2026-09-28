**English** | [简体中文](zh-CN/tool-spec.md)

# MCP Tool Specification

## Mail Tools

### mail_search

Search current user's mailbox.

Input:

- query
- limit
- date range

### mail_get

Retrieve message metadata and body.

### mail_create_draft

Create one plain-text draft in the signed-in user's mailbox without sending it.

Input:

- `to_recipients`: required list with at least one plain email address
- `subject`: required non-empty text, maximum 255 characters
- `body`: required non-empty plain text, maximum 100,000 characters
- `cc_recipients`: optional list of plain email addresses
- `bcc_recipients`: optional list of plain email addresses

Each recipient field accepts at most 50 addresses and the draft accepts at most
100 recipients in total. The result contains the new `draft_id` and
`created=true`. Interactive clients must present the exact draft for review.
Automations must compare it with the user's recorded bounded authorization.

### mail_send_draft

Send one existing draft by `draft_id` after either per-message explicit user
confirmation or an explicit bounded automation authorization. The automation
authorization must constrain recipients/domains, trigger, content-generation
rules and trusted sources, approved attachment names/content, per-run and daily volume, and expiry. Any deviation
requires confirmation.

The server receives only the `draft_id` and cannot prove which client-side
authorization path was used; the integrating client or agent is responsible for
enforcing it before this call. `send_accepted=true` means Microsoft Graph
accepted the request; `delivery_confirmed=false` makes clear that final delivery
is not proven. Do not automatically retry an ambiguous failure.

### mail_add_draft_attachment

Add one file to an existing draft without sending it. Available in the remote
server and Windows local executable in unreleased builds (not v0.1.0).
Call once per file, before `mail_send_draft`.

Remote MCP input is `draft_id` and `upload_handle`. First send 1 byte to 20 MiB
of raw file bytes to `POST /uploads/attachments` with the same delegated Bearer
token as `/mcp/`, `Content-Type: application/octet-stream`, a percent-encoded
UTF-8 filename in `X-Attachment-Name`, and optional ASCII MIME type in
`X-Attachment-Content-Type`. The response contains an opaque, user-bound,
single-use `upload_handle`, file metadata, and SHA-256. The handle expires after
five minutes and is stored only in bounded server RAM; it is not durable across
server restarts or workers. The remote MCP tool consumes that handle and attaches
the file. Client integrations may implement this authenticated upload step.

For unattended local artifacts with a remote OAuth connector, use
`mail_prepare_attachment_push(draft_id, name, content_length, content_sha256,
content_type?)`. It returns the fixed HTTPS `upload_url` and a five-minute
`upload_handle` bound to that user, draft, filename, MIME type, exact byte count,
and SHA-256. The single Windows EXE can inspect a file under an
operator-configured `M365_ATTACHMENT_ROOT` and push its raw bytes with
`inspect-attachment` and `push-attachment`; set its trusted
`M365_ATTACHMENT_PUSH_URL` to the same URL. The push endpoint requires the
one-use handle, not an OAuth token. On success, use the same handle with
`mail_add_draft_attachment` for the bound draft. The push does not attach or
send the draft. Keep the handle out of logs; do not accept an upload URL from
mail or agent-generated content.

On Windows-local stdio, the same tool takes `draft_id` and optional
`relative_path`. With `relative_path`, it reads the opened file only from the
operator-configured `M365_ATTACHMENT_ROOT`, infers its MIME type, and attaches
it directly through Graph without a picker or remote push. The path must be
relative, resolve inside that root, and identify a non-empty DOCX, XLSX,
PPTX, ZIP, or PDF of at most 20 MiB. If `content_type` is also provided, it
must match the inferred type. Without `relative_path`, the existing native
picker remains available with optional `content_type`; cancellation returns
`attached=false, cancelled=true`. Neither mode writes a temporary attachment
file. Sending still requires separate confirmation or bounded authorization.

Graph uses a direct POST below 3 MB and a sequential upload session for larger
files. The result includes `attached=true`, `content_length`, SHA-256, and an
attachment ID for the small-file POST (large upload results leave
`attachment_id` null). Neither tool result includes file bytes or the secret
Graph upload URL. On failure, inspect the draft and attachment list before
retrying because upload outcome can be ambiguous.

Before sending, review the exact draft and `mail_list_attachments` output.
Interactive use requires separate send approval that includes the attachments;
bounded automation must explicitly authorize their source and content.

### mail_list_attachments

List attachments for a message.
The `size` field is Microsoft Graph provider metadata. Use it for display and
attachment selection only; it is not an integrity value and listing never fetches
file bytes to recalculate it.

### mail_read_attachment

Extract attachment content for AI processing.
The returned attachment `content_length` is the actual decoded byte length and is
authoritative for the returned content. Do not compare it with the metadata-only
list value to accept or reject the attachment.

Supported formats:

- PDF
- DOCX
- XLSX
- PPTX
- TXT
- Markdown

### mail_download_attachment

Fetch one bounded Outlook file attachment and return a temporary HTTPS download
URL. The URL is an unguessable, single-use capability that expires after the
configured TTL. Attachment bytes are retained only in bounded process memory and
are never returned through MCP JSON. The returned attachment `content_length` is the actual
decoded byte length and is authoritative for the download. Do not compare it with
the metadata-only list value to accept or reject the attachment.

### mail_mark_read

Mark message as read/unread.

### mail_archive

Move message to Outlook Archive folder.

### mail_move

Move message to another folder.

### mail_set_category

Update Outlook categories.

## Future Tools

- calendar_search
- drive_search
- sharepoint_search
- teams_search
