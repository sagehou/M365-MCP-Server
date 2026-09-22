**English** | [简体中文](../zh-CN/codex/004-mail-tools.md)

# Task 004 - Mail MCP Tools

## Goal

Implement enterprise Outlook mail MCP tools.

## Tools

Implemented tools:

- mail_search
- mail_get
- mail_create_draft
- mail_send_draft
- mail_list_attachments
- mail_read_attachment
- mail_download_attachment
- mail_mark_read
- mail_archive
- mail_move
- mail_set_category

## Requirements

- MCP tools must be agent friendly.
- Do not expose raw Graph APIs.
- Use /me mailbox operations.
- Preserve user identity isolation.
- Create a plain-text draft first and require separate explicit confirmation
  before sending it.
- Do not automatically retry ambiguous send failures.

## Deliverables

- MCP tool definitions
- Mail service implementation
- Tool tests

## Non goals

- No one-step direct-send tool, HTML/attachment composition, reply, or forward.
- No shared mailbox support.
