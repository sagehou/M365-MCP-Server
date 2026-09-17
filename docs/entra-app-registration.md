**English** | [简体中文](zh-CN/entra-app-registration.md)

# Microsoft Entra App Registration Guide

## Quick links

- **Microsoft Entra admin center:** https://entra.microsoft.com/
- **Azure portal - Microsoft Entra overview:** https://portal.azure.com/?quickstart=true#view/Microsoft_AAD_IAM/ActiveDirectoryMenuBlade/~/Overview
- **Register an application:** https://learn.microsoft.com/en-us/graph/auth-register-app-v2
- **Expose a web API / add `access_as_user`:** https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-configure-app-expose-web-apis
- **OAuth 2.0 On-Behalf-Of flow:** https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-on-behalf-of-flow
- **Microsoft Graph permissions reference:** https://learn.microsoft.com/en-us/graph/permissions-reference
- **Access-token claims reference:** https://learn.microsoft.com/en-us/entra/identity-platform/access-token-claims-reference
- **Grant tenant-wide admin consent:** https://learn.microsoft.com/en-us/entra/identity/enterprise-apps/grant-admin-consent

For the steps below, use the **Microsoft Entra admin center** unless a step explicitly points elsewhere. Before creating anything, switch to the intended directory/tenant and confirm the tenant name shown in the portal.

This guide describes the Microsoft Entra configuration required by M365 MCP Server.

It is written for the current implementation in this repository:

- self-hosted MCP API
- delegated user identity
- OAuth 2.0 On-Behalf-Of (OBO) to Microsoft Graph
- Microsoft Graph delegated permissions only
- optional cross-tenant use where the app is registered in Tenant A and mailbox users are in other Microsoft Entra tenants
- optional personal Microsoft accounts when the App Registration explicitly supports them

> The MCP server is a protected web API, not an interactive web application. Do not add a redirect URI to the MCP API registration just because an OAuth client normally has one. Redirect URIs belong to the interactive client application.

## 1. Target identity model

