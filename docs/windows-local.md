**English** | [简体中文](zh-CN/windows-local.md)

# Windows local single-executable roadmap

## Decision

After the v0.1 release-hardening gate is complete, the next delivery track is a
Windows-local MCP server. Calendar, Drive, SharePoint, and Teams expansion does
not begin before this track reaches its acceptance gate.

The local server runs on the same PC as the agent. The agent launches the server
as a child process and communicates over MCP stdio. There is no HTTP listener and
no OAuth, JWT, OBO, client secret, or certificate between the agent and the local
server.

Microsoft Graph access uses a separate desktop/public-client application with
delegated permissions. Windows Web Account Manager (WAM) is preferred, with
system-browser authorization code plus PKCE as the fallback. The remote server's
confidential-client and OBO flow remains unchanged.

## Implementation status

- The automated P0 hardening changes are implemented; live WorkBuddy and tenant
  acceptance evidence is still required before release.
- W1 has started with the Graph token-provider boundary and injectable tool
  authentication context.
- W0 packaging feasibility and W2 Windows authentication are not complete. No
  Windows executable has been published.

## Distribution contract

- The user receives and executes one `m365-mcp.exe` file.
- Python, native extensions, and application modules must load from the executable
  without extracting a runtime tree to a temporary directory.
- PyOxidizer is the first packaging candidate. PyInstaller/Nuitka one-file modes
  that unpack a runtime tree are not accepted as satisfying this contract.
- Normal stdio execution must not create services, registry entries, scheduled
  tasks, startup entries, log files, or runtime extraction directories.
- Diagnostics go to `stderr`; `stdout` is reserved exclusively for MCP messages.
- Persistent mode may create exactly one documented DPAPI-protected state file at
  `%LOCALAPPDATA%\M365-MCP-Server\state.bin`.
- `--ephemeral` mode must not persist authentication or application state.
- System-service installation is an explicit compatibility command, never a side
  effect of normal execution.

## Delivery sequence

### P0 — release hardening

- Pin Linux workflows to `ubuntu-24.04` and use Node 24-compatible action majors.
- Assert that the reference returned for a failed tool invocation exactly matches
  the safe audit event ID.
- Complete the documented real WorkBuddy, real mailbox, two-user, restart, and
  cross-tenant acceptance run before publishing the first stable server release.

### W0 — packaging feasibility

- Add a Windows-only optional dependency/build profile; do not increase the
  remote container's runtime surface.
- Build an x64 executable in GitHub Actions only.
- Prove in-memory loading for `cryptography`, `pydantic-core`, `lxml`, FastMCP,
  MSAL, and the supported attachment parsers.
- Run the executable on a clean Windows runner without Python installed on PATH.
- Fail the gate if runtime extraction artifacts remain after normal exit or a
  forced termination.

### W1 — local runtime boundary

- Add an explicit `stdio` entry point and keep the existing HTTP entry point as
  `serve`.
- Inject the authenticated user context into tools instead of reading a FastAPI
  request from inside tool implementations.
- Introduce a Graph token-provider boundary so remote OBO and local public-client
  authentication share the same bounded Graph/mail services.
- Preserve `/me` path confinement, response limits, redaction, audit correlation,
  write ambiguity warnings, and attachment isolation in both modes.

### W2 — Windows delegated authentication

- Use MSAL `PublicClientApplication`; never ship a client secret or private key.
- Prefer WAM for the signed-in Windows user and fall back to system-browser PKCE.
- Protect the optional persistent token cache with current-user DPAPI inside the
  single `state.bin` file.
- Support `login`, `logout`, `status`, `doctor`, `stdio`, and `--ephemeral`.

### W3 — signed release

- Produce the executable only in GitHub Actions on a pinned Windows runner.
- Add Authenticode signing, timestamping, SHA-256 checksums, and an SBOM.
- Publish the exact smoke-tested executable as a GitHub Release asset.
- Document agent configuration using an absolute executable path and stdio.

## Acceptance gate

On a clean supported Windows x64 VM with no Python, Docker, Git, or development
tools installed:

1. One executable starts as an MCP stdio server and lists the expected mail tools.
2. First Graph use signs in the current Windows user without an application
   secret; later calls use the protected cache when persistent mode is selected.
3. Search, read, attachment parsing, and one representative write operation work
   against a real mailbox under delegated permissions.
4. The executable creates no undeclared files or system changes. Persistent mode
   creates only the documented state file; ephemeral mode leaves no state.
5. No token, message body, attachment content, or provider error detail reaches
   logs, stderr diagnostics, or MCP error text.
6. A remote/container regression run remains green, proving that local-mode work
   did not weaken HTTP/OBO isolation.

## Stop conditions

If required native extensions cannot load reliably from the executable, the team
must either replace the incompatible dependency or implement the Windows-local
host in a native Windows technology. Runtime extraction must not be silently
introduced or described as a true single-executable build.
