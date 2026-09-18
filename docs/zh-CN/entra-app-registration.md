[English](../entra-app-registration.md) | **简体中文**

# Microsoft Entra 应用注册操作手册

## 快速入口

- **Microsoft Entra 管理中心：** https://entra.microsoft.com/
- **Azure Portal - Microsoft Entra 概览：** https://portal.azure.com/?quickstart=true#view/Microsoft_AAD_IAM/ActiveDirectoryMenuBlade/~/Overview
- **注册应用官方文档：** https://learn.microsoft.com/zh-cn/graph/auth-register-app-v2
- **暴露 Web API / 添加 `access_as_user`：** https://learn.microsoft.com/zh-cn/entra/identity-platform/quickstart-configure-app-expose-web-apis
- **OAuth 2.0 On-Behalf-Of 流程：** https://learn.microsoft.com/zh-cn/entra/identity-platform/v2-oauth2-on-behalf-of-flow
- **Microsoft Graph 权限参考：** https://learn.microsoft.com/zh-cn/graph/permissions-reference
- **Access Token Claims 参考：** https://learn.microsoft.com/zh-cn/entra/identity-platform/access-token-claims-reference
- **授予租户范围管理员同意：** https://learn.microsoft.com/zh-cn/entra/identity/enterprise-apps/grant-admin-consent

下面的操作默认使用 **Microsoft Entra 管理中心**。创建任何对象之前，先切换到目标 Directory / Tenant，并确认 Portal 顶部显示的租户名称正确。

本文说明 M365 MCP Server 所需的 Microsoft Entra 配置。

内容与当前仓库实现保持一致：

- 自托管 MCP API
- 委托用户身份
- 通过 OAuth 2.0 On-Behalf-Of（OBO）访问 Microsoft Graph
- 只使用 Microsoft Graph Delegated Permissions
- 可选跨租户：App Registration 位于 Tenant A，邮箱用户位于其他 Microsoft Entra Tenant
- App Registration 明确支持时，可选支持 Personal Microsoft Accounts

> v0.1 明确使用一个紧耦合 App Registration 同时承担两个角色：Protected MCP API 与 Confidential Interactive OAuth Client。必须在同一个 Registration 上添加 Server Callback 作为 Web Redirect URI；不要为 WorkBuddy Flow 创建第二个 Entra App。

## 1. 目标身份模型

```text
Interactive client / MCP client
        |
        | token A
        | aud = <MCP_API_CLIENT_ID> 或已配置 API Audience
        | scp = access_as_user
        | tid = 当前登录用户所在 Tenant
        v
M365 MCP Server
        |
        | OBO using MCP API confidential credential
        | scope = https://graph.microsoft.com/.default
        v
Microsoft identity platform
        |
        | token B, delegated user identity
        v
Microsoft Graph
        |
        v
/me/messages
```

MCP Server 校验入站 Token，然后根据已验证的 `tid` Claim 对对应 Tenant 执行 OBO。`ALLOWED_TENANTS` 可以限制为指定 Tenant，也可以设置为 `*` 接受任意有效 Microsoft Tenant。

## 2. 公有云前提

仓库默认配置面向 Microsoft Global Cloud：

```text
AUTHORITY_HOST=https://login.microsoftonline.com
GRAPH_BASE_URL=https://graph.microsoft.com/v1.0
```

不要把 Global Cloud App Registration 与世纪互联运营的 Microsoft 365 混用。National Cloud 使用不同的 Identity 和 Microsoft Graph Endpoint，必须单独验证。

## 3. 选择账户范围

根据实际要允许登录的用户选择 App Registration 的 Supported account types：

- **Accounts in this organizational directory only**：只允许一个 Microsoft Entra Tenant。
- **Accounts in any organizational directory**：允许任意 Microsoft Entra Tenant 中的工作/学校账号。
- **Accounts in any organizational directory and personal Microsoft accounts**：除工作/学校账号外，也允许 Outlook.com、Hotmail、Live 等个人 Microsoft 账户。

如果仅供一个组织内部使用，Single-tenant 最简单。

如果要让多个组织使用，选择 Multitenant。若还要支持个人 Outlook.com 类账户，必须选择明确包含 Personal Microsoft Accounts 的账户类型。

## 4. 创建唯一的 MCP Application

1. 打开 https://entra.microsoft.com/ 并登录 Microsoft Entra Admin Center。
2. 切换到用于拥有 App Registration 的 Tenant。
3. 打开 **Entra ID > App registrations > New registration**。
4. 使用清晰名称，例如：

   ```text
   M365-MCP-Server
   ```