```text
Interactive client / MCP client
        |
        | token A
        | aud = <MCP_API_CLIENT_ID> or configured API audience
        | scp = access_as_user
        | tid = signed-in user's tenant
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

The MCP server validates the inbound token and performs OBO against the tenant identified by the validated `tid` claim. `ALLOWED_TENANTS` can restrict this to specific tenants or use `*` to accept any valid Microsoft tenant.

## 2. Public-cloud assumption

The default repository settings target the global Microsoft cloud:

```text
AUTHORITY_HOST=https://login.microsoftonline.com
GRAPH_BASE_URL=https://graph.microsoft.com/v1.0
```

Do not mix global-cloud registrations with Microsoft 365 operated by 21Vianet. National clouds use different identity and Microsoft Graph endpoints and require separate validation before use.

## 3. Choose the account reach

Choose the App Registration account type based on who should be able to sign in:

- **Accounts in this organizational directory only**: one Microsoft Entra tenant.
- **Accounts in any organizational directory**: any work or school account from a Microsoft Entra tenant.
- **Accounts in any organizational directory and personal Microsoft accounts**: work/school accounts plus Outlook.com, Hotmail, Live and other personal Microsoft accounts.

For an internal deployment where all users belong to one organization, single-tenant is the simplest option.

For a service intended for multiple organizations, use a multitenant registration. If personal Outlook.com-style accounts are also required, select the account type that explicitly includes personal Microsoft accounts.

## 4. Create the MCP API application

1. Open https://entra.microsoft.com/ and sign in to the Microsoft Entra admin center.
2. Switch to the tenant that will own the App Registration.
3. Go to **Entra ID > App registrations > New registration**.
4. Use a clear name, for example:

   ```text
   M365-MCP-Server
   ```

5. Under **Supported account types**, select the account reach chosen in the previous section. For organization-only multitenant use:

   ```text
   Accounts in any organizational directory
   (Any Microsoft Entra ID tenant - Multitenant)
   ```

   To also support personal Microsoft accounts, select:

   ```text
   Accounts in any organizational directory
   and personal Microsoft accounts
   ```

6. Leave **Redirect URI** empty for the MCP API registration.
7. Select **Register**.

Record the following values from **Overview**:

- Application (client) ID
- Directory (tenant) ID of the home tenant

The **Application (client) ID** becomes `CLIENT_ID` for the MCP server.

## 5. Expose the MCP API scope

Open the `M365-MCP-Server` app registration.

1. Go to **Expose an API**.
2. Select **Add** next to **Application ID URI**.
3. Accept the default value:

   ```text
   api://<MCP_API_CLIENT_ID>
   ```

4. Select **Add a scope**.
5. Configure:

   | Setting | Value |
   | --- | --- |
   | Scope name | `access_as_user` |
   | Who can consent | Admins and users, unless tenant policy requires admin-only |
   | Admin consent display name | Access M365 MCP Server as the signed-in user |
   | Admin consent description | Allows a client to call M365 MCP Server on behalf of the signed-in user. |
   | User consent display name | Access M365 MCP Server |
   | User consent description | Allows this client to use M365 MCP Server on your behalf. |
   | State | Enabled |

The full scope becomes:

```text
api://<MCP_API_CLIENT_ID>/access_as_user
```

The current server expects the `scp` claim to contain `access_as_user` unless `REQUIRED_SCOPES` is changed.

## 6. Add Microsoft Graph delegated permissions

Open **API permissions > Add a permission > Microsoft Graph > Delegated permissions**.

Add:

```text
User.Read
Mail.ReadWrite
```

Do **not** add application mailbox permissions.

In particular, do not add application-permission variants for mailbox access. `Mail.ReadWrite` delegated permission acts only in the signed-in user's delegated context and does not include mail sending.

Microsoft Graph currently supports the delegated `Mail.ReadWrite` permission for both work/school accounts and personal Microsoft accounts. Shared-mailbox-specific delegated permissions are a separate capability and are not part of the current MVP.

`Mail.Send` is deliberately not required by the current MVP. Add the **delegated** `Mail.Send` permission only if the project later implements an approved send-mail tool.

## 7. Create the confidential client credential

The OBO middle tier must authenticate itself to Microsoft Entra.

The repository supports exactly one of:

- client secret
- certificate/private key

### 7.1 Test environment: client secret

1. Open **Certificates & secrets**.
2. Select **Client secrets > New client secret**.
3. Use a short test lifetime.
4. Create the secret.
5. Copy the **Value** immediately.

Use the secret **Value**, not the Secret ID.

Configure:

```env
CLIENT_ID=<MCP_API_CLIENT_ID>
CLIENT_SECRET=<secret-value>
```

### 7.2 Production: certificate

Certificate credentials are preferred for production.

The current server expects:

```env
CLIENT_ID=<MCP_API_CLIENT_ID>
CLIENT_CERT_PATH=/run/secrets/m365-mcp-private-key.pem
CLIENT_CERT_THUMBPRINT=<certificate-thumbprint>
```

Do not set `CLIENT_SECRET` when certificate authentication is used.

## 8. Organizational cross-tenant consent

For an organizational user in another Microsoft Entra tenant, the multitenant application needs a service principal (Enterprise Application) in that tenant and the downstream Graph delegated permissions must be consented there.

### Recommended enterprise test path: tenant-wide admin consent

Sign in as an authorized administrator in the target tenant and open:

```text
https://login.microsoftonline.com/<TARGET-TENANT-ID>/adminconsent?client_id=<MCP_API_CLIENT_ID>
```

Review the requested delegated permissions carefully before accepting them.

This provisions the enterprise application in the target tenant and grants tenant-wide consent to the API permissions configured on the multitenant app, subject to the administrator's role and tenant policy.

Then verify in that tenant:

1. Go to **Entra ID > Enterprise applications > All applications**.
2. Find `M365-MCP-Server`.
3. Open **Security > Permissions**.
4. Confirm the intended delegated Microsoft Graph permissions are present.

For this project the expected Graph delegated permissions are:

```text
User.Read
Mail.ReadWrite
```

Do not approve unexpected application permissions.

Personal Microsoft accounts do not use a customer organization's Enterprise Application/admin-consent workflow in the same way. Their ability to sign in is controlled first by the App Registration's Supported account types, and the delegated permissions are consented in the personal-account flow.

## 9. Configure tenant admission on the MCP server

### Explicit tenant allowlist

For one approved organizational tenant:

```env
CLIENT_ID=<MCP_API_CLIENT_ID>
CLIENT_SECRET=<test-secret>
AUDIENCE=
ALLOWED_TENANTS=<TARGET-TENANT-ID>
REQUIRED_SCOPES=access_as_user
GRAPH_SCOPES=https://graph.microsoft.com/.default
GRAPH_BASE_URL=https://graph.microsoft.com/v1.0
```

For multiple approved tenants, use a comma-separated list:

```env
ALLOWED_TENANTS=<TENANT-ID-1>,<TENANT-ID-2>
```

### Accept any Microsoft tenant

For a deliberately open multitenant deployment:

```env
ALLOWED_TENANTS=*
```

`*` means any tenant that presents a token which passes the normal signature, issuer, audience, expiry and delegated-scope validation. It also includes the Microsoft consumer tenant used by personal Microsoft accounts **if** the App Registration's Supported account types allow personal Microsoft accounts.

The Microsoft consumer tenant ID is:

```text
9188040d-6c67-4c5b-b112-36a304b66dad
```

If the App Registration is organization-only, personal accounts cannot obtain a valid token for the API, so `ALLOWED_TENANTS=*` does not override that Entra setting.

Do not combine `*` with explicit tenant IDs. Leaving `ALLOWED_TENANTS` empty remains invalid and fails closed.

`AUDIENCE` can normally be left empty. The server then accepts the configured `CLIENT_ID` and `api://<CLIENT_ID>` audience forms. Set `AUDIENCE` only when an explicit override is required.

