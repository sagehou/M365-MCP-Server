[English](../security.md) | **简体中文**

# 安全设计

## 身份

身份认证基于 Microsoft Entra ID Delegated Access Tokens。

Server 在接受任何 MCP Request 前，通过 OpenID Connect Discovery Document 和已发布 Signing Keys 验证 Token Signature。

## 权限

推荐 Graph Permissions：

- User.Read
- Mail.ReadWrite

避免：

- Mail.Read.All
- Mail.ReadWrite.All
- Application Permissions

## Token 校验

受保护的 `/mcp/` Endpoint 要求：

- Bearer Access Token 的 Audience 必须是本 API
- Token Tenant 必须显式存在于 `ALLOWED_TENANTS`，或者配置 `ALLOWED_TENANTS=*`
- Issuer 必须与 Token Tenant 和 Entra Metadata 推导结果完全一致
- Delegated `scp` Claim 必须包含 `REQUIRED_SCOPES`

`ALLOWED_TENANTS=*` 只取消 Server 本地的 Tenant Allowlist 限制，不会绕过 Signature、Issuer、Audience、Expiry、Delegated Scope 或 User Identity 校验。只有当 Entra App Registration 的 Supported account types 本身支持 Personal Microsoft Accounts 时，个人 Microsoft 账户才能登录；其 Token 使用 Microsoft Consumer Tenant。

Server 会拒绝：发给 Graph 的 Token、只有 `roles` 的 Application-only Token、显式 Allowlist 之外的 Tenant、无效 Signature、Expired Token 和 Issuer Mismatch。

## Tenant Isolation

Server 验证：

- Tenant ID
- User Object ID（无法取得 Object ID 时使用 Subject）
- Audience
- Issuer
- Delegated Scopes

Downstream Operation 必须使用经过验证、带 Tenant Qualification 的 Identity，并且 MCP Tools 不得接受任意 Mailbox/User Identifier。即使使用 `ALLOWED_TENANTS=*`，Tenant ID 仍然是每次请求 Identity 和 OBO Authority 的组成部分，因此不会取消用户/租户隔离。

## On-Behalf-Of

Graph Token 通过 MSAL On-Behalf-Of Flow，从已经验证的 Inbound Assertion 获取。Service 不会交换调用者自行提供的 User ID，也不会使用 Graph Application Permissions 访问邮箱。

## Audit

记录：

- Timestamp
- Tenant
- User
- MCP Tool
- Operation Result

Mail Attachment Listing 会在返回 MCP Client 前移除 `contentBytes`。`mail_read_attachment` 只在 Server 端解码 File Attachment，并应用 Byte Limit 与 Extracted-text Limit；PDF、DOCX、XLSX、PPTX、TXT 只返回 Metadata 与 Text，不会把 Graph `contentBytes` Base64 返回 MCP Client。

不得记录：

- Email Body
- Attachment Content
- Access Tokens
- Secrets

## Logging Policy

Audit Logger 对每个 MCP Mail-tool Invocation 输出一条 JSON Event 到 stderr。Event 包含明确 UTC Timestamp、Tenant ID、User ID、Tool Name、Success/Failure Outcome、Duration 和安全的 Exception Type。

Logger 不接受也不序列化 Tool Arguments、Graph Responses、Email Bodies、Attachment Names、Attachment Bytes、Access Tokens 或 Secrets。

Tool Boundary 会在 FastMCP Logging 前替换 Exception，原始 Provider/Parser Message 不会暴露。未进入已注册 Mail Tool Function 的 Invalid Protocol/Schema Request 不属于 Mailbox Audit Event。

Graph Response Bytes 在 JSON Parsing 前进行限制。Attachment Base64 长度会在 Decode 前检查；不可信 Parser 运行在 Resource-limited Linux Process 中，不继承 Entra Secrets，并带 Timeout/Cancellation Cleanup。

Email Preview、Message Body 和 Extracted Attachment Text 都会带明确的 Untrusted-content Marker。它们只是 Agent 要分析的数据，不是 System、Developer、User 或 Tool Instructions。Tool Description 也重复这一边界，因此 Client 不应执行邮件或附件中嵌入的指令。

HTTP Security Middleware 会添加 `no-store`、Anti-framing、Content-type、Referrer、Content-security 和 Permissions-policy Response Headers。它不能替代 TLS Termination、Token Validation 或 Downstream Authorization。
