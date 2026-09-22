[English](../workbuddy-oauth.md) | **简体中文**

# WorkBuddy OAuth

## 当前阶段

Server 当前实现 Discovery、Registration 与 Interactive Authorization-code Flow：

- `GET /.well-known/oauth-protected-resource`
- 未认证 `/mcp/` Bearer Challenge 中的 `resource_metadata` Link
- `GET /.well-known/oauth-authorization-server`
- 面向无 Client Secret Public Client 的 `POST /oauth/register`
- 使用 Exact Client/Redirect/Resource Binding 与 S256 PKCE 的 `GET /oauth/authorize`
- 由 MSAL Python 驱动、使用独立 Upstream State 的 `GET /oauth/callback`
- TTL 不超过 10 分钟、只能使用一次的 Local Authorization Code
- 支持 `grant_type=authorization_code` 与 `refresh_token` 的 `POST /oauth/token`
- 仅以 SHA-256 Hash 保存的 Opaque Local Refresh Token
- 带 One-time Rotation 与 Family Replay Revocation 的 Encrypted Persistent MSAL Cache
- 存储在配置 SQLite Database 中的 Restart-safe Session
- 由 `OAUTH_DATABASE_PATH` 指定、带 Issuer Binding 的 SQLite Persistence

Token Endpoint 返回发给唯一 `M365-MCP-Server` App Registration、并已通过现有 `JwtValidator` 复验的 Entra Access Token，因此现有 JWT Validation 与 OBO 链路仍是权威安全边界，不会另外签发 MCP JWT。Entra Authorization-flow Object、Token A 与 MSAL Cache 使用 `OAUTH_ENCRYPTION_KEY` 执行 AES-256-GCM 加密，并通过 Record-specific Authenticated Context 绑定不可变 OAuth Metadata；敏感 Token Material 不会进入 Browser Redirect 或 SQLite Plaintext Column。

在真实 WorkBuddy Acceptance Gate 完成前，受控集成开发以外应保持 `OAUTH_ENABLED=false`。Restarted 或 Replacement Process 必须使用同一 SQLite Database 与 Encryption Key。Distributed 或 Multi-host Session Storage 不属于 v0.1 Scope。

## Connector Package

