# Task 005 - Attachment Extraction

## Goal

Provide AI-friendly attachment reading capabilities.

## Supported formats

- PDF
- DOCX
- XLSX
- PPTX
- TXT
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

Supported handlers are PDF, DOCX, XLSX, PPTX, and UTF-8 TXT. Image OCR and email
classification remain out of scope.
