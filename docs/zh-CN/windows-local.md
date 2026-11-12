[English](../windows-local.md) | **简体中文**

# Windows 本地版（.NET 与 Go）

| 能力 | .NET NativeAOT | Go |
| --- | --- | --- |
| Windows 架构 | AMD64 / x64 | AMD64 / x64、ARM64 |
| 安装运行时 | 无需 | 无需 |
| Microsoft 登录 | 系统浏览器、Authorization Code + S256 PKCE | 系统浏览器、Authorization Code + S256 PKCE |
| MCP 传输 | stdio，命令为 `stdio` | stdio，命令为 `stdio`；本机鉴权 HTTP，命令为 `http` |
| 邮件工具 | 12 项 | 13 项，含附件下载 URL |
| 附件文本提取 | UTF-8 文本、CSV、JSON、XML | PDF、DOCX、XLSX、PPTX、TXT、Markdown |
| 添加本地草稿附件 | 文件选择框或配置目录下的相对路径 | 配置目录下的相对路径 |
| 保存原附件 | `mail_save_attachment`，默认下载目录下的 M365-MCP 或自定义目录；默认上限 150 MiB 且可配置 | 与 .NET 的接口和行为一致 |
| 远端服务器上传辅助命令 | `inspect-attachment`、`push-attachment` | 不提供 |

## 安装

### Go 一键安装

```powershell
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/sagehou/M365-MCP-Server/main/scripts/install-windows-local.ps1')))
```

自动选择最新稳定版 Go AMD64/ARM64，核对压缩包、EXE 和 Skill 的 SHA-256，安装到
`%LOCALAPPDATA%\Programs\M365-MCP`，包含双语指南和许可声明。安装时询问 Client ID
及租户 ID；留空使用内置公开 Client ID 和 `organizations`，随后启动浏览器登录并生成
stdio `mcp.json`。将其中的 `m365-local` 条目合并到客户端配置，通过当前客户端的 Skill
机制安装完整 `m365-mail/` 文件夹。

<details>
<summary>ⓘ Agent 参数与延后登录</summary>

Agent 应先在对话中询问自定义 ID，再用
`-NonInteractive -ClientId '<GUID>' -TenantId '<GUID>'` 运行安装脚本。自建单租户
应用填写所属的目录（租户）GUID；`organizations`、`common`、`consumers` 仍可用于
匹配的账户类型。只有用户选择默认值时才使用默认 ID，无需 Client Secret。

添加 `-SkipLogin` 可先准备文件，不启动浏览器；使用 MCP 连接前，执行安装目录
`login-command.txt` 中的准确命令。Go 仅在成功登录后将选定 ID 随账户持久保存。
`-InstallDirectory` 接受自定义绝对路径，也可对下载到本地的安装脚本使用这些参数。
脚本生成配置供 Agent 合并，不改写已有客户端设置、不安装服务、不修改 PATH。
重复安装前先关闭 MCP 进程。支持 Windows PowerShell 5.1 和 PowerShell 7。

</details>

### 手动安装（.NET 或 Go）

