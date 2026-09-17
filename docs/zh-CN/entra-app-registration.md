[English](../entra-app-registration.md) | **简体中文**

# Microsoft Entra 应用注册操作手册

本文说明 M365 MCP Server 所需的 Microsoft Entra 配置。

内容与当前仓库实现保持一致：

- 自托管 MCP API
- 委托用户身份
- 通过 OAuth 2.0 On-Behalf-Of（OBO）访问 Microsoft Graph
- 只使用 Microsoft Graph Delegated Permissions
- 可选跨租户测试：应用注册在 Tenant A，邮箱用户位于 Tenant B

> MCP Server 是受保护的 Web API，不是交互式 Web Application。不要因为普通 OAuth Client 需要 Redirect URI，就给 MCP API Registration 随意添加 Redirect URI。Redirect URI 属于执行交互式登录的 Client Application。

## 1. 目标身份模型

```text
Interactive client / MCP client
        |
        | token A
        | aud = api://<MCP_API_CLIENT_ID>
        | scp = access_as_user
        | tid = target user tenant
        v
M365 MCP Server
        |
        | OBO using MCP API confidential credential
        | scope = https://graph.microsoft.com/.default
        v
Microsoft Entra ID (token A tenant)
        |
        | token B, delegated user identity
        v
Microsoft Graph
        |
        v
/me/messages
```

MCP Server 校验入站 Token、检查 Token Tenant Allowlist，然后根据入站 Token 的 `tid` Claim 向该租户执行 OBO。

## 2. 公有云前提

仓库默认配置面向 Microsoft Global Cloud：

```text
AUTHORITY_HOST=https://login.microsoftonline.com
GRAPH_BASE_URL=https://graph.microsoft.com/v1.0
```

不要把 Global Cloud App Registration 与世纪互联运营的 Microsoft 365 混用。National Cloud 使用不同的 Identity 和 Microsoft Graph Endpoint，必须单独验证。

## 3. 选择 Home Tenant

本项目跨租户测试场景：

- **Tenant A**：拥有 App Registration 的 Home Tenant
- **Tenant B**：包含测试邮箱用户的 Microsoft 365 Tenant

如果生产环境所有用户都属于同一个组织，直接在生产 Tenant 中注册并使用 Single-tenant Registration 更简单。

跨租户测试则使用 Multitenant Registration。

## 4. 在 Tenant A 创建 MCP API Application

1. 登录 Microsoft Entra Admin Center。
2. 切换到 **Tenant A**。
3. 打开 **Entra ID > App registrations > New registration**。
4. 使用清晰名称，例如：

   ```text
   M365-MCP-Server
   ```

5. 在 **Supported account types** 选择：

   ```text
   Accounts in any organizational directory
   (Any Microsoft Entra ID tenant - Multitenant)
   ```

6. **Redirect URI 保持为空**。
7. 点击 **Register**。

在 **Overview** 记录：

- Application (client) ID
- Tenant A 的 Directory (tenant) ID

其中 **Application (client) ID** 对应 MCP Server 的 `CLIENT_ID`。

## 5. 暴露 MCP API Scope

打开 `M365-MCP-Server` App Registration：

1. 进入 **Expose an API**。
2. 在 **Application ID URI** 旁点击 **Add**。
3. 接受默认值：

   ```text
   api://<MCP_API_CLIENT_ID>
   ```

4. 点击 **Add a scope**。
5. 建议配置：

   | Setting | Value |
   | --- | --- |
   | Scope name | `access_as_user` |
   | Who can consent | Admins and users；如果租户策略要求则改为 Admin-only |
   | Admin consent display name | Access M365 MCP Server as the signed-in user |
   | Admin consent description | Allows a client to call M365 MCP Server on behalf of the signed-in user. |
   | User consent display name | Access M365 MCP Server |
   | User consent description | Allows this client to use M365 MCP Server on your behalf. |
   | State | Enabled |

完整 Scope：

```text
api://<MCP_API_CLIENT_ID>/access_as_user
```

当前 Server 默认要求 `scp` Claim 包含 `access_as_user`，除非修改 `REQUIRED_SCOPES`。

## 6. 添加 Microsoft Graph Delegated Permissions

进入 **API permissions > Add a permission > Microsoft Graph > Delegated permissions**。

添加：

```text
User.Read
Mail.ReadWrite
```

不要添加 Application Mailbox Permissions。

尤其不要添加：

```text
Mail.Read (Application)
Mail.ReadWrite (Application)
Mail.Send (Application)
```

Delegated `Mail.ReadWrite` 只允许应用在当前登录用户的委托上下文中操作邮箱，并不包含发送邮件能力。

当前 MVP 不需要 `Mail.Send`。未来只有在项目正式实现并批准发信工具后，才增加 **Delegated** `Mail.Send`。

## 7. 创建 Confidential Client Credential

OBO Middle Tier 必须向 Microsoft Entra 证明自身身份。

