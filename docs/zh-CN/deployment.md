[English](../deployment.md) | **简体中文**

# 部署

## 支持的交付物

正式支持的交付物是容器镜像：

    ghcr.io/sagehou/m365-mcp-server:<version>

镜像使用 Python 3.12 构建，并以非 root 用户运行。默认暴露 8000 端口，并提供无需认证的 `/health` 与 `/healthz` 健康检查，供容器和反向代理探测使用。MCP Endpoint 仍由 Microsoft Entra Bearer Token 校验保护。

## 先完成 Entra 配置

部署前先按照以下手册完成 Portal 配置：

- [Microsoft Entra 应用注册操作手册](entra-app-registration.md)

该手册覆盖服务器当前使用的应用模型，包括跨租户测试、`access_as_user` API Scope、Microsoft Graph 委托权限、OBO 凭据、目标租户授权以及可选测试客户端注册。

## Docker Compose 部署

复制环境变量模板到 deploy 目录，填写 Entra 和 Graph 配置，并确保实际 `.env` 不进入版本控制：

    cp deploy/.env.example deploy/.env

启动镜像：

    docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d

检查容器状态和进程存活：

    docker compose --env-file deploy/.env -f deploy/docker-compose.yml ps
    curl --fail http://127.0.0.1:8000/healthz

`M365_MCP_IMAGE` 必须指向已经存在的版本或 Digest。模板故意使用 `CHANGE_ME`。正式启动前应先用同样参数执行 `docker compose ... pull`，如果镜像不存在则停止部署。若 GHCR Package 为 private，还需要使用具有 package read 权限的凭据执行 `docker login ghcr.io`。

真实环境预发布验证可以使用仓库从已审核 `main` 分支发布的：

```text
ghcr.io/sagehou/m365-mcp-server:edge
ghcr.io/sagehou/m365-mcp-server:sha-<commit>
```

记录可复现测试结果时优先使用 SHA Tag。稳定版 `latest` 仅用于正式版本发布。

## 生产网络边界

推荐在反向代理终止 TLS，并固定公网 Hostname：

    Traefik -> HTTPS -> M365 MCP Server -> Microsoft Graph

Compose 默认只绑定 `127.0.0.1`。如果反向代理运行在其他主机或容器中，需要显式配置私有接口/网络，不要简单绑定所有接口。`MCP_PORT` 同时控制监听端口和健康检查端口。外部 HTTPS Endpoint URL 应配置在 MCP Client 与反向代理中。

没有 TLS 和完整 Entra 配置时，不要把容器直接暴露到 Internet。

## OAuth Authorization Broker

OAuth Broker 已提供 Discovery Metadata、Dynamic Public-client Registration、MSAL Interactive Authorization、S256 PKCE、一次性 Authorization-code Exchange 与 Persistent Local Refresh Session。在真实 WorkBuddy 验收完成前仍默认关闭：

    OAUTH_ENABLED=false
    MCP_PUBLIC_URL=https://mcp.example.com/mcp/
    OAUTH_ISSUER_URL=https://mcp.example.com
    OAUTH_DATABASE_PATH=/data/oauth.db
    OAUTH_ENCRYPTION_KEY=<32-random-bytes-base64>
    OAUTH_REFRESH_TOKEN_TTL_DAYS=30
    OAUTH_REFRESH_MAX_ROTATIONS=10000
    ENTRA_BROKER_CLIENT_ID=<app-b-client-id>
    ENTRA_BROKER_CLIENT_SECRET=<app-b-secret>
    ENTRA_BROKER_AUTHORITY=https://login.microsoftonline.com/organizations

在集成开发中显式开启后，两个 Public URL 都来自经过验证的配置，绝不从 Host 或 Forwarded Header 推导。除 Loopback 开发外必须使用 HTTPS。Compose 把 Named Volume `oauth-data` 挂载到 `/data`，使 Registered Client 与加密 Session 在 Container Recreate 后仍然存在。该 Volume 属于敏感认证状态，必须纳入备份保护。`OAUTH_ENCRYPTION_KEY` 必须存入部署 Secret Manager，不得进入 Database、Image、Repository 或 Log；恢复与替换进程必须使用同一 Database 和 Key。v0.1 不提供 Distributed 或 Multi-host Session Storage。

反向代理必须把 `/.well-known/*`、`/oauth/*` 和 `/mcp/` 路由到同一固定 Public Origin，并且只在 App B 注册 `https://mcp.example.com/oauth/callback/entra`。对 `/oauth/register` 配置 Request-size 与 Rate Limit，并对 `/oauth/token` 配置 Rate/Concurrency Limit；应用不会为此增加 Redis 或 Enterprise Rate Limiter。生产入口已关闭 Uvicorn Request-line Access Log，因为 OAuth Authorization 和 Callback Query String 包含敏感的短期值；所有反向代理与日志采集器也必须对 `/oauth/*` 省略 Query String。在 WorkBuddy E2E Gate 完成前，不要在生产设置 `OAUTH_ENABLED=true`。详见 [WorkBuddy OAuth](workbuddy-oauth.md)。

