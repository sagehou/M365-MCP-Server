[English](README.md) | **简体中文**

# M365 MCP Server

基于 Microsoft Graph API 的企业级 Microsoft 365 MCP Server。

## 概述

本项目为 AI Agent（WorkBuddy、Claude、Cursor 等）提供一个安全访问 Microsoft 365 的 MCP 接口。

设计目标：

- 支持自托管部署
- 使用 Microsoft Entra ID 身份认证
- 使用委托权限模型
- 通过 On-Behalf-Of（OBO）流程访问 Microsoft Graph
- 用户身份隔离
- 不依赖额外 SaaS

## 规划能力

### 第一阶段：Outlook 邮件

- 搜索邮件
- 读取邮件正文
- 列出附件
- 提取附件文本
- 标记已读/未读
- 移动邮件
- 归档邮件
- 分类
- 草稿管理

### 后续规划

- Calendar
- OneDrive
- SharePoint
- Teams

## 架构

```text
MCP Client
   |
   | Entra delegated bearer token
   v
M365 MCP Server
   |
   | OBO Flow
   v
Microsoft Graph
   |
   v
Microsoft 365
```

## 开发状态

任务 001–007 已有实现和 CI 覆盖，包括全部 8 个邮件工具。GitHub Actions 是当前唯一的构建/测试环境。稳定版发布工作流可以发布经过审核的版本标签；工作流存在并不代表镜像已经发布，部署前必须选择一个实际存在的 GHCR 版本。

服务端接收由客户端取得的 Entra 委托 Bearer Token。OAuth Protected Resource Metadata、Authorization Server Metadata 和 Public Client Registration 已位于 `OAUTH_ENABLED` 后；在 Authorization 与 Refresh Flow 完成前，该开关保持默认关闭。Interactive Sign-in、草稿、OCR、共享邮箱、RBAC、限流以及其他 Microsoft 365 工作负载尚未实现。Mock Graph/OBO 测试不代表真实租户已经验收。详见[实现复核状态](docs/zh-CN/review-status.md)、[运行时依赖审计](docs/zh-CN/runtime-dependency-audit.md)和 [WorkBuddy OAuth 指南](docs/zh-CN/workbuddy-oauth.md)。

## 部署

部署前先配置 Microsoft Entra。仓库提供了逐步操作手册，覆盖单租户/跨租户注册、`access_as_user`、Graph 委托权限、OBO 凭据、目标租户授权以及可选测试客户端：

- [Microsoft Entra 应用注册操作手册](docs/zh-CN/entra-app-registration.md)

随后按照[部署清单](docs/zh-CN/deployment.md)执行：

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d
```

应用提供：

- `GET /health`（同时支持 `/healthz`），仅用于进程存活检查
- `/mcp/`，受保护的 FastMCP Streamable HTTP Endpoint

使用 `/mcp/` 前必须配置 `CLIENT_ID`、且只配置一种客户端凭据、`ALLOWED_TENANTS` 和 `REQUIRED_SCOPES`。`ALLOWED_TENANTS` 可以填写逗号分隔的 Tenant ID 列表，也可以填写 `*` 表示接受任意有效 Microsoft Tenant；留空仍然按 fail closed 处理。`AUDIENCE` 可留空，此时 Server 会自动接受 API Client ID 和 `api://<client-id>` 两种形式。受保护端点只允许当前登录用户访问其委托 Outlook 邮箱。

测试和 Docker 构建均在 GitHub Actions 中执行。
