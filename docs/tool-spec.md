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
`created=true`. The caller must present the exact draft for review before
requesting a separate confirmation to send it.

### mail_send_draft

Send one existing draft by `draft_id`, only after separate explicit user
confirmation. `send_accepted=true` means Microsoft Graph accepted the request;
`delivery_confirmed=false` makes clear that final delivery is not proven. Do
not automatically retry an ambiguous failure.

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
