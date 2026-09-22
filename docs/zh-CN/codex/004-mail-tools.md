[English](../../codex/004-mail-tools.md) | **简体中文**

# Task 004 - Mail MCP Tools

## 目标

实现企业级 Outlook Mail MCP Tools。

## Tools

已实现工具：

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

## 要求

- MCP Tools 必须适合 Agent 使用。
- 不暴露 Raw Graph APIs。
- 使用 `/me` Mailbox Operations。
- 保持 User Identity Isolation。
- 先创建纯文本草稿，并在逐封确认或明确的受限自动化授权后发送。
- 自动化授权必须约束收件人/域名、触发条件、内容规则与可信数据源、单次和每日
  发送量以及到期时间。
- 发送结果不明确时不得自动重试。

## 交付物

- MCP Tool Definitions
- Mail Service Implementation
- Tool Tests

## 非目标

- 不提供一步式直接发送、HTML/附件撰写、Reply 或 Forward。
- 不支持 Shared Mailbox。