5. 在 **Supported account types** 按上一节确定的范围选择。仅支持组织账户的跨租户场景选择：

   ```text
   Accounts in any organizational directory
   (Any Microsoft Entra ID tenant - Multitenant)
   ```

   如果还要支持个人 Microsoft 账户，则选择：

   ```text
   Accounts in any organizational directory
   and personal Microsoft accounts
   ```

6. 在 **Redirect URI** 中选择 **Web**，并填写当前环境的 Callback：

   ```text
   https://mcp.example.com/oauth/callback
   ```

   本地 Loopback 开发使用 `http://localhost:8000/oauth/callback`。如果两个环境都需要，在注册完成后到 **Authentication > Web** 中分别添加两个精确值。
7. 点击 **Register**。

在 **Overview** 记录：

- Application (client) ID
- Home Tenant 的 Directory (tenant) ID

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

Delegated `Mail.ReadWrite` 只允许应用在当前登录用户的委托上下文中操作邮箱，并不包含发送邮件能力。

Microsoft Graph 当前明确支持个人 Microsoft 账户对 Delegated `Mail.ReadWrite` 进行 Consent，因此个人 Outlook.com 类邮箱本身并不是这里的阻碍。Shared Mailbox 相关 Delegated Permission 是另一类能力，不属于当前 MVP。

当前 MVP 不需要 `Mail.Send`。未来只有在项目正式实现并批准发信工具后，才增加 **Delegated** `Mail.Send`。

## 7. 创建 Confidential Client Credential

同一个 Application 必须在 Interactive Authorization-code Exchange 与 OBO Middle-tier Exchange 中向 Microsoft Entra 证明自身身份。

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

## 8. 组织租户的跨租户 Consent

对于另一个 Microsoft Entra Tenant 中的组织用户，Multitenant Application 需要在目标 Tenant 中生成 Service Principal（Enterprise Application），并在该 Tenant 对下游 Microsoft Graph Delegated Permissions 完成 Consent。

### 推荐企业测试路径：Tenant-wide Admin Consent

使用目标 Tenant 中具备权限的管理员访问：

```text
https://login.microsoftonline.com/<TARGET-TENANT-ID>/adminconsent?client_id=<MCP_API_CLIENT_ID>
```

授权前仔细确认申请的 Delegated Permissions。

此操作会在目标 Tenant 中创建 Enterprise Application，并根据管理员角色与 Tenant Policy，对 Multitenant App 当前配置的 API Permissions 执行 Tenant-wide Consent。

随后在目标 Tenant 验证：

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

个人 Microsoft 账户没有客户组织中的 Enterprise Application / Tenant Admin Consent 这一套组织级流程。它们是否可以登录，首先由 App Registration 的 Supported account types 决定，Delegated Permissions 则走个人账户自己的 Consent 流程。

## 9. 配置 MCP Server 的 Tenant Admission

### 显式 Tenant Allowlist

仅允许一个目标组织 Tenant：

```env
CLIENT_ID=<MCP_API_CLIENT_ID>
CLIENT_SECRET=<test-secret>
AUDIENCE=
ALLOWED_TENANTS=<TARGET-TENANT-ID>
REQUIRED_SCOPES=access_as_user
GRAPH_SCOPES=https://graph.microsoft.com/.default
GRAPH_BASE_URL=https://graph.microsoft.com/v1.0
```

允许多个指定 Tenant：

```env
ALLOWED_TENANTS=<TENANT-ID-1>,<TENANT-ID-2>
```

### 接受任意 Microsoft Tenant

如果部署本身就是明确对所有 Tenant 开放的 Multitenant 服务：

```env
ALLOWED_TENANTS=*
```

`*` 表示接受任何能通过正常 Signature、Issuer、Audience、Expiry 和 Delegated Scope 校验的 Microsoft Tenant。如果 App Registration 的 Supported account types 允许 Personal Microsoft Accounts，该语义也包含个人 Microsoft 账户使用的 Microsoft Consumer Tenant。

Microsoft Consumer Tenant ID 固定为：

```text
9188040d-6c67-4c5b-b112-36a304b66dad
```

如果 App Registration 只允许组织账户，那么个人账户根本无法为本 API 获取有效 Token，因此 `ALLOWED_TENANTS=*` 不会绕过 Entra 的账户类型限制。

`*` 不允许与具体 Tenant ID 混写。`ALLOWED_TENANTS` 留空仍然是无效配置，并按 fail closed 处理。

