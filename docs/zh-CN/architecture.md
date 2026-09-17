[English](../architecture.md) | **简体中文**

# 架构

## 概述

M365 MCP Server 是一个面向 Microsoft 365 的自托管 MCP 网关。

目标：

- 企业多用户支持
- Microsoft Entra ID 身份认证
- 委托权限
- 兼容 OAuth 2.0 / OAuth 2.1 的集成方式
- Microsoft Graph OBO 流程

## 请求流程

```text
MCP Client
    |
    | User token
    v
M365 MCP Server
    |
    | Validate token
    |
    | OBO exchange
    v
Microsoft Graph
    |
    v
User mailbox
```

## 安全原则

- 邮箱访问绝不使用 Graph Application permissions
- 工具不接受任意 mailbox/user 标识
- 除非明确实现共享邮箱，否则始终使用 `/me`
- 从 Token Claims 校验租户和用户身份

## 集成边界

Graph Client 接收经过验证的 `AuthContext`，通过 Entra OBO 服务取得 Microsoft Graph 委托 Token，并且只允许访问 `/me` 下的相对路径。它负责处理 Graph 限流和瞬时故障，然后向 Service 层返回经过清理的响应或错误。

Mail Service 位于 8 个已注册 MCP 邮件工具之后，作为内部业务层。HTTP Transport 是无状态的：每次调用都携带并重新验证自己的 Token，不在 MCP Session 中保存调用者身份。MSAL 在 ASGI Event Loop 之外执行。附件解析运行在短生命周期、带资源限制的 Linux Worker 中。Graph Transport、邮箱策略和 HTTP 集成分别有独立测试。

## OAuth Authorization Broker

OAuth 是现有 Resource Server 前方的独立 Deep Module。它的 Interface 提供 Discovery、Public-client Registration 与 Authorization-code Operation，同时隐藏 Redirect Policy、State Binding、PKCE、MSAL 与 SQLite 细节。`DynamicClientRegistry` 负责 Redirect Validation 和 Issuer Binding；`OAuthAuthorizationService` 负责 Interactive Flow；Route 只是 HTTP Adapter，不了解 SQLite Schema。

`SQLiteOAuthStore` 是内部 Store Seam 的 Persistence Adapter。它持久化 Registered Client，原子消费 Entra Transaction 与 Local Authorization Code，并使用 Compare-and-swap 原子轮换带 Issuer Binding 的 Refresh Session。`MsalEntraAuthorizationBroker` 是 App B 的 True-external Adapter；创建 Local Code 之前，现有 `JwtValidator` 会再次验证发给 App A 的 Token A。`OAuthSessionService` 通过小型 Interface 封装 Opaque-token Hash、Encrypted MSAL Cache Persistence、Silent Refresh、Identity Rebinding Check、Revocation 与 One-time Rotation。Authorization-flow Object、Token A 与 MSAL Cache 使用配置的 Restart-stable Key 执行 AES-256-GCM 加密。

Public Resource 和 Issuer URL 只能来自 `MCP_PUBLIC_URL` 与 `OAUTH_ISSUER_URL`；Request Host 和 Forwarded-host Header 不能定义这些安全 Metadata。在真实 WorkBuddy 验收完成前，该模块仍默认关闭。
