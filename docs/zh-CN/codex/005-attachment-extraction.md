[English](../../codex/005-attachment-extraction.md) | **简体中文**

# Task 005 - 附件提取

## 目标

提供适合 AI 使用的 Attachment Reading Capability。

## 支持格式

- PDF
- DOCX
- XLSX
- PPTX
- TXT
- Markdown（`.md`、`.markdown`）
- Images（未来 OCR）

## 要求

- 不向 Model 返回大型 Base64 Payload。
- 在 Server-side 提取文本。
- 返回 Metadata 与 Extracted Content。

## 交付物

- Extractor Abstraction
- Format Handlers
- Attachment MCP Tool
- Tests

## 非目标

- 不进行 Email Classification。

## 实现说明

`mail_read_attachment` 只接受当前用户的 Message ID 和 Attachment ID。Graph File-attachment Bytes 在 Server 内部 Decode，并受 `ATTACHMENT_MAX_BYTES` 限制，然后传给 Format Handler 做 Server-side Extraction。

返回文本受 `ATTACHMENT_MAX_TEXT_CHARS` 限制；Raw `contentBytes` 永远不会返回给 MCP Client。

当前 Handler 支持 PDF、DOCX、XLSX、PPTX、UTF-8 TXT 和 UTF-8 Markdown。Image OCR 与 Email Classification 仍不在 Scope 内。

`mail_download_attachment` 复用同一条受限的 Graph File-attachment Decode Path，但不解析文件。它只在受限 In-memory Store 中保留 Bytes，并返回短时、单次使用的 Capability URL。Ticket 只保存 Hash，会自动过期，且在 Process Restart 后失效。
