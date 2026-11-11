[English](../windows-local-go.md) | **简体中文**

# Windows 本机 Go 版

## 安装

Intel/AMD 电脑解压 `m365-mcp-windows-local-go-amd64.zip`，Windows ARM 电脑解压
`m365-mcp-windows-local-go-arm64.zip`，将程序放在固定目录。无需 Python、Docker、管理员权限或
Client Secret。安装前用 `SHA256SUMS.txt` 核对压缩包。

若下载单 EXE 的 Artifact，先将程序重命名为 `m365-mcp-windows-local-go.exe`，
再使用下文命令。

## 登录

两套本机版默认使用同一个项目公共客户端应用：

```text
应用：M365-MCP-Localhost
Client ID：6e35216e-2623-43cc-b867-83bec0865cf3
租户：organizations
```

在解压目录打开 PowerShell：

```powershell
.\m365-mcp-windows-local-go.exe login
```

在系统浏览器完成 Microsoft 登录。程序使用 S256 PKCE 和随机端口的本机回调，后续调用绑定
此次选择的账户；刷新失败时不会切换到缓存中的其他账户。租户策略可能要求管理员批准
委托权限，使用内置应用时也一样。

## 使用自建应用

组织部署建议在自己的租户中注册、管理独立的 Desktop/Public Client 应用；使用内置应用
不需要自行注册。

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

| 注册时支持的账户类型 | 登录 `--tenant` / `M365_LOCAL_TENANT_ID` |
| --- | --- |
| 仅此组织目录中的账户 | 应用所属目录（租户）ID；单组织使用建议选此项 |
| 任何组织目录中的账户 | `organizations`，或指定组织的租户 ID |
| 任何组织目录中的账户和个人 Microsoft 账户 | `common`，同时允许组织和个人账户 |

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

Go 版接受租户 GUID、`organizations`、`common`，不接受 `consumers`。
如需 Outlook.com 个人账户，选择表中第三种注册类型并使用 `common`。修改登录 Authority
不会改变应用注册支持的账户类型。登录账户需要有可访问的 Outlook/Exchange 邮箱。
若没有**新注册**入口，需由租户管理员授予应用注册权限；它与邮箱权限的管理员同意是两件事。

Client ID 是公开标识。两套本机版均内置同一个公开 Client ID 并允许覆盖，均没有内置或
使用 Client Secret。应独立注册桌面应用，不要分发 Python 服务端机密客户端/OBO 应用的
凭据。本机使用无需邮箱 **Application 权限**，也不需要暴露 `access_as_user` API。

</details>

<details>
<summary>ⓘ User.Read 与管理员批准</summary>

邮件接口和 PKCE 登录本身不依赖 `User.Read`，但当前 Go 版仍默认请求以上三项 Scope，
因此自建应用应与当前请求保持一致。仅从 **API 权限**列表删除某项，不会改变 EXE 的登录
请求。Go 版目前没有自定义 Scope 参数，也不读取 `M365_LOCAL_GRAPH_SCOPES`。

