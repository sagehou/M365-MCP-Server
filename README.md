**English** | [简体中文](README.zh-CN.md)

# M365 MCP Server

A self-hosted Microsoft 365 MCP gateway with a deliberately bounded tool surface,
delegated Microsoft Entra identity, per-user isolation, and security-focused
handling of Outlook mail and attachments.

> **Current status:** the remote Streamable HTTP server is an Outlook Mail v0.1
> release candidate. Automated CI is green, but real WorkBuddy, tenant, mailbox,
> restart, and cross-tenant acceptance is still required before the first stable
> release. A Windows x64 NativeAOT integration build now produces one
> dependency-free `m365-mcp.exe` in Actions; it is not yet a signed stable
> release.

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

### Outlook Mail tools

| Tool | Purpose | Type |
|---|---|---|
| `mail_search` | Search one bounded page of the signed-in user's mailbox | Read |
| `mail_get` | Read one message | Read |
| `mail_create_draft` | Create a reviewed plain-text draft without sending it | Write |
| `mail_send_draft` | Send one confirmed or bounded-preauthorized existing draft | Write |
| `mail_list_attachments` | List attachment metadata | Read |
| `mail_read_attachment` | Extract bounded text from a supported attachment | Read |
| `mail_download_attachment` | Create a short-lived, single-use download link | Read |
| `mail_mark_read` | Mark a message read or unread | Write |
| `mail_archive` | Move a message to Archive | Write |
| `mail_move` | Move a message to a specified folder ID | Write |
| `mail_set_category` | Replace message categories | Write |

Interactive sends require per-message confirmation. An unattended automation may
send without prompting on every run only when the user explicitly pre-authorizes
its recipients/domains, trigger, content rules, trusted data sources, per-run and
daily limits, and expiry. Any deviation pauses for confirmation.

Attachment processing supports PDF, DOCX, XLSX, PPTX, text, and guarded archive
inspection. Parsing runs in supervised worker processes with byte, archive,
resource, and timeout limits. Attachment and message content is treated as
untrusted data.

## Runtime architecture

### Remote server — implemented

```text
MCP client / WorkBuddy
        |
        | Streamable HTTP + Entra delegated bearer token
        v
M365 MCP Server
        |
        | OBO token exchange
        v
Microsoft Graph / signed-in user's mailbox
```

### Windows local mode — under development

```text
Agent on Windows
        |
        | MCP stdio
        v
m365-mcp.exe
        |
        | Public-client delegated sign-in (browser PKCE; optional WAM after live evaluation)
        v
Microsoft Graph / signed-in Windows user
```

The first local integration build is implemented as a separate .NET 8 NativeAOT
host. It provides public-client browser PKCE, current-user DPAPI state,
`login/logout/status/doctor/stdio`, and ten local mail tools. GitHub Actions
must publish exactly one `m365-mcp.exe`, run it without a language runtime on
`PATH`, and prove that an ephemeral smoke run leaves no files.

The remote Python server remains unchanged. Normal local stdio execution does not
install services or create registry, startup, scheduled-task, extraction, or log
files. Optional WAM evaluation, rich PDF/Office attachment parsing, signing, and
clean-VM live acceptance remain open. See the
[Windows local single-executable guide](docs/windows-local.md).

## Release and validation status

| Area | Status |
|---|---|
| Python tests and bilingual documentation checks | Run in GitHub Actions |
| Production Docker image build | CI-covered |
| Container health smoke test | CI-covered |
| Docker Compose validation | CI-covered |
| Mock WorkBuddy OAuth and refresh flow | CI-covered |
| Real WorkBuddy and real mailbox acceptance | Pending release gate |
| First stable `v0.1.0` GitHub release | Not published |
| Windows single executable | NativeAOT Actions integration artifact; unsigned and not released |

GitHub Actions is the only build and test environment for this repository.
A configured release workflow or successful image build does not mean a stable
image has been published.

## Deploy the current server

Configure Microsoft Entra first. The portal guide covers the App Registration,
`access_as_user`, delegated Microsoft Graph permissions, OBO/OAuth credentials,
tenant selection, and consent:

- [Microsoft Entra app registration guide](docs/entra-app-registration.md)

Then follow the [deployment checklist](docs/deployment.md):

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d
```

The application exposes:

- `GET /health` and `GET /healthz` for process liveness only.
- `/mcp/` for the protected FastMCP Streamable HTTP endpoint.

Before using `/mcp/`, configure `CLIENT_ID`, exactly one shared OAuth/OBO
client credential, `ALLOWED_TENANTS`, `REQUIRED_SCOPES`, and
`GRAPH_CONSENT_SCOPES`. `ALLOWED_TENANTS` accepts a comma-separated tenant
allowlist or `*` for any valid Microsoft tenant; an empty value fails closed.
`AUDIENCE` is optional and defaults to accepting the client ID and
`api://<client-id>` forms. OBO uses
`GRAPH_SCOPES=https://graph.microsoft.com/.default`.

## Not implemented yet

- Real-client and real-tenant release acceptance.
- Search continuation cursors and folder discovery.
- Reply and forward workflows; HTML and attachment composition.
- OCR, shared mailboxes, RBAC, read-only mode, dynamic tool exposure, and rate
  limiting.
- Calendar, OneDrive, SharePoint, and Teams.
- A signed, clean-VM-accepted Windows EXE release; optional WAM evaluation and rich local attachment parsing.

## Documentation

- [Development plan](docs/development-plan.md)
- [Implementation review status](docs/review-status.md)
- [Windows local roadmap](docs/windows-local.md)
- [v0.1.0 release checklist](docs/release-checklist.md)
- [v0.1.0 release notes](docs/releases/v0.1.0.md)
- [WorkBuddy OAuth guide](docs/workbuddy-oauth.md)
- [Runtime dependency audit](docs/runtime-dependency-audit.md)
- [Deployment checklist](docs/deployment.md)

The current delivery order is: finish the real v0.1 acceptance gate, deliver the
Windows local runtime, then resume Outlook workflow completion and broader
Microsoft 365 workloads.
