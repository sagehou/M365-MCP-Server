**English** | [简体中文](README.zh-CN.md)

# M365 MCP Server

A self-hosted Microsoft 365 MCP gateway with a deliberately bounded tool surface,
delegated Microsoft Entra identity, per-user isolation, and security-focused
handling of Outlook mail and attachments.

> **Current status:** `v0.1.0` release preparation is in progress. Automated CI
> validates the release pipeline, including the container image and Windows x64
> NativeAOT executable. Stable publication remains gated by real WorkBuddy,
> tenant, mailbox, restart, and cross-tenant acceptance evidence.

## What works today

### Remote MCP server

- FastMCP Streamable HTTP endpoint at `/mcp/`.
- Microsoft Entra bearer-token validation with tenant and scope enforcement.
- Microsoft Graph delegated access through On-Behalf-Of (OBO).
- Per-request user identity isolation; Graph calls are confined to `/me`.
- Optional OAuth discovery, dynamic public-client registration, interactive
  sign-in, S256 PKCE, encrypted refresh sessions, rotation, and replay rejection.
- A WorkBuddy connector package under `workbuddy/` with a mocked end-to-end
  client flow in CI.
- Structured, redacted audit events with correlation IDs returned in safe errors.

### Windows local executable

The Windows x64 NativeAOT local runtime is part of the v0.1.0 release target.
The release pipeline publishes:

- `m365-mcp-windows-x64.exe`
- SHA-256 checksum
- GitHub Artifact Attestation provenance

The executable does not require Python, .NET runtime, Docker, or an installer on
the target PC. Authenticode signing remains a future hardening item.

## Release and validation status

| Area | Status |
|---|---|
| Python tests and bilingual documentation checks | Run in GitHub Actions |
| Production Docker image build | CI-covered |
| Container health smoke test | CI-covered |
| Docker Compose validation | CI-covered |
| Windows NativeAOT executable build | CI-covered |
| Windows SHA-256 and provenance attestation | Included in v0.1.0 release pipeline |
| Real WorkBuddy and real mailbox acceptance | Pending release gate |
| Stable `v0.1.0` GitHub release | Pending release gate |

GitHub Actions is the only build and test environment for this repository.

## Not implemented yet

- Real-client and real-tenant release acceptance.
- Search continuation cursors and folder discovery.
- Reply and forward workflows; HTML and attachment composition.
- OCR, shared mailboxes, RBAC, read-only mode, dynamic tool exposure, and rate
  limiting.
- Calendar, OneDrive, SharePoint, and Teams.
- Authenticode signing and clean-VM acceptance for the Windows EXE; optional WAM evaluation and rich local attachment parsing.

See the [v0.1.0 release checklist](docs/release-checklist.md) before deployment.
