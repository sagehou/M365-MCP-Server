[English](../mcp-server.md) | **简体中文**

# 远端 MCP Server

本文介绍以容器运行的 Python Server，不是 Windows 本地 stdio Connector。
Server 在 `/mcp/` 提供 Streamable HTTP，通过 OBO 以当前登录用户的委托身份
访问 Microsoft Graph，邮箱操作限定在 `/me`。客户端电脑上的文件路径并不是
Server 上的文件路径。

## 部署与连接

1. 按 [Entra 手册](entra-app-registration.md)配置 Server App Registration、
   Graph 委托权限和目标租户同意。
2. 按[部署指南](deployment.md)配置容器、TLS 反向代理和密钥。v0.1.1 镜像为
   `ghcr.io/sagehou/m365-mcp-server:v0.1.1`。`/healthz` 仅检查进程存活，
   不证明 Entra 同意或邮箱访问可用。
3. 让客户端连接公开的 HTTPS `/mcp/` URL。默认模式需要可通过本 API 校验的
   Entra Bearer Token。可选的 WorkBuddy Server-managed OAuth 登录见
   [OAuth 指南](workbuddy-oauth.md)，须显式启用。默认模式提供 11 个邮件工具；
   OAuth 模式另增加 `mail_download_attachment` 和
   `mail_prepare_attachment_push`，共 13 个。完整契约见[工具说明](tool-spec.md)。

Windows 单文件 EXE 的本地 `stdio` 模式采用独立认证和工具契约，见
[Windows 指南](windows-local.md)。

## 为远端草稿添加文件

远端工具 `mail_add_draft_attachment(draft_id, upload_handle)` 不读取客户端的
本地路径。客户端须通过以下任一路径主动提供 1 字节至 20 MiB 的原始文件字节，
再调用 MCP 工具。上传或添加附件都不会发送草稿。

### Bearer 鉴权的二进制上传

适用于上传客户端能够提供与 `/mcp/` 相同的委托 Bearer Token 的情况：

1. 调用 `mail_create_draft` 创建草稿。
2. 向 `POST /uploads/attachments` 发送 `Authorization: Bearer <token>`、
   `Content-Type: application/octet-stream`、放在 `X-Attachment-Name` 中
   经百分号编码的 UTF-8 纯文件名，并可选使用 `X-Attachment-Content-Type`
   指定 ASCII MIME 类型。请求体是原始文件字节，不是 Base64 或 Multipart。
3. 将返回的 `upload_handle` 和草稿 ID 传给 `mail_add_draft_attachment`。
   授权发送前核对返回的 SHA-256 和 `mail_list_attachments`。

句柄绑定已认证用户，五分钟过期，只能消费一次。此路径不限于 Windows，但
客户端必须自行实现明确的二进制上传动作。

### OAuth Push Grant：无人值守本机产物

Server-managed OAuth 已启用，且 MCP 客户端不向本机文件上传程序交付 OAuth
Token 时，可使用 Grant 路径：

1. 检查已完成的本机产物，取得文件名、MIME 类型、精确字节数和 SHA-256；
   通过远端 MCP Connector 创建草稿。
2. 调用 `mail_prepare_attachment_push(draft_id, name, content_length,
   content_sha256, content_type?)`，取得固定 HTTPS `upload_url` 和绑定该用户、
   草稿及精确文件元数据的短时 `upload_handle`。
3. 向该 URL 推送原始字节，请求头为 `Content-Type: application/octet-stream`
   和 `X-Upload-Handle: <upload_handle>`。这一步凭 Grant 认证，不需要 Bearer
   Token。长度或 SHA-256 不匹配时 Server 会拒绝。
4. Push 成功后，经同一个远端 MCP Connector 调用
   `mail_add_draft_attachment(draft_id, upload_handle)`，发送前检查
   `mail_list_attachments`。

在 Windows 上，同一个 `m365-mcp.exe` 可用 `inspect-attachment` 和
`push-attachment` 命令完成第 1、3 步；WorkBuddy 可通过撰写 Skill 的 Bash
工具调用。按照 [Windows EXE 辅助命令指南](windows-local.md#远端-connector-的本机-exe-辅助命令)
配置可信的 `M365_ATTACHMENT_ROOT` 和固定 HTTPS
`M365_ATTACHMENT_PUSH_URL`。该辅助程序不是必需的：其他可信客户端也可实现同一
HTTP 契约。EXE 的目录限制不约束 WorkBuddy 的通用 Bash 权限，仍需客户端自身的
沙箱和审批策略。

## 运行边界

- 文件名必须是纯文件名，最多 255 字符；可选 MIME 类型必须是有效 ASCII。
  文件须非空，单个不超过 20 MiB。
- Grant 和暂存字节在 Server 进程内存中有容量限制，五分钟过期。签发 Grant、
  上传与添加附件必须命中同一 Worker；v0.1.1 没有多 Worker/副本共享存储。
  Worker 重启后，未消费句柄失效。
- `/mcp/`、`/uploads/attachments` 和 `/uploads/push` 应经同一个固定的 HTTPS
  Origin 路由。不要记录 Bearer Token 或 `X-Upload-Handle`，并按
  [部署指南](deployment.md#oauth-authorization)限制代理请求体和速率。
- Push 只暂存文件，不会添加附件；添加附件也不构成发送授权。交互发送需另行
  确认，受限自动化需要明确的 Client/Agent 授权。若添加附件或发送结果不明确，
  重试前先检查草稿。

小于 3 MB 的文件由 Graph 直接添加，大文件使用顺序上传会话。Server 不经 MCP
返回文件字节或 Graph 上传 URL。结果字段和上限见
[工具契约](tool-spec.md#mail_add_draft_attachment)。
