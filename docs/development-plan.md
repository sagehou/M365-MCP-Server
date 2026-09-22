**English** | [简体中文](zh-CN/development-plan.md)

# Development Plan

## Current Delivery Order

1. Complete the P0 release-hardening gate. The automated CI and image gates are
   implemented; live WorkBuddy happy-path/failure evidence still has to be
   recorded.
2. Promote the Windows local-mode integration build to a release candidate:
   validate real Entra public-client sign-in and a real mailbox, align remaining
   tool contracts, decide whether WAM is required, add code signing, and publish
   a stable downloadable asset.
3. Resume richer attachment processing and broader M365 expansion after the
   local runtime foundation is accepted.

The automated part of P0 is enforced by GitHub Actions. The live WorkBuddy and
Windows/Entra acceptance paths are release gates and are not simulated by unit
tests. Record automated and live evidence in the
[v0.1.0 release checklist](release-checklist.md) before creating the stable tag.

## Windows local-mode implementation status

The first integration implementation is available in
`windows/M365Mcp.Local` and documented in the
[Windows local mode guide](windows-local.md).

Completed in the integration branch:

- .NET 8 NativeAOT, self-contained Windows x64 executable
- one-file artifact check and isolated no-runtime smoke test in GitHub Actions
- MCP stdio server intended to be launched as an agent child process
- system-browser authorization code + S256 PKCE for a dedicated Entra public
  client
- current-user DPAPI-protected refresh state and an `--ephemeral` no-persistence
  mode
- ten bounded mail tools, including draft creation and draft sending
- explicit omission of arbitrary attachment file writes

Remaining release gates:

- live public-client sign-in, restart/refresh, logout, and real-mailbox
  acceptance
- WorkBuddy or target-agent configuration and lifecycle acceptance
- parity decisions for rich attachment extraction and download behavior
- Authenticode signing, malware scanning, provenance/SBOM, and stable release
  publication
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
