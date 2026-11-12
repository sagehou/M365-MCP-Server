[English](README.md) | **简体中文**

# 安装 m365-mail

## 连接邮箱

- [Python 服务器版配置](https://github.com/sagehou/M365-MCP-Server/blob/main/docs/zh-CN/mcp-server.md)
- [Windows 本地版配置：.NET 与 Go](https://github.com/sagehou/M365-MCP-Server/blob/main/docs/zh-CN/windows-local.md)

使用 Skill 前，先在 AI 客户端中配置并登录一个 M365 MCP 连接。两种 Windows 版本均用
`args: ["stdio"]`，Go 还支持本机 HTTP。安装 Skill 不会注册 Entra 应用、配置 MCP
服务或完成登录。同一个 Skill 根据实际暴露的工具及 Schema 适配三种版本。

## 安装到 Codex 或 Claude Code

1. [下载 m365-mail-skill.zip](https://github.com/sagehou/M365-MCP-Server/releases/latest/download/m365-mail-skill.zip)，
   解压到一个工作目录，在该目录打开终端；其中应包含 `m365-mail/` 文件夹。
   将 ZIP 的 SHA-256 与 Release 的 `SHA256SUMS.txt` 核对。
2. 将**整个 `m365-mail` 文件夹**（含 `references/`）复制到一个客户端 Skill 目录：

| 客户端 | 个人安装 | 项目安装 | 显式调用 |
| --- | --- | --- | --- |
| Codex CLI / IDE | `~/.agents/skills/m365-mail/` | `<你的项目>/.agents/skills/m365-mail/` | `$m365-mail` |
| Claude Code | `~/.claude/skills/m365-mail/` | `<你的项目>/.claude/skills/m365-mail/` | `/m365-mail` |

Windows PowerShell，安装到个人 Codex：

```powershell
$m365SkillParent = Join-Path $env:USERPROFILE '.agents\skills'
New-Item -ItemType Directory -Path $m365SkillParent -Force | Out-Null
Copy-Item -LiteralPath '.\m365-mail' -Destination $m365SkillParent -Recurse
```

Claude Code 将 `$m365SkillParent` 改为
`Join-Path $env:USERPROFILE '.claude\skills'`。项目安装改为目标项目下的
`.agents\skills` 或 `.claude\skills` 目录。

macOS/Linux Shell，安装到个人 Codex：

```bash
m365_skill_parent="$HOME/.agents/skills"
mkdir -p "$m365_skill_parent"
cp -R m365-mail "$m365_skill_parent/"
```

Claude Code 使用 `"$HOME/.claude/skills"`；项目安装使用目标项目的 `.agents/skills`
或 `.claude/skills`。安装后的结构须为 `m365-mail/SKILL.md`，不要再嵌套一层
`m365-mail`。

3. 检查客户端 Skill 列表；尚未发现时刷新或重启客户端。使用上表名称显式调用，或提出
   匹配的邮件任务。每个预期作用域只保留一份安装。

<details>
<summary>ⓘ 客户端路径、语言与其他客户端</summary>

路径及调用形式依据官方 [Codex Skill 文档](https://learn.chatgpt.com/docs/build-skills.md)
和 [Claude Code Skill 文档](https://code.claude.com/docs/en/skills)。其他 Agent Skills
客户端可将同一个完整文件夹放入其文档指定的 Skill 目录。仅支持 MCP 的客户端不一定
能发现 Skill，还须支持 Skill 格式或允许手动加载指令。

克隆仓库或使用[源码包](https://github.com/sagehou/M365-MCP-Server/archive/refs/heads/main.zip)
时，共享源文件仍在 `workbuddy/skills/m365-mail/`。从仓库根目录运行复制命令，将源路径
`m365-mail` 换成该路径。WorkBuddy 打包同一个文件夹，无需维护另一份 Skill。

`SKILL.md` 是唯一入口，其中的中文链接指向完整[中文指令](references/zh-CN.md)，
两种语言使用一致的工具名称和能力边界。远端上传仅在需要时加载单独参考文件。不要把
中文译本改名为第二个 `SKILL.md`，也不必因对话语言变化替换入口。

</details>

## WorkBuddy

服务器连接使用仓库的 `workbuddy/` 模板，按服务器版指南配置 OAuth。将
`workbuddy/mcp.json` 的 `${M365_MCP_URL}` 替换为精确的服务器 MCP URL，再将
`workbuddy/` 的**内容**打成 ZIP：

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

通过 WorkBuddy 的连接器管理导入并完成浏览器登录。保留 OAuth Discovery，不在包内
添加 Client Secret 或 Token 表单。此模板配置的是远端服务器连接。本地 .NET/Go 须在
支持相应传输的客户端中单独配置本机 MCP，再通过该客户端的 Skill 机制安装/加载同一个
`m365-mail` 文件夹。本机 HTTP 端点不实现 MCP OAuth。

## 使用与更新

- “查找本周项目验收相关的邮件，总结选定的几封。”
- “给 alice@example.com 起草进展邮件，添加 reports/weekly.docx，发送前展示完整草稿。”
- “列出选定邮件的附件，当前连接支持下载时获取原始 PDF。”

更新时用完整新文件夹替换已安装的 `m365-mail`，再刷新客户端。此 Skill 合并了原来的
`outlook-mail`、`outlook-mail-compose`、`outlook-mail-management` 和
`outlook-attachments`；从客户端移除旧 Skill 副本，或替换旧 WorkBuddy 连接器包，
避免重复指令被选中。本次指令更新不要求改动 MCP 连接或替换 EXE。

---

Skill 发现方式和权限取决于宿主客户端。Skill 指导工具使用，不会授予邮箱或 Shell 权限。
更新日期：2026-11-12。