## 容器发布

稳定版 Release Workflow 只响应 `vX.Y.Z` 格式的 Version Tag。它会：

1. 运行测试
2. 确认被打 Tag 的 Commit 位于 `main`
3. 构建生产 Dockerfile
4. 对该精确镜像执行 Smoke Test
5. 通过后才发布

示例：

    git tag v0.1.0
    git push origin v0.1.0

对于 `v0.1.0`，Workflow 会发布 version、major/minor 和 `latest` GHCR Tags。Workflow 使用仓库 GitHub Token 发布 Package，不在仓库中保存 Registry Secret。

独立测试镜像 Workflow 在测试、Docker Build 和 Smoke Test 成功后，从 `main` 发布 `edge` 和 Commit-specific SHA Tag；测试标签不会覆盖 `latest`。

## 配置

所有 Runtime Settings 均通过环境变量提供。只允许配置 `CLIENT_SECRET` 或 `CLIENT_CERT_PATH` 其中一种，并设置 `ALLOWED_TENANTS`。Graph Delegated Permissions 只授予 Mail Tools 实际需要的最小权限。Secrets 必须由部署环境或 Secret Management System 注入。

`ALLOWED_TENANTS` 支持两种模式：

- 填写逗号分隔的 Tenant GUID，形成显式 Allowlist；
- 填写 `*`，接受任何能通过完整 Token Signature / Issuer / Audience / Scope 校验的有效 Microsoft Tenant。若 App Registration 的 Supported account types 同时允许 Personal Microsoft Accounts，则该语义也包含 Microsoft Consumer Tenant。

`ALLOWED_TENANTS` 留空仍然是无效配置，并按 fail closed 处理。`*` 不能和具体 Tenant ID 混写。对于仅供内部组织使用的部署，显式 Tenant Allowlist 仍然是更窄的安全边界；`*` 适合明确要对所有 Microsoft Tenant 开放的 Multitenant 部署。

`AUDIENCE` 可以留空。留空时 Server 会自动接受已配置的 `CLIENT_ID` 和 `api://<CLIENT_ID>` 两种 Audience 形式。

## Entra / Client 前置条件与验收

1. 注册 API Application，暴露 `access_as_user` Delegated Scope，并使用 v2 Access Token。`CLIENT_ID`、`ALLOWED_TENANTS`、`REQUIRED_SCOPES` 必须对应真实 API Registration。`ALLOWED_TENANTS` 要么填写逗号分隔的 Tenant Allowlist，要么明确填写 `*`。除非确实需要覆盖默认 Audience 行为，否则 `AUDIENCE` 留空即可。
2. 授予 Graph Delegated `User.Read` 和 `Mail.ReadWrite`，并在目标租户完成所需 Consent。不要授予 Application Mailbox Permissions 或 `Mail.Send`；当前没有发信工具。
3. 只配置一种 Credential。使用证书时，将 PEM Private Key 以只读方式挂载进容器，把 `CLIENT_CERT_PATH` 设置为容器内路径，并设置 `CLIENT_CERT_THUMBPRINT`。只填写宿主机路径并不会自动挂载文件。Compose Override 可使用：`./secrets/client.pem:/run/secrets/client.pem:ro`。
4. 注册独立 Confidential App B，配置 Broker Callback 与三个 `ENTRA_BROKER_*` 值，并向 App B 授予 App A 的 `api://<CLIENT_ID>/access_as_user` Delegated Scope。不要向 App B 授予 Graph Permission。Interactive Sign-in、Local Authorization-code Exchange 与 Persistent Refresh 已位于默认关闭的 Feature Flag 后；真实 WorkBuddy 验收仍是 Release Blocker。
5. 确认 `/healthz` 返回 200，未带 Bearer Token 的 `/mcp/` 返回 401。这两个检查不能证明 Tenant Credential、Graph Consent 或 OBO 已正确工作。
6. 使用两个测试用户分别初始化 MCP、列出 8 个工具并读取各自邮箱中的已知消息，确认无法跨用户访问消息。写操作只对可丢弃测试消息执行，并检查 Move 后的新 ID。
7. 读取代表性附件；确认 JSON Audit Event 包含 Identity、Tool、Outcome 和 Timestamp，但不包含邮件正文、文件名或 Token。若 OBO/Tool 调用失败，应查看 Audit Error Type 与 Entra Sign-in Diagnostics，禁止开启 Payload/Token Logging。

附件 Worker 默认限制：512 MiB Address Space、15 CPU Seconds、20 Seconds Wall Time，并且每个 Server Process 最多两个 Active Workers。Office Archive 最多允许 64 MiB 解压数据和 2048 个 Entries。这些限制用于资源隔离，并不等价于 Filesystem/Network Sandbox。生产环境还应在反向代理配置 Request Size / Concurrency Limits，并设置 Container Memory/PID Limits。

如果提高 `ATTACHMENT_MAX_BYTES`，也要同步提高 `GRAPH_MAX_RESPONSE_BYTES`，因为 Graph JSON 中 Base64 后的数据至少需要原始字节的 4/3，再加 Metadata。
