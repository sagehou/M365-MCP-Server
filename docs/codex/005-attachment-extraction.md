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
