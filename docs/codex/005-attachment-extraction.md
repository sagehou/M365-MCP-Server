**English** | [简体中文](../zh-CN/codex/005-attachment-extraction.md)

# Task 005 - Attachment Extraction

## Goal

Provide AI-friendly attachment reading capabilities.

## Supported formats

- PDF
- DOCX
- XLSX
- PPTX
- TXT
- Markdown (`.md`, `.markdown`)
- Images (future OCR)

## Requirements

- Do not return large base64 payloads to models.
- Extract text server-side.
- Provide metadata and extracted content.

## Deliverables

- Extractor abstraction
- Format handlers
- Attachment MCP tool
- Tests

## Non goals

- No email classification.

## Implementation notes

The mail_read_attachment tool accepts only the current user's message and
attachment identifiers. Graph file-attachment bytes are decoded inside the
server, bounded by ATTACHMENT_MAX_BYTES, and passed to format handlers for
server-side extraction. Returned text is bounded by
ATTACHMENT_MAX_TEXT_CHARS; raw contentBytes is never returned.

Supported handlers are PDF, DOCX, XLSX, PPTX, UTF-8 TXT, and UTF-8 Markdown.
Image OCR and email classification remain out of scope.

`mail_download_attachment` uses the same bounded Graph file-attachment decode
path but does not parse the file. It retains bytes only in a bounded in-memory
store and returns a short-lived, single-use capability URL. Tickets are hashed,
expire automatically, and are invalidated by process restart.