从 [GitHub Release](https://github.com/sagehou/M365-MCP-Server/releases/tag/v0.1.7)
下载对应文件：

| 版本 | 发布文件 | 下文使用的 EXE |
| --- | --- | --- |
| .NET NativeAOT，Intel/AMD 电脑 | `m365-mcp-windows-local-amd64.exe` | 保持原文件名 |
| Go，Intel/AMD 电脑 | `m365-mcp-windows-local-go-amd64.zip` | ZIP 内的 `m365-mcp-windows-local-go.exe` |
| Go，Windows ARM 电脑 | `m365-mcp-windows-local-go-arm64.zip` | ZIP 内的 `m365-mcp-windows-local-go.exe` |

将程序放在 `C:\Tools` 等固定目录。两套版本均不需要 Python、.NET Runtime、Docker、
安装器或 Windows Service。用 EXE 对应的 `.sha256`，或 ZIP 对应的 `SHA256SUMS.txt`
核对下载文件的 SHA-256：

```powershell
Get-FileHash .\m365-mcp-windows-local-amd64.exe -Algorithm SHA256
Get-FileHash .\m365-mcp-windows-local-go-amd64.zip -Algorithm SHA256
```

执行与你下载文件对应的命令。单独下载 Go EXE 时，可重命名为
`m365-mcp-windows-local-go.exe`；保留架构后缀时，所有命令和客户端路径也要保留。
ZIP 包包含本指南的中英文版本及许可声明，实际运行只需 EXE。

<details>
<summary>ⓘ Go 命令更新与旧版配置</summary>

下文的 `stdio`、`http` 和 `consumers` 支持适用于 Go `v0.1.4` 及以后版本。
Go `v0.1.3` 及以前版本使用 `serve`，不接受 `consumers`；修改配置不会更新已有 EXE。
升级程序后，将 `args: ["serve"]` 改为 `args: ["stdio"]`，或执行 `connection` 重新生成
配置；HTTP 启动命令由 `serve --http` 改为 `http`。已有加密登录状态仍可使用，仅因
命令更新无需重新登录。

</details>

## 使用内置应用登录

```text
应用：M365-MCP-Localhost
公开 Client ID：6e35216e-2623-43cc-b867-83bec0865cf3
默认租户：organizations
```

在 EXE 目录打开 PowerShell，执行所用版本的命令：

```powershell
# .NET NativeAOT
.\m365-mcp-windows-local-amd64.exe login

# Go
.\m365-mcp-windows-local-go.exe login
```

在系统浏览器完成 Microsoft 登录和权限同意。两套版本内置同一个公开 Client ID，均没有
内置 Client Secret，也都允许使用自建应用覆盖。内置应用同样受目标租户的同意策略约束。

## 注册自建应用

1. 打开 [Microsoft Entra 管理中心](https://entra.microsoft.com/)，切换到管理此应用的
   租户，进入 **Entra ID > 应用注册 > 新注册**。名称可填 `M365-MCP-Local-Custom`，
   按下表选择支持的账户类型，暂不填写重定向 URI，然后选择**注册**。
2. 在**概述**复制**应用程序（客户端）ID**和**目录（租户）ID**。Client ID 使用应用程序
   ID，不能填写**对象 ID**。
3. 进入**身份验证 > 添加平台 > 移动和桌面应用程序**，添加自定义重定向 URI
   `http://localhost` 并保存。使用根地址，不加 `/callback` 或固定端口，不要在 **Web**
   或**单页应用程序**平台重复注册。
4. 进入 **API 权限 > 添加权限 > Microsoft Graph > 委托的权限**，添加下表三项权限。
   此本地应用无需创建 Client Secret、邮箱 Application 权限，或公开名为 `access_as_user`
   的自定义 API 权限范围。
5. 继续配置下文中所用版本。租户允许用户自行同意时，在登录过程中授权即可；只有需要批准
   时才走组织的管理员同意流程。

| 注册时支持的账户类型（两种版本一致） | 租户配置 |
| --- | --- |
| 仅此组织目录中的账户 | 应用所属目录（租户）GUID；单组织建议选择此项 |
| 任何组织目录中的账户 | `organizations`，或指定租户 GUID |
| 组织账户和个人 Microsoft 账户 | `common` |
| 仅个人 Microsoft 账户 | `consumers` |

| Graph 委托权限 | 当前用途 | 权限本身是否强制管理员同意 |
| --- | --- | --- |
| `User.Read` | 默认请求；当前邮件功能未调用用户资料 API | 否 |
| `Mail.ReadWrite` | 读取、修改邮件、草稿和附件 | 否 |
| `Mail.Send` | 以登录用户身份发送邮件 | 否 |

<details>
<summary>ⓘ 公共客户端配置与账户类型</summary>

组织部署建议自行注册、管理独立的 Desktop/Public Client 应用。Client ID 是公开标识；
此流程不使用 Client Secret 或证书。Python 服务器的机密客户端/OBO 注册具有独立用途
和凭据。

在**移动和桌面应用程序**注册 `http://localhost` 后，浏览器 Authorization Code +
PKCE 会按公共客户端处理。Entra 匹配时忽略随机端口，但路径必须一致。
**Allow public client flows（允许公共客户端流）**可保持默认 **No**；该开关用于设备代码、
用户名/密码和 Windows 集成身份验证等其他流程。参见微软的
[桌面应用注册](https://learn.microsoft.com/zh-cn/entra/identity-platform/scenario-desktop-app-configuration)
和[公共客户端说明](https://learn.microsoft.com/zh-cn/entra/identity-platform/msal-client-applications)。

两种版本都接受租户 GUID、`organizations`、`common` 和 `consumers`。仅支持个人账户的
应用使用 `consumers`；同时支持组织和个人账户的应用使用 `common`。修改 Authority
不会改变应用注册支持的账户类型。账户需有可访问的 Outlook/Exchange 邮箱。租户禁用
应用注册时，需单独申请注册权限；它与邮箱权限同意是两件事。

</details>

<details>
<summary>ⓘ User.Read 与管理员批准</summary>

邮件接口和 PKCE 本身不依赖 `User.Read`，但当前发布的两套版本仍默认请求它。仅从
**API 权限**删除此项，不会改变 EXE 请求。.NET 支持下文的 Scope 覆盖；Go 目前既没有
自定义 Scope 参数，也不支持 `M365_LOCAL_GRAPH_SCOPES`。

两套默认登录还会请求 `openid`、`profile`、`offline_access`，Go 中由 MSAL 自动附加。
管理员已批准但用户仍遇到审批提示时，按失败日志的应用程序 ID 找到**企业应用 > 此应用 >
权限 > 管理员同意**，将实际请求的 Scope 与整个组织的委托授权逐项比较；只授予管理员
个人的权限不覆盖其他用户。

这三项委托权限在[微软权限表](https://learn.microsoft.com/zh-cn/graph/permissions-reference)
中均为 **AdminConsentRequired: No**。[租户用户同意策略](https://learn.microsoft.com/zh-cn/entra/identity/enterprise-apps/configure-user-consent)
仍可禁止用户自行同意、要求发布者验证，或仅允许选定的低影响权限。移除 `User.Read`
不能绕过策略。

需要批准时，提供应用 ID、目标租户、请求的委托权限和登录错误码。应用注册在该租户时，
有权限的管理员可在**应用注册 > 此应用 > API 权限 > 授予管理员同意**审核。外部租户
需使用自己的同意流程；应用所属租户的同意不会覆盖其他租户。新增权限或撤销授权后需
重新同意。权限状态为空本身不代表必须管理员批准。

</details>

## 配置 .NET NativeAOT

使用自建应用时，**先设置变量，再登录**：

```powershell
$env:M365_LOCAL_CLIENT_ID = '<application-client-id>'
$env:M365_LOCAL_TENANT_ID = '<directory-tenant-guid>'
.\m365-mcp-windows-local-amd64.exe doctor
.\m365-mcp-windows-local-amd64.exe login
.\m365-mcp-windows-local-amd64.exe status
```

`doctor` 应显示你的 `client_id`、`tenant` 和 `client_id_source: "environment"`。
缓存 Access Token 可用时，`status` 显示 `authenticated: true`。使用内置应用时不设置
这些覆盖值。

在 MCP 客户端填写相同 ID：

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

替换实际 EXE 路径和 ID。使用内置应用时省略 `env`。.NET 每次启动都会读取这些配置；
PowerShell 的 `$env:` 赋值不会修改已运行的 MCP 客户端。登录和客户端需使用同一 Windows
用户、Client ID 和租户，才能复用 DPAPI State。没有可用状态时，首次工具调用也可触发登录。

<details>
<summary>ⓘ .NET 自定义 Scope 与临时模式</summary>

需要从 .NET 请求中去掉 `User.Read` 时，替换整个 Scope 列表：

```powershell
$env:M365_LOCAL_GRAPH_SCOPES = 'openid profile offline_access https://graph.microsoft.com/Mail.ReadWrite https://graph.microsoft.com/Mail.Send'
```

停止 MCP 客户端，执行 `logout` 后重新 `login`，并在客户端 `env` 填写同一个完整值。
保留 `offline_access`，因为 EXE 需要 Refresh Token。此变量不配置 Go 版。

`--ephemeral` 不读取或写入持久认证状态。需要不落盘的会话时，使用 `stdio --ephemeral`，
在提示时完成登录。单独执行 `login --ephemeral`，不能将其进程内 Token 交给后续进程。
协议数据写入 stdout，诊断信息写入 stderr；正常运行不安装服务、计划任务或启动项。

</details>

## 配置 Go

通过参数覆盖本次登录的应用：

```powershell
.\m365-mcp-windows-local-go.exe login --client-id YOUR-APPLICATION-ID --tenant YOUR-TENANT-ID
.\m365-mcp-windows-local-go.exe connection
```

也可使用环境变量：

```powershell
$env:M365_LOCAL_CLIENT_ID = 'YOUR-APPLICATION-ID'
$env:M365_LOCAL_TENANT_ID = 'YOUR-TENANT-ID'
.\m365-mcp-windows-local-go.exe login
.\m365-mcp-windows-local-go.exe connection
```

登录优先级为：参数 → 环境变量 → 内置默认值。授权前核对浏览器中的应用名称。
成功时输出 `Signed in. Run connection to generate your MCP client configuration.`。
Go 没有 `doctor` 或 `status` 命令。

### stdio

将 `connection` 输出的 JSON 填入 MCP 客户端，或手工配置：

```json
{
  "mcpServers": {
    "m365-local": {
      "command": "C:\\Tools\\m365-mcp-windows-local-go.exe",
      "args": ["stdio"]
    }
  }
}
```

Go 登录后保存所选应用、租户和账户，`stdio`、`http`、`connection` 使用已保存的配置，
客户端无需再携带登录环境变量。只有 `login` 接受 `--client-id`、`--tenant`；切换应用
需重新执行 `login`。
MCP 客户端负责启动进程，stdout 只输出协议数据，日志写入 stderr。

### Streamable HTTP

支持自定义请求头的客户端执行：

```powershell
.\m365-mcp-windows-local-go.exe connection --http --port 8000
.\m365-mcp-windows-local-go.exe http --port 8000
```

将第一条命令输出的 JSON（包含 Bearer 请求头）填入客户端。监听仅绑定 `127.0.0.1`，
所有 MCP 请求都需携带本机 Token，请妥善保管。重新登录会轮换此 Token，需重新生成 HTTP
配置。stdio 模式使用 `stdio` 命令，不接受 `--http`。

<details>
<summary>ⓘ 服务器 OAuth 连接器与本机传输</summary>

两套本地版均不提供 Python 服务器的 OAuth Discovery/DCR 端点。仓库的 WorkBuddy OAuth
连接器包用于服务器版。要求 OAuth Discovery 的客户端需连接服务器，或提供独立的
stdio/自定义请求头配置。Go HTTP Token 是本机访问凭据，不是 Microsoft Access Token。

</details>

## 邮件与附件

两套版本均提供 `mail_search`、`mail_get`、`mail_create_draft`、`mail_send_draft`、
`mail_add_draft_attachment`、`mail_list_attachments`、`mail_read_attachment`、`mail_save_attachment`、
`mail_mark_read`、`mail_archive`、`mail_move`、`mail_set_category`。
Go 另提供 `mail_download_attachment`。所有 Graph 请求使用登录用户的 `/me` 邮箱。

可在 AI 客户端中选装[通用 m365-mail Skill](https://github.com/sagehou/M365-MCP-Server/blob/main/workbuddy/skills/m365-mail/README.zh-CN.md)。
它按当前版本适配附件、下载和发送流程，不代替 MCP 配置或登录。

草稿使用纯文本。发送前，MCP 客户端需取得逐封确认，或执行明确的受限自动化授权，约束
收件人、可信内容/附件来源、数量和有效期。Graph 接受请求不代表最终送达。结果不明的写入
不会自动重试；先检查草稿和附件，再决定后续操作。

### 保存附件

从 v0.1.7 起，两种版本采用相同的流式保存接口。调用 `mail_save_attachment`，
传入三个必填参数：

```json
{
  "message_id": "<邮件 ID>",
  "attachment_id": "<附件 ID>",
  "relative_path": "downloads/report.pdf"
}
```

无需配置，此示例会保存到 Windows 当前用户实际“下载”目录下的
`M365-MCP\downloads\report.pdf`，支持系统重定向后的下载目录。保存时自动创建缺失
目录。两种版本的 `relative_path` 均使用正斜杠。EXE 将 Outlook 原始文件附件流式
写入磁盘，stdio 和 Go HTTP 均无需浏览器、本机 Shell、文件选择框或独立下载器。
目标在 EXE 所在电脑，即使 MCP 客户端运行在别处也是如此。

| 优先级 | 目标目录 |
| --- | --- |
| 1 | 本次工具调用可选的绝对路径 `download_dir`，由用户、Skill 或 Agent 选择 |
| 2 | MCP 进程环境中的 `M365_ATTACHMENT_ROOT` |
| 3 | Windows“下载”目录下的 `M365-MCP` |

例如，在参数中增加 `"download_dir": "D:\\MailArchive"`，本文件就保存到
`D:\MailArchive\downloads\report.pdf`；只影响当前调用。用户没有指定目录或自动化
规则时，Skill/Agent 可直接使用默认值，无需额外询问目录配置。

需要持久自定义目录或大小上限时，在 MCP Server 的 `env` 中设置：

```json
{
  "M365_ATTACHMENT_ROOT": "D:\\MailArchive",
  "M365_MAX_DOWNLOAD_MIB": "512"
}
```

两个变量均可选。Go `connection` 会将其进程环境中已设置的变量写入 stdio JSON，
修改后重新生成配置；Go HTTP 在启动 `http` 时继承变量。环境变量改变后需重启 MCP
连接；只在 `login` 时设置不会将它们持久保存在登录状态中。

两种版本返回相同字段：

```json
{
  "saved": true,
  "relative_path": "downloads/report.pdf",
  "path": "C:\\Users\\Alice\\Downloads\\M365-MCP\\downloads\\report.pdf",
  "name": "report.pdf",
  "content_type": "application/pdf",
  "content_length": 12345,
  "content_sha256": "<保存字节的 SHA-256>"
}
```

<details>
<summary>ⓘ 保存限制、目标路径与重试</summary>

每个文件默认上限 **150 MiB** 原始字节（157,286,400 字节）。`M365_MAX_DOWNLOAD_MIB`
接受 MiB 单位的正整数，可提高或降低上限；这是应用限制，不保证 Graph 或租户允许相同
大小。此前 10 MiB 保存限制来自内存 Base64/文本读取流程，并非 Graph 的附件硬上限。
现在改用 Graph 原始字节 `$value` 端点，以 64 KiB 缓冲流式写入并增量计算 SHA-256，
操作总超时为五分钟。文本读取及 Go 内存暂存的临时下载 URL 仍限制每个文件 10 MiB。

任意文件格式均可保存，包括零字节文件；不会解析、打开或执行文件。不支持嵌入邮件项和
引用附件。`name` 是服务方提供的原文件名；`path` 是由目标目录与 `relative_path`
确定的实际绝对保存路径。

工具自动创建缺失的根目录和父目录。`relative_path` 拒绝绝对路径、反斜杠、父目录跳转、
NTFS 备用数据流及 Windows 设备名，目标目录不得是符号链接或联接。已有目标文件绝不
覆盖，同时保存同名文件也只会成功一个。超限、取消或传输失败时，会尝试清理未完成文件；
结果不明确时，先检查目标及大小/哈希，再决定是否重试，工具不会悄悄改名或覆盖。
无人值守任务使用可信的目标和命名规则，不从邮件内容中接受指令。

</details>

### 添加本地文件

生成或启动客户端配置前，设置由操作者控制的附件目录：

```powershell
$env:M365_ATTACHMENT_ROOT = 'C:\M365Artifacts'
```

.NET 将此变量加入 MCP Server 的 `env`，调用
`mail_add_draft_attachment(draft_id, relative_path="reports\\weekly.docx")`。
不传 `relative_path` 时使用 Windows 文件选择框。

Go 设置目录后重新执行 `connection`，stdio JSON 会包含对应 `env`；HTTP 模式在启动
`http` 时继承变量。调用
`mail_add_draft_attachment(draft_id, relative_path="reports/weekly.docx")`。
Go 必须提供相对路径，不支持文件选择框。

两套版本均允许 20 MiB 以内的 PDF、DOCX、XLSX、PPTX、ZIP。使用相对路径时，核验已打开
文件仍在配置目录内，并返回实际字节数与 SHA-256。小于 3,000,000 字节的文件直接上传，
更大的使用受限顺序 Upload Session。添加附件不会发送邮件。

<details>
<summary>ⓘ 文本提取、下载与远端上传辅助命令</summary>

.NET 支持有界的 UTF-8 文本/CSV/JSON/XML 附件读取，没有下载端点或 PDF/Office 解析器。
Go 在独立 Worker 提取 PDF、DOCX、XLSX、PPTX、TXT、Markdown，限制为 512 MiB 内存、
15 秒 CPU、20 秒总时间，最多两个同时运行。提取文件最大 10 MiB，Office 解压最大
64 MiB/2,048 项，输出最多 100,000 字符。XLSX 使用缓存公式结果；扫描版 PDF 需要外部 OCR。

Go 临时下载支持最大 10 MiB 文件，使用不可猜测、五分钟、一次性的 HTTP URL，仅绑定
`127.0.0.1`。stdio 在随机
端口启动该监听器，内存最多保留 16 项、64 MiB，重启后 URL 失效。同一电脑上的浏览器或
可信脚本可消费一次 URL；自动保存优先使用 `mail_save_attachment`。
附件列表的 `size` 是服务方元数据，获取后的 `content_length` 是实际解码字节数。

.NET EXE 还提供供远端服务器连接器使用的 `inspect-attachment` 和 `push-attachment`，
无需本机登录；完整 Grant 和上传流程统一写在
[服务器版指南](https://github.com/sagehou/M365-MCP-Server/blob/main/docs/zh-CN/mcp-server.md#为远端草稿添加文件)。
这些命令不会创建第二个本地 MCP 连接器。Go 不提供它们。

</details>

## 切换应用与退出登录

修改凭据前，先停止 MCP 客户端/服务：

```powershell
# 执行所用版本的命令
.\m365-mcp-windows-local-amd64.exe logout
.\m365-mcp-windows-local-go.exe logout
```

.NET 设置新的应用/租户后执行 `doctor` 和 `login`，同步修改 MCP 客户端 `env` 再重启。
Go 用新参数或变量执行 `login`，然后执行 `connection`。重新登录会轮换 HTTP Token，
已有 HTTP 配置需替换；stdio 保持 EXE 路径和 `stdio` 参数。

<details>
<summary>ⓘ 恢复内置应用与本机状态位置</summary>

退出登录后，在 PowerShell 清除覆盖值：

```powershell
Remove-Item Env:M365_LOCAL_CLIENT_ID, Env:M365_LOCAL_TENANT_ID, Env:M365_LOCAL_GRAPH_SCOPES -ErrorAction SilentlyContinue
```

同时移除 .NET MCP 客户端 `env` 中的覆盖值。重新执行所用版本的 `login`；Go 再生成
`connection`。变量修改只影响当前 PowerShell 及子进程；以后从其他进程登录时可能继承
不同配置。

| 版本 | 当前用户加密状态 |
| --- | --- |
| .NET NativeAOT | `%LOCALAPPDATA%\M365-MCP-Server\state.bin`；读取时 Client ID 和租户需一致 |
| Go | `%LOCALAPPDATA%\M365MCP`；保存配置、MSAL Cache、本机 HTTP Token，目录采用仅当前用户可访问的 Windows ACL |

两者均使用当前用户 DPAPI。Go 将后续调用绑定到所选账户，刷新失败不会切换到其他缓存
用户；一次只允许一个 Go 登录/服务/退出进程使用该状态。本机退出会移除凭据，不会注销
浏览器会话或撤销租户同意。

</details>

## 故障排查

<details>
<summary>ⓘ 登录与客户端配置</summary>

| 提示或现象 | 检查与处理 |
| --- | --- |
| 管理员批准 / `AADSTS90094` / `AADSTS65001` | 检查目标租户授权和同意策略；`65001` 也可能只是用户尚未完成同意。 |
| `AADSTS50011` | 在**移动和桌面应用程序**注册根地址 `http://localhost`，不加额外路径。 |
| `AADSTS7000218` / 要求 Secret | 修正重定向平台；桌面公共客户端无需 Secret。 |
| `AADSTS700016` / 找不到应用 | 检查应用程序（客户端）ID、所选租户和支持的账户类型。 |
| .NET 在 PowerShell 登录成功，但 MCP 仍要求登录 | 核对 Windows 用户及 `env`；`--ephemeral` 不会跨进程保存状态。 |
| Go 仍使用旧应用/账户 | 停止 `stdio` 或 `http`，退出登录，再用显式参数 `login`，之后执行 `connection`。 |
| `doctor` 成功，但无法登录 | .NET `doctor` 只校验本机配置，不检查租户注册或同意。 |
| 登录成功，但 Graph `403` | 检查委托邮件授权和 Exchange/Outlook 邮箱可用性。 |
| Go 重新登录后 HTTP `401` | 重新生成 `connection --http`，替换旧 Bearer Token。 |

</details>

## 杀毒软件误报

<details>
<summary>ⓘ 核验并上报被检出的文件</summary>

1. 从同一 GitHub Release 下载精确 EXE 和校验文件，核对 SHA-256。.NET 产物还可使用
   GitHub CLI 核验来源：
   `gh attestation verify m365-mcp-windows-local-amd64.exe --repo sagehou/M365-MCP-Server`。
   核验不一致时先解决问题再运行。
2. 记录安全产品/病毒库版本、检出名称、SHA-256、Release URL 和触发步骤，不包含 Token
   或邮箱内容。
3. 通过厂商误报流程提交被检出的那份文件。奇安信的
   [样本上报页面](https://www.qianxin.com/other/sample-upload)支持 100 MB 以内文件，
   需要联系邮箱和验证码。
4. 厂商处理后，在受影响电脑用同一哈希核验。组织管理员需要临时例外时，评估针对精确文件
   的窄范围、限时规则。只有旧式白名单表单要求时才使用 Release 中的 MD5/SHA-1，完整性
   校验仍使用 SHA-256；程序变化后需重新核验和审核。

保持终端防护启用。上报实际行为：单个 EXE、浏览器 PKCE 和 Loopback 回调、用户委托
Graph 访问、当前用户加密状态。整个目录或进程名例外超出精确文件审核范围。

</details>

## 构建与分发

| 版本 | GitHub Actions 流水线 | 集成产物 |
| --- | --- | --- |
| .NET NativeAOT | `Windows local executable`（`windows-exe.yml`） | `m365-mcp-windows-local-amd64` |
| Go | `windows-local-go` | `windows-local-go-amd64`、`windows-local-go-arm64`、`windows-local-go-packages` |

构建与测试全部在 GitHub Actions 执行。Go ZIP 将本统一指南收录为 `README.md` 和
`README.zh-CN.md`，同时包含依赖声明和许可证。两条流水线继续独立运行；版本发布统一
提供经过测试的 EXE 和校验文件。普通 Actions Artifact 属于集成产物。
Go AMD64 在 Windows 执行运行检查，ARM64 进行交叉编译和版本资源检查。

---

EXE 尚未签名。Go 不保证降低杀毒软件检出；校验和、版本信息和来源证明不能替代
Authenticode 签名或厂商审核。Worker 资源限制不等于文件系统/网络沙箱。真实租户登录、
客户端兼容性和杀毒行为需在目标电脑验收。编辑环境不得构建、测试、安装测试依赖或创建
测试虚拟环境。更新日期：2026-11-12。
