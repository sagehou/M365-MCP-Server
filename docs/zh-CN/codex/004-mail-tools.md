[English](../../codex/004-mail-tools.md) | **简体中文**

# Task 004 - Mail MCP Tools

## 目标

实现企业级 Outlook Mail MCP Tools。

## Tools

初始工具：

- mail_search
- mail_get
- mail_list_attachments
- mail_mark_read
- mail_archive
- mail_move
- mail_set_category

## 要求

- MCP Tools 必须适合 Agent 使用。
- 不暴露 Raw Graph APIs。
- 使用 `/me` Mailbox Operations。
- 保持 User Identity Isolation。

## 交付物

- MCP Tool Definitions
- Mail Service Implementation
- Tool Tests

## 非目标

- 不发送邮件。
- 不支持 Shared Mailbox。