`AUDIENCE` 通常可以留空。留空后 Server 会自动接受已配置的 `CLIENT_ID` 和 `api://<CLIENT_ID>` 两种 Audience 形式。只有明确需要覆盖默认行为时才填写 `AUDIENCE`。

App Registration 的 Home Tenant ID 不用于其他 Tenant User 的 OBO Authority。Server 会读取并验证入站 Token 的 `tid`，然后对该 Tenant-specific Authority 执行 OBO。

## 10. 一个 App Registration，两个角色

`M365-MCP-Server` Registration 同时作为 Resource/OBO Middle-tier API 与 Confidential Interactive OAuth Client。它请求自己暴露的 Scope：

Client 必须先取得 Token A：

```text
api://<MCP_API_CLIENT_ID>/access_as_user
```

MSAL 为该 Scope 获取 Token A，WorkBuddy 再把 Token A 作为 Bearer Token 发送给 `/mcp/`。Server 在执行 Graph OBO 前验证 Token A。

当前仓库状态：

- Inbound Bearer Token Validation：已实现
- OBO to Microsoft Graph：已实现
- MCP OAuth Discovery / Dynamic Client Registration：已在 `OAUTH_ENABLED` 后实现
- MSAL Interactive Sign-in、S256 PKCE 与 Local Authorization-code Exchange：已在 `OAUTH_ENABLED` 后实现
- Persistent Encrypted Local Refresh Session 与 Rotation：已在 `OAUTH_ENABLED` 后实现
- 真实 WorkBuddy 验收：尚未完成

### 10.1 核对 Web Authentication 配置

1. 打开现有 `M365-MCP-Server` Registration。
2. 在 **Authentication > Web** 中注册精确的生产 Callback：

   ```text
   https://mcp.example.com/oauth/callback
   ```

3. 只有需要本地 Loopback 测试时，才另加 `http://localhost:8000/oauth/callback` Web Redirect URI。
4. 确认 **Expose an API** 包含 `api://<MCP_API_CLIENT_ID>/access_as_user`。
5. 确认 **API permissions** 只包含必需的 Microsoft Graph Delegated Permissions（`User.Read` 和 `Mail.ReadWrite`），不存在 Mailbox Application Permission。
6. 配置唯一 Registration 和唯一 Credential：

   ```env
   CLIENT_ID=<MCP_API_CLIENT_ID>
   CLIENT_SECRET=<secret-value>
   MCP_PUBLIC_URL=https://mcp.example.com/mcp/
   OAUTH_ISSUER_URL=https://mcp.example.com
   OAUTH_ENABLED=true
   OAUTH_DATABASE_PATH=/data/oauth.db
   OAUTH_ENCRYPTION_KEY=<32-random-bytes-base64>
   ```

MSAL 会自动管理 Reserved OpenID Scopes。返回的 Token A 仍必须通过现有 JWT Validator 复验。系统不再使用第二个 App Registration、Client ID、Secret 或 Authority Setting。

### 10.2 Token A 验收条件

发送给 MCP Server 的 Token A 至少需要包含：

```text
aud = <MCP_API_CLIENT_ID> 或其他已配置接受的 Audience
scp includes access_as_user
tid = 当前登录用户的 Tenant ID
oid/sub = 当前登录用户 Identity
```

对于个人 Microsoft 账户，`tid` 就是上面给出的 Microsoft Consumer Tenant ID。App-only Token 不适用于此架构，因为 OBO 必须有 User Principal。

## 11. 第一次真实环境验证顺序

不要一开始就把全部 Tools 都测一遍，先验证 Identity Chain。

1. 使用测试用户登录。
2. 获取 MCP API Scope 的 Token A。
3. 使用 Token A 调用 MCP Endpoint。
4. 确认 JWT Validation 成功。
5. 确认 OBO 能获取 Microsoft Graph Delegated Token。
6. 对当前登录用户邮箱执行 `mail_search` 或 `mail_get`。
7. 对已知测试邮件验证 Attachment Metadata / Read。
8. 测试 `mail_mark_read`。
9. 对可丢弃测试邮件执行 `mail_archive`。
10. 换第二个用户重复，并确认 Mailbox Isolation。

如果启用了 Personal Microsoft Accounts，正式声称支持该账户类型之前，应额外用一个 Outlook.com / Hotmail 类账户完成独立验证。

## 12. 预期安全边界

Server 绝不能接受以下 Mailbox Identity 参数：

```text
user_id=someone@example.com
mailbox=someone@example.com
```

