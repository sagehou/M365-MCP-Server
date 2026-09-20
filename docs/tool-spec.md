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

### mail_list_attachments

List attachments for a message.
For file attachments whose Graph response includes `contentBytes`, `size` is the
decoded content length. If Graph's `size` metadata differs, the response also
includes `reported_size` so callers do not confuse a provider-reported metadata
difference with file integrity.

### mail_read_attachment

Extract attachment content for AI processing.

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
are never returned through MCP JSON. `size` is the actual decoded content length;
`reported_size` is included only when the Graph metadata differs. The same size
contract applies to `mail_read_attachment`.

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
