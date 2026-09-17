**English** | [简体中文](zh-CN/entra-app-registration.md)

# Microsoft Entra App Registration Guide

## Quick links

- **Microsoft Entra admin center:** https://entra.microsoft.com/
- **Azure portal - Microsoft Entra overview:** https://portal.azure.com/?quickstart=true#view/Microsoft_AAD_IAM/ActiveDirectoryMenuBlade/~/Overview
- **Register an application:** https://learn.microsoft.com/en-us/graph/auth-register-app-v2
- **Expose a web API / add `access_as_user`:** https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-configure-app-expose-web-apis
- **OAuth 2.0 On-Behalf-Of flow:** https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-on-behalf-of-flow
- **Microsoft Graph permissions reference:** https://learn.microsoft.com/en-us/graph/permissions-reference
- **Grant tenant-wide admin consent:** https://learn.microsoft.com/en-us/entra/identity/enterprise-apps/grant-admin-consent

For the steps below, use the **Microsoft Entra admin center** unless a step explicitly points elsewhere. Before creating anything, switch to the intended directory/tenant and confirm the tenant name shown in the portal.

This guide describes the Microsoft Entra configuration required by M365 MCP Server.

It is written for the current implementation in this repository:

- self-hosted MCP API
- delegated user identity
- OAuth 2.0 On-Behalf-Of (OBO) to Microsoft Graph
- Microsoft Graph delegated permissions only
- optional cross-tenant test where the app is registered in Tenant A and the mailbox user is in Tenant B

> The MCP server is a protected web API, not an interactive web application. Do not add a redirect URI to the MCP API registration just because an OAuth client normally has one. Redirect URIs belong to the interactive client application.

## 1. Target identity model

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

The MCP server validates the inbound token, allowlists the token tenant, and performs OBO against the tenant identified by the inbound `tid` claim.

## 2. Public-cloud assumption

The default repository settings target the global Microsoft cloud:

```text
AUTHORITY_HOST=https://login.microsoftonline.com
GRAPH_BASE_URL=https://graph.microsoft.com/v1.0
```

Do not mix global-cloud registrations with Microsoft 365 operated by 21Vianet. National clouds use different identity and Microsoft Graph endpoints and require separate validation before use.

## 3. Choose the home tenant

For the cross-tenant test scenario used by this project:

- **Tenant A**: home tenant that owns the app registration.
- **Tenant B**: Microsoft 365 tenant containing the test mailbox users.

For an internal production deployment where all users are in one organization, registering the app directly in the production tenant and using a single-tenant registration is simpler.

For the cross-tenant test, use a multitenant registration.

## 4. Create the MCP API application in Tenant A

1. Open https://entra.microsoft.com/ and sign in to the Microsoft Entra admin center.
2. Switch to **Tenant A**.
3. Go to **Entra ID > App registrations > New registration**.
4. Use a clear name, for example:

   ```text
   M365-MCP-Server
   ```

5. Under **Supported account types**, select:

   ```text
   Accounts in any organizational directory
   (Any Microsoft Entra ID tenant - Multitenant)
   ```

6. Leave **Redirect URI** empty.
7. Select **Register**.

Record the following values from **Overview**:

- Application (client) ID
- Directory (tenant) ID of Tenant A

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

In particular, do not add:

```text
Mail.Read (Application)
Mail.ReadWrite (Application)
Mail.Send (Application)
```

`Mail.ReadWrite` delegated permission lets the app act only in the signed-in user's delegated context and does not include mail sending.

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

## 8. Configure Tenant B for a cross-tenant test

The multitenant application must have a service principal (Enterprise Application) in Tenant B and the downstream Microsoft Graph delegated permissions must be consented there.

### Recommended test path: tenant-wide admin consent

Sign in as an authorized administrator in **Tenant B** and open:

```text
https://login.microsoftonline.com/<TENANT-B-ID>/adminconsent?client_id=<MCP_API_CLIENT_ID>
```

Review the requested delegated permissions carefully before accepting them.

This provisions the enterprise application in Tenant B and grants tenant-wide consent to the API permissions configured on the multitenant app, subject to the administrator's role and tenant policy.

Then verify in Tenant B:

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

## 9. Configure the MCP server for Tenant B

For a single target tenant test:

