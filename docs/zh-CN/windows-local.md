[English](../windows-local.md) | **简体中文**

# Windows 本地单文件版本

## 当前状态

首个 Windows 本地实现位于 `windows/M365Mcp.Local`，只通过 GitHub Actions
构建。它使用 .NET 10 NativeAOT，发布结果严格为一个 `m365-mcp-windows-local-amd64.exe`；用户电脑
不需要 Python、.NET、Docker、Git 或安装器。

原有流水线继续保留；新增的 [Go 版](windows-local-go.md)使用独立流水线和产物名。
已发布的 v0.1.3 NativeAOT EXE 使用 .NET 10 LTS。

当前 EXE 已提供：

- `doctor`、`login`、`logout`、`status` 和 `stdio` 命令；
- 面向独立 Entra Desktop/Public Client App 的系统浏览器 Authorization Code +
  S256 PKCE 登录；
- 默认内置项目公共客户端 `M365-MCP-Localhost`，并允许企业覆盖 Client ID；
- 使用当前 Windows 用户 DPAPI 保护可选持久 Token State；
- 通过 MCP stdio 提供 11 个有边界的 Outlook Mail 工具；
- `--ephemeral` 模式，不读取也不写入持久状态；
- Windows Actions 门禁：构建结果不是单个 EXE 就失败；Smoke Test 时从
  `PATH` 移除语言 Runtime，并在 Ephemeral 运行产生文件时失败。

