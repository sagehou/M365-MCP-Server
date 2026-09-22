[English](../windows-local.md) | **简体中文**

# Windows 本地单文件版本

## 当前状态

首个 Windows 本地实现位于 `windows/M365Mcp.Local`，只通过 GitHub Actions
构建。它使用 .NET 8 NativeAOT，发布结果严格为一个 `m365-mcp.exe`；用户电脑
不需要 Python、.NET、Docker、Git 或安装器。

当前 EXE 已提供：

- `doctor`、`login`、`logout`、`status` 和 `stdio` 命令；
- 面向独立 Entra Desktop/Public Client App 的系统浏览器 Authorization Code +
  S256 PKCE 登录；
- 使用当前 Windows 用户 DPAPI 保护可选持久 Token State；
- 通过 MCP stdio 提供 10 个有边界的 Outlook Mail 工具；
- `--ephemeral` 模式，不读取也不写入持久状态；
- Windows Actions 门禁：构建结果不是单个 EXE 就失败；Smoke Test 时从
  `PATH` 移除语言 Runtime，并在 Ephemeral 运行产生文件时失败。

这仍是集成版本，不是已签名的 Stable Release。WAM Broker、PDF/Office 附件解析、
Authenticode 签名、SBOM 和 Clean VM 真实邮箱验收仍需完成。

## Runtime 决策

远端/容器 Server 继续使用 Python 3.12。Windows 本地 Host 是一个小型、独立的
.NET NativeAOT 边界，只负责本地认证、MCP stdio 和受控 Graph/Mail 工具面。

这取代了早期 PyOxidizer 候选方案。PyOxidizer 最新稳定版内置 CPython 3.10，
不适合作为当前 Python 3.12 项目的可维护交付基础；PyInstaller 和 Nuitka 的
One-file 模式会在启动时解压 Runtime Tree，也不满足“不产生解压目录”的约束。
NativeAOT 生成原生 Windows EXE，用户电脑无需安装 Python 或 .NET Runtime。

## 分发约束

- 用户只接收并运行一个 `m365-mcp.exe`。
- 正常运行不解压 Runtime Tree。
- `stdio` 不安装 Service，不创建 Registry、Startup、Scheduled Task 或日志文件。
- stdout 只输出 MCP JSON-RPC；诊断信息只写 stderr。
- 持久模式最多创建一个已声明的当前用户文件：
  `%LOCALAPPDATA%\M365-MCP-Server\state.bin`。
- State 中的 OAuth Token 使用当前 Windows 用户 DPAPI 保护。
- `--ephemeral` 不读取、新建或修改 State 文件。
- Agent 将 `stdio` 作为子进程启动。当前版本不提供 Windows Service 安装，
  因为 Service 无法拥有 Agent 的 stdio 通道。

## Entra Public Client 配置

为 Windows 本地 EXE 创建独立的 App Registration：

1. 添加 **移动和桌面应用程序（Mobile and desktop applications）**平台。
2. 注册 Redirect URI：`http://localhost`。EXE 每次登录会监听随机 Loopback Port。
3. 配置 Microsoft Graph 委托权限：`User.Read`、`Mail.ReadWrite` 和
   `Mail.Send`。
4. 不要创建或分发 Client Secret 或证书。
5. 记录 Application (client) ID；Tenant Policy 要求时同时记录 Tenant ID。

远端 Server 现有的 Confidential-client/OBO App Registration 保持不变，不能把
它的凭据作为 Public Desktop Credential 分发。

## 运行

在 PowerShell 中：

```powershell
$env:M365_LOCAL_CLIENT_ID = "<desktop-public-client-id>"
$env:M365_LOCAL_TENANT_ID = "organizations"

.\m365-mcp.exe doctor
.\m365-mcp.exe login
.\m365-mcp.exe status
```

`login` 会打开系统浏览器，通过 Loopback 完成 PKCE，然后保存 DPAPI 保护的 State。
不允许认证状态跨进程保留时，对 `login` 或 `stdio` 增加 `--ephemeral`。

MCP Client 配置示例：

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

如果没有可用状态，首次 Tool Call 也可以触发交互登录；Agent 必须给用户留出足够
时间完成浏览器流程。

## 当前本地工具面

EXE 当前提供：

- `mail_search`
- `mail_get`
- `mail_create_draft`
- `mail_send_draft`
- `mail_list_attachments`
- `mail_read_attachment`：支持有边界的 UTF-8 Text、CSV、JSON 和 XML
- `mail_mark_read`
- `mail_archive`
- `mail_move`
- `mail_set_category`

本地 stdio Runtime 没有 HTTP Download Endpoint，并且不得任意写文件，因此暂不
提供 `mail_download_attachment`。PDF/DOCX/XLSX/PPTX 解析仍在验收待办中。邮件
发送仍必须在 Client/Agent 层逐封确认，或具有明确的受限自动化授权。

## 构建与取得集成产物

`Windows local executable` Workflow 会上传
`m365-mcp-windows-x64` Actions Artifact。该 Workflow：

1. 使用固定 Windows Runner；
2. 通过 NativeAOT 发布 `windows/M365Mcp.Local/M365Mcp.Local.csproj`；
3. 断言输出目录中只有 `m365-mcp.exe`；
4. 在 `PATH` 中没有语言 Runtime 的条件下执行 `doctor`、MCP
   `initialize` 和 `tools/list`；
5. 断言 Ephemeral 运行不会留下文件。

Actions Artifact 不能宣称为 Stable Release。后续必须在干净的受支持 Windows x64
VM 上验证已签名 EXE，并把精确通过 Smoke Test 的文件发布为 GitHub Release Asset。

## 剩余验收门禁

- 增加首选 WAM 登录，同时保留 Browser PKCE 回退。
- 在不解压 Runtime 的前提下增加安全的富文档附件解析。
- 使用真实邮箱验证搜索、读取、草稿、确认发送、受限自动化发送、附件读取和代表性修改。
- 验证 Refresh、Logout、损坏 State 恢复、双账户隔离和 Tenant Policy。
- 增加 Authenticode 签名、时间戳、SHA-256 Checksum 和 SBOM。
- 在干净 Windows x64 VM 上发布并验证精确的已签名 EXE。