```env
CLIENT_ID=<MCP_API_CLIENT_ID>
CLIENT_SECRET=<test-secret>
AUDIENCE=api://<MCP_API_CLIENT_ID>
ALLOWED_TENANTS=<TENANT-B-ID>
REQUIRED_SCOPES=access_as_user
GRAPH_SCOPES=https://graph.microsoft.com/.default
GRAPH_BASE_URL=https://graph.microsoft.com/v1.0
```

For multiple approved tenants, `ALLOWED_TENANTS` is a comma-separated list.

The application registration home tenant ID is not used as the OBO authority for a Tenant B user. The server uses the validated inbound token's `tid` and performs OBO against that tenant-specific authority.

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

Therefore the first live-tenant validation should use either:

1. an MCP client that can be configured with an Entra access token for this API, or
2. a small dedicated test client app registration.

## 11. Optional: create a test client app

If a suitable MCP client cannot yet acquire token A, create a separate public-client registration for validation.

### 11.1 Create the registration

In Tenant A:

1. Go to **App registrations > New registration**.
2. Name it:

   ```text
   M365-MCP-Test-Client
   ```

3. For a cross-tenant test, select:

   ```text
   Accounts in any organizational directory
   ```

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
aud = api://<MCP_API_CLIENT_ID>
# Some Entra token forms may use the bare client ID; the server accepts the configured audience/client ID forms.

scp includes access_as_user

tid = <TENANT-B-ID>

oid = the signed-in Tenant B user's object ID
```

An app-only token is invalid for this architecture. OBO requires a user principal.

## 12. First live validation sequence

Do not start with all tools. Validate the identity chain first.

1. Sign in as a Tenant B test user.
2. Obtain token A for the MCP API scope.
3. Call the MCP endpoint with token A.
4. Confirm JWT validation succeeds.
5. Confirm OBO obtains a Microsoft Graph delegated token.
6. Run `mail_search` or `mail_get` against the signed-in user's mailbox.
7. Test attachment metadata/read on a known test message.
8. Test `mail_mark_read`.
9. Test `mail_archive` on a disposable test message.
10. Repeat with a second Tenant B user and confirm mailbox isolation.

## 13. Expected security boundary

The server must never accept a mailbox identity such as:

```text
user_id=someone@example.com
mailbox=someone@example.com
```

The Graph layer uses `/me` and the OBO delegated token. Effective access is constrained by both:

- the delegated permissions granted to the application
- the permissions of the signed-in user

## 14. Common problems

### AADSTS50011 - redirect URI mismatch

Cause: an interactive client is using a redirect URI that is not registered on that **client application**.

Fix: add the exact redirect URI to the interactive client app registration. Do not add an arbitrary WorkBuddy callback to the MCP API registration unless the MCP API itself is acting as that interactive client.

### AADSTS65001 / consent_required

Cause: the client-to-MCP scope or the MCP-to-Graph delegated permissions have not been consented in the target tenant.

Check:

- test/client app has `access_as_user` permission to M365-MCP-Server
- M365-MCP-Server enterprise application exists in Tenant B
- Tenant B has consented `User.Read` and `Mail.ReadWrite`

### AADSTS70011 - invalid scope

Do not mix a resource `.default` request with individual delegated scopes in the same OBO request.

The MCP server currently requests:

```text
https://graph.microsoft.com/.default
```

The actual Graph delegated permissions come from the app registration and consent grants.

### OBO fails only for cross-tenant users

Verify:

- the app registration is multitenant
- Tenant B is present in `ALLOWED_TENANTS`
- the inbound token's `tid` is Tenant B
- the enterprise application exists in Tenant B
- Graph delegated permissions have been consented in Tenant B

The OBO authority must be tenant-specific. Do not use `/common` or `/organizations` for the OBO token exchange.

### Graph returns 403

Check the token and consent before changing Graph code.

Common causes:

- Graph delegated permission was not consented
- the token is app-only instead of delegated
- the wrong user/tenant is signed in
- Exchange/Microsoft 365 licensing or mailbox availability does not permit the requested operation

## 15. Production hardening checklist

Before production:

- Prefer certificate credentials over client secrets.
- Keep only required delegated Graph permissions.
- Review Tenant B Enterprise Application permissions.
- Decide whether tenant-wide consent is appropriate for the organization.
- Apply Conditional Access as required by organizational policy.
- Restrict `ALLOWED_TENANTS` explicitly.
- Do not enable application mailbox permissions.
- Test at least two users for identity isolation.
- Validate supported MCP clients with real sign-in behavior.
- Rotate credentials before their expiration date.

## 16. Official Microsoft references

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
