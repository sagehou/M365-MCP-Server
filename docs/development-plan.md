**English** | [简体中文](zh-CN/development-plan.md)

# Development Plan

## Current Delivery Order

1. Complete the P0 release-hardening gate: pinned CI images and actions, exact
   audit error correlation, and live WorkBuddy happy-path/failure evidence.
2. Deliver Windows local mode immediately after P0. It runs beside the agent
   over MCP stdio, uses public-client sign-in for Microsoft Graph, and ships as
   a true single executable with no extraction directory. See the
   [Windows local mode roadmap](windows-local.md).
3. Resume attachment processing and broader M365 expansion after the local
   runtime foundation is accepted.

The automated part of P0 is enforced by GitHub Actions. The live WorkBuddy
acceptance remains a release gate and is not simulated by unit tests.
Record both automated and live evidence in the
[v0.1.0 release checklist](release-checklist.md) before creating the stable tag.

## Phase 0 - Bootstrap

- Python project
- FastAPI
- FastMCP
- Docker support
- Health endpoint

## Phase 1 - Authentication

- Microsoft Entra ID integration
- JWT validation
- Tenant allowlist
- OBO token exchange
- Graph client abstraction

## Phase 2 - Mail MVP

Tools:

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

## Phase 3 - Attachment Processing

Support:

- PDF extraction
- DOCX extraction
- XLSX extraction
- PPTX extraction
- OCR interface

## Phase 4 - Enterprise Features

- Audit logging
- Shared mailbox
- RBAC
- Rate limiting
- Observability

## Phase 5 - M365 Expansion

- Calendar
- OneDrive
- SharePoint
- Teams
