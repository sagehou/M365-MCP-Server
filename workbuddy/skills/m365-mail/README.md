**English** | [简体中文](README.zh-CN.md)

# Install m365-mail

## Connect the mailbox

- [Python server setup](https://github.com/sagehou/M365-MCP-Server/blob/main/docs/mcp-server.md)
- [Windows local setup: .NET and Go](https://github.com/sagehou/M365-MCP-Server/blob/main/docs/windows-local.md)

Configure and sign in to one M365 MCP connection in the AI client before using
the Skill. Both Windows editions use `args: ["stdio"]`; Go also offers local
HTTP. Installing a Skill does not register an Entra application, configure an
MCP server, or sign in. The same Skill works with all three editions by reading
the available tools and their schemas.

## Install in Codex or Claude Code

1. [Download m365-mail-skill.zip](https://github.com/sagehou/M365-MCP-Server/releases/latest/download/m365-mail-skill.zip)
   and extract it into a working folder. Open a terminal in that folder; it
   should contain the `m365-mail/` directory. Verify the ZIP's SHA-256 against
   the release's `SHA256SUMS.txt`.
2. Copy the **whole `m365-mail` folder**, including `references/`, into one
   client Skill directory:

| Client | Personal installation | Project installation | Explicit invocation |
| --- | --- | --- | --- |
| Codex CLI / IDE | `~/.agents/skills/m365-mail/` | `<your-project>/.agents/skills/m365-mail/` | `$m365-mail` |
| Claude Code | `~/.claude/skills/m365-mail/` | `<your-project>/.claude/skills/m365-mail/` | `/m365-mail` |

Windows PowerShell, personal Codex installation:

```powershell
$m365SkillParent = Join-Path $env:USERPROFILE '.agents\skills'
New-Item -ItemType Directory -Path $m365SkillParent -Force | Out-Null
Copy-Item -LiteralPath '.\m365-mail' -Destination $m365SkillParent -Recurse
```

For Claude Code, set `$m365SkillParent` to
`Join-Path $env:USERPROFILE '.claude\skills'` instead. For a project install,
use that project's `.agents\skills` or `.claude\skills` directory.

macOS/Linux shell, personal Codex installation:

```bash
m365_skill_parent="$HOME/.agents/skills"
mkdir -p "$m365_skill_parent"
cp -R m365-mail "$m365_skill_parent/"
```

For Claude Code, use `"$HOME/.claude/skills"`; for project scope, use the
target project's `.agents/skills` or `.claude/skills` directory. The installed
layout must contain `m365-mail/SKILL.md`, not an extra nested `m365-mail` folder.

3. Check the client's Skill list. Refresh/restart the client if it has not
   discovered the folder. Invoke it with the name above or ask a matching mail
   question. Keep only one installed copy per intended scope.

<details>
<summary>ⓘ Client paths, languages, and other clients</summary>

The paths and invocation forms follow the official
[Codex Skill documentation](https://learn.chatgpt.com/docs/build-skills.md) and
[Claude Code Skill documentation](https://code.claude.com/docs/en/skills).
Other Agent Skills clients can use the same complete folder in their own
documented Skill directory. A client with MCP support alone may not discover
Skills; it must also support the Skill format or load the instructions manually.

For a clone or [source archive](https://github.com/sagehou/M365-MCP-Server/archive/refs/heads/main.zip),
the shared source remains `workbuddy/skills/m365-mail/`. Run from the repository
root and use that source path instead of `m365-mail` in the copy commands.
WorkBuddy packages this same folder without maintaining another Skill copy.

`SKILL.md` is the single entry point. Its Chinese link opens the complete
[Chinese instructions](references/zh-CN.md); both versions use the same tool
names and capability boundaries. Remote uploads load a separate reference only
when needed. Do not rename the translation to another `SKILL.md` or replace the
entry point when changing conversation language.

</details>

## WorkBuddy

For a server connection, use the repository's `workbuddy/` template and the
server guide's OAuth setup. Replace `${M365_MCP_URL}` in `workbuddy/mcp.json`
with the exact server MCP URL, then ZIP the **contents** of `workbuddy/`:

```text
connector-meta.json
mcp.json
icon.svg
skills/
  m365-mail/
    SKILL.md
    README.md
    README.zh-CN.md
    references/
```

Import the connector package through WorkBuddy's connector management and
complete browser sign-in. Keep OAuth discovery; do not add a Client Secret or
token form to the package. This template configures a remote server connection.
For local .NET/Go, configure the local MCP transport separately in a client that
supports it, then install/load the same `m365-mail` folder using that client's
Skill mechanism. The local HTTP endpoint does not implement MCP OAuth.

## Use and update

- “Find this week's project acceptance emails and summarize the selected ones.”
- “Draft an update to alice@example.com and attach reports/weekly.docx; show me
  the final draft before sending.”
- “List the selected email's attachments and download the original PDF if this
  connection supports downloads.”
- “Save the selected email's original attachment as reports/report.pdf in the
  default download folder.”
- “Save these attachments to D:\MailArchive using download_dir.”

When updating, replace the installed `m365-mail` folder with the complete new
folder and refresh the client. This consolidates `outlook-mail`,
`outlook-mail-compose`, `outlook-mail-management`, and `outlook-attachments`;
remove those old Skill copies from the client or replace its old WorkBuddy
package so duplicate instructions are not selected. To use direct local saves,
upgrade the .NET or Go EXE to v0.1.7 or later and refresh/restart the MCP
connection to load its current tool list. No download-folder configuration is
required: saves default to the actual Windows Downloads folder plus `M365-MCP`,
and missing directories are created automatically. A user, Skill, or Agent can
pass an absolute `download_dir` for a task; it takes priority over the optional
process environment `M365_ATTACHMENT_ROOT` and the default folder. The original
file save limit defaults to 150 MiB; set positive-integer `M365_MAX_DOWNLOAD_MIB`
in the MCP server's environment to change it. Text reads and Go temporary URLs
remain limited to 10 MiB. Environment changes require restarting the MCP
process; setting variables only during `login` does not persist them. Updating
the Skill alone does not add executable capabilities; older versions retain
their existing supported workflows.

---

Client discovery and permissions depend on the host application. A Skill guides
tool use; it does not grant mailbox or shell permissions. Updated: 2026-11-12.