微软[委托权限表](https://learn.microsoft.com/zh-cn/graph/permissions-reference)中，这三项的
**AdminConsentRequired** 均为 **No**。[租户用户同意策略](https://learn.microsoft.com/zh-cn/entra/identity/enterprise-apps/configure-user-consent)
仍可能要求批准：例如禁用用户自行同意、应用不满足发布者验证要求，或未将邮件权限列为
低影响权限。移除 `User.Read` 不能绕过这些策略。

需要批准时，向管理员提供应用 ID、目标租户、请求的委托权限和登录错误码。应用注册在该
租户时，有权限的管理员可在**应用注册 > 此应用 > API 权限 > 代表租户授予管理员同意**
中审核。跨租户使用需走目标租户自己的管理员同意流程；在应用所属租户同意，不代表其他
租户也已同意。批准需覆盖当前权限集合；新增权限或撤销授权后需要重新同意。

</details>

通过命令行覆盖本次登录的默认值：

```powershell
.\m365-mcp-windows-local-go.exe login --client-id 你的应用ID --tenant 你的租户ID
```

授权前核对浏览器显示的是否为自建应用名称。登录成功后输出
`Signed in. Run connection to generate your MCP client configuration.`；此版本没有
`doctor` 或 `status` 命令。

也可使用与 NativeAOT 版相同的环境变量：

```powershell
$env:M365_LOCAL_CLIENT_ID = '你的应用ID'
$env:M365_LOCAL_TENANT_ID = '你的租户ID'
.\m365-mcp-windows-local-go.exe login
.\m365-mcp-windows-local-go.exe connection
```

登录时的优先级为：命令行参数 → 环境变量 → 内置默认值。登录成功后保存所选应用和租户，
`serve` 和 `connection` 使用保存的配置，MCP 客户端不需要再携带登录环境变量。
仅修改环境变量，或给 `serve` 传入 `--client-id`，都不会切换已保存的应用。

<details>
<summary>ⓘ 切换应用或恢复内置应用</summary>

先停止 MCP 客户端/服务，执行 `logout`，再用新的应用和租户重新执行 `login`，然后执行
`connection`。重新登录会轮换本机 HTTP Bearer Token，已有 HTTP 客户端配置需要替换；
stdio 客户端仍使用原来的 EXE 路径和 `serve` 参数。

在 PowerShell 中恢复内置应用：

```powershell
.\m365-mcp-windows-local-go.exe logout
Remove-Item Env:M365_LOCAL_CLIENT_ID, Env:M365_LOCAL_TENANT_ID -ErrorAction SilentlyContinue
.\m365-mcp-windows-local-go.exe login
.\m365-mcp-windows-local-go.exe connection
```

以上环境变量修改只影响当前 PowerShell 会话。以后从其他进程执行 `login` 时可能继承
不同的变量；显式登录参数优先级最高。本机退出登录不会撤销租户同意或浏览器会话。

</details>

<details>
<summary>ⓘ 自建应用登录排查</summary>

| 登录提示或现象 | 检查与处理 |
| --- | --- |
| 需要管理员批准 / `AADSTS90094` / `AADSTS65001` | 检查目标租户的授权记录及用户同意策略；`65001` 也可能只是用户尚未完成同意。 |
| `AADSTS50011` / 重定向 URI 不匹配 | 在**移动和桌面应用程序**注册根地址 `http://localhost`，不加额外路径。 |
| `AADSTS7000218` / 要求 Client Secret | 检查回调所属平台；EXE 使用桌面公共客户端，应修正误配的 Web 平台，不应添加 Secret。 |
| `AADSTS700016` / 找不到应用 | 检查应用程序（客户端）ID、租户选择及支持的账户类型。 |
| 修改配置后仍使用旧账户或旧应用 | 停止 `serve`，执行 `logout`，用显式参数重新 `login`，再生成 `connection`。 |
| 登录成功但 Graph 返回 `403` | 检查委托邮件权限及账户的 Exchange/Outlook 邮箱可用性；登录成功不等于已能访问邮箱。 |

</details>

## 连接 MCP 客户端

### stdio

`serve` 默认使用 stdio。先完成上方 `login`，再在 MCP 客户端选择 stdio，填写程序绝对路径
和参数 `serve`：

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

将 `command` 改为实际程序路径；若保留下载文件名中的 `-amd64.exe` 或 `-arm64.exe`，
路径也应保留该后缀。MCP 客户端负责启动和管理进程，stdout 只输出协议数据，日志写入 stderr。

也可自动生成含实际程序路径的配置：

```powershell
.\m365-mcp-windows-local-go.exe connection
```

将生成的 `mcpServers` JSON 填入客户端。

### Streamable HTTP

支持 Streamable HTTP 和自定义请求头的客户端执行：

```powershell
.\m365-mcp-windows-local-go.exe connection --http --port 8000
.\m365-mcp-windows-local-go.exe serve --http --port 8000
```

将第一条命令输出的 JSON 填入客户端，妥善保管其中的 Bearer Token。监听地址固定为
`127.0.0.1`，所有 MCP 请求均需携带该 Token。本机版不提供容器版的 OAuth/DCR 端点；
仅支持自动 OAuth Discovery 的客户端应连接 Python 服务，或改用 stdio/自定义请求头。
仓库现有的 WorkBuddy OAuth 连接器包用于 Python 服务。

## 邮件工具

提供 12 项工具：`mail_search`、`mail_get`、`mail_list_attachments`、
`mail_read_attachment`、`mail_download_attachment`、`mail_mark_read`、
`mail_archive`、`mail_move`、`mail_set_category`、`mail_create_draft`、
`mail_send_draft`、`mail_add_draft_attachment`。所有 Graph 请求通过委托权限访问登录账户的
`/me` 邮箱。

草稿使用纯文本。发送前，MCP 客户端必须取得逐封确认或明确且有范围的自动化授权。
Graph 接受发送请求不代表最终送达；网络失败且结果不明时，不会自动重试写入。

添加本地 PDF、DOCX、XLSX、PPTX、ZIP 附件前，设置由操作者控制的目录，再生成客户端配置：

```powershell
$env:M365_ATTACHMENT_ROOT = 'C:\M365Artifacts'
.\m365-mcp-windows-local-go.exe connection
```

调用 `mail_add_draft_attachment` 时传入 `draft_id` 和 `relative_path`，例如
`reports/report.zip`。stdio 配置会将目录写入 `env`；HTTP 模式在启动 `serve` 时继承环境变量。
路径使用正斜杠，不能越出配置目录，附件最大 20 MiB。Go 版需要相对路径；原有 NativeAOT 版还
提供原生文件选择器和远程附件推送辅助程序。小于 3,000,000 字节的附件直接上传，更大的附件
使用受限的 Outlook Upload Session。返回结果包含实际字节数和 SHA-256；发送授权前需核对
草稿与附件。

搜索返回一页有界结果和 `next_link` 提示。附件列表的 `size` 是服务提供方元数据，下载后的
`content_length` 是实际解码字节数。PDF、DOCX、XLSX、PPTX、TXT、Markdown 文本提取使用
独立进程，限制为 512 MiB 内存、15 秒 CPU、20 秒总时间，最多同时运行两个 Worker。
附件不超过 10 MiB，Office 解压不超过 64 MiB / 2,048 个文件，提取文本不超过 100,000 字符。
XLSX 读取公式缓存结果；纯图片 PDF 所需的 OCR 尚未提供。

下载链接为绑定 `127.0.0.1` 的随机 HTTP URL，五分钟过期且仅可兑换一次。stdio 模式在随机
本机端口启动下载监听器。内存中最多保留 16 个下载和 64 MiB 数据，重启后全部失效。
链接供同一台电脑上的浏览器使用，不经过远程下载服务。

## 退出登录

先停止 MCP 客户端或服务进程，再执行：

```powershell
.\m365-mcp-windows-local-go.exe logout
```

同一时刻仅允许一个登录、服务或退出进程使用该账户。本地凭据与 HTTP Token 保存在
`%LOCALAPPDATA%\M365MCP`，使用当前 Windows 用户的 DPAPI 加密和用户专属 ACL。
退出登录删除本地凭据，不会撤销 Microsoft 浏览器会话或租户授权。Microsoft 要求交互式登录时，
停止服务并重新执行 `login`；这会同时轮换本地 HTTP Token，需重新生成 HTTP 客户端配置。

## 构建

所有构建和测试仅在 GitHub Actions 执行。`windows-local-go` 工作流使用
`scripts/build-windows-go.py` 打包 AMD64、ARM64 程序、中英文使用说明和第三方许可证。
CI 成功后，下载 `windows-local-go-amd64` 或 `windows-local-go-arm64` 获取单文件 EXE，
下载 `windows-local-go-packages` 获取 ZIP 包和校验和。工作流覆盖 Linux、Windows 测试，包括
Windows DPAPI、进程互斥和隔离 Worker。禁止在此编辑环境构建或测试。

构建仅在 CI 使用 `goversioninfo` v1.7.0，为两个架构嵌入资源管理器文件详细信息，
产品/文件版本取自 `pyproject.toml`。Tag 发布流水线复用同一构建，核对校验和，
将 Go EXE、ZIP 与原有 NativeAOT EXE 一起发布。

---

程序尚未代码签名。Go 不保证更少的杀软检测，SmartScreen 信誉、代码签名和误报申诉仍需按
发布环境处理。Job Object 限制资源，不隔离文件系统或网络。真实 Entra 登录、客户端兼容性、
代表性文档和杀软行为仍需在目标 Windows 电脑验收。更新日期：2026-11-11。
