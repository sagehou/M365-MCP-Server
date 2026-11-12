**English** | [简体中文](zh-CN/review-status.md)

# Implementation review

## Runtime scope

| Edition | Transport | Tools | Attachment reading |
| --- | --- | --- | --- |
| Python server | Authenticated Streamable HTTP | 11 core tools; OAuth also enables download and upload-grant tools | PDF, DOCX, XLSX, PPTX, TXT, Markdown in isolated Linux workers |
| Windows .NET | stdio | 12 mail tools, including direct attachment saves | Bounded UTF-8 text, JSON, CSV, XML |
| Windows Go | stdio; authenticated loopback Streamable HTTP | 13 mail tools, including direct saves and download URLs | PDF, DOCX, XLSX, PPTX, TXT, Markdown in Windows Job Object workers |

All editions create plain-text drafts and attach files up to 20 MiB. Sending
returns Graph acceptance without claiming delivery. Per-message confirmation or
bounded automation authorization remains a client/agent responsibility. Search
returns one bounded page; continuation cursors, replies, forwarding, shared
mailboxes, OCR, Calendar, Drive, SharePoint and Teams are outside the implemented
scope. Release `v0.1.4` includes the review corrections in
[PR #60](https://github.com/sagehou/M365-MCP-Server/pull/60) and the local-command
and account-type alignment in [PR #63](https://github.com/sagehou/M365-MCP-Server/pull/63).
Release `v0.1.7` streams `mail_save_attachment` bytes to disk in both local
editions with a configurable 150 MiB default limit. Directory priority is
`download_dir`, `M365_ATTACHMENT_ROOT`, then Windows Downloads/M365-MCP; missing
directories are created. Both return the actual absolute path, byte count,
and SHA-256 without overwriting. Text reads and Go temporary URLs retain their
10 MiB limits; .NET has no PDF/Office parser.

## Findings and corrections

- Public OAuth registration bounds request bodies to 128 KiB before parsing,
  including chunked requests and false length headers. Registered redirects
  share authorization's 2048-character limit; malformed deeply nested JSON
  returns a client error.
- .NET keyword/date searches now put dates in KQL; date-only searches use OData
  filtering and received-time ordering. Timezone-free dates and incorrectly
  typed optional arguments are rejected.
- .NET accepts an empty category array to clear categories. Draft text,
  recipients, resource IDs and MIME types have explicit validation and limits.
- .NET attachment listings request metadata without downloading file bytes.
  Invalid Graph responses and malformed JSON-RPC envelopes return errors while
  keeping stdio usable.
- .NET rejects malformed token responses and invalid lifetimes, bounds encrypted
  state reads, and persists login state before reporting browser success.
- Removed the unused Python `MailService.list_messages` wrapper and `tenant_id`
  setting, unused imports, and never-populated .NET profile fields. The unusable
  version-1 state parsing branch was removed; unreadable old state requires
  logout and a new sign-in. Valid version-2 state remains compatible.
- Updated Python direct and transitive dependencies. Container builds use
  Alpine with system security updates, omit unused Debian tools with unresolved
  advisories, and remove `pip` and `uv` after installation. Details are in the
  [dependency audit](runtime-dependency-audit.md).

OAuth services, attachment workers, token-provider interfaces and non-Windows
Go stubs have active callers or platform/test roles and are retained. Both HTTP
client families are required: application Graph/OIDC uses `httpx`; FastMCP/MCP
uses `httpx2`. Historical release-repair workflows remain explicit manual tools.

## GitHub Actions evidence

The PR checks cover these paths; CI, test-image publication and stable releases
share the dependency/security gates relevant to their artifacts.

| Check | Coverage |
| --- | --- |
| Python tests and `pip-audit` | Application factory, both MCP protocol generations, every core mail tool, identity isolation, JWT/OBO, OAuth discovery/PKCE/refresh rotation/replay, upload/download handles and worker limits |
| Ruff and Vulture | Unused imports, undefined names, duplicate definitions, unreachable code and unused variables at 100% confidence; three SDK protocol keyword parameters have line-specific exclusions |
| Docker smoke and Trivy | Exact installed non-root image, health, authentication, OAuth storage, extraction worker, Compose; block known container findings at every severity, including those without fixes |
| Windows .NET checks | All 12 tools through stdio with mock Graph, binary/empty/17 MiB saves, configured limits with known/unknown lengths, default/overridden directories and automatic creation, interrupted/cancelled cleanup, no overwrite, path/link rejection, date/search/category/draft validation, small and chunked attachments, sanitized failures, DPAPI binding/ephemeral state, refresh and malformed token responses |
| Windows .NET artifact | NativeAOT single executable, Windows file details, client-ID defaults/overrides and startup without a runtime on PATH |
| Windows Go checks | Windows/Linux race tests, common save-result contract, binary/empty/17 MiB saves, configured limits with fixed/chunked lengths, default/overridden directories and automatic creation, interrupted/cancelled cleanup, concurrent no-overwrite and path/link rejection, module verification, vet, unreachable application functions and Windows AMD64/ARM64 vulnerability analysis |
| Windows Go artifacts | Single-file AMD64/ARM64 builds, version details, ZIPs/checksums, AMD64 startup without an external runtime, and generated stdio configuration with persisted personal-account state |

---

Known-advisory scans and static analysis describe the checked snapshot, not a proof of zero defects or vulnerabilities. Live tenant consent, real Graph delivery, target-agent integration, Windows ARM64 execution, interactive file-picker behavior and antivirus/code-signing trust have not been validated by these checks. No local tests, builds, dependency installs or virtual environments were used. Updated: 2026-11-12.