[v0.1.3 GitHub Release](https://github.com/sagehou/M365-MCP-Server/releases/tag/v0.1.3)
已提供稳定版 Windows EXE、SHA-256 校验文件、MIT 许可声明和该精确 Smoke Test
二进制文件的 GitHub Artifact Attestation。普通分支的 Actions Artifact 仍只是
集成产物。已发布 EXE 尚无 Authenticode 签名；SBOM 与 PDF/Office 本地附件解析
属于独立加固事项。是否引入 WAM 取决于部署需求。已发布 v0.1.3 EXE 提供 11 个
邮件工具，包括添加草稿附件。

## Runtime 决策

远端/容器 Server 继续使用 Python 3.12。Windows 本地 Host 是一个小型、独立的
.NET NativeAOT 边界，只负责本地认证、MCP stdio 和受控 Graph/Mail 工具面。

这取代了早期 PyOxidizer 候选方案。PyOxidizer 最新稳定版内置 CPython 3.10，
不适合作为当前 Python 3.12 项目的可维护交付基础；PyInstaller 和 Nuitka 的
One-file 模式会在启动时解压 Runtime Tree，也不满足“不产生解压目录”的约束。
NativeAOT 生成原生 Windows EXE，用户电脑无需安装 Python 或 .NET Runtime。

## 分发约束

- 用户只接收并运行一个 `m365-mcp-windows-local-amd64.exe`。
- 正常运行不解压 Runtime Tree。
- `stdio` 不安装 Service，不创建 Registry、Startup、Scheduled Task 或日志文件。
- stdout 只输出 MCP JSON-RPC；诊断信息只写 stderr。
- 持久模式最多创建一个已声明的当前用户文件：
  `%LOCALAPPDATA%\M365-MCP-Server\state.bin`。
- State 中的 OAuth Token 使用当前 Windows 用户 DPAPI 保护。
- `--ephemeral` 不读取、新建或修改 State 文件。
- Agent 将 `stdio` 作为子进程启动。当前版本不提供 Windows Service 安装，
  因为 Service 无法拥有 Agent 的 stdio 通道。

## 杀毒软件误报

未签名的 NativeAOT EXE 可能被终端安全软件隔离。构建参数、ZIP 包、Checksum 或
GitHub Attestation 都不能保证杀毒软件放行。Windows 构建已写入产品名称、文件描述
和版本号，有助于识别样本，但不等于发布者签名。

如果 EXE 被拦截：

1. 从项目 GitHub Release 获取精确的 EXE 和 `.sha256` 文件。用
   `Get-FileHash .\m365-mcp-windows-local-amd64.exe -Algorithm SHA256` 与发布的校验值
   对比；如已安装 GitHub CLI，再运行
   `gh attestation verify m365-mcp-windows-local-amd64.exe --repo sagehou/M365-MCP-Server`。
   任一验证失败都不要继续运行。
2. 记录安全产品及病毒库版本、检出名称、SHA-256、Release 来源链接和触发步骤。
   不要包含 Token、邮件内容或未经脱敏的用户/租户标识。
3. 将*被检出的那份二进制文件*作为疑似误报提交给对应厂商。奇安信使用其官方
   [样本上报页面](https://www.qianxin.com/other/sample-upload)；页面限制文件不
   超过 100 MB，并要求联系邮箱和验证码。附上仓库、Release 链接、构建来源证明
   和简要行为说明：这是单文件 MCP stdio 进程；登录时打开系统浏览器完成 Entra
   PKCE、仅监听本机 Loopback；访问 Microsoft Graph；可选地在已声明路径保存
   DPAPI 保护的状态。
4. 等待厂商判定和病毒库更新，再用同一 SHA-256 在受影响终端复测。企业受管终端
   如需临时例外，应由安全管理员评估对已验证的*精确文件哈希*设置窄范围、限时
   规则。不要关闭安全软件，也不要放行整个目录或同名进程家族。

二进制哈希改变后需重新核验；旧版本的判定不自动覆盖新构建。GitHub Attestation
证明构建来源，不证明文件绝对安全，也不代表所有杀毒引擎都会信任它。

若奇安信或其他受管终端安全产品要求提供 MD5 和 SHA-1 以按精确文件哈希加白，
请使用同一 GitHub Release 说明中 `m365-mcp-windows-local-amd64.exe` 对应的值。先用
发布的 `.sha256` 文件核对 EXE 的 SHA-256，再由安全管理员评估窄范围白名单。
MD5 和 SHA-1 不是可信性证明；任何 EXE 变更都必须重新计算并审核白名单。

## Entra Public Client 配置

NativeAOT EXE 默认内置以下项目公共客户端的 Client ID，没有内置或使用 Client Secret：

```text
应用名称：M365-MCP-Localhost
Application (client) ID：6e35216e-2623-43cc-b867-83bec0865cf3
Authority：organizations
```

使用内置应用不需要自行注册。组织部署建议在自己的租户中注册、管理独立的
Desktop/Public Client 应用：

1. 打开 [Microsoft Entra 管理中心](https://entra.microsoft.com/)，切换到管理此应用的租户，
   进入 **Entra ID > 应用注册 > 新注册**。名称可填 `M365-MCP-Local-Custom`，
   按下表选择**支持的账户类型**，暂不填写重定向 URI，然后选择**注册**。
2. 在**概述**复制**应用程序（客户端）ID**和**目录（租户）ID**。
   `M365_LOCAL_CLIENT_ID` 使用应用程序 ID，不能填写**对象 ID**。
3. 进入**身份验证 > 添加平台 > 移动和桌面应用程序**，添加自定义重定向 URI
   `http://localhost` 并保存。使用根路径，不加 `/callback` 或固定端口，也不要在
   **Web** 或**单页应用程序**平台重复添加同一个 URI。无需创建 Client Secret 或证书。
4. 进入 **API 权限 > 添加权限 > Microsoft Graph > 委托的权限**，添加下表三项权限并
   保存。租户允许用户自行同意时，继续在本机登录；仅在策略要求时走组织的管理员同意流程。

| 注册时支持的账户类型 | `M365_LOCAL_TENANT_ID` |
| --- | --- |
| 仅此组织目录中的账户 | 应用所属目录（租户）ID；单组织使用建议选此项 |
| 任何组织目录中的账户 | `organizations`，或指定组织的租户 ID |
| 任何组织目录中的账户和个人 Microsoft 账户 | `common`，同时允许组织和个人账户 |
| 仅个人 Microsoft 账户 | 此 NativeAOT 版使用 `consumers` |

| Microsoft Graph 委托权限 | 当前版本中的用途 | 权限本身是否强制管理员同意 |
| --- | --- | --- |
| `User.Read` | 默认登录仍会请求；邮件功能未调用用户资料 API | 否 |
| `Mail.ReadWrite` | 读取、修改邮件、草稿和附件 | 否 |
| `Mail.Send` | 以登录用户身份发送邮件 | 否 |

<details>
<summary>ⓘ 公共客户端设置与账户类型</summary>

在**移动和桌面应用程序**注册回调后，浏览器 Authorization Code + S256 PKCE 流程会按
公共客户端处理。Entra 匹配 `http://localhost` 时忽略随机端口，但路径必须一致。
此流程的 **Allow public client flows（允许公共客户端流）**可保持默认 **No**；该开关
用于设备代码、用户名/密码、Windows 集成身份验证等其他流程。参见微软的
[桌面应用注册](https://learn.microsoft.com/zh-cn/entra/identity-platform/scenario-desktop-app-configuration)
和[公共客户端说明](https://learn.microsoft.com/zh-cn/entra/identity-platform/msal-client-applications)。

租户配置接受 GUID、`organizations`、`common`、`consumers`；修改它不会改变应用注册支持的
账户类型。登录账户需要有可访问的 Outlook/Exchange 邮箱。若没有**新注册**入口，需由
租户管理员授予应用注册权限；它与邮箱权限的管理员同意是两件事。

Client ID 是公开标识。应独立注册桌面应用，不要分发 Python 服务端机密客户端/OBO 应用的
凭据。本机使用无需邮箱 **Application 权限**，也不需要暴露 `access_as_user` API。

</details>

<details>
<summary>ⓘ User.Read、自定义 Scope 与管理员批准</summary>

邮件接口和 PKCE 登录本身不依赖 `User.Read`，但当前 EXE 仍默认请求它。仅从注册的
**API 权限**列表删除此项，不会改变登录请求。NativeAOT 版支持显式覆盖 Scope，例如：

```powershell
$env:M365_LOCAL_GRAPH_SCOPES = 'openid profile offline_access https://graph.microsoft.com/Mail.ReadWrite https://graph.microsoft.com/Mail.Send'
```

此变量会替换完整的默认 Scope 列表。保留 `offline_access`，否则 EXE 无法获取所需的
Refresh Token。先停止 MCP 客户端/服务，执行 `logout`，再重新 `login`；MCP 客户端
的 `env` 也要携带同一 Scope 配置。Go 版不支持此变量。

微软[委托权限表](https://learn.microsoft.com/zh-cn/graph/permissions-reference)中，这三项的
**AdminConsentRequired** 均为 **No**。[租户用户同意策略](https://learn.microsoft.com/zh-cn/entra/identity/enterprise-apps/configure-user-consent)
仍可能要求批准：例如禁用用户自行同意、应用不满足发布者验证要求，或未将邮件权限列为
低影响权限。移除 `User.Read` 不能绕过这些策略。

需要批准时，向管理员提供应用 ID、目标租户、请求的委托权限和登录错误码。应用注册在该
租户时，有权限的管理员可在**应用注册 > 此应用 > API 权限 > 代表租户授予管理员同意**
中审核。跨租户使用需走目标租户自己的管理员同意流程；在应用所属租户同意，不代表其他
租户也已同意。批准需覆盖当前权限集合；新增权限或撤销授权后需要重新同意。

</details>

## 运行

在 PowerShell 中：

```powershell
.\m365-mcp-windows-local-amd64.exe doctor
.\m365-mcp-windows-local-amd64.exe login
.\m365-mcp-windows-local-amd64.exe status
```

默认运行不需要设置环境变量。使用企业自己的 App Registration 时再覆盖：

```powershell
$env:M365_LOCAL_CLIENT_ID = "<custom-desktop-public-client-id>"
$env:M365_LOCAL_TENANT_ID = "<directory-tenant-id>"
.\m365-mcp-windows-local-amd64.exe doctor
.\m365-mcp-windows-local-amd64.exe login
.\m365-mcp-windows-local-amd64.exe status
```

先设置以上变量，再执行 `login`。`doctor` 应显示自建应用的 `client_id`、选择的 `tenant`
以及 `client_id_source: "environment"`；缓存 Access Token 可用时，`status` 显示
`authenticated: true`。

`login` 会打开系统浏览器，通过 Loopback 完成 PKCE，然后保存 DPAPI 保护的 State。
不允许认证状态跨进程保留时，对 `login` 或 `stdio` 增加 `--ephemeral`。

自建应用的 MCP 客户端配置：

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

将路径和两个 ID 替换为实际值。NativeAOT 版每次启动都会读取这些环境变量；PowerShell
中的 `$env:` 赋值只影响当前会话及其子进程，不会修改已经运行的 MCP 客户端。
`login` 与 MCP 配置中的 Client ID、Tenant 必须一致；使用内置应用时省略 `env`。
登录、`stdio` 和退出登录需使用同一个 Windows 用户，才能读取对应的 DPAPI State。

如果没有可用状态，首次 Tool Call 也可以触发交互登录；Agent 必须给用户留出足够
时间完成浏览器流程。

<details>
<summary>ⓘ 切换应用或恢复内置应用</summary>

先停止 MCP 客户端，执行 `logout`，设置新的应用和租户，再执行 `doctor` 和 `login`。
同步修改 MCP 客户端的 `env` 并重启。Client ID 或 Tenant ID 变更后，不会复用旧的
DPAPI Token State。

在 PowerShell 中恢复内置应用：

```powershell
.\m365-mcp-windows-local-amd64.exe logout
Remove-Item Env:M365_LOCAL_CLIENT_ID, Env:M365_LOCAL_TENANT_ID, Env:M365_LOCAL_GRAPH_SCOPES -ErrorAction SilentlyContinue
.\m365-mcp-windows-local-amd64.exe doctor
.\m365-mcp-windows-local-amd64.exe login
```

同时移除 MCP 客户端 `env` 中的这些覆盖值。本机退出登录不会撤销租户同意或浏览器会话。

</details>

<details>
<summary>ⓘ 自建应用登录排查</summary>

| 登录提示或现象 | 检查与处理 |
| --- | --- |
| 需要管理员批准 / `AADSTS90094` / `AADSTS65001` | 检查目标租户的授权记录及用户同意策略；`65001` 也可能只是用户尚未完成同意。 |
| `AADSTS50011` / 重定向 URI 不匹配 | 在**移动和桌面应用程序**注册根地址 `http://localhost`，不加额外路径。 |
| `AADSTS7000218` / 要求 Client Secret | 检查回调所属平台；应修正误配的 Web 平台，不应添加 Secret。 |
| `AADSTS700016` / 找不到应用 | 检查应用程序（客户端）ID、租户选择及支持的账户类型。 |
| PowerShell 登录成功，但 MCP 客户端再次要求登录 | 检查两个进程是否使用同一 Windows 用户及相同 `env`；`--ephemeral` 不会跨进程保存状态。 |
| `doctor` 成功，但登录或邮件访问失败 | `doctor` 只检查本机配置；仍需单独检查 Entra 同意及账户的 Exchange/Outlook 邮箱可用性。 |

</details>

## 当前本地工具面

EXE 当前提供：

- `mail_search`
- `mail_get`
- `mail_create_draft`
- `mail_send_draft`
- `mail_add_draft_attachment`：每次最多添加 20 MiB 的单个文件
- `mail_list_attachments`
- `mail_read_attachment`：支持有边界的 UTF-8 Text、CSV、JSON 和 XML
- `mail_mark_read`
- `mail_archive`
- `mail_move`
- `mail_set_category`

本地 stdio Runtime 没有 HTTP Download Endpoint，并且不得任意写文件，因此暂不
提供 `mail_download_attachment`。PDF/DOCX/XLSX/PPTX 解析仍在验收待办中。邮件
发送仍必须在 Client/Agent 层逐封确认，或具有明确的受限自动化授权。

### Windows 本地 Connector 的无人值守产物附件

使用 Windows 本地 stdio Connector 做无人值守自动化时，在 Connector 进程环境中
把 `M365_ATTACHMENT_ROOT` 配为可信的产物绝对目录，然后调用
`mail_add_draft_attachment(draft_id, relative_path="reports\\weekly.docx")`。
工具只读取最终路径仍在该目录内的已打开文件，限制为 20 MiB 以内的
DOCX/XLSX/PPTX/ZIP/PDF，并通过本地登录用户的 Graph 会话直接添加附件；
不需要浏览器上传、第二个 Connector、Bash 命令或远端 Push URL。不写临时附件
文件，也不通过 MCP 返回文件字节。不传 `relative_path` 时，才使用原有的
Windows 文件选择框。授权发送前须核对草稿和附件列表。

### 远端 Connector 的本机 EXE 辅助命令

已发布的同一个单文件 EXE 还提供
`inspect-attachment <relative-path>` 和 `push-attachment <relative-path>`。
这些命令不使用 Entra 登录，也不启动另一个 MCP Connector。把
`M365_ATTACHMENT_ROOT` 配为存放已完成自动化产物的可信绝对目录，把
`M365_ATTACHMENT_PUSH_URL` 配为 Server 固定的 HTTPS `/uploads/push` URL。
调用者只能给出该目录下的相对路径；EXE 校验打开文件的最终路径，仅允许
DOCX、XLSX、PPTX、ZIP 和 PDF，拒绝空文件及超过 20 MiB 的文件，不创建临时文件。

`inspect-attachment` 返回本机文件名、MIME 类型、字节数及 SHA-256。
`push-attachment` 从标准输入读取同一路径的完整 Grant JSON；EXE 会再次检查
配置的 URL 和文件，再推送原始字节，不接收用户 OAuth Token，也不跟随 HTTP
Redirect。Server 端的 Grant、上传、添加附件和发送完整步骤见
[远端 MCP Server 指南](mcp-server.md)。

例如 PowerShell 中已经把 MCP 工具返回的 Grant JSON 暂存在 `$grantJson` 时：

```powershell
$env:M365_ATTACHMENT_ROOT = 'C:\Automation\Output'
$env:M365_ATTACHMENT_PUSH_URL = 'https://mcp.example.com/uploads/push'
& 'C:\Tools\m365-mcp-windows-local-amd64.exe' inspect-attachment 'reports\weekly.docx'
$grantJson | & 'C:\Tools\m365-mcp-windows-local-amd64.exe' push-attachment 'reports\weekly.docx'
```

不要记录 Grant 或放在命令行参数中。如检查与推送之间文件已变化，重新签发
Grant，不要猜测哈希。WorkBuddy 撰写 Skill 可通过 Bash 工具调用这些命令；EXE 必须放在
管理员认可的位置。受限自动化授权仍须明确约束产物来源、收件人、大小、邮件
数量与有效期。EXE 的目录限制只约束该命令；WorkBuddy 的通用 Bash 权限仍可能
访问其他文件，还需要依赖客户端自身的沙箱与工具审批策略。

## 构建与取得集成产物

`Windows local executable` Workflow 会上传
`m365-mcp-windows-local-amd64` Actions Artifact。该 Workflow：

1. 使用固定 Windows Runner；
2. 通过 NativeAOT 发布 `windows/M365Mcp.Local/M365Mcp.Local.csproj`；
3. 断言输出目录中只有 `m365-mcp-windows-local-amd64.exe`；
4. 在 `PATH` 中没有语言 Runtime 的条件下执行 `doctor`、MCP
   `initialize` 和 `tools/list`；
5. 断言 Ephemeral 运行不会留下文件。

Actions Artifact 不能宣称为 Stable Release。Tag Release Workflow 会重新构建并
Smoke Test Windows x64 EXE，发布 SHA-256 校验文件和 MIT 许可声明，为该文件
记录 GitHub Artifact Attestation，并把精确通过测试的文件附加到 GitHub Release。

## 后续加固与部署检查

- 先验证 Browser PKCE，再根据账户选择、SSO 或 Tenant Policy 的实际需要决定
  是否增加可选 WAM 集成。
- 在不解压 Runtime 的前提下增加安全的富文档附件解析。
- 使用真实邮箱验证搜索、读取、草稿、确认发送、受限自动化发送、附件读取和代表性修改。
- 验证 Refresh、Logout、损坏 State 恢复、双账户隔离和 Tenant Policy。
- Authenticode 签名、时间戳和 SBOM 作为后续加固；v0.1.3 附有 SHA-256 Checksum 与 GitHub Artifact Attestation。
- 在干净 Windows x64 VM 上验证已发布的精确 EXE。
