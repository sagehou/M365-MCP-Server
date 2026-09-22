[English](README.md) | **简体中文**

# M365 MCP Server

一个自托管的 Microsoft 365 MCP Gateway，采用受控工具面、Microsoft Entra
委托身份和按用户隔离，并重点保护 Outlook 邮件与附件处理边界。

> **当前状态：**远端 Streamable HTTP Server 是 Outlook Mail v0.1 Release
> Candidate。自动化 CI 已通过，但首个稳定版发布前仍需完成真实 WorkBuddy、真实
> Tenant、真实邮箱、重启和跨租户验收。Windows 本地单文件版本已经开始实施，
> 目前没有已发布的 EXE。

## 当前已经可用

### 远端 MCP Server

- FastMCP Streamable HTTP Endpoint：`/mcp/`。
- Microsoft Entra Bearer Token 校验，并执行 Tenant 与 Scope 约束。
- 通过 On-Behalf-Of（OBO）使用 Microsoft Graph 委托权限。
- 每个请求独立绑定用户身份；Graph 调用被限制在 `/me`。
- 可选的 OAuth Discovery、Dynamic Public-client Registration、Interactive
  Sign-in、S256 PKCE、加密 Refresh Session、Rotation 和 Replay Rejection。
- `workbuddy/` 中提供 WorkBuddy Connector Package，CI 覆盖完整的 Mock
  Client Flow。
- 结构化脱敏 Audit Event；安全错误会返回可关联的 Event ID。

### Outlook Mail 工具

| 工具 | 用途 | 类型 |
|---|---|---|
| `mail_search` | 搜索当前登录用户邮箱中的一个有边界页面 | 读取 |
| `mail_get` | 读取一封邮件 | 读取 |
| `mail_create_draft` | 创建已审核的纯文本草稿，但不发送 | 写入 |
| `mail_send_draft` | 发送一封已经另行明确确认的现有草稿 | 写入 |
| `mail_list_attachments` | 列出附件元数据 | 读取 |
| `mail_read_attachment` | 从受支持附件中提取有边界的文本 | 读取 |
| `mail_download_attachment` | 创建短时、单次使用的下载链接 | 读取 |
| `mail_mark_read` | 标记邮件已读或未读 | 写入 |
| `mail_archive` | 将邮件移动到 Archive | 写入 |
| `mail_move` | 将邮件移动到指定 Folder ID | 写入 |
| `mail_set_category` | 替换邮件分类 | 写入 |

附件处理支持 PDF、DOCX、XLSX、PPTX、文本和受保护的压缩包检查。解析在受监督
Worker Process 中运行，并设置 Byte、Archive、Resource 和 Timeout 限制。邮件与
附件内容一律视为不可信输入。

## Runtime 架构

### 远端 Server——已经实现

```text
MCP Client / WorkBuddy
        |
        | Streamable HTTP + Entra delegated bearer token
        v
M365 MCP Server
        |
        | OBO token exchange
        v
Microsoft Graph / 当前登录用户邮箱
```

### Windows 本地模式——实施中

```text
Windows 上的 Agent
        |
        | MCP stdio
        v
m365-mcp.exe
        |
        | Public-client 委托登录（优先 WAM，浏览器 PKCE 回退）
        v
Microsoft Graph / 当前 Windows 登录用户
```

第一批本地模式基础已经实现：Graph 访问改为小型 Token Provider Interface，
Tool 的身份上下文可以在不依赖 HTTP Request 的情况下注入。打包可行性、Windows
Public Client 认证、DPAPI 状态存储、签名以及实际 EXE 尚未完成。

分发约束是真正的单文件，并且不能解压 Python Runtime Tree。正常 stdio 运行不得
安装 Service，也不得产生 Registry、Startup、Scheduled Task 或日志文件副作用。
详见 [Windows 本地单文件路线图](docs/zh-CN/windows-local.md)。

## 发布与验证状态

| 范围 | 状态 |
|---|---|
| Python 测试与双语文档检查 | GitHub Actions 执行 |
| Production Docker Image 构建 | CI 覆盖 |
| Container Health Smoke Test | CI 覆盖 |
| Docker Compose 校验 | CI 覆盖 |
| Mock WorkBuddy OAuth 与 Refresh Flow | CI 覆盖 |
| 真实 WorkBuddy 与真实邮箱验收 | 待完成的发布门禁 |
| 首个稳定 `v0.1.0` GitHub Release | 尚未发布 |
| Windows 单文件 EXE | 实施中，尚未发布 |

GitHub Actions 是本仓库唯一的构建与测试环境。存在 Release Workflow 或 Docker
Image 构建成功，并不代表已经发布稳定镜像。

## 部署当前远端 Server

部署前先配置 Microsoft Entra。操作手册覆盖 App Registration、
`access_as_user`、Microsoft Graph 委托权限、OBO/OAuth Credential、Tenant
范围与 Consent：

- [Microsoft Entra 应用注册操作手册](docs/zh-CN/entra-app-registration.md)

随后按照[部署清单](docs/zh-CN/deployment.md)执行：

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d
```

应用提供：

- `GET /health` 和 `GET /healthz`，仅用于进程存活检查。
- `/mcp/`，受保护的 FastMCP Streamable HTTP Endpoint。

使用 `/mcp/` 前必须配置 `CLIENT_ID`、且只配置一种由 OAuth/OBO 共用的 Client
Credential、`ALLOWED_TENANTS`、`REQUIRED_SCOPES` 和
`GRAPH_CONSENT_SCOPES`。`ALLOWED_TENANTS` 可以填写逗号分隔的 Tenant
Allowlist，也可以填写 `*` 接受任意有效 Microsoft Tenant；留空按 Fail Closed
处理。`AUDIENCE` 可留空，此时接受 Client ID 与 `api://<client-id>` 两种形式。
OBO 使用 `GRAPH_SCOPES=https://graph.microsoft.com/.default`。

## 尚未实现

- 真实 Client 与真实 Tenant 的发布验收。
- Search Continuation Cursor 与 Folder Discovery。
- Reply、Forward 工作流，以及 HTML 和附件撰写。
- OCR、Shared Mailbox、RBAC、Read-only Mode、Dynamic Tool Exposure 和 Rate
  Limiting。
- Calendar、OneDrive、SharePoint 和 Teams。
- 可分发的 Windows EXE。

## 文档

- [开发计划](docs/zh-CN/development-plan.md)
- [实现复核状态](docs/zh-CN/review-status.md)
- [Windows 本地路线图](docs/zh-CN/windows-local.md)
- [v0.1.0 发布检查清单](docs/zh-CN/release-checklist.md)
- [v0.1.0 Release Notes](docs/zh-CN/releases/v0.1.0.md)
- [WorkBuddy OAuth 指南](docs/zh-CN/workbuddy-oauth.md)
- [Runtime 依赖审计](docs/zh-CN/runtime-dependency-audit.md)
- [部署清单](docs/zh-CN/deployment.md)

当前交付顺序是：完成真实 v0.1 验收门禁，交付 Windows 本地 Runtime，然后再继续
Outlook 工作流闭环和更广泛的 Microsoft 365 Workload。
