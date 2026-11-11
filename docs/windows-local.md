**English** | [简体中文](zh-CN/windows-local.md)

# Windows local edition (.NET and Go)

| Capability | .NET NativeAOT | Go |
| --- | --- | --- |
| Windows architecture | AMD64 / x64 | AMD64 / x64 and ARM64 |
| Runtime installation | None | None |
| Microsoft sign-in | System browser, Authorization Code + S256 PKCE | System browser, Authorization Code + S256 PKCE |
| MCP transport | stdio, command `stdio` | stdio, command `serve`; optional authenticated loopback HTTP |
| Mail tools | 11 | 12, including attachment downloads |
| Attachment text extraction | UTF-8 text, CSV, JSON, XML | PDF, DOCX, XLSX, PPTX, TXT, Markdown |
| Add a local draft attachment | File picker or configured relative path | Configured relative path |
| Remote-server upload helper | `inspect-attachment`, `push-attachment` | Not provided |

## Install

Download the appropriate files from the
[GitHub Release](https://github.com/sagehou/M365-MCP-Server/releases/tag/v0.1.3):

| Edition | Release file | Executable used below |
| --- | --- | --- |
| .NET NativeAOT, Intel/AMD PC | `m365-mcp-windows-local-amd64.exe` | Same filename |
| Go, Intel/AMD PC | `m365-mcp-windows-local-go-amd64.zip` | `m365-mcp-windows-local-go.exe` inside the ZIP |
| Go, Windows on ARM | `m365-mcp-windows-local-go-arm64.zip` | `m365-mcp-windows-local-go.exe` inside the ZIP |

Keep the executable in a stable folder such as `C:\Tools`. Neither edition
requires Python, a .NET runtime, Docker, an installer, or a Windows service.
Compare the downloaded EXE's SHA-256 with its `.sha256` file, or the ZIP's hash
with `SHA256SUMS.txt`:

```powershell
Get-FileHash .\m365-mcp-windows-local-amd64.exe -Algorithm SHA256
Get-FileHash .\m365-mcp-windows-local-go-amd64.zip -Algorithm SHA256
```

Run the command for the file you downloaded. If using a standalone Go EXE,
rename it to `m365-mcp-windows-local-go.exe` or keep its architecture suffix in
all commands and client paths. The ZIP contains this complete guide in both
languages and license notices; only the EXE is needed at runtime.

## Sign in with the built-in application

```text
Application: M365-MCP-Localhost
Public Client ID: 6e35216e-2623-43cc-b867-83bec0865cf3
Default tenant: organizations
```

Open PowerShell in the executable's directory and run the command for your
edition:

```powershell
# .NET NativeAOT
.\m365-mcp-windows-local-amd64.exe login

# Go
.\m365-mcp-windows-local-go.exe login
```

Complete Microsoft sign-in and consent in the system browser. Both editions
use the same built-in public Client ID, have no embedded Client Secret, and
allow your own application to override it. Tenant consent policy also applies
to the built-in application.

## Register your own application

1. Open the [Microsoft Entra admin center](https://entra.microsoft.com/), switch
   to the tenant that will own the application, then select **Entra ID > App
   registrations > New registration**. Use a name such as
   `M365-MCP-Local-Custom`, choose the supported account types below, leave the
   initial redirect URI empty, and select **Register**.
2. Copy **Application (client) ID** and **Directory (tenant) ID** from
   **Overview**. Use the application ID, not **Object ID**, as your Client ID.
3. Under **Authentication > Add a platform > Mobile and desktop applications**,
   add the custom redirect URI `http://localhost` and save. Use the root URI
   without `/callback` or a fixed port. Do not duplicate it under **Web** or
   **Single-page application**.
4. Under **API permissions > Add a permission > Microsoft Graph > Delegated
   permissions**, add the three permissions in the table below. Do not create
   a Client Secret, mailbox Application permissions, or an `access_as_user` API
   for this local application.
5. Continue with your edition's configuration below. When tenant policy allows
   user consent, grant the delegated permissions during sign-in. Use the
   organization's admin-consent process only when approval is required.

| Registration's supported account types | Tenant setting | Editions |
| --- | --- | --- |
| Accounts in this organizational directory only | Owning Directory (tenant) GUID; recommended for one organization | Both |
| Accounts in any organizational directory | `organizations`, or a specific tenant GUID | Both |
| Organizational and personal Microsoft accounts | `common` | Both |
| Personal Microsoft accounts only | `consumers` | .NET NativeAOT only |

| Graph delegated permission | Current use | Admin consent required by the permission itself |
| --- | --- | --- |
| `User.Read` | Requested by default; current mail operations do not call the profile API | No |
| `Mail.ReadWrite` | Read and modify mail, drafts, and attachments | No |
| `Mail.Send` | Send as the signed-in user | No |

<details>
<summary>ⓘ Public-client configuration and account types</summary>

For organization deployments, we recommend a dedicated desktop/public-client
registration managed by your organization. A Client ID is a public identifier;
this flow does not use a Client Secret or certificate. The Python server's
confidential-client/OBO registration has a separate role and credential.

Registering `http://localhost` under **Mobile and desktop applications**
identifies browser Authorization Code + PKCE as a public-client flow. Entra
ignores the random localhost port while matching, but the path must agree.
**Allow public client flows** can remain at its default **No** for this flow;
the switch enables other flows such as device code, username/password, and
Integrated Windows Authentication. See Microsoft's
[desktop registration](https://learn.microsoft.com/en-us/entra/identity-platform/scenario-desktop-app-configuration)
and [public-client guidance](https://learn.microsoft.com/en-us/entra/identity-platform/msal-client-applications).

Go accepts tenant GUIDs, `organizations`, and `common`, but not `consumers`.
For personal Outlook.com accounts in Go, register for organizational **and**
personal accounts and use `common`. Changing the authority does not change the
registration's supported account types. The account needs an accessible
Outlook/Exchange mailbox. Application-registration access, if disabled in your
tenant, must be granted separately from consent to mailbox permissions.

</details>

<details>
<summary>ⓘ User.Read and administrator approval</summary>

`User.Read` is not needed by the mail endpoints or PKCE itself. Both released
editions still request it by default. Removing it from **API permissions** does
not change the EXE's request. .NET supports the custom-scope override below;
Go currently has neither a custom-scope flag nor support for
`M365_LOCAL_GRAPH_SCOPES`.

All three delegated permissions have **AdminConsentRequired: No** in
[Microsoft's permission reference](https://learn.microsoft.com/en-us/graph/permissions-reference).
The tenant's [user-consent policy](https://learn.microsoft.com/en-us/entra/identity/enterprise-apps/configure-user-consent)
can still disable user consent, require publisher verification, or allow only
selected low-impact permissions. Removing `User.Read` does not bypass policy.

For approval, give the administrator the application ID, target tenant,
requested delegated permissions, and sign-in error code. For an app registered
in that tenant, an authorized administrator can review **App registrations >
your app > API permissions > Grant admin consent**. External tenants use their
own admin-consent workflow; home-tenant consent does not approve other tenants.
New permissions or revoked grants need new consent. A blank permission Status
column alone does not mean an administrator must approve it.

</details>

## Configure .NET NativeAOT

For a custom application, set these values **before** signing in:

```powershell
$env:M365_LOCAL_CLIENT_ID = '<application-client-id>'
$env:M365_LOCAL_TENANT_ID = '<directory-tenant-guid>'
.\m365-mcp-windows-local-amd64.exe doctor
.\m365-mcp-windows-local-amd64.exe login
.\m365-mcp-windows-local-amd64.exe status
```

`doctor` should show your `client_id`, `tenant`, and
`client_id_source: "environment"`. `status` shows `authenticated: true` while
the cached access token is usable. To use the built-in application, leave
these overrides unset.

Configure the MCP client with the same IDs:

```json
{
  "mcpServers": {
    "m365-local": {
      "command": "C:\\Tools\\m365-mcp-windows-local-amd64.exe",
      "args": ["stdio"],
      "env": {
        "M365_LOCAL_CLIENT_ID": "<application-client-id>",
        "M365_LOCAL_TENANT_ID": "<directory-tenant-guid>"
      }
    }
  }
}
```

Replace the executable path and IDs. Omit `env` for the built-in application.
.NET reads these settings on every start; a PowerShell `$env:` assignment does
not update an already-running MCP client. Login and the client must use the
same Windows user, Client ID, and tenant to reuse the DPAPI-protected state.
The first tool call can prompt for sign-in when no usable state exists.

<details>
<summary>ⓘ .NET custom scopes and ephemeral mode</summary>

To omit `User.Read` from the .NET request, replace the whole scope list:

```powershell
$env:M365_LOCAL_GRAPH_SCOPES = 'openid profile offline_access https://graph.microsoft.com/Mail.ReadWrite https://graph.microsoft.com/Mail.Send'
```

Stop the MCP client, run `logout`, then `login` again. Carry this exact value
into the MCP client's `env` too. Keep `offline_access` because the EXE requires
a refresh token. This variable does not configure the Go edition.

`--ephemeral` prevents reading or writing persistent authentication state.
For a session without persistence, use `stdio --ephemeral` and complete sign-in
when prompted. A separate `login --ephemeral` process cannot pass its in-memory
tokens to a later process. Protocol output uses stdout and diagnostics stderr;
normal execution installs no service, scheduled task, or startup entry.

</details>

## Configure Go

Override the application for sign-in with flags:

```powershell
.\m365-mcp-windows-local-go.exe login --client-id YOUR-APPLICATION-ID --tenant YOUR-TENANT-ID
.\m365-mcp-windows-local-go.exe connection
```

Or use environment variables:

```powershell
$env:M365_LOCAL_CLIENT_ID = 'YOUR-APPLICATION-ID'
$env:M365_LOCAL_TENANT_ID = 'YOUR-TENANT-ID'
.\m365-mcp-windows-local-go.exe login
.\m365-mcp-windows-local-go.exe connection
```

At login the priority is flags, environment variables, then built-in defaults.
Check the browser's application name before consent. Successful login prints
`Signed in. Run connection to generate your MCP client configuration.`
Go has no `doctor` or `status` command.

### stdio

Copy the JSON from `connection` into the MCP client, or configure:

```json
{
  "mcpServers": {
    "m365-local": {
      "command": "C:\\Tools\\m365-mcp-windows-local-go.exe",
      "args": ["serve"]
    }
  }
}
```

Go saves the selected application, tenant, and account at login. `serve` and
`connection` use those saved settings; the client does not need the login
environment variables. Changing variables or passing `--client-id` to `serve`
does not switch the saved application. The MCP client starts the process;
stdout carries only protocol data and stderr carries logs.

### Streamable HTTP

For a client supporting custom request headers:

```powershell
.\m365-mcp-windows-local-go.exe connection --http --port 8000
.\m365-mcp-windows-local-go.exe serve --http --port 8000
```

Copy the first command's JSON, including its bearer header, into the client.
The listener binds only to `127.0.0.1` and every MCP request needs the local
token. Keep it private. Re-login rotates this token, so regenerate HTTP
configuration afterward. Stdio uses the default `serve` command instead.

<details>
<summary>ⓘ Server OAuth connectors and local transports</summary>

Neither local edition provides the Python server's OAuth discovery/DCR
endpoints. WorkBuddy's repository OAuth connector package is for the server
edition. A client requiring OAuth discovery must use the server, or offer a
separate stdio/custom-header configuration. The Go HTTP token is a local
capability, not a Microsoft access token.

</details>

## Mail and attachments

Both editions provide `mail_search`, `mail_get`, `mail_create_draft`,
`mail_send_draft`, `mail_add_draft_attachment`, `mail_list_attachments`,
`mail_read_attachment`, `mail_mark_read`, `mail_archive`, `mail_move`, and
`mail_set_category`. Go also provides `mail_download_attachment`.
Every Graph request uses the signed-in user's `/me` mailbox.

Drafts are plain text. Before sending, the MCP client must obtain per-message
confirmation or enforce an explicit bounded automation authorization covering
recipients, trusted content/attachment sources, volume, and expiry. Graph
acceptance does not prove delivery. Ambiguous writes are not automatically
retried; inspect the draft and attachments before deciding what to do next.

### Add a local file

Set an operator-controlled attachment folder before generating or starting the
client configuration:

```powershell
$env:M365_ATTACHMENT_ROOT = 'C:\M365Artifacts'
```

For .NET, add this variable to the MCP server's `env` and call
`mail_add_draft_attachment(draft_id, relative_path="reports\\weekly.docx")`.
Omit `relative_path` to use its Windows file picker.

For Go, run `connection` again after setting the folder; stdio JSON includes
it in `env`. HTTP mode inherits the value when `serve` starts. Call
`mail_add_draft_attachment(draft_id, relative_path="reports/weekly.docx")`.
Go requires a relative path and has no file picker.

Both permit PDF, DOCX, XLSX, PPTX, and ZIP files up to 20 MiB, verify the
opened file stays within the configured root for relative paths, and return
byte length and SHA-256. Files below 3,000,000 bytes use a direct Graph upload;
larger files use a restricted sequential upload session. Attaching never sends.

<details>
<summary>ⓘ Text extraction, downloads, and the remote upload helper</summary>

.NET reads bounded UTF-8 text/CSV/JSON/XML attachments. It has no download
endpoint or PDF/Office parser. Go extracts PDF, DOCX, XLSX, PPTX, TXT, and
Markdown in separate workers: 512 MiB memory, 15 CPU seconds, 20 seconds wall
time, and at most two active workers. Extraction is limited to 10 MiB files,
64 MiB/2,048-entry Office expansion, and 100,000 output characters. XLSX uses
cached formula results; image-only PDFs require external OCR.

Go downloads use unguessable, five-minute, single-use HTTP URLs bound to
`127.0.0.1`. Stdio starts this listener on a random port. At most 16 downloads
and 64 MiB are retained in memory; restart invalidates the URLs. Open them on
the same PC. Attachment list `size` is provider metadata; fetched
`content_length` is the decoded byte count.

For a remote-server connector, the .NET EXE also offers `inspect-attachment`
and `push-attachment`, without local sign-in. The complete grant and upload
sequence belongs to the
[server guide](https://github.com/sagehou/M365-MCP-Server/blob/main/docs/mcp-server.md#add-a-file-to-a-remote-draft).
These commands do not create a second local MCP connector. Go does not provide
them.

</details>

## Switch applications or sign out

Stop the MCP client/server before changing credentials:

```powershell
# Run the command for your edition
.\m365-mcp-windows-local-amd64.exe logout
.\m365-mcp-windows-local-go.exe logout
```

For .NET, set the new application/tenant, run `doctor` and `login`, update the
MCP client's `env`, and restart it. For Go, repeat `login` with the new flags
or variables, then `connection`. Replace existing HTTP configuration because
re-login rotates its token. Stdio keeps the executable path and `serve` argument.

<details>
<summary>ⓘ Return to the built-in application and local state locations</summary>

After logging out, clear overrides in PowerShell:

```powershell
Remove-Item Env:M365_LOCAL_CLIENT_ID, Env:M365_LOCAL_TENANT_ID, Env:M365_LOCAL_GRAPH_SCOPES -ErrorAction SilentlyContinue
```

Also remove overrides from the .NET MCP client's `env`. Run your edition's
`login` again, and for Go regenerate `connection`. Environment changes affect
that PowerShell session and its children; future logins from another process
can inherit different settings.

| Edition | Current-user encrypted state |
| --- | --- |
| .NET NativeAOT | `%LOCALAPPDATA%\M365-MCP-Server\state.bin`; Client ID and tenant must match at load |
| Go | `%LOCALAPPDATA%\M365MCP`; saved settings, MSAL cache, local HTTP token, and a user-only Windows ACL |

Both use current-user DPAPI. Go binds subsequent calls to the chosen account
and never falls back to a different cached user on refresh failure. Only one
Go login/server/logout process can use its state at a time. Local logout
removes credentials, not browser sessions or tenant consent.

</details>

## Troubleshooting

<details>
<summary>ⓘ Sign-in and client configuration</summary>

| Message or symptom | Check or action |
| --- | --- |
| Need admin approval / `AADSTS90094` / `AADSTS65001` | Check the target tenant's grants and consent policy; `65001` can also mean user consent is not yet complete. |
| `AADSTS50011` | Register root `http://localhost` under **Mobile and desktop applications**, with no extra path. |
| `AADSTS7000218` / client secret requested | Correct the redirect platform; a desktop public client does not need a secret. |
| `AADSTS700016` / app not found | Check Application (client) ID, selected tenant, and supported account types. |
| .NET PowerShell login works but MCP asks again | Match Windows user and `env` values; `--ephemeral` does not persist state across processes. |
| Go keeps the old application/account | Stop `serve`, log out, and repeat `login` with explicit flags, then `connection`. |
| `doctor` works but sign-in fails | .NET `doctor` validates local settings, not tenant registration or consent. |
| Login works but Graph returns `403` | Check delegated mail grants and Exchange/Outlook mailbox availability. |
| Go HTTP client gets `401` after login | Regenerate `connection --http` and replace the old bearer token. |

</details>

## Antivirus false positives

<details>
<summary>ⓘ Verify and report a detected file</summary>

1. Download the exact EXE and checksum from the same GitHub Release and compare
   SHA-256. For the .NET artifact, GitHub CLI can also verify provenance with
   `gh attestation verify m365-mcp-windows-local-amd64.exe --repo sagehou/M365-MCP-Server`.
   Resolve a verification mismatch before running it.
2. Record the security product/database version, detection name, SHA-256,
   release URL, and trigger steps without tokens or mailbox content.
3. Submit that exact detected binary through the vendor's false-positive
   process. Qianxin provides a
   [sample submission page](https://www.qianxin.com/other/sample-upload)
   accepting files up to 100 MB with a contact email and CAPTCHA.
4. After vendor review, verify the same hash on the affected PC. If the
   organization's administrator needs an interim exception, assess a narrow,
   time-limited rule for that verified file. Use the Release's MD5/SHA-1 only
   where a legacy allowlist form requires them; SHA-256 remains the integrity
   check. Changed binaries need fresh verification and review.

Keep endpoint protection enabled. Report the actual behavior: a single EXE,
browser PKCE login with a loopback callback, delegated Graph access, and
current-user encrypted state. A whole-directory or process-name exception is
broader than the exact-file review.

</details>

## Build and distribution

| Edition | GitHub Actions workflow | Integration artifacts |
| --- | --- | --- |
| .NET NativeAOT | `Windows local executable` (`windows-exe.yml`) | `m365-mcp-windows-local-amd64` |
| Go | `windows-local-go` | `windows-local-go-amd64`, `windows-local-go-arm64`, `windows-local-go-packages` |

All builds and tests run in GitHub Actions. Go ZIPs include this unified guide
as `README.md` and `README.zh-CN.md`, dependency notices, and the license. Both
workflows continue independently; tagged releases publish the tested EXEs and
checksums together. Ordinary Actions artifacts are integration outputs.
Go AMD64 receives a Windows runtime smoke test; ARM64 is cross-compiled and its
version resources are checked.

---

The EXEs are unsigned. Go does not guarantee fewer antivirus detections;
checksums, version details, and provenance do not replace Authenticode signing
or vendor review. Worker resource limits are not a filesystem/network sandbox.
Real tenant sign-in, client compatibility, and antivirus behavior require
acceptance on the target PC. The editing environment must not build, test,
install test dependencies, or create a test virtual environment. Updated: 2026-11-11.
