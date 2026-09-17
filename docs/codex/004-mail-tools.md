**English** | [简体中文](../zh-CN/codex/004-mail-tools.md)

# Task 004 - Mail MCP Tools

## Goal

Implement enterprise Outlook mail MCP tools.

## Tools

Initial tools:

- mail_search
- mail_get
- mail_list_attachments
- mail_mark_read
- mail_archive
- mail_move
- mail_set_category

## Requirements

- MCP tools must be agent friendly.
- Do not expose raw Graph APIs.
- Use /me mailbox operations.
- Preserve user identity isolation.

## Deliverables

- MCP tool definitions
- Mail service implementation
- Tool tests

## Non goals

- No send mail.
- No shared mailbox support.
