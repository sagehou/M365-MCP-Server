**English** | [简体中文](zh-CN/development-plan.md)

# Development Plan

## Current Delivery Order

1. `v0.1.7` ships under MIT with a container image, Windows .NET/Go single EXEs,
   and the shared bilingual `m365-mail` Skill.
2. Draft-file attachments up to 20 MiB are included: remote clients use binary
   staging and an optional one-use push grant, while Windows local stdio uses a
   bounded relative artifact path or optional native file picker.
3. Future scope includes richer attachment extraction, search continuation,
   replies and forwarding, and broader Microsoft 365 workloads. Signing and
   antivirus false-positive handling are separate Windows distribution concerns.

Deployment-specific acceptance records are kept outside this repository.

## Windows local-mode implementation status

The released Windows implementations are available in
`windows/M365Mcp.Local` and `native`, and documented in the
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

Added in v0.1.1:

- eleven local mail tools, including bounded draft-file attachments
- relative-path attachment automation under `M365_ATTACHMENT_ROOT`
- `inspect-attachment` and `push-attachment` commands for remote connectors

Added since v0.1.2:

- .NET 10 NativeAOT and Go AMD64/ARM64 single executables; shared `stdio` and
  tenant/account options
- Go PDF/Office extraction and temporary download URLs
- both editions stream original attachments with `mail_save_attachment`;
  default Windows Downloads/M365-MCP, optional `download_dir`, automatic
  directory creation, and a configurable 150 MiB default limit in v0.1.7

Current design boundaries:

- .NET reads UTF-8 text/CSV/JSON/XML and has no PDF/Office parser or download URL
  endpoint; both editions can directly save original files
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

Windows Go implements every item above; .NET omits `mail_download_attachment`
and limits `mail_read_attachment` to bounded UTF-8 text-like content. Both add
`mail_save_attachment` and bounded draft attachments.

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
