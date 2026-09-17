[English](../../codex/002-entra-auth-obo.md) | **简体中文**

# Task 002 - Entra 身份认证与 OBO

## 目标

实现 Microsoft Entra ID Authentication 与 Microsoft Graph On-Behalf-Of Flow。

## 要求

- 验证入站 JWT Access Tokens。
- 支持 Tenant Allowlist Validation。
- 实现 OBO Token Exchange。
- 获取 Microsoft Graph Delegated Tokens。
- 保留原始请求中的 User Identity。

## 安全要求

- 不实现 Application Permission Mailbox Access。
- MCP Tools 不接受任意 User ID。
- 验证 Tenant、Audience、Issuer、Scopes。

## 交付物

- Auth Middleware
- OBO Service
- Configuration Model
- Authentication Tests

## 非目标

- 不实现 Mail Tools。
- 不处理 Attachments。
