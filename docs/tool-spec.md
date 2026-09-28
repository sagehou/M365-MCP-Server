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

Input: `draft_id`, plain `name`, `content_base64`, and optional ASCII
`content_type` (default `application/octet-stream`). The decoded file must be
1 byte to 20 MiB. Graph uses a direct POST below 3 MB and a sequential upload
session for larger files. The MCP client must supply the bytes; neither runtime
reads arbitrary file paths or writes temporary attachment files. A 20 MiB file
expands to about 27 MiB of base64 in one MCP request, so remote reverse proxies
must permit a request body above that size. The result includes `attached=true`,
`content_length`, SHA-256, and an attachment ID for the small-file POST (large
upload responses leave `attachment_id` null); it never
returns bytes or the secret upload URL. On failure, inspect the draft and its
attachment list before retrying because upload outcome can be ambiguous.

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