Graph Layer 使用 `/me` 和 OBO Delegated Token。实际访问权限同时受以下两项约束：

- 应用被授予的 Delegated Permissions
- 当前登录用户本身拥有的权限

`ALLOWED_TENANTS=*` 只改变哪些已经通过验证的 Microsoft Tenant 可以访问 API，不会改变每个用户的 `/me` 安全边界。

## 13. 常见问题

### AADSTS50011 - Redirect URI mismatch

原因：MCP Server 使用了未在 `M365-MCP-Server` Application 中注册的 Redirect URI。

处理：在 **Authentication > Web** 中添加精确的 Server Callback（`https://<your-host>/oauth/callback` 或文档规定的 localhost 值）。WorkBuddy Private Callback 由 WorkBuddy 向 MCP Server 动态注册，不应填入 Entra。

### AADSTS65001 / consent_required

原因：单 App 自请求的 MCP Scope 或 MCP-to-Graph Delegated Permissions 没有在目标 Identity Context 中完成 Consent。

组织 Tenant 场景检查：

- **Expose an API** 中的 `access_as_user` 是否已启用
- 目标 Tenant 中是否存在 `M365-MCP-Server` Enterprise Application
- 目标 Tenant 是否已 Consent `User.Read` 和 `Mail.ReadWrite`

### AADSTS70011 - invalid scope

同一个 OBO Request 中不要混合某个 Resource 的 `.default` 和单独 Delegated Scopes。

当前 MCP Server 请求：

```text
https://graph.microsoft.com/.default
```

实际 Graph Delegated Permissions 来自 App Registration 与 Consent Grants。

### 组织账户正常，但个人账户无法登录

确认唯一的 `M365-MCP-Server` Registration 的 Supported account types 明确包含 Personal Microsoft Accounts。`ALLOWED_TENANTS=*` 无法扩大 Entra 中已经配置的账户类型范围。

### 只有外部组织 Tenant 的 OBO 失败

检查：

- App Registration 是否 Multitenant
- 目标 Tenant 是否显式位于 `ALLOWED_TENANTS`，或是否使用 `ALLOWED_TENANTS=*`
- 入站 Token 的 `tid` 是否目标 Tenant
- 目标 Tenant 中是否存在 Enterprise Application
- 目标 Tenant 是否已 Consent Graph Delegated Permissions

OBO Authority 根据已经验证的 Token Tenant 动态确定。

### Graph 返回 403

先检查 Token 与 Consent，再修改 Graph Code。

常见原因：

- Graph Delegated Permission 未完成 Consent
- Token 是 App-only 而不是 Delegated
- 登录了错误用户/租户
- Exchange / Microsoft 365 Mailbox Availability 不允许该操作

## 14. 生产加固清单

生产前：

- 优先 Certificate Credential，不使用长期 Client Secret
- Graph Delegated Permissions 只保留实际需要的最小集合
- 只有部署明确要对所有受支持 Microsoft Tenant 开放时才使用 `ALLOWED_TENANTS=*`；否则使用显式 Tenant ID
- 对组织 Tenant 检查 Enterprise Application Permissions
- 根据每个组织策略决定是否采用 Tenant-wide Consent
- 按组织策略应用 Conditional Access
- 禁止 Application Mailbox Permissions
- 至少使用两个用户验证 Identity Isolation
- 如果支持 Personal Microsoft Accounts，单独验证该登录路径
- 使用真实 Sign-in 行为验证支持的 MCP Clients
- 在 Credential 到期前完成轮换
- 把单一 Credential 作为共享 Trust Boundary 保护：泄露会同时影响 Interactive Code Exchange 与 Graph OBO

## 15. Microsoft 官方参考

- Register an application with the Microsoft identity platform:
  https://learn.microsoft.com/en-us/graph/auth-register-app-v2
- Configure an application to expose a web API:
  https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-configure-app-expose-web-apis
- OAuth 2.0 On-Behalf-Of flow:
  https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-on-behalf-of-flow
- Microsoft Graph permissions reference:
  https://learn.microsoft.com/en-us/graph/permissions-reference
- Access-token claims reference:
  https://learn.microsoft.com/en-us/entra/identity-platform/access-token-claims-reference
- MSAL Python token acquisition / OBO:
  https://learn.microsoft.com/en-us/entra/msal/python/getting-started/acquiring-tokens
- Grant tenant-wide admin consent:
  https://learn.microsoft.com/en-us/entra/identity/enterprise-apps/grant-admin-consent
