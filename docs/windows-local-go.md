**English** | [简体中文](zh-CN/windows-local-go.md)

# Windows local Go edition

## Install

Extract `m365-mcp-windows-local-go-amd64.zip` for Intel/AMD PCs, or
`m365-mcp-windows-local-go-arm64.zip` for Windows on ARM. Keep the extracted executable
in a stable folder. Python, Docker, administrator access, and a client secret
are not required. Check the archive against `SHA256SUMS.txt` before installing.

If downloading a single-EXE artifact, rename its executable to
`m365-mcp-windows-local-go.exe` before following the commands below.

## Sign in

Both local editions use the project's public-client application by default:

```text
Application: M365-MCP-Localhost
Client ID: 6e35216e-2623-43cc-b867-83bec0865cf3
Tenant: organizations
```

In PowerShell, from the extracted folder:

```powershell
.\m365-mcp-windows-local-go.exe login
```

Complete Microsoft sign-in in the system browser. The application uses S256
PKCE and an ephemeral localhost callback. The selected account is bound to
subsequent calls; a refresh failure never selects another cached account.
Tenant policy may require administrator consent for the delegated permissions,
including when using the built-in application.

## Use your own application

For organization deployments, we recommend registering and managing a dedicated
desktop/public-client application in your own tenant. The built-in application
remains available without a new registration.