仓库在 `workbuddy/` 下提供符合[WorkBuddy 官方 Connector 结构](https://open.workbuddy.cn/docs/connector)的 Package Template：

    workbuddy/
    |-- connector-meta.json
    |-- mcp.json
    |-- icon.svg
    `-- skills/
        |-- outlook-mail/SKILL.md
        |-- outlook-attachments/SKILL.md
        `-- outlook-mail-management/SKILL.md

Package 明确不包含 `auth_mode`、Request Header、Token 字段或 `token-schema.json`。WorkBuddy 必须作为 Public Client 自动发现并完成 Server 的标准 MCP OAuth Flow；不能要求用户粘贴 Access Token，也不能把 Entra Client Secret 交给 WorkBuddy。Metadata 使用当前中英文名称和示例字段，因此最低 WorkBuddy 版本为 4.24.0。三个 Skill 均采用当前[WorkBuddy Skill 格式](https://open.workbuddy.cn/docs/skill)，并且只开放各自需要的 Tools。

`workbuddy/mcp.json` 是纳入版本控制的 Deployment Template。制作提交包之前，必须把 `${M365_MCP_URL}` 替换为与 `MCP_PUBLIC_URL` 完全一致的生产 HTTPS `/mcp/` URL。不得增加 Authorization Header，也不得切换为用户自填 Token Mode。压缩 `workbuddy/` 的内容，确保 `connector-meta.json`、`mcp.json`、`icon.svg` 和 `skills/` 位于 Archive Root。

## Authorization Flow

1. WorkBuddy 通过 DCR 注册 Exact Redirect URI。
2. `/oauth/authorize` 校验 Client、Redirect、Scope、Resource、Response Type 与 S256 Challenge。
3. Server 保存 WorkBuddy State，并生成不同的 Cryptographically Random Entra State，再启动 MSAL Authorization。
4. `/oauth/callback` 原子消费 Transaction，由 MSAL 兑换 Microsoft Code，再通过现有 `JwtValidator` 复验 Token A。
5. 对 WorkBuddy Private Redirect，Server 返回带 `no-store` 和严格 CSP 的完成页：
   页面会唤起精确注册的 `workbuddy://` URI，尝试关闭由脚本打开的认证窗口；如果
   浏览器不允许自动关闭，则显示中英双语的手动关闭提示。Loopback 与 HTTPS Client
   仍保持普通 302 Redirect。交接内容只有
   `code=<local-code>&state=<original-state>`。
6. `/oauth/token` 接受 RFC 8707 `resource` Indicator；提供时必须与 `MCP_PUBLIC_URL` 精确匹配，并在 Exact Client、Redirect 与 PKCE 校验通过后原子兑换 Local Code，返回 Token A 与 Random Local Refresh Token；第二次兑换返回 `invalid_grant`。

## Refresh Flow

1. WorkBuddy 发送 `grant_type=refresh_token`、Public `client_id`、当前 Opaque Local Refresh Token，以及提供时相同的 `resource`。
2. Server 对 Handle 做 Hash，并查找绑定到 Configured Issuer 和 Client、尚未过期且未吊销的 Session。
3. 打开 Encrypted MSAL Cache，强制执行 MSAL Silent Token Acquisition；结果 Token A 再次通过 Validator，并且必须与原 Session 的 Tenant/User 一致。
4. SQLite 使用 Compare-and-swap 把旧 Handle Hash 与 Encrypted Cache 替换为新值；已消费 Hash 会继续绑定 Rotation Family。
5. WorkBuddy 获得 Token A 与新的 Opaque Refresh Token；任意已消费值 Replay 都返回 `invalid_grant` 并吊销当前 Family，包括 Attacker-first 取得的 Successor。

Microsoft Revocation、Unusable Cache 或 Identity Mismatch 会吊销 Local Session。Transient Upstream 或 Identity-metadata Outage 返回 `temporarily_unavailable`，不会消费当前 Local Refresh Token。

## Public URL 配置

显式配置外部可达 URL：

    MCP_PUBLIC_URL=https://mcp.example.com/mcp/
    OAUTH_ISSUER_URL=https://mcp.example.com
    OAUTH_DATABASE_PATH=/data/oauth.db
    OAUTH_ENCRYPTION_KEY=<32-random-bytes-base64>
    OAUTH_REFRESH_TOKEN_TTL_DAYS=30
    OAUTH_REFRESH_MAX_ROTATIONS=10000

Public URL 必须与 Reverse-proxy Route 精确一致。应用不会从 Request Header 推导这些值。生产值必须使用 HTTPS；HTTP 仅允许 Loopback 开发。Encryption Key 必须留在 Database、Image、Repository 与 Log 之外；丢失 Key 会使已保存 Session 失效。Rotation Limit 会限制单个 Session 的 Replay History 增长；达到上限后 Session 会被吊销，并要求重新执行 Interactive Authorization。

## Dynamic Registration Policy

Registration 接受 RFC 7591 风格的 Public-client Metadata，返回生成的 Client ID 和原样 Registered Redirect List，绝不返回 Client Secret。只有 Registered `grant_types` 包含 `refresh_token` 的 Authorization-code Client 才会获得 Refresh Token；其他 Client 的 Refresh Request 返回 `unauthorized_client`。支持的 Redirect 形式：

- `workbuddy://workbuddy/<非空路径>`，例如 `workbuddy://workbuddy/mcp/test/oauth/callback`
- `http://localhost:<port>/<非空路径>`
- `http://127.0.0.1:<port>/<非空路径>`
- `http://[::1]:<port>/<非空路径>`
- 显式注册的 HTTPS Redirect

Public HTTP Redirect、Malformed Private Scheme、Fragment、Wildcard Match、Prefix Match 和 Unregistered Redirect 均被拒绝。Loopback HTTP Redirect 必须包含显式 Port；每次 Authorization Request 都必须与已保存的 Redirect URI 精确匹配。Registration State 绑定到配置的 Issuer，并持久化在 Compose `/data` Volume。

## 单 Entra Application

只创建一个名为 `M365-MCP-Server` 的 App Registration。它同时作为 Protected Resource/OBO Middle Tier 与 Confidential Interactive OAuth Client：

    CLIENT_ID=<m365-mcp-server-client-id>
    CLIENT_SECRET=<m365-mcp-server-secret>

在该 App 上注册生产 Web Redirect URI：

    https://mcp.example.com/oauth/callback

本地开发另行注册 Loopback Web Redirect URI：

    http://localhost:8000/oauth/callback

MSAL 会让用户同时授权同一个 App 的 `api://<CLIENT_ID>/access_as_user` Scope 与显式 Graph Delegated Consent Scopes（默认 `User.Read`、`Mail.ReadWrite`、`Mail.Send`）。代码兑换 Authorization Code 时只请求 Token A 的 MCP Resource，因此 WorkBuddy 收到的仍是 MCP API Token，而不是 Graph Token；MCP API 接收 Token A 后继续通过现有 `.default` OBO 链路访问 Graph。不存在第二个 Entra App，也不存在第二套 Client Credential 配置。即使某项 Delegated Permission 默认不要求管理员，Tenant Policy 仍可能要求管理员批准。

## 自动测试与真实验收边界

GitHub Actions 会针对真实 ASGI/FastMCP Application 运行 Mock WorkBuddy E2E Test：解析 401 `resource_metadata` Challenge，发现两份 Metadata，动态注册 WorkBuddy Private Callback，通过 Mock Entra Callback 完成 S256 Authorization，兑换 Local Code，初始化 MCP，轮换 Refresh Token，再使用刷新后的 Access Token 列出 Tools。该测试不连接真实 Tenant，也不会修改邮箱。

生产启用 OAuth 或把 v0.1 标记为 Ready 之前，必须针对精确 Release Image 和 Connector Archive 执行并记录以下 Live Checks：

1. 在 WorkBuddy 4.24.0 或更高版本安装 Connector，确认不会出现 Token 填写表单。
2. 使用干净 WorkBuddy Profile 连接，确认 Browser Launch、Microsoft Login 与 Consent，并通过 `workbuddy://workbuddy/mcp/connector%3Asagehou-m365-mcp-server/oauth/callback` 返回 WorkBuddy。
3. 初始化 MCP，确认只列出 11 个 Tools；执行 Search、单封读取、Draft 创建、逐封
   确认后的 Draft 发送、一次受限自动化发送、一次被阻止的越界自动化尝试、附件
   提取、单次附件下载和对可丢弃消息的有意 Mutation，并确认 Move/Archive 后继续
   使用返回的新 ID。
4. 使用第二个用户重复测试，确认两个用户都不能访问对方邮箱内容。
5. 等待 Token A 到期（或使用批准的短期测试策略），确认 WorkBuddy 无需再次填写 Token 即可自动 Refresh 并重试原请求。
6. 保留 `OAUTH_DATABASE_PATH` 与 `OAUTH_ENCRYPTION_KEY` 后重启 Server，确认 WorkBuddy Session 仍可继续 Refresh。
7. 在 Allowlist 内第二个 Tenant 完成同一 Flow，并记录 Consent、Issuer、Audience 与 OBO 结果。只有部署明确支持 Consumer Account 时才单独测试该场景。
8. 确认 Application、Proxy 与 Platform Logs 不含 Authorization Code、Access/Refresh Token、MSAL Cache、Client Secret、Code Verifier、Message Body 或 Attachment Content。

这些 Live Checks 是 Manual Release Gates。Mock CI Flow 通过不能把它们标记为已完成。
