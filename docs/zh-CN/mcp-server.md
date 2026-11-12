[English](../mcp-server.md) | **简体中文**

# 服务器版

| 项目 | 配置 |
| --- | --- |
| 运行环境 | 非 root 容器中的 Python 3.12 |
| 镜像 | `ghcr.io/sagehou/m365-mcp-server:v0.1.5` |
| MCP 入口 | `https://<你的域名>/mcp/`，使用 Streamable HTTP |
| 身份 | Microsoft Entra 用户委托身份，通过 OBO 和 `/me` 访问 Graph |
| Entra 应用 | 自建一个机密客户端应用，同时用于 API 和浏览器登录 |

## 注册 Entra 应用

1. 打开 [Microsoft Entra 管理中心](https://entra.microsoft.com/)，切换到管理此应用的
   租户，进入 **Entra ID > 应用注册 > 新注册**。
2. 名称填写 `M365-MCP-Server`，按下表选择支持的账户类型，添加 **Web** 重定向 URI
   `https://<你的域名>/oauth/callback`，然后选择**注册**。
3. 在**概述**复制**应用程序（客户端）ID**和**目录（租户）ID**。
   `CLIENT_ID` 使用应用程序 ID，不能填写**对象 ID**。
4. 在**公开 API**将应用程序 ID URI 设为 `api://<CLIENT_ID>`，添加下表中的作用域并启用。
5. 在**清单**将 `api.requestedAccessTokenVersion` 设为 `2`，让 API 接收 v2 Access Token。
6. 在 **API 权限 > 添加权限 > Microsoft Graph > 委托的权限**添加 `User.Read`、
   `Mail.ReadWrite` 和 `Mail.Send`。
7. 在**证书和密码**按下文创建服务器凭据。浏览器登录和 Graph OBO 共用这个应用及凭据。

| 注册时支持的账户类型 | `ALLOWED_TENANTS` |
| --- | --- |
| 仅此组织目录中的账户 | 此租户的 GUID；内部部署建议选择此项 |
| 任何组织目录中的账户 | 以逗号分隔允许的租户 GUID，或明确使用 `*` |
| 组织账户和个人 Microsoft 账户 | 填写允许的租户 GUID（包含个人账户租户），或明确使用 `*` |

| 公开 API 设置 | 值 |
| --- | --- |
| 作用域名称 | `access_as_user` |
| 谁可以同意 | 管理员和用户；仍受租户策略约束 |
| 管理员同意显示名称 | Access M365 MCP Server as the signed-in user |
| 管理员同意说明 | Allows a client to call M365 MCP Server on behalf of the signed-in user. |
| 用户同意显示名称 | Access M365 MCP Server |
| 用户同意说明 | Allows this client to use M365 MCP Server on your behalf. |
| 状态 | 已启用 |

完整作用域为 `api://<CLIENT_ID>/access_as_user`。

<details>
<summary>ⓘ 委托权限与管理员同意</summary>

| Graph 委托权限 | 用途 | 权限本身是否强制管理员同意 |
| --- | --- | --- |
| `User.Read` | 当前默认同意请求仍包含此项 | 否 |
| `Mail.ReadWrite` | 读取、修改邮件、草稿和附件 | 否 |
| `Mail.Send` | 以登录用户身份发送邮件 | 否 |

邮件接口不依赖 `User.Read`，但默认 `GRAPH_CONSENT_SCOPES` 仍会请求它。
以上均为**委托权限**；当前实现不使用邮箱 **Application 权限**。

目标租户允许用户自行同意时，登录页面展示权限，由用户批准即可。权限**状态**列为空，
不代表必须管理员批准。租户仍可能禁用用户同意、要求经过验证的发布者，或仅允许用户
同意选定的低影响权限。

策略要求批准时，走目标租户的管理员同意流程。应用注册在该租户时，有权限的管理员可在
**应用注册 > 此应用 > API 权限 > 授予管理员同意**中审核。跨租户应用也可由目标租户的
授权管理员访问：

```text
https://login.microsoftonline.com/<TARGET-TENANT-ID>/adminconsent?client_id=<CLIENT_ID>
```

随后在该租户的**企业应用程序 > 此应用 > 安全性 > 权限**检查委托授权。在应用所属租户
同意，不代表其他租户已同意；新增权限或撤销授权后需重新同意。个人 Microsoft 账户走
自己的同意流程。

参考：[Graph 权限表](https://learn.microsoft.com/zh-cn/graph/permissions-reference)、
[用户同意策略](https://learn.microsoft.com/zh-cn/entra/identity/enterprise-apps/configure-user-consent)、
[OBO 流程](https://learn.microsoft.com/zh-cn/entra/identity-platform/v2-oauth2-on-behalf-of-flow)。

</details>

<details>
<summary>ⓘ Token Audience、租户准入与云端点</summary>

客户端发送的是 MCP API Token：`aud` 对应 `CLIENT_ID` 或明确配置的 API Audience，
`scp` 包含 `access_as_user`，`tid` 与 `oid/sub` 标识用户。不能使用 Graph Token 或
App-only Token 替代。服务器验证后，以该用户经过验证的租户为 Authority，通过 OBO
请求 `https://graph.microsoft.com/.default`。所有邮件请求都使用 `/me`，调用者不能
指定其他邮箱。

`ALLOWED_TENANTS` 不能为空。填写逗号分隔的租户 GUID，或单独使用 `*`，两者不能混写。
通配符扩大租户准入范围，同时保留签名、Issuer、Audience、有效期、Scope 和身份校验，
不会改变应用注册支持的账户类型。个人账户的 Consumer Tenant 为
`9188040d-6c67-4c5b-b112-36a304b66dad`。`AUDIENCE` 留空时，接受配置的
`CLIENT_ID` 和 `api://<CLIENT_ID>` 两种形式。

默认端点属于 Microsoft 全球云：`https://login.microsoftonline.com` 和
`https://graph.microsoft.com/v1.0`。世纪互联运营的 Microsoft 365 及其他国家云需要
独立的应用注册、端点配置和部署验证。

</details>

## 配置与部署

在部署主机的仓库目录执行：

```bash
cp deploy/.env.example deploy/.env
```

编辑 `deploy/.env`。使用服务器管理的浏览器登录（包括 WorkBuddy）时填写：

```dotenv
M365_MCP_IMAGE=ghcr.io/sagehou/m365-mcp-server:v0.1.5
CLIENT_ID=<application-client-id>
CLIENT_SECRET=<client-secret-value>
CLIENT_CERT_PATH=
CLIENT_CERT_THUMBPRINT=
AUDIENCE=
ALLOWED_TENANTS=<approved-tenant-guid>
REQUIRED_SCOPES=access_as_user
GRAPH_SCOPES=https://graph.microsoft.com/.default
GRAPH_CONSENT_SCOPES=https://graph.microsoft.com/User.Read,https://graph.microsoft.com/Mail.ReadWrite,https://graph.microsoft.com/Mail.Send
OAUTH_ENABLED=true
MCP_PUBLIC_URL=https://mcp.example.com/mcp/
OAUTH_ISSUER_URL=https://mcp.example.com
OAUTH_DATABASE_PATH=/data/oauth.db
OAUTH_ENCRYPTION_KEY=<base64-encoded-32-random-bytes>
OAUTH_REFRESH_TOKEN_TTL_DAYS=30
OAUTH_REFRESH_MAX_ROTATIONS=10000
MCP_BIND_ADDRESS=127.0.0.1
MCP_PORT=8000
```

替换全部占位符和域名。使用 Client Secret 时，复制其**值**，不是密码 ID。在部署主机
生成 OAuth 加密密钥，例如执行 `openssl rand -base64 32`，并保存在部署密钥管理系统中。
不要将 `deploy/.env` 纳入版本控制。

模板默认 `OAUTH_ENABLED=false`。只有 MCP 客户端已经自行获取并刷新此 API 的有效
Entra Token 时才保持关闭；服务器管理的 Discovery、浏览器登录、下载及 Push Grant
需要设为 `true` 并填写上述 OAuth 配置。

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml pull
docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d
docker compose --env-file deploy/.env -f deploy/docker-compose.yml ps
curl --fail http://127.0.0.1:8000/healthz
curl -i http://127.0.0.1:8000/mcp/
```

健康检查应返回 `200`，未认证的 MCP 请求应返回 `401`。镜像拉取失败时，先解决版本或
仓库访问问题再启动。私有 GHCR 包需要先使用有读取权限的凭据执行 `docker login ghcr.io`。

<details>
<summary>ⓘ 证书凭据与可复现的镜像选择</summary>

`CLIENT_SECRET` 和 `CLIENT_CERT_PATH` 只能配置其中一种。生产环境建议使用证书：
在**证书和密码 > 证书**上传公钥证书，将 PEM 私钥保存在部署密钥系统中，清空
`CLIENT_SECRET`，并设置：

```dotenv
CLIENT_CERT_PATH=/run/secrets/m365-client.pem
CLIENT_CERT_THUMBPRINT=<certificate-thumbprint>
```

以只读方式挂载私钥。例如创建 `deploy/compose.cert.yml`：

```yaml
services:
  m365-mcp:
    volumes:
      - ./secrets/m365-client.pem:/run/secrets/m365-client.pem:ro
```

将受保护的私钥放在 `deploy/secrets/m365-client.pem`。所有 Compose 命令均在
`-f deploy/docker-compose.yml` 后添加 `-f deploy/compose.cert.yml`。仅在
`CLIENT_CERT_PATH` 填写宿主机路径并不会挂载文件。凭据需在到期前轮换。

固定使用已发布的镜像版本或 Digest。`edge` 和 `sha-<commit>` 是从经过审核的 `main`
发布的集成镜像；记录可复现验收结果时使用 Commit Tag。版本标签发布在 CI 成功后生成
稳定镜像标签。

</details>

## 配置 HTTPS 反向代理

在固定公网域名终止 TLS，将以下路由转发到同一服务器进程：

| 路由 | 访问方式 |
| --- | --- |
| `/mcp/`、`/uploads/attachments` | 有效的用户委托 Bearer Token |
| `/.well-known/*`、`/oauth/*` | OAuth Discovery 与浏览器/Token 流程 |
| `/uploads/push` | 精确匹配的短时 `X-Upload-Handle` 凭据 |
| `/downloads/*` | 短时、一次性下载凭据 |
| `/health`、`/healthz` | 无认证的进程探测；按部署需要限制暴露范围 |

`MCP_PUBLIC_URL` 和 `OAUTH_ISSUER_URL` 必须与公网路由精确一致，应用不会从 Host 或
Forwarded Header 推导它们。生产 URL 必须使用 HTTPS。Entra 的 **Web** 回调必须精确为
`OAUTH_ISSUER_URL` 加 `/oauth/callback`。WorkBuddy 私有回调注册在本服务器，不能填入
Entra 应用注册。

<details>
<summary>ⓘ 代理限制、日志与持久化</summary>

Compose 默认将发布端口绑定在 `127.0.0.1`。代理在其他容器或主机时，需要显式配置私有
网络/接口。`MCP_PORT` 同时控制监听、发布端口和健康探测。

二进制上传请求体限制为 20 MiB 加 HTTP 封装开销。为上传、`/oauth/register` 和
`/oauth/token` 配置请求体、速率与并发限制。不要记录认证请求头、`X-Upload-Handle`、
OAuth Query String 或 `/downloads/*` 凭据路径。应用已关闭请求行访问日志，代理和日志
采集器也需一致配置。

Compose 将已注册客户端及加密 OAuth Session 保存在挂载到 `/data` 的 `oauth-data`
卷中。数据库属于敏感身份状态，应备份并保护；恢复或替换进程时必须使用同一个
`OAUTH_ENCRYPTION_KEY`。Token/缓存内容经加密保存；Refresh Handle 只保存哈希，每次
使用轮换，重放会吊销整个轮换族。

Upload Handle、暂存文件和下载内容保存在有界进程内存中，创建和使用必须到达同一个
Worker，重启后丢失。当前实现没有为这些能力提供跨 Worker 或跨主机路由的共享存储。

</details>

## 连接 MCP 客户端

### 浏览器登录与 WorkBuddy

启用 OAuth 后，在支持 MCP OAuth Discovery 和 Public-client Registration 的客户端配置：

```json
{
  "mcpServers": {
    "m365": {
      "type": "streamableHttp",
      "url": "https://mcp.example.com/mcp/",
      "timeout": 30000
    }
  }
}
```

连接时完成浏览器登录和委托权限同意。客户端使用 S256 PKCE，获取 MCP API Token；注册了
Refresh Grant 时同时获取轮换的 Refresh Token，服务器随后通过 OBO 访问 Graph。

WorkBuddy 4.24.0 及以上使用仓库的 `workbuddy/` 包模板。将 `mcp.json` 中的
`${M365_MCP_URL}` 替换成精确的 `MCP_PUBLIC_URL`，压缩该目录的**内容**，使
`connector-meta.json`、`mcp.json`、`icon.svg` 和 `skills/` 位于压缩包根目录。
保留其 OAuth Discovery 配置，不添加 Token 表单、认证请求头或 Entra Client Secret。

<details>
<summary>ⓘ OAuth 回调与刷新行为</summary>

动态注册接受精确的 HTTPS 回调、`workbuddy://workbuddy/<非空路径>`，以及带显式端口、
非空路径的 Loopback 回调（`localhost`、`127.0.0.1`、`[::1]`）。拒绝通配符、Fragment、
公网 HTTP 回调和未注册的值。

Discovery 使用 `/.well-known/oauth-protected-resource` 和
`/.well-known/oauth-authorization-server`。注册、授权、回调及 Token 路由分别为
`/oauth/register`、`/oauth/authorize`、`/oauth/callback`、`/oauth/token`。浏览器交接
只包含一次性本地 Code 和客户端原始 State。WorkBuddy 通过完成页唤起已注册的私有 URI；
HTTPS 和 Loopback 客户端使用重定向。

Code 兑换校验 Client、精确回调、Resource 和 S256 Verifier。本地 Code 最长十分钟有效，
只能使用一次。刷新要求客户端注册 `refresh_token` Grant；刷新时复验同一租户/用户，
原子轮换本地 Handle，重放会吊销轮换族。临时上游故障返回 `temporarily_unavailable`，
不会消费当前 Refresh Token。

</details>

### 自行管理 Entra Token 的客户端

`OAUTH_ENABLED=false` 时，客户端自行获取 `api://<CLIENT_ID>/access_as_user` 的委托
Token，并在 MCP 请求中发送 `Authorization: Bearer <MCP-API-access-token>`。
客户端负责获取、同意、过期和刷新处理；Graph Access Token 的 Audience 不匹配。
此模式提供 11 个邮件工具，启用服务器管理的 OAuth 后增加下表标注的两项工具。

客户端邮件工作流可选装 [m365-mail](../../workbuddy/skills/m365-mail/README.zh-CN.md)。
同一个 Skill 支持服务器及两套本地版，WorkBuddy 模板已包含它。

## 邮件工具

| 工具 | 用途 |
| --- | --- |
| `mail_search`、`mail_get` | 搜索一页有界结果、读取邮件 |
| `mail_create_draft`、`mail_send_draft` | 创建纯文本草稿、发送现有草稿 |
| `mail_add_draft_attachment` | 将明确上传的文件添加到草稿 |
| `mail_list_attachments`、`mail_read_attachment` | 列出附件、提取有界文本 |
| `mail_mark_read`、`mail_archive`、`mail_move`、`mail_set_category` | 修改登录用户的邮件 |
| `mail_download_attachment` | 一次性下载 URL；需启用服务器管理的 OAuth |
| `mail_prepare_attachment_push` | 绑定草稿/文件的上传授权；需启用服务器管理的 OAuth |

创建草稿和添加附件不会发送邮件。调用 `mail_send_draft` 前，客户端需取得逐封确认，或执行
用户明确给出的受限自动化授权，约束收件人、可信内容/附件来源、数量和有效期。服务器无法
验证客户端是否取得该授权。Graph 接受请求不代表最终送达；写入或发送结果不明时，先检查
草稿再决定是否重试。

## 为远端草稿添加文件

### 认证二进制上传

1. 使用 `mail_create_draft` 创建草稿。
2. 向 `POST /uploads/attachments` 发送与 `/mcp/` 相同的委托 Bearer Token、
   `Content-Type: application/octet-stream`、`X-Attachment-Name`（经百分号编码的
   UTF-8 纯文件名），可选 `X-Attachment-Content-Type`（ASCII MIME 类型）。正文发送
   1 字节至 20 MiB 原始文件内容，不使用 Base64 或 Multipart。
3. 使用返回的 Handle 调用 `mail_add_draft_attachment(draft_id, upload_handle)`。
   发送前核对 SHA-256 和 `mail_list_attachments`。

Handle 绑定当前用户，五分钟过期，只能消费一次。客户端本机路径不能替代向服务器上传文件。

### 无人值守客户端产物的 OAuth Push Grant

1. 检查已生成产物的文件名、MIME 类型、精确字节数和 SHA-256，通过远端 MCP 连接器创建草稿。
2. 通过该连接器调用 `mail_prepare_attachment_push(draft_id, name, content_length,
   content_sha256, content_type?)`。
3. 向返回的固定 HTTPS `upload_url` POST 原始字节，携带
   `Content-Type: application/octet-stream` 和 `X-Upload-Handle: <upload_handle>`。
   此请求使用 Grant，不使用 OAuth Bearer Token；精确长度和 SHA-256 必须一致。
4. 通过同一个连接器调用 `mail_add_draft_attachment(draft_id, upload_handle)`，再检查
   附件列表，最后才授权发送。

<details>
<summary>ⓘ 可选的 Windows .NET 远端上传辅助程序</summary>

.NET NativeAOT EXE 提供 `inspect-attachment` 和 `push-attachment`，无需本机 Entra 登录
或第二个 MCP 连接器。配置可信产物目录和固定服务器上传端点：

```powershell
$env:M365_ATTACHMENT_ROOT = 'C:\Automation\Output'
$env:M365_ATTACHMENT_PUSH_URL = 'https://mcp.example.com/uploads/push'
& 'C:\Tools\m365-mcp-windows-local-amd64.exe' inspect-attachment 'reports\weekly.docx'
$grantJson | & 'C:\Tools\m365-mcp-windows-local-amd64.exe' push-attachment 'reports\weekly.docx'
```

`$grantJson` 是 `mail_prepare_attachment_push` 返回的完整 Grant。辅助程序只接受配置目录
下的相对路径及非空、20 MiB 以内的 PDF/DOCX/XLSX/PPTX/ZIP，核验已打开的文件，不写临时
附件。通过 stdin 传递 Grant，不放入命令行参数或日志。文件改变后需重新检查并申请 Grant。

通用 `m365-mail` Skill 可通过已有授权的 Shell 能力执行这些命令，包括 WorkBuddy 的
Bash 工具。辅助程序的目录检查只约束此 EXE 操作；
客户端的通用 Bash 访问还需配置自身沙箱和授权。其他可信上传程序也可实现同样的 HTTP 契约。

</details>

## 附件限制与运维

| 操作 | 默认边界 |
| --- | --- |
| 上传到草稿 | 非空、最大 20 MiB；纯文件名不超过 255 字符 |
| 附件文本提取 | 文件最大 10 MiB；输出不超过 100,000 字符 |
| 提取 Worker | 512 MiB 地址空间、15 秒 CPU、20 秒总时间；最多两个同时运行 |
| Office 解压 | 64 MiB、2,048 个条目 |
| 下载 URL | 五分钟、一次性；内存最多 16 项、64 MiB |

支持 PDF、DOCX、XLSX、PPTX、TXT 和 Markdown 文本提取；XLSX 读取缓存公式结果，扫描版
PDF 需要外部 OCR。小于 3,000,000 字节的 Graph 附件直接创建，更大的使用顺序 Upload
Session。MCP 不返回 Graph 上传 URL 或文件字节。

<details>
<summary>ⓘ 调整限制与故障排查</summary>

文本提取由 `ATTACHMENT_MAX_BYTES` 和 `ATTACHMENT_MAX_TEXT_CHARS` 限制。提高文件上限时，
同步扩大 `GRAPH_MAX_RESPONSE_BYTES`，覆盖 Base64 JSON：至少为文件上限的 4/3 加元数据。
下载使用 `ATTACHMENT_DOWNLOAD_TTL_SECONDS`、`ATTACHMENT_DOWNLOAD_MAX_ITEMS` 和
`ATTACHMENT_DOWNLOAD_MAX_TOTAL_BYTES`，其中总字节上限不得小于 `ATTACHMENT_MAX_BYTES`。
Worker 资源限制不等于文件系统/网络沙箱，仍需容器内存/PID 和代理限制。

| 提示或现象 | 检查与处理 |
| --- | --- |
| `AADSTS50011` | 在 **Web** 注册精确的服务器 `/oauth/callback`；客户端私有回调属于 MCP DCR。 |
| `AADSTS65001` / `consent_required` / 管理员批准 | 检查 `access_as_user`、显式 `GRAPH_CONSENT_SCOPES` 及目标租户授权/策略；允许用户同意时重新连接完成授权。 |
| `AADSTS70011` | `GRAPH_SCOPES` 保持 Graph `.default`，不要与显式 Scope 混写。 |
| API 拒绝 Bearer Token | 检查 MCP API Audience、委托 `scp`、租户 Allowlist、Issuer 和有效期。 |
| 外部租户 OBO 失败 | 检查多租户注册、目标租户准入、当地 Enterprise Application 及委托授权。 |
| 个人账户无法登录 | 检查支持的账户类型及 Consumer Tenant 准入；`*` 不会覆盖注册设置。 |
| Graph `403` | 检查委托同意、登录身份及账户的 Outlook/Exchange 邮箱可用性。 |
| 替换容器后无法刷新 | 恢复同一 SQLite 卷和加密密钥，检查过期/吊销状态，需要时重新连接。 |

OBO 故障可通过安全审计字段 `entra_error`、`entra_suberror`、`entra_error_code` 和
`correlation_id` 关联 Entra 诊断。保持 Token、邮件、文件名、Grant 和附件正文日志关闭。

</details>

## 部署验收

1. 确认公网健康检查以及未认证 MCP 的 `401` 响应。
2. 完成真实客户端登录、初始化 MCP，确认预期的 11 或 13 项工具；WorkBuddy 不应出现手工
   Token 表单。
3. 使用两个用户搜索、读取已知邮件，确认不能访问彼此邮箱。启用外部租户或个人账户时，
   分别验证对应场景。
4. 创建草稿、附加已知文件，取得所需授权后才发送给受控收件人。修改操作仅使用可丢弃邮件；
   移动/归档后使用返回的新 ID。
5. OAuth 模式下验证 Token 到期和容器重启后的刷新，保留数据库/密钥；检查下载过期及一次性
   兑换。
6. 确认应用和代理日志不含凭据或邮件内容，在部署记录中保存精确镜像 Digest 和连接器包。

---

仓库构建与测试仅通过 GitHub Actions 执行，编辑环境不得运行本地测试或安装测试依赖。
CI 使用模拟身份流程，不能代替目标租户和客户端验收。更新日期：2026-11-12。
