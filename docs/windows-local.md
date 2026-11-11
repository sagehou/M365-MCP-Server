**English** | [简体中文](zh-CN/windows-local.md)

# Windows local single-executable

## Current status

The first Windows-local implementation is available in
`windows/M365Mcp.Local` and is built only by GitHub Actions. It is a .NET 10
NativeAOT application that publishes as exactly one `m365-mcp-windows-local-amd64.exe`; the target
PC does not need Python, .NET, Docker, Git, or an installer.

The existing workflow is retained. The separately built
[Go edition](windows-local-go.md) has its own workflow and artifact names.
The published v0.1.3 NativeAOT executable uses .NET 10 LTS.

The executable currently provides:

- `doctor`, `login`, `logout`, `status`, and `stdio` commands
- system-browser authorization code plus S256 PKCE for a dedicated Entra
  desktop/public-client application
- the project `M365-MCP-Localhost` public client built in by default, with an
  enterprise client-ID override
- current-user DPAPI protection for the optional persistent token state
- MCP stdio with eleven bounded Outlook mail tools
- an `--ephemeral` mode that neither reads nor writes persistent state
- a Windows Actions gate that rejects anything except one executable, removes
  language runtimes from `PATH` during smoke testing, and fails if the
  ephemeral smoke run creates files