1. Open the [Microsoft Entra admin center](https://entra.microsoft.com/), switch
   to the tenant that will own the application, then select **Entra ID > App
   registrations > New registration**. Enter a name such as
   `M365-MCP-Local-Custom` and choose **Supported account types** from the table
   below. Leave the initial redirect URI empty and select **Register**.
2. On **Overview**, copy **Application (client) ID** and **Directory (tenant)
   ID**. Use the application ID for `M365_LOCAL_CLIENT_ID`; the **Object ID** is
   a different identifier and must not be used here.
3. Open **Authentication > Add a platform > Mobile and desktop applications**.
   Add `http://localhost` as a custom redirect URI and save. Use the root path;
   do not append `/callback`, specify a fixed port, or add the same URI under
   **Web** or **Single-page application**. No client secret or certificate is
   needed.
4. Open **API permissions > Add a permission > Microsoft Graph > Delegated
   permissions**, add the three permissions below, and save. If the tenant
   allows user consent, continue with local sign-in. Use the organization's
   admin-consent process only when policy requires approval.

| Supported account types in the registration | Login `--tenant` / `M365_LOCAL_TENANT_ID` |
| --- | --- |
| Accounts in this organizational directory only | The owning Directory (tenant) ID; recommended for one organization |
| Accounts in any organizational directory | `organizations`, or a specific organizational tenant ID |
| Accounts in any organizational directory and personal Microsoft accounts | `common` for both organizational and personal accounts |

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

The Go edition accepts a tenant GUID, `organizations`, or `common`; it does not
accept `consumers`. To include Outlook.com accounts, use the third registration
option and `common`. Changing the login authority does not change which account
types the registration supports. The selected account must have an accessible
Outlook/Exchange mailbox. If **New registration** is unavailable, ask the tenant
administrator for application-registration access; this is separate from consent
to mailbox permissions.

A Client ID is a public identifier. Both local editions embed the same public
Client ID and allow an override; neither embeds or uses a Client Secret. Create
a dedicated desktop registration instead of distributing credentials from the
Python server's confidential-client/OBO registration. Mailbox **Application
permissions** and an exposed `access_as_user` API are not needed for local use.

</details>

<details>
<summary>ⓘ User.Read and administrator approval</summary>

`User.Read` is not required by the mail endpoints or by PKCE sign-in itself.
The current Go release still requests all three scopes above, so configure the
application to match that request. Removing a permission from **API permissions**
does not remove it from the EXE's sign-in request. The Go edition currently has
no custom-scope flag and does not read `M365_LOCAL_GRAPH_SCOPES`.

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

Override the defaults for a login:

```powershell
.\m365-mcp-windows-local-go.exe login --client-id YOUR-APPLICATION-ID --tenant YOUR-TENANT-ID
```

Check that the browser shows your custom application's name before granting
consent. A successful login prints `Signed in. Run connection to generate your
MCP client configuration.`; this edition has no `doctor` or `status` command.

Or use the same environment variables as the NativeAOT edition:

```powershell
$env:M365_LOCAL_CLIENT_ID = 'YOUR-APPLICATION-ID'
$env:M365_LOCAL_TENANT_ID = 'YOUR-TENANT-ID'
.\m365-mcp-windows-local-go.exe login
.\m365-mcp-windows-local-go.exe connection
```

At login, command-line flags take precedence over environment variables, then
the built-in defaults. The selected application and tenant are saved after
successful sign-in; `serve` and `connection` use those saved settings, so the MCP
client does not need the login environment variables. Merely changing a variable
or passing `--client-id` to `serve` does not switch the saved application.

<details>
<summary>ⓘ Switch applications or return to the built-in application</summary>

Stop the MCP client/server, run `logout`, and repeat `login` with the new
application and tenant. Run `connection` again afterward; re-login rotates the
local HTTP bearer token, so replace any existing HTTP client configuration.
Stdio clients continue to use the same executable path and `serve` argument.

To return to the built-in application from PowerShell:

```powershell
.\m365-mcp-windows-local-go.exe logout
Remove-Item Env:M365_LOCAL_CLIENT_ID, Env:M365_LOCAL_TENANT_ID -ErrorAction SilentlyContinue
.\m365-mcp-windows-local-go.exe login
.\m365-mcp-windows-local-go.exe connection
```

These environment changes affect this PowerShell session. A later `login` from
another process may inherit different values; explicit login flags take
precedence. Local logout does not revoke tenant consent or browser sessions.

</details>

<details>
<summary>ⓘ Troubleshoot custom-application sign-in</summary>

| Sign-in message or symptom | Check or action |
| --- | --- |
| Need admin approval / `AADSTS90094` / `AADSTS65001` | Check the target tenant's consent grant and user-consent policy; `65001` can also mean the user has not yet granted consent. |
| `AADSTS50011` / redirect URI mismatch | Register the root `http://localhost` under **Mobile and desktop applications**, with no extra path. |
| `AADSTS7000218` / client secret requested | Check the redirect's platform; this EXE uses a desktop public client. Correct a Web-platform registration rather than adding a secret. |
| `AADSTS700016` / application not found | Check Application (client) ID, tenant selection, and supported account types. |
| Wrong account or old application after changing configuration | Stop `serve`, run `logout`, then repeat `login` with explicit flags and regenerate `connection`. |
| Sign-in succeeds but Graph returns `403` | Check the delegated mail grants and the account's Exchange/Outlook mailbox availability; a successful sign-in alone does not prove mailbox access. |

</details>

## Connect an MCP client

### stdio

`serve` uses stdio by default. Complete `login` above, then configure the MCP
client with the executable's absolute path and `serve` as its argument:

```json
{
  "mcpServers": {
    "m365": {
      "command": "C:\\Tools\\m365-mcp-windows-local-go.exe",
      "args": ["serve"]
    }
  }
}
```

Set `command` to the actual executable path. If you kept the downloaded
`-amd64.exe` or `-arm64.exe` filename, include that suffix. The MCP client starts
and manages the process. Protocol traffic uses stdout; logs use stderr.

To generate this configuration with the actual executable path:

```powershell
.\m365-mcp-windows-local-go.exe connection
```

Copy the resulting `mcpServers` JSON into the client.

### Streamable HTTP

For clients supporting Streamable HTTP and custom request headers:

```powershell
.\m365-mcp-windows-local-go.exe connection --http --port 8000
.\m365-mcp-windows-local-go.exe serve --http --port 8000
```

Copy the first command's JSON into the client. Keep its bearer token private.
The listener binds only to `127.0.0.1`; every MCP request requires that token.
The local edition does not serve the container edition's OAuth/DCR endpoints.
Clients that require automatic OAuth discovery must use the Python server or
configure stdio/custom headers instead. WorkBuddy's existing OAuth connector
package is intended for the Python server.

## Mail tools

Twelve tools are available: `mail_search`, `mail_get`, `mail_list_attachments`,
`mail_read_attachment`, `mail_download_attachment`, `mail_mark_read`,
`mail_archive`, `mail_move`, `mail_set_category`, `mail_create_draft`,
`mail_send_draft`, and `mail_add_draft_attachment`. Every Graph request uses
the signed-in account's `/me` mailbox and delegated permissions.

Drafts use plain text. Sending requires per-message confirmation or explicit
bounded automation authorization at the MCP client; Graph acceptance does not
confirm delivery. Writes are never retried after ambiguous network failures.

To attach local PDF, DOCX, XLSX, PPTX, or ZIP files up to 20 MiB, configure an
operator-controlled attachment folder before generating client configuration:

```powershell
$env:M365_ATTACHMENT_ROOT = 'C:\M365Artifacts'
.\m365-mcp-windows-local-go.exe connection
```

Pass `draft_id` and a `relative_path` such as `reports/report.zip` to
`mail_add_draft_attachment`. Stdio configuration includes the configured folder
in `env`; HTTP mode inherits it when `serve` starts. Paths use forward slashes
and cannot escape that folder. This edition requires a relative path; the
existing NativeAOT edition also offers a native file picker and a remote push
helper. Attachments below 3,000,000 bytes use a direct Graph request; larger
files use a restricted Outlook upload session. Results include byte length and
SHA-256. Review the draft and attachments before authorizing a send.

Search returns one bounded page and a `next_link` hint. Attachment list `size`
is provider metadata; fetched `content_length` is the actual decoded byte count.
PDF, DOCX, XLSX, PPTX, TXT, and Markdown text extraction runs in a separate
process, with 512 MiB memory, 15 CPU seconds, 20 seconds wall time, and at most
two concurrent workers. Files are limited to 10 MiB, Office expansion to 64 MiB
and 2,048 entries, and output to 100,000 characters. XLSX extraction reads
cached formula results. Image-only PDFs require OCR, which is not included.

Downloads use an unguessable, five-minute, single-use HTTP URL bound to
`127.0.0.1`. Stdio mode starts its download listener on a random local port.
At most 16 downloads and 64 MiB are retained in memory. They expire on restart.
URLs are intended for a browser on the same PC. No remote download host is used.

## Sign out

Stop the MCP client/server first, then run:

```powershell
.\m365-mcp-windows-local-go.exe logout
```

Only one login/server/logout process can use the local account at a time.
Credentials and the local HTTP token live under `%LOCALAPPDATA%\M365MCP` with
a user-only Windows ACL and current-user DPAPI encryption. Sign-out removes
the local credentials; it does not revoke Microsoft browser sessions or tenant
consent. If Microsoft requires interactive sign-in again, stop the server and
repeat `login`; this also rotates the local HTTP token, so regenerate HTTP
client configuration afterward.

## Build

Builds and tests run only in GitHub Actions. The `windows-local-go` workflow uses
`scripts/build-windows-go.py` to package AMD64 and ARM64 executables, both usage
guides, and third-party license notices. After CI succeeds, download
`windows-local-go-amd64` or `windows-local-go-arm64` for a single EXE, or
`windows-local-go-packages` for ZIP packages and checksums. The workflow covers Linux and Windows tests, including
Windows DPAPI, process locking, and isolated workers. Do not build or test in
the editing environment.

The build uses `goversioninfo` v1.7.0 only in CI to embed Explorer file details
for both architectures. Product/file versions come from `pyproject.toml`.
The tag release workflow reuses this same build, verifies checksums, and
publishes the Go EXEs/ZIPs alongside the existing NativeAOT EXE.

---

The executable is unsigned. Go does not guarantee fewer antivirus detections;
SmartScreen reputation, code signing, and vendor false-positive review still
apply. Job Objects limit resources, not filesystem/network access. Real Entra
sign-in, client compatibility, representative documents, and antivirus behavior
require acceptance on the target Windows PC. Updated: 2026-11-11.
