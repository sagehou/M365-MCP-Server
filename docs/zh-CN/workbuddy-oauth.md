[English](../workbuddy-oauth.md) | **简体中文**

# WorkBuddy OAuth

## 当前阶段

Server 当前实现 Discovery、Registration 与 Interactive Authorization-code Flow：

- `GET /.well-known/oauth-protected-resource`
- 未认证 `/mcp/` Bearer Challenge 中的 `resource_metadata` Link
- `GET /.well-known/oauth-authorization-server`
- 面向无 Client Secret Public Client 的 `POST /oauth/register`
- 使用 Exact Client/Redirect/Resource Binding 与 S256 PKCE 的 `GET /oauth/authorize`
- 由 MSAL Python 驱动、使用独立 Upstream State 的 `GET /oauth/callback/entra`
- TTL 不超过 10 分钟、只能使用一次的 Local Authorization Code
- 支持 `grant_type=authorization_code` 与 `refresh_token` 的 `POST /oauth/token`
- 仅以 SHA-256 Hash 保存的 Opaque Local Refresh Token
- 带 One-time Rotation 与 Replay Rejection 的 Encrypted Persistent MSAL Cache
- 存储在配置 SQLite Database 中的 Restart-safe Session
- 由 `OAUTH_DATABASE_PATH` 指定、带 Issuer Binding 的 SQLite Persistence

Token Endpoint 返回发给 App A、并已通过现有 `JwtValidator` 复验的 Entra Access Token，因此现有 JWT Validation 与 OBO 链路仍是权威安全边界，不会另外签发 MCP JWT。Entra Authorization-flow Object、Token A 与 MSAL Cache 使用 `OAUTH_ENCRYPTION_KEY` 执行 AES-256-GCM 加密；敏感 Token Material 不会进入 Browser Redirect 或 SQLite Plaintext Column。

在真实 WorkBuddy Acceptance Gate 完成前，受控集成开发以外应保持 `OAUTH_ENABLED=false`。Restarted 或 Replacement Process 必须使用同一 SQLite Database 与 Encryption Key。Distributed 或 Multi-host Session Storage 不属于 v0.1 Scope。

## Authorization Flow

1. WorkBuddy 通过 DCR 注册 Exact Redirect URI。
2. `/oauth/authorize` 校验 Client、Redirect、Scope、Resource、Response Type 与 S256 Challenge。
3. Server 保存 WorkBuddy State，并生成不同的 Cryptographically Random Entra State，再启动 MSAL Authorization。
4. `/oauth/callback/entra` 原子消费 Transaction，由 MSAL 兑换 Microsoft Code，再通过现有 `JwtValidator` 复验 Token A。
5. Browser 只会把 `code=<local-code>&state=<original-state>` 发送到 Exact Registered Redirect。
6. `/oauth/token` 在 Exact Client、Redirect 与 PKCE 校验通过后原子兑换 Local Code，返回 Token A 与 Random Local Refresh Token；第二次兑换返回 `invalid_grant`。

## Refresh Flow

1. WorkBuddy 发送 `grant_type=refresh_token`、Public `client_id` 与当前 Opaque Local Refresh Token。
2. Server 对 Handle 做 Hash，并查找绑定到 Configured Issuer 和 Client、尚未过期且未吊销的 Session。
3. 打开 Encrypted MSAL Cache，强制执行 MSAL Silent Token Acquisition；结果 Token A 再次通过 Validator，并且必须与原 Session 的 Tenant/User 一致。
4. SQLite 使用 Compare-and-swap 把旧 Handle Hash 与 Encrypted Cache 替换为新值；只有匹配预期旧 Hash 的请求能够完成轮换。
5. WorkBuddy 获得 Token A 与新的 Opaque Refresh Token；旧值 Replay 返回 `invalid_grant`。

Microsoft Revocation、Unusable Cache 或 Identity Mismatch 会吊销 Local Session。Transient Upstream Outage 返回 `temporarily_unavailable`，不会消费当前 Local Refresh Token。

## Public URL 配置

显式配置外部可达 URL：

    MCP_PUBLIC_URL=https://mcp.example.com/mcp/
    OAUTH_ISSUER_URL=https://mcp.example.com
    OAUTH_DATABASE_PATH=/data/oauth.db
    OAUTH_ENCRYPTION_KEY=<32-random-bytes-base64>
    OAUTH_REFRESH_TOKEN_TTL_DAYS=30

Public URL 必须与 Reverse-proxy Route 精确一致。应用不会从 Request Header 推导这些值。生产值必须使用 HTTPS；HTTP 仅允许 Loopback 开发。Encryption Key 必须留在 Database、Image、Repository 与 Log 之外；丢失 Key 会使已保存 Session 失效。

## Dynamic Registration Policy

Registration 接受 RFC 7591 风格的 Public-client Metadata，返回生成的 Client ID 和原样 Registered Redirect List，绝不返回 Client Secret。支持的 Redirect 形式：

- `workbuddy://workbuddy/mcp/connector%3A<source>/oauth/callback`
- `http://localhost:<port>/oauth/callback`
- `http://127.0.0.1:<port>/oauth/callback`
- `http://[::1]:<port>/oauth/callback`
- 显式注册的 HTTPS Redirect

Public HTTP Redirect、Malformed Private Scheme、Fragment、Wildcard Match、Prefix Match 和 Unregistered Redirect 均被拒绝。Registration State 绑定到配置的 Issuer，并持久化在 Compose `/data` Volume。

## Entra Application 隔离

现有 App A 继续作为 Protected Resource/OBO Application。App B 是独立的 Confidential Interactive OAuth Broker：

    ENTRA_BROKER_CLIENT_ID=<app-b-client-id>
    ENTRA_BROKER_CLIENT_SECRET=<app-b-secret>
    ENTRA_BROKER_AUTHORITY=https://login.microsoftonline.com/organizations

只在 App B 注册以下 Redirect URI：

    https://mcp.example.com/oauth/callback/entra

App B 请求 App A 的 `api://<CLIENT_ID>/access_as_user` Scope；MSAL 会按需要加入其 Reserved OpenID Scopes。Broker 不直接请求 Graph Token；MCP API 接收 Token A 后仍通过现有 OBO 链路访问 Graph。不要复用 App A 的 Client Credential，也不要把 Broker Callback 配到 App A。