The [v0.1.3 GitHub Release](https://github.com/sagehou/M365-MCP-Server/releases/tag/v0.1.3)
contains the stable Windows asset, its SHA-256 checksum, MIT notice, and GitHub
Artifact Attestation for the exact smoke-tested binary. Actions artifacts from
ordinary branch builds remain integration builds. The released EXE is unsigned;
Authenticode signing, SBOM, and rich local attachment extraction remain separate
hardening work. Optional WAM depends on deployment requirements. The published
v0.1.3 EXE has eleven mail tools, including draft attachments.

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

- The user receives and executes one `m365-mcp-windows-local-amd64.exe` file.
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

## Antivirus false positives

The unsigned NativeAOT executable may be quarantined by endpoint security
software. No build option, ZIP wrapper, checksum, or GitHub attestation can
guarantee an antivirus allow decision. The Windows build embeds the product
name, file description, and version; these help identify a sample but are not
a publisher signature.

If a security product blocks the EXE:

1. Obtain the exact EXE and `.sha256` file from the project's GitHub Release.
   Compare `Get-FileHash .\m365-mcp-windows-local-amd64.exe -Algorithm SHA256` with the
   published checksum and, if GitHub CLI is available, run
   `gh attestation verify m365-mcp-windows-local-amd64.exe --repo sagehou/M365-MCP-Server`.
   Stop if either verification fails.
2. Record the security product and definition versions, detection name, SHA-256,
   source Release URL, and the step that triggered detection. Do not include
   tokens, mail content, or unredacted user/tenant IDs.
3. Submit the *exact detected binary* as a suspected false positive to that
   vendor. For Qianxin, use its official
   [sample upload form](https://www.qianxin.com/other/sample-upload); the form
   has a 100 MB file limit and asks for a contact email and CAPTCHA. Include
   the repository and Release URL, build provenance, and a short explanation:
   this is a single-file MCP stdio process, opens the system browser for Entra
   PKCE, listens only on loopback during sign-in, calls Microsoft Graph, and
   optionally stores DPAPI-protected state at the documented path.
4. Wait for the vendor's determination and updated definitions, then retest
   the same SHA-256 on the affected endpoint. If a managed business endpoint
   needs an interim exception, let its security administrator assess a narrow,
   time-limited rule for the verified exact file hash. Do not disable the
   security product or exempt a whole directory or process family.

Repeat the sample review for a changed binary hash; a prior verdict does not
automatically cover new builds. GitHub attestation proves build provenance,
not that the binary is malware-free or trusted by every antivirus engine.

For Qianxin or another managed endpoint product that requests MD5 and SHA-1
for exact-file allowlisting, use the values for `m365-mcp-windows-local-amd64.exe` in
the same GitHub Release description. First confirm the EXE's SHA-256 against
the published `.sha256` file; then give the MD5 and SHA-1 to the security
administrator for a narrowly scoped rule. These older hashes are not proof of
authenticity and must be recalculated for any changed executable.

## Entra public-client setup

The NativeAOT executable embeds the Client ID of this project-managed public
client by default. It does not embed or use a Client Secret:

```text
Application name: M365-MCP-Localhost
Application (client) ID: 6e35216e-2623-43cc-b867-83bec0865cf3
Authority: organizations
```

Using this built-in application does not require a new registration. For
organization deployments, we recommend a dedicated desktop/public-client
application managed in your own tenant:

1. Open the [Microsoft Entra admin center](https://entra.microsoft.com/), switch
   to the tenant that will own the application, then select **Entra ID > App
   registrations > New registration**. Enter a name such as
   `M365-MCP-Local-Custom` and choose **Supported account types** from the table
   below. Leave the initial redirect URI empty and select **Register**.
2. On **Overview**, copy **Application (client) ID** and **Directory (tenant)
   ID**. Use the application ID for `M365_LOCAL_CLIENT_ID`; do not use the
   **Object ID**.
3. Open **Authentication > Add a platform > Mobile and desktop applications**.
   Add `http://localhost` as a custom redirect URI and save. Use the root path;
   do not append `/callback`, specify a fixed port, or add the same URI under
   **Web** or **Single-page application**. No client secret or certificate is
   needed.
4. Open **API permissions > Add a permission > Microsoft Graph > Delegated
   permissions**, add the three permissions below, and save. If the tenant
   allows user consent, continue with local sign-in. Use the organization's
   admin-consent process only when policy requires approval.

| Supported account types in the registration | `M365_LOCAL_TENANT_ID` |
| --- | --- |
| Accounts in this organizational directory only | The owning Directory (tenant) ID; recommended for one organization |
| Accounts in any organizational directory | `organizations`, or a specific organizational tenant ID |
| Accounts in any organizational directory and personal Microsoft accounts | `common` for both organizational and personal accounts |
| Personal Microsoft accounts only | `consumers` in this NativeAOT edition |

| Microsoft Graph delegated permission | Use in the current release | Admin consent required by the permission itself |
| --- | --- | --- |
| `User.Read` | Included in the default sign-in request; mail operations do not use the profile API | No |
| `Mail.ReadWrite` | Read and modify mail, drafts, and attachments | No |
| `Mail.Send` | Send mail as the signed-in user | No |

<details>
<summary>ⓘ Public-client settings and account types</summary>

The registered **Mobile and desktop applications** redirect identifies the
browser-based Authorization Code + S256 PKCE flow as a public client. Entra
ignores the random port when matching `http://localhost`, but the path must
match. **Allow public client flows** can remain at its default **No** for this
flow; that switch enables other flows such as device code, username/password,
and Integrated Windows Authentication. See Microsoft's
[desktop registration](https://learn.microsoft.com/en-us/entra/identity-platform/scenario-desktop-app-configuration)
and [public-client guidance](https://learn.microsoft.com/en-us/entra/identity-platform/msal-client-applications).

The tenant setting accepts a GUID, `organizations`, `common`, or `consumers`.
Changing it does not change the registration's supported account types. The
selected account must have an accessible Outlook/Exchange mailbox. If **New
registration** is unavailable, ask the tenant administrator for
application-registration access; this is separate from consent to mailbox
permissions.

A Client ID is a public identifier. Create a dedicated desktop registration
instead of distributing credentials from the Python server's confidential-client/
OBO registration. Mailbox **Application permissions** and an exposed
`access_as_user` API are not needed for local use.

</details>

<details>
<summary>ⓘ User.Read, custom scopes, and administrator approval</summary>

`User.Read` is not required by the mail endpoints or by PKCE sign-in itself.
The current executable still requests it by default. Removing it from the
registration's **API permissions** list does not remove it from that request.
The NativeAOT edition supports an explicit scope override, for example:

```powershell
$env:M365_LOCAL_GRAPH_SCOPES = 'openid profile offline_access https://graph.microsoft.com/Mail.ReadWrite https://graph.microsoft.com/Mail.Send'
```

This replaces the entire default scope list. Keep `offline_access` so the
executable can obtain the refresh token it requires. Stop the MCP client/server,
run `logout`, then `login` again; carry the same scope setting into the MCP
client's `env` block. The Go edition does not support this variable.

Microsoft lists **AdminConsentRequired: No** for all three
[delegated permissions](https://learn.microsoft.com/en-us/graph/permissions-reference).
The tenant's [user-consent policy](https://learn.microsoft.com/en-us/entra/identity/enterprise-apps/configure-user-consent)
can still require approval: user consent may be disabled, the application may
not meet publisher requirements, or the mail permissions may not be classified
as low impact. Removing `User.Read` does not bypass those policies.

If approval is required, give the administrator the application ID, target
tenant, requested delegated permissions, and the sign-in error code. For an
application registered in that tenant, an authorized administrator can review
**App registrations > your app > API permissions > Grant admin consent for
the tenant**. For another tenant, use that tenant's admin-consent workflow;
consent in the application's home tenant does not grant consent elsewhere.
Approval must cover the current permissions and be renewed if new permissions
are added or the grant is revoked.

</details>

## Run

In PowerShell:

```powershell
.\m365-mcp-windows-local-amd64.exe doctor
.\m365-mcp-windows-local-amd64.exe login
.\m365-mcp-windows-local-amd64.exe status
```

The default build needs no environment variables. Override it only when using
an enterprise-owned App Registration:

```powershell
$env:M365_LOCAL_CLIENT_ID = "<custom-desktop-public-client-id>"
$env:M365_LOCAL_TENANT_ID = "<directory-tenant-id>"
.\m365-mcp-windows-local-amd64.exe doctor
.\m365-mcp-windows-local-amd64.exe login
.\m365-mcp-windows-local-amd64.exe status
```

Set these values before running `login`. `doctor` should report your
`client_id`, the selected `tenant`, and `client_id_source: "environment"`;
`status` reports `authenticated: true` while the cached access token is usable.

`login` opens the system browser, completes PKCE on loopback, then saves the
DPAPI-protected state. Use `--ephemeral` with `login` or `stdio` when no
authentication state may survive process exit.

MCP client configuration for the custom application:

```json
{
  "mcpServers": {
    "m365-local": {
      "command": "C:\\Tools\\m365-mcp-windows-local-amd64.exe",
      "args": ["stdio"],
      "env": {
        "M365_LOCAL_CLIENT_ID": "<custom-desktop-public-client-id>",
        "M365_LOCAL_TENANT_ID": "<directory-tenant-id>"
      }
    }
  }
}
```

Replace the path and both IDs with your actual values. The NativeAOT edition
reads these variables on every start; a PowerShell `$env:` assignment affects
that session and its child processes, not an already-running MCP client.
Keep the client ID and tenant identical in `login` and the MCP configuration.
For the built-in application, omit the `env` block. Login, `stdio`, and logout
must run as the same Windows user to use the DPAPI-protected state.

The first tool call can also start interactive sign-in if no usable state exists.
The agent must allow enough time for the user to finish the browser flow.

<details>
<summary>ⓘ Switch applications or return to the built-in application</summary>

Stop the MCP client, run `logout`, set the new application and tenant, then
repeat `doctor` and `login`. Update the MCP client's `env` block and restart
it. A client-ID or tenant-ID change prevents reuse of the old DPAPI token state.

To return to the built-in application from PowerShell:

```powershell
.\m365-mcp-windows-local-amd64.exe logout
Remove-Item Env:M365_LOCAL_CLIENT_ID, Env:M365_LOCAL_TENANT_ID, Env:M365_LOCAL_GRAPH_SCOPES -ErrorAction SilentlyContinue
.\m365-mcp-windows-local-amd64.exe doctor
.\m365-mcp-windows-local-amd64.exe login
```

Also remove these overrides from the MCP client's `env` block. Local logout
does not revoke tenant consent or browser sessions.

</details>

<details>
<summary>ⓘ Troubleshoot custom-application sign-in</summary>

| Sign-in message or symptom | Check or action |
| --- | --- |
| Need admin approval / `AADSTS90094` / `AADSTS65001` | Check the target tenant's consent grant and user-consent policy; `65001` can also mean the user has not yet granted consent. |
| `AADSTS50011` / redirect URI mismatch | Register the root `http://localhost` under **Mobile and desktop applications**, with no extra path. |
| `AADSTS7000218` / client secret requested | Check the redirect's platform; correct a Web-platform registration rather than adding a secret. |
| `AADSTS700016` / application not found | Check Application (client) ID, tenant selection, and supported account types. |
| PowerShell login succeeds but the MCP client asks again | Check that both processes run as the same Windows user with the same `env` values; `--ephemeral` does not persist state between processes. |
| `doctor` succeeds but sign-in or mail access fails | `doctor` validates local configuration only. Check Entra consent and the account's Exchange/Outlook mailbox availability separately. |

</details>

## Current local tool surface

The executable exposes these tools:

- `mail_search`
- `mail_get`
- `mail_create_draft`
- `mail_send_draft`
- `mail_add_draft_attachment` (one file up to 20 MiB per call)
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

### Unattended artifacts for a Windows-local connector

For unattended automation using the Windows-local stdio connector, set
`M365_ATTACHMENT_ROOT` in the connector process environment to a trusted,
absolute output directory. Call
`mail_add_draft_attachment(draft_id, relative_path="reports\\weekly.docx")`.
The tool reads only an opened file whose resolved path stays inside that root,
with the same 20 MiB and DOCX/XLSX/PPTX/ZIP/PDF limits as the EXE upload
commands. It attaches directly through the locally signed-in user's Graph
session: no browser upload, second connector, Bash command, or remote push URL
is needed. It never writes a temporary attachment file or returns file bytes
through MCP. Omit `relative_path` for the existing interactive Windows file
picker. Review the draft and attachment list before an authorized send.

### Local EXE helper for a remote connector

The same released single EXE also provides
`inspect-attachment <relative-path>` and `push-attachment <relative-path>`.
These commands do not use Entra login or start an MCP connector. Set
`M365_ATTACHMENT_ROOT` to a trusted, absolute directory containing completed
automation outputs, and `M365_ATTACHMENT_PUSH_URL` to the server's fixed HTTPS
`/uploads/push` URL. The caller may specify only a relative path beneath that
root; the EXE checks the opened file's resolved path, permits DOCX, XLSX,
PPTX, ZIP, and PDF, and rejects empty files or files over 20 MiB. It creates
no temporary file.

`inspect-attachment` returns the local file's name, MIME type, byte length and
SHA-256. `push-attachment` accepts the complete grant JSON through standard
input for the same path. The EXE checks the configured URL and the file again
before posting raw bytes; it receives no user OAuth token and does not follow
HTTP redirects. The full server-side grant, upload, attachment and send
sequence belongs to the [remote MCP server guide](mcp-server.md).

For example, in PowerShell with an already received MCP grant JSON held only in
`$grantJson`:

```powershell
$env:M365_ATTACHMENT_ROOT = 'C:\Automation\Output'
$env:M365_ATTACHMENT_PUSH_URL = 'https://mcp.example.com/uploads/push'
& 'C:\Tools\m365-mcp-windows-local-amd64.exe' inspect-attachment 'reports\weekly.docx'
$grantJson | & 'C:\Tools\m365-mcp-windows-local-amd64.exe' push-attachment 'reports\weekly.docx'
```

Do not log the grant or place it in command arguments. If inspection and push
differ, regenerate the grant; never guess the hash.
The WorkBuddy compose Skill can invoke these commands through its Bash tool;
the EXE must be installed at an operator-approved path. A bounded automation
authorization must still name the permitted output source, recipients, sizes,
message limits, and expiry. The EXE's file-root check limits only this command:
WorkBuddy's general Bash permission may access other files, so use the client's
own sandbox and tool-approval policy for that broader capability.

## Build and obtain the integration artifact

The `Windows local executable` workflow publishes the
`m365-mcp-windows-local-amd64` Actions artifact. The workflow:

1. runs on a pinned Windows runner;
2. publishes `windows/M365Mcp.Local/M365Mcp.Local.csproj` with NativeAOT;
3. asserts that the output contains exactly `m365-mcp-windows-local-amd64.exe`;
4. runs `doctor`, MCP `initialize`, and `tools/list` with no language runtime
   on `PATH`;
5. asserts that the ephemeral run leaves no files.

Do not describe an Actions artifact as a stable release. The tagged release
workflow rebuilds and smoke-tests the Windows x64 executable, publishes its
SHA-256 checksum and MIT notice, records GitHub Artifact Attestation for that
binary, and attaches the exact tested files to the GitHub Release.

## Follow-up hardening and deployment checks

- Validate browser PKCE first, then decide whether optional WAM integration is
  justified by account-selection, SSO, or tenant-policy requirements.
- Add safe rich attachment extraction without runtime extraction.
- Exercise search, read, draft, confirmed send, bounded automation send,
  attachment reading, and representative mutations against a real mailbox.
- Verify refresh, logout, corrupted-state recovery, two-account isolation, and
  tenant policy behavior.
- Add Authenticode signing, timestamping, and an SBOM as follow-up hardening; SHA-256 checksums and GitHub Artifact Attestation accompany v0.1.3.
- Validate the published executable on a clean Windows x64 VM.
