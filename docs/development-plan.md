**English** | [简体中文](zh-CN/development-plan.md)

# Development Plan

## Current Delivery Order

1. `v0.1.0` is [released](https://github.com/sagehou/M365-MCP-Server/releases/tag/v0.1.0)
   under MIT with a container image and Windows single EXE.
2. Current source adds file attachments to drafts (up to 20 MiB) through binary
   staging for remote clients, or a bounded relative artifact path and optional
   native file picker for Windows. This is not part of the published v0.1.0 assets.
3. Future scope includes richer attachment extraction, search continuation,
   replies and forwarding, and broader Microsoft 365 workloads. Signing and
   antivirus false-positive handling are separate Windows distribution concerns.

Deployment-specific acceptance records are kept outside this repository.

## Windows local-mode implementation status

The released Windows implementation is available in
`windows/M365Mcp.Local` and documented in the
[Windows local mode guide](windows-local.md).

Delivered in v0.1.0:

- .NET 8 NativeAOT, self-contained Windows x64 executable
- one-file artifact check and isolated no-runtime smoke test in GitHub Actions
- MCP stdio server intended to be launched as an agent child process
- system-browser authorization code + S256 PKCE for a dedicated Entra public
  client
- current-user DPAPI-protected refresh state and an `--ephemeral` no-persistence
  mode
- ten bounded mail tools, including draft creation and draft sending
- explicit omission of arbitrary attachment file writes

Current design boundaries:

- local rich attachment extraction and download parity are not implemented
- SHA-256 and GitHub build provenance are published; optional Authenticode
  signing and an SBOM are distinct distribution improvements
- Windows Web Account Manager is optional and depends on deployment needs

Windows Service installation is not part of the current stdio contract. An
stdio MCP host is owned by the agent process; service mode would require a
separate IPC transport and an explicit lifecycle/security design.

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

Windows local mode currently implements every item above except
`mail_download_attachment`; local `mail_read_attachment` is limited to bounded
text-like content.

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
