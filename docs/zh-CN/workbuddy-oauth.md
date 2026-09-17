[English](../workbuddy-oauth.md) | **简体中文**

# WorkBuddy OAuth

## 当前阶段

Server 当前实现 Discovery 与 Registration 基础：

- `GET /.well-known/oauth-protected-resource`
- 未认证 `/mcp/` Bearer Challenge 中的 `resource_metadata` Link
- `GET /.well-known/oauth-authorization-server`
- 面向无 Client Secret Public Client 的 `POST /oauth/register`
- 由 `OAUTH_DATABASE_PATH` 指定、带 Issuer Binding 的 SQLite Persistence

本阶段尚未实现 `/oauth/authorize`、`/oauth/token`、Microsoft Interactive Login、Local Authorization Code 或 Refresh Session。在受控集成开发以外应保持 `OAUTH_ENABLED=false`。

## Public URL 配置

显式配置外部可达 URL：

    MCP_PUBLIC_URL=https://mcp.example.com/mcp/
    OAUTH_ISSUER_URL=https://mcp.example.com

它们必须与 Reverse-proxy Route 精确一致。应用不会从 Request Header 推导这些值。生产值必须使用 HTTPS；HTTP 仅允许 Loopback 开发。

## Dynamic Registration Policy

Registration 接受 RFC 7591 风格的 Public-client Metadata，返回生成的 Client ID 和原样 Registered Redirect List，绝不返回 Client Secret。支持的 Redirect 形式：

- `workbuddy://workbuddy/mcp/connector%3A<source>/oauth/callback`
- `http://localhost:<port>/oauth/callback`
- `http://127.0.0.1:<port>/oauth/callback`
- `http://[::1]:<port>/oauth/callback`
- 显式注册的 HTTPS Redirect

Public HTTP Redirect、Malformed Private Scheme、Fragment、Wildcard Match、Prefix Match 和 Unregistered Redirect 均被拒绝。Registration State 绑定到配置的 Issuer，并持久化在 Compose `/data` Volume。

## Entra Application 隔离

现有 App A 继续作为 Protected Resource/OBO Application。后续阶段新增 App B，作为 Confidential Interactive OAuth Broker。不要复用 App A 的 Client Credential，也不要把 Broker Callback 配到 App A。