仓库要求二选一：

- Client Secret
- Certificate / Private Key

### 7.1 测试环境：Client Secret

1. 打开 **Certificates & secrets**。
2. 选择 **Client secrets > New client secret**。
3. 测试环境建议使用较短有效期。
4. 创建 Secret。
5. 立即复制 **Value**。

使用 Secret 的 **Value**，不要使用 Secret ID。

配置：

```env
CLIENT_ID=<MCP_API_CLIENT_ID>
CLIENT_SECRET=<secret-value>
```

### 7.2 生产环境：Certificate

生产环境优先使用证书凭据。

当前 Server 期望：

```env
CLIENT_ID=<MCP_API_CLIENT_ID>
CLIENT_CERT_PATH=/run/secrets/m365-mcp-private-key.pem
CLIENT_CERT_THUMBPRINT=<certificate-thumbprint>
```

使用 Certificate Authentication 时不要同时设置 `CLIENT_SECRET`。

## 8. 跨租户测试：配置 Tenant B

Multitenant Application 必须在 Tenant B 中生成 Service Principal（Enterprise Application），并在 Tenant B 对下游 Microsoft Graph Delegated Permissions 完成 Consent。

### 推荐测试路径：Tenant-wide Admin Consent

使用 Tenant B 中具备权限的管理员访问：

```text
https://login.microsoftonline.com/<TENANT-B-ID>/adminconsent?client_id=<MCP_API_CLIENT_ID>
```

授权前仔细确认申请的 Delegated Permissions。

此操作会在 Tenant B 中创建 Enterprise Application，并根据管理员角色与 Tenant Policy，对 Multitenant App 当前配置的 API Permissions 执行 Tenant-wide Consent。

随后在 Tenant B 验证：

1. 打开 **Entra ID > Enterprise applications > All applications**。
2. 找到 `M365-MCP-Server`。
3. 进入 **Security > Permissions**。
4. 确认只出现预期 Microsoft Graph Delegated Permissions。

本项目预期：

```text
User.Read
Mail.ReadWrite
```

不要批准意外出现的 Application Permissions。

## 9. 为 Tenant B 配置 MCP Server

单目标 Tenant 测试：

```env
CLIENT_ID=<MCP_API_CLIENT_ID>
CLIENT_SECRET=<test-secret>
AUDIENCE=api://<MCP_API_CLIENT_ID>
ALLOWED_TENANTS=<TENANT-B-ID>
REQUIRED_SCOPES=access_as_user
GRAPH_SCOPES=https://graph.microsoft.com/.default
GRAPH_BASE_URL=https://graph.microsoft.com/v1.0
```

如果允许多个 Tenant，`ALLOWED_TENANTS` 使用逗号分隔列表。

App Registration 的 Home Tenant ID 不用于 Tenant B User 的 OBO Authority。Server 会读取并验证入站 Token 的 `tid`，然后对该 Tenant-specific Authority 执行 OBO。

## 10. Client Application 与 MCP API 是两个角色

上述 MCP API Registration 是 **Resource / Middle-tier API**，它自己不执行 Interactive Sign-in。

Client 必须先取得 Token A：

```text
api://<MCP_API_CLIENT_ID>/access_as_user
```

再以 Bearer Token 形式发送给 `/mcp/`。

当前仓库状态：

- Inbound Bearer Token Validation：已实现
- OBO to Microsoft Graph：已实现
- MCP OAuth Discovery / Dynamic Client Registration：未实现
- 由 MCP Server 自己负责 Interactive Sign-in：未实现

因此第一次真实租户验证应使用：

1. 可以配置为获取本 API Entra Access Token 的 MCP Client；或
2. 独立的测试 Client App Registration。

## 11. 可选：创建测试 Client App

如果暂时没有 MCP Client 可以正确获取 Token A，创建独立 Public Client Registration 做验证。

### 11.1 创建 Registration

在 Tenant A：

1. 打开 **App registrations > New registration**。
2. 名称：

   ```text
   M365-MCP-Test-Client
   ```

3. 跨租户测试选择：

   ```text
   Accounts in any organizational directory
   ```

4. 注册。
5. 记录 Application (client) ID 为 `TEST_CLIENT_ID`。

### 11.2 允许 Public Client Authentication

进入 **Authentication**，按照所选测试方式启用对应 Public-client Flow。

使用 Device Code Flow 测试时，启用 Public Client Flows。

不要把 MCP Server 的 Client Secret 放入这个 Test Client。

### 11.3 给 Test Client 授予 MCP API 权限

打开 `M365-MCP-Test-Client`：

1. 进入 **API permissions > Add a permission**。
2. 选择 **My APIs**。
3. 选择 `M365-MCP-Server`。
4. 选择 Delegated Permission：

   ```text
   access_as_user
   ```

也可以在 API Registration 的 **Expose an API > Authorized client applications** 中显式 Pre-authorize 已知 Test Client。

