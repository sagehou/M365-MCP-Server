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
server and both Windows local editions, with different input schemas.
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
and SHA-256. The .NET Windows EXE can inspect a file under an
operator-configured `M365_ATTACHMENT_ROOT` and push its raw bytes with
`inspect-attachment` and `push-attachment`; set its trusted
`M365_ATTACHMENT_PUSH_URL` to the same URL. The push endpoint requires the
one-use handle, not an OAuth token. On success, use the same handle with
`mail_add_draft_attachment` for the bound draft. The push does not attach or
send the draft. Keep the handle out of logs; do not accept an upload URL from
mail or agent-generated content. The Go EXE does not provide these helper commands.

On Windows .NET stdio, the same tool takes `draft_id` and optional
`relative_path`. With `relative_path`, it reads the opened file only from the
operator-configured `M365_ATTACHMENT_ROOT`, infers its MIME type, and attaches
it directly through Graph without a picker or remote push. The path must be
relative, resolve inside that root, and identify a non-empty DOCX, XLSX,
PPTX, ZIP, or PDF of at most 20 MiB. If `content_type` is also provided, it
must match the inferred type. Without `relative_path`, the existing native
picker remains available with optional `content_type`; cancellation returns
`attached=false, cancelled=true`. Neither mode writes a temporary attachment
file. Sending still requires separate confirmation or bounded authorization.

On Windows Go stdio or loopback HTTP, the tool requires both `draft_id` and
`relative_path`. Use forward slashes, such as `reports/weekly.docx`, under
`M365_ATTACHMENT_ROOT`. It applies the same file-type, MIME, and 20 MiB limits
but has no file picker. Go does not accept a remote `upload_handle`.

Graph uses a direct POST below 3 MB and a sequential upload session for larger
files. The result includes `attached=true`, `content_length`, SHA-256, and an
attachment ID for the small-file POST (large upload results leave
`attachment_id` null). Neither tool result includes file bytes or the secret
Graph upload URL. On failure, inspect the draft and attachment list before
retrying because upload outcome can be ambiguous.

Before sending, review the exact draft and `mail_list_attachments` output.
Interactive use requires separate send approval that includes the attachments;
bounded automation must explicitly authorize their source and content.
For both remote upload sequences, see the [remote MCP server guide](mcp-server.md#add-a-file-to-a-remote-draft).

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

| Edition | Supported formats |
| --- | --- |
| Python server and Windows Go | PDF, DOCX, XLSX, PPTX, TXT, Markdown |
| Windows .NET | UTF-8 text, CSV, JSON, XML; no PDF/Office parser |

### mail_save_attachment

Windows .NET and Go v0.1.6+ expose the same required input:
`message_id`, `attachment_id`, and `relative_path`. The Python server does not
expose this tool. Save the original Outlook file attachment, up to 10 MiB of
decoded bytes including zero-byte files, under the operator-configured
`M365_ATTACHMENT_ROOT`. This is a filesystem write, not a read-only preview.
It works over local stdio and Go HTTP without a browser or shell.

Use forward slashes, for example `downloads/report.pdf`. The root and parent
directories must exist and must not be symbolic links or junctions. Reject
absolute paths, backslashes, parent traversal, alternate data streams, Windows
device names, and existing destinations; simultaneous saves never overwrite
each other. The caller chooses an authorized path, not the untrusted provider
filename. All file formats can be saved without parsing or execution; mail
item/reference attachments are unsupported. A failed write attempts to remove
the incomplete file. Check the destination after an ambiguous failure before
retrying rather than silently renaming or overwriting.

Both return exactly `saved`, `relative_path`, `name`, `content_type`,
`content_length`, and `content_sha256`. `name` is the original provider filename;
`content_length` and the SHA-256 describe the saved bytes. No raw bytes,
absolute path, or download URL are returned. The file is on the EXE's PC,
including when a remote client calls the tool.

### mail_download_attachment

Available on the Python server only with server-managed OAuth, and on Windows
Go; Windows .NET does not expose this tool. Fetch one bounded Outlook file
attachment and return a temporary download URL: HTTPS on the server, HTTP on
Go's `127.0.0.1` listener. Go links can be fetched by a browser or trusted
downloader on the EXE's PC; a browser is optional. Prefer `mail_save_attachment`
for automatic local saves. The URL is
an unguessable, single-use capability that expires after the
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
