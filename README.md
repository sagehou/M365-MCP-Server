**English** | [简体中文](README.zh-CN.md)

# M365 MCP Server

## Get started

| Run mode | Guide | Delivery |
| --- | --- | --- |
| Server | [Server edition](docs/mcp-server.md) | Python container, HTTPS Streamable HTTP, Entra/OBO, optional browser OAuth |
| Windows local | [Local edition: .NET and Go](docs/windows-local.md) | Single-user EXE, browser PKCE, stdio; Go also offers authenticated loopback HTTP |

Optional AI workflow: [install the shared m365-mail Skill](workbuddy/skills/m365-mail/README.md)
for the server, .NET, or Go connection.

## Windows one-command install (Go)

```powershell
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/sagehou/M365-MCP-Server/main/scripts/install-windows-local.ps1')))
```

The installer selects the latest stable Go AMD64/ARM64 release, verifies
SHA-256, installs the EXE and complete Skill to
`%LOCALAPPDATA%\Programs\M365-MCP`, and generates `mcp.json`. It asks for your
Client ID and tenant ID; leave them blank for the built-in public application
and `organizations`. Complete sign-in in the system browser.

<details>
<summary>ⓘ Agent instructions and non-interactive installation</summary>

Give an Agent this instruction:

```text
Install M365 MCP on this Windows PC, using the Go edition by default.
First ask whether I want the built-in public application or my own Client ID,
and ask which tenant to use. A single-tenant application needs its owning
Directory (tenant) GUID. Do not ask for a Client Secret or tokens.
Read scripts/install-windows-local.ps1 in sagehou/M365-MCP-Server, then run it
with -NonInteractive and my chosen -ClientId/-TenantId. Omit these two arguments
only if I chose the built-in Client ID and organizations. Use -SkipLogin when
browser sign-in must be completed separately, and give me login-command.txt.
Merge the generated m365-local entry into my agent's existing MCP settings,
preserving other entries. Install the complete m365-mail folder using my
client's Skill mechanism, then refresh the connection and confirm tools/list.
```

For an Agent that has already collected your custom IDs:

```powershell
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/sagehou/M365-MCP-Server/main/scripts/install-windows-local.ps1'))) -NonInteractive -ClientId '<application-client-guid>' -TenantId '<directory-tenant-guid>' -SkipLogin
```

`-NonInteractive` skips terminal questions. `-SkipLogin` also defers browser
sign-in; the exact login command is saved as `login-command.txt` in the install
directory. `-InstallDirectory 'D:\Tools\M365-MCP'` changes that directory.
The generated `mcp.json` contains a stdio entry and no tokens. Copy/merge that
entry into your client; the installer does not edit client-specific settings.
The `m365-mail/` folder is ready to copy to the client's
[Skill directory](workbuddy/skills/m365-mail/README.md).

Windows PowerShell 5.1 and PowerShell 7 are supported; administrator access
and a Go runtime are unnecessary. Close the local MCP process before reinstalling.
For manual .NET installation or your own Entra application, use the
[local guide](docs/windows-local.md).

</details>

## Mail capabilities

- Search and read the signed-in user's Outlook mailbox through delegated `/me`
  access.
- Create plain-text drafts, attach files, and send after client-enforced
  confirmation or bounded authorization.
- Mark read/unread, archive, move, and set categories.
- Read bounded attachment text; extraction formats and download support depend
  on the edition and are listed in the local/server guide.
- Stream original attachments in both local editions with `mail_save_attachment`:
  default Windows Downloads/M365-MCP, optional `download_dir`, and a configurable
  150 MiB default limit, without a browser or shell.

The server provides 11 tools by default or 13 with server-managed OAuth.
The .NET local edition provides 12, and Go provides 13.

## Releases

[Download v0.1.7](https://github.com/sagehou/M365-MCP-Server/releases/tag/v0.1.7).

| Artifact | Name |
| --- | --- |
| Container image | `ghcr.io/sagehou/m365-mcp-server:v0.1.7` |
| .NET NativeAOT, Windows x64 | `m365-mcp-windows-local-amd64.exe` |
| Go, Windows x64 / ARM64 | `m365-mcp-windows-local-go-amd64.exe`, `m365-mcp-windows-local-go-arm64.exe` |
| Go packages with both language guides | `m365-mcp-windows-local-go-amd64.zip`, `m365-mcp-windows-local-go-arm64.zip` |
| Shared mail Skill with both language instructions | `m365-mail-skill.zip` |

The release includes SHA-256 checksums and EXE hashes in its description.
All three EXEs also have GitHub Artifact Attestation. Both local editions
include the same public Client ID and support your own application; their
configuration steps are in the single local guide.

## Development

All tests, dependency audits, container builds, and Windows builds run in
GitHub Actions. The editing environment must not create test virtual
environments, install test dependencies, or run local tests/builds.

<details>
<summary>ⓘ Engineering references and release history</summary>

- [Architecture](docs/architecture.md)
- [Tool contracts](docs/tool-spec.md)
- [Security design](docs/security.md)
- [Development plan](docs/development-plan.md)
- [Release acceptance checklist](docs/release-checklist.md)
- [v0.1.7 release notes](docs/releases/v0.1.7.md)

Search continuation, reply/forward, HTML composition, OCR, shared mailboxes,
enterprise policy features, and Calendar/OneDrive/SharePoint/Teams are future
work. Windows Authenticode signing and optional WAM integration also remain
follow-up work.

</details>

## License

Source code and documentation use the [MIT License](LICENSE). Third-party
dependencies retain their own licenses.

---

Real tenant consent and client behavior require deployment acceptance. Windows
EXEs are unsigned; hashes and provenance do not guarantee antivirus acceptance.
Updated: 2026-11-12.