The App Registration home tenant ID is not used as the OBO authority for another tenant's user. The server uses the validated inbound token's `tid` and performs OBO against that tenant-specific authority.

## 10. The client application is separate from the MCP API

The MCP API registration above is a **resource / middle-tier API**. It does not perform an interactive sign-in itself.

A client must first obtain token A for:

```text
api://<MCP_API_CLIENT_ID>/access_as_user
```

and send it to `/mcp/` as a bearer token.

Current repository status:

- inbound bearer token validation: implemented
- OBO to Microsoft Graph: implemented
- MCP OAuth discovery / dynamic client registration: not implemented
- interactive sign-in owned by the MCP server: not implemented

Therefore the first live validation should use either:

1. an MCP client that can be configured with an Entra access token for this API, or
2. a small dedicated test client app registration.

## 11. Optional: create a test client app

If a suitable MCP client cannot yet acquire token A, create a separate public-client registration for validation.

### 11.1 Create the registration

1. Go to **App registrations > New registration**.
2. Name it:

   ```text
   M365-MCP-Test-Client
   ```

3. Select an account type that matches the identities you intend to test. For organization-only testing use **Accounts in any organizational directory**. To test Outlook.com/Hotmail/Live accounts too, select the option that also includes personal Microsoft accounts.
4. Register it.
5. Record its Application (client) ID as `TEST_CLIENT_ID`.

### 11.2 Allow public-client authentication

Open **Authentication** and enable the appropriate public-client flow for the chosen test method.

For device-code testing, enable public client flows.

Do not put the MCP server client secret into this test client.

### 11.3 Grant the client access to the MCP API

Open the **M365-MCP-Test-Client** registration:

1. Go to **API permissions > Add a permission**.
2. Select **My APIs**.
3. Select `M365-MCP-Server`.
4. Select the delegated permission:

   ```text
   access_as_user
   ```

Alternatively, the API registration can explicitly preauthorize a known test client under **Expose an API > Authorized client applications**.

### 11.4 Token A acceptance criteria

A token sent to the MCP server must contain, at minimum:

