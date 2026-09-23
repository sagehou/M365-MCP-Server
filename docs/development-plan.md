**English** | [简体中文](zh-CN/development-plan.md)

# Development Plan

## Current Delivery Order

1. `v0.1.0` is [released](https://github.com/sagehou/M365-MCP-Server/releases/tag/v0.1.0)
   under MIT with a tested container image and Windows single EXE. The maintainer
   retains live WorkBuddy and mailbox acceptance records outside this repository.
2. Complete post-release hardening: live-test bounded automation sending before
   enabling it in a deployment, validate the Windows EXE on a clean VM, pursue
   antivirus false-positive review and signing, and decide whether WAM is needed.
3. Resume richer attachment processing and broader M365 expansion after the
   local runtime foundation is accepted.

The automated release pipeline passed in GitHub Actions. The maintainer reports
the core live WorkBuddy and mailbox checks passed; bounded automation sending
remains an explicit deployment gate, not a completed live test. See the
[v0.1.0 release checklist](release-checklist.md) for the distinction.

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

Remaining hardening and deployment checks:

- clean-VM public-client sign-in, restart/refresh, logout, and real-mailbox
  acceptance for the released EXE
- target-agent configuration and lifecycle acceptance on supported PCs
- parity decisions for rich attachment extraction and download behavior
- antivirus false-positive review, possible Authenticode signing, and SBOM;
  SHA-256 and GitHub build provenance are already published
- decide from real deployment evidence whether system-browser PKCE is
  sufficient or Windows Web Account Manager is needed

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