### 11.4 Token A 验收条件

发送给 MCP Server 的 Token 至少需要包含：

```text
aud = api://<MCP_API_CLIENT_ID>
# 某些 Entra Token 形式可能使用裸 Client ID；Server 会接受已配置 Audience/Client ID 形式。

scp includes access_as_user

tid = <TENANT-B-ID>

oid = 登录的 Tenant B 用户 Object ID
```

App-only Token 不适用于此架构。OBO 必须有 User Principal。

## 12. 第一次真实环境验证顺序

不要一开始就把全部 Tools 都测一遍，先验证 Identity Chain。

1. 使用 Tenant B 测试用户登录。
2. 获取 MCP API Scope 的 Token A。
3. 使用 Token A 调用 MCP Endpoint。
4. 确认 JWT Validation 成功。
5. 确认 OBO 能获取 Microsoft Graph Delegated Token。
6. 对当前登录用户邮箱执行 `mail_search` 或 `mail_get`。
7. 对已知测试邮件验证 Attachment Metadata / Read。
8. 测试 `mail_mark_read`。
9. 对可丢弃测试邮件执行 `mail_archive`。
10. 换第二个 Tenant B User 重复，并确认 Mailbox Isolation。

## 13. 预期安全边界

Server 绝不能接受以下 Mailbox Identity 参数：

```text
user_id=someone@example.com
mailbox=someone@example.com
```

Graph Layer 使用 `/me` 和 OBO Delegated Token。实际访问权限同时受以下两项约束：

- 应用被授予的 Delegated Permissions
- 当前登录用户本身拥有的权限

## 14. 常见问题

### AADSTS50011 - Redirect URI mismatch

原因：Interactive Client 使用了未在该 **Client Application** 中注册的 Redirect URI。

处理：把完全一致的 Redirect URI 添加到 Interactive Client App Registration。不要把任意 WorkBuddy Callback 填到 MCP API Registration，除非 MCP API 自己正在充当该 Interactive Client。

### AADSTS65001 / consent_required

原因：Client-to-MCP Scope 或 MCP-to-Graph Delegated Permissions 没有在目标 Tenant 完成 Consent。

检查：

- Test/Client App 是否拥有 `M365-MCP-Server` 的 `access_as_user`
- Tenant B 中是否存在 `M365-MCP-Server` Enterprise Application
- Tenant B 是否已 Consent `User.Read` 和 `Mail.ReadWrite`

### AADSTS70011 - invalid scope

同一个 OBO Request 中不要混合某个 Resource 的 `.default` 和单独 Delegated Scopes。

当前 MCP Server 请求：

```text
https://graph.microsoft.com/.default
```

实际 Graph Delegated Permissions 来自 App Registration 与 Consent Grants。

### 只有跨租户用户 OBO 失败

检查：

- App Registration 是否 Multitenant
- Tenant B 是否位于 `ALLOWED_TENANTS`
- 入站 Token 的 `tid` 是否 Tenant B
- Tenant B 中是否存在 Enterprise Application
- Tenant B 是否已 Consent Graph Delegated Permissions

OBO Authority 必须 Tenant-specific。OBO Token Exchange 不要使用 `/common` 或 `/organizations`。

### Graph 返回 403

先检查 Token 与 Consent，再修改 Graph Code。

常见原因：

- Graph Delegated Permission 未完成 Consent
- Token 是 App-only 而不是 Delegated
- 登录了错误用户/租户
- Exchange / Microsoft 365 Licensing 或 Mailbox Availability 不允许该操作

## 15. 生产加固清单

生产前：

- 优先 Certificate Credential，不使用长期 Client Secret
- Graph Delegated Permissions 只保留实际需要的最小集合
- 检查 Tenant B Enterprise Application Permissions
- 根据组织策略决定是否采用 Tenant-wide Consent
- 按组织策略应用 Conditional Access
- 明确限制 `ALLOWED_TENANTS`
- 禁止 Application Mailbox Permissions
- 至少使用两个用户验证 Identity Isolation
- 使用真实 Sign-in 行为验证支持的 MCP Clients
- 在 Credential 到期前完成轮换

## 16. Microsoft 官方参考

- Register an application with the Microsoft identity platform:
  https://learn.microsoft.com/en-us/graph/auth-register-app-v2
- Configure an application to expose a web API:
  https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-configure-app-expose-web-apis
- OAuth 2.0 On-Behalf-Of flow:
  https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-on-behalf-of-flow
- MSAL Python token acquisition / OBO:
  https://learn.microsoft.com/en-us/entra/msal/python/getting-started/acquiring-tokens
- Microsoft Graph permissions reference:
  https://learn.microsoft.com/en-us/graph/permissions-reference
- Grant tenant-wide admin consent:
  https://learn.microsoft.com/en-us/entra/identity/enterprise-apps/grant-admin-consent
