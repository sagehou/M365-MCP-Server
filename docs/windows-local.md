**English** | [简体中文](zh-CN/windows-local.md)

# Windows local single-executable

## Current status

The first Windows-local implementation is available in
`windows/M365Mcp.Local` and is built only by GitHub Actions. It is a .NET 8
NativeAOT application that publishes as exactly one `m365-mcp.exe`; the target
PC does not need Python, .NET, Docker, Git, or an installer.

The executable currently provides:

- `doctor`, `login`, `logout`, `status`, and `stdio` commands
- system-browser authorization code plus S256 PKCE for a dedicated Entra
  desktop/public-client application
- current-user DPAPI protection for the optional persistent token state
- MCP stdio with ten bounded Outlook mail tools
- an `--ephemeral` mode that neither reads nor writes persistent state
- a Windows Actions gate that rejects anything except one executable, removes
  language runtimes from `PATH` during smoke testing, and fails if the
  ephemeral smoke run creates files

This is an integration build, not yet a signed stable release. WAM broker
integration, PDF/Office attachment extraction, Authenticode signing, SBOM, and
clean-VM live mailbox acceptance remain required.

## Runtime decision

The remote/container server remains Python 3.12. The Windows-local host is a
small separate .NET NativeAOT boundary that implements only local authentication,
MCP stdio, and the bounded Graph/mail surface.

This replaces the earlier PyOxidizer candidate. PyOxidizer's latest stable
release embeds CPython 3.10 and is not a supportable basis for this Python 3.12
application. PyInstaller and Nuitka one-file modes extract a runtime tree before
execution, so they do not satisfy the no-extraction contract. NativeAOT produces
a native Windows executable and needs no Python or .NET runtime on the user PC.

## Distribution contract

- The user receives and executes one `m365-mcp.exe` file.
- Normal execution does not extract a runtime tree.
- `stdio` does not install a service, write registry/startup/scheduled-task
  entries, or create log files.
- MCP JSON-RPC is the only stdout content; diagnostics use stderr.
- Persistent mode may create one documented current-user file:
  `%LOCALAPPDATA%\M365-MCP-Server\state.bin`.
- The state contains OAuth tokens protected with current-user Windows DPAPI.
- `--ephemeral` does not read, create, or modify the state file.
- The agent launches `stdio` as a child process. Windows service installation
  is not part of this build because a service cannot own the agent's stdio
  channel.

## Entra public-client setup

Create a separate App Registration for the Windows-local executable:

1. Add the **Mobile and desktop applications** platform.
2. Register `http://localhost` as the redirect URI. The executable listens on a
   random loopback port for each sign-in.
3. Configure delegated Microsoft Graph permissions:
   `User.Read`, `Mail.ReadWrite`, and `Mail.Send`.
4. Do not create or distribute a client secret or certificate.
5. Record the Application (client) ID and, when required, the tenant ID.

The remote server's confidential-client/OBO App Registration is unchanged and
must not be reused as a public desktop credential.

## Run

In PowerShell:

```powershell
$env:M365_LOCAL_CLIENT_ID = "<desktop-public-client-id>"
$env:M365_LOCAL_TENANT_ID = "organizations"

.\m365-mcp.exe doctor
.\m365-mcp.exe login
.\m365-mcp.exe status
```

`login` opens the system browser, completes PKCE on loopback, then saves the
DPAPI-protected state. Use `--ephemeral` with `login` or `stdio` when no
authentication state may survive process exit.

Example MCP client configuration:

```json
{
  "mcpServers": {
    "m365-local": {
      "command": "C:\\Tools\\m365-mcp.exe",
      "args": ["stdio"],
      "env": {
        "M365_LOCAL_CLIENT_ID": "<desktop-public-client-id>",
        "M365_LOCAL_TENANT_ID": "organizations"
      }
    }
  }
}
```

The first tool call can also start interactive sign-in if no usable state exists.
The agent must allow enough time for the user to finish the browser flow.

## Current local tool surface

The executable exposes these tools:

- `mail_search`
- `mail_get`
- `mail_create_draft`
- `mail_send_draft`
- `mail_list_attachments`
- `mail_read_attachment` for bounded UTF-8 text, CSV, JSON, and XML
- `mail_mark_read`
- `mail_archive`
- `mail_move`
- `mail_set_category`

`mail_download_attachment` is intentionally absent because the local stdio
runtime has no HTTP download endpoint and must not write arbitrary files.
PDF/DOCX/XLSX/PPTX extraction remains on the acceptance backlog. Sending still
requires per-message confirmation or an explicit bounded automation
authorization at the client/agent layer.

## Build and obtain the integration artifact

The `Windows local executable` workflow publishes the
`m365-mcp-windows-x64` Actions artifact. The workflow:

1. runs on a pinned Windows runner;
2. publishes `windows/M365Mcp.Local/M365Mcp.Local.csproj` with NativeAOT;
3. asserts that the output contains exactly `m365-mcp.exe`;
4. runs `doctor`, MCP `initialize`, and `tools/list` with no language runtime
   on `PATH`;
5. asserts that the ephemeral run leaves no files.

Do not describe an Actions artifact as a stable release. The signed executable
must later be smoke-tested on a clean supported Windows x64 VM and published as
the exact tested GitHub Release asset.

## Remaining acceptance gate

- Add WAM as the preferred sign-in path while retaining browser PKCE fallback.
- Add safe rich attachment extraction without runtime extraction.
- Exercise search, read, draft, confirmed send, bounded automation send,
  attachment reading, and representative mutations against a real mailbox.
- Verify refresh, logout, corrupted-state recovery, two-account isolation, and
  tenant policy behavior.
- Add Authenticode signing, timestamping, SHA-256 checksums, and an SBOM.
- Publish and verify the exact signed executable on a clean Windows x64 VM.