```text
aud = <MCP_API_CLIENT_ID> or another configured accepted audience
scp includes access_as_user
tid = the signed-in user's tenant ID
oid/sub = the signed-in user identity
```

For a personal Microsoft account, `tid` is the Microsoft consumer tenant ID shown above. An app-only token is invalid for this architecture because OBO requires a user principal.

## 12. First live validation sequence

Do not start with all tools. Validate the identity chain first.

1. Sign in as a test user.
2. Obtain token A for the MCP API scope.
3. Call the MCP endpoint with token A.
4. Confirm JWT validation succeeds.
5. Confirm OBO obtains a Microsoft Graph delegated token.
6. Run `mail_search` or `mail_get` against the signed-in user's mailbox.
7. Test attachment metadata/read on a known test message.
8. Test `mail_mark_read`.
9. Test `mail_archive` on a disposable test message.
10. Repeat with a second user and confirm mailbox isolation.

If personal Microsoft accounts are enabled, include one Outlook.com/Hotmail-style account in a separate validation pass before claiming support for that account type.

## 13. Expected security boundary

The server must never accept a mailbox identity such as:

```text
user_id=someone@example.com
mailbox=someone@example.com
```

The Graph layer uses `/me` and the OBO delegated token. Effective access is constrained by both:

- the delegated permissions granted to the application
- the permissions of the signed-in user

`ALLOWED_TENANTS=*` changes which validated Microsoft tenants may call the API; it does not change this per-user `/me` boundary.

## 14. Common problems

### AADSTS50011 - redirect URI mismatch

Cause: an interactive client is using a redirect URI that is not registered on that **client application**.

Fix: add the exact redirect URI to the interactive client app registration. Do not add an arbitrary WorkBuddy callback to the MCP API registration unless the MCP API itself is acting as that interactive client.

### AADSTS65001 / consent_required

Cause: the client-to-MCP scope or the MCP-to-Graph delegated permissions have not been consented in the target identity context.

For organizational tenants check:

- test/client app has `access_as_user` permission to M365-MCP-Server
- M365-MCP-Server enterprise application exists in the target tenant
- target tenant has consented `User.Read` and `Mail.ReadWrite`

### AADSTS70011 - invalid scope

Do not mix a resource `.default` request with individual delegated scopes in the same OBO request.

The MCP server currently requests:

```text
https://graph.microsoft.com/.default
```

The actual Graph delegated permissions come from the app registration and consent grants.

### Organization account works but personal account does not

Verify that both the MCP API registration and the interactive client registration use a Supported account type that includes personal Microsoft accounts. `ALLOWED_TENANTS=*` cannot widen the account types configured in Entra.

### OBO fails only for an external organizational tenant

Verify:

- the app registration is multitenant
- the target tenant is explicitly allowlisted or `ALLOWED_TENANTS=*`
- the inbound token's `tid` is the target tenant
- the enterprise application exists in the target tenant
- Graph delegated permissions have been consented in the target tenant

The OBO authority is tenant-specific and is derived from the validated token tenant.

### Graph returns 403

Check the token and consent before changing Graph code.

Common causes:

- Graph delegated permission was not consented
- the token is app-only instead of delegated
- the wrong user/tenant is signed in
- Exchange/Microsoft 365 mailbox availability does not permit the requested operation

## 15. Production hardening checklist

Before production:

- Prefer certificate credentials over client secrets.
- Keep only required delegated Graph permissions.
- Choose `ALLOWED_TENANTS=*` only when the deployment is intentionally open to all supported Microsoft tenants; otherwise use explicit tenant IDs.
- Review target-tenant Enterprise Application permissions for organizational tenants.
- Decide whether tenant-wide consent is appropriate for each organization.
- Apply Conditional Access as required by organizational policy.
- Do not enable application mailbox permissions.
- Test at least two users for identity isolation.
- If personal Microsoft accounts are supported, test that path separately.
- Validate supported MCP clients with real sign-in behavior.
- Rotate credentials before their expiration date.

## 16. Official Microsoft references

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
