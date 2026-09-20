[English](../runtime-dependency-audit.md) | **简体中文**

# 运行时依赖审计

本文记录 FastMCP 4 迁移的依赖边界。版本来自 2026-09-17 GitHub Actions
实际解析结果，不是根据版本范围推测的估计值。

## 实际解析版本

| Package | 关系 | 迁移前 | 迁移后 |
| --- | --- | ---: | ---: |
| `fastmcp` | 直接依赖，MCP Runtime | 2.14.7 | 4.0.4 |
| `fastmcp-slim` | 由 `fastmcp` 传递引入 | 未安装 | 4.0.4 |
| `mcp` | 由 `fastmcp` 传递引入 | 1.30.0 | 2.2.0 |
| `mcp-types` | 由 MCP/FastMCP 传递引入 | 未安装 | 2.2.0 |
| `authlib` | 由 FastMCP 传递引入 | 1.8.0 | 1.8.0 |
| `joserfc` | 由 FastMCP 传递引入 | 1.7.5 | 1.7.5 |
| `httpx` | 直接依赖，Graph/OIDC Client | 0.28.1 | 0.28.1 |
| `httpx2` | FastMCP HTTP Stack 传递依赖 | 未安装 | 2.13.0 |
| `msal` | 直接依赖，Entra OBO Client | 1.38.0 | 1.38.0 |
| `PyJWT` | 直接依赖，JWT Validation | 2.14.0 | 2.14.0 |
| `fastapi` | 直接依赖，ASGI Application | 0.141.1 | 0.141.1 |
| `starlette` | 由 FastAPI/FastMCP 传递引入 | 1.6.0 | 1.6.0 |
| `pydantic` | 直接依赖，Models/Settings | 2.13.5 | 2.13.5 |

项目有意同时保留两套 HTTP Client。项目自身的 Graph 和 OpenID Connect
请求继续使用直接依赖 `httpx`；FastMCP 4 与 MCP SDK v2 内部使用独立的传递依赖
`httpx2`。两者责任方不同，不是意外的重复依赖。

本次接受的依赖约束为 `fastmcp==4.0.4`、`fastapi>=0.133,<1` 和
`pydantic>=2.12,<3`。精确锁定 FastMCP 使本次 Runtime Migration 可复现，
其他现有范围仍可获得兼容的维护版本。

## 兼容性证据

迁移审计未发现项目使用已移除的 FastMCP API。现有 ASGI Mount、Stateless
HTTP 配置、Tool Error Boundary 和 Request Dependency Helper 都继续通过生产
Application Factory 接受测试。

GitHub Actions 在同一端点覆盖两代协议：

- Legacy `2025-03-26`：initialize、tools/list、全部 9 个 Mail Tools、
  Sanitized Failure，以及 Alice/Bob 并发身份隔离。
- Modern `2026-07-28`：携带 Request Metadata 且无 MCP Session ID 的
  server/discover、tools/list 和 tools/call。
- 完整 Unit/Integration Suite、Production Docker Image、Health Endpoint、
  Non-root Worker Startup 和 Docker Compose Smoke Path。

Container Smoke Test 还会拒绝包含已知 Authlib JOSE 和 HTTPX 迁移告警的生产
启动日志。它不会隐藏 Warning、降级 Authlib、修改已安装包或保留 FastMCP 2。

迁移前快照见 [GitHub Actions run 35195153651](https://github.com/sagehou/M365-MCP-Server/actions/runs/35195153651)。
迁移成功快照见 [GitHub Actions run 35195810661](https://github.com/sagehou/M365-MCP-Server/actions/runs/35195810661)。

## 范围边界

本阶段只变更 MCP Runtime。Authentication 仍要求 Client 提供 Bearer Token，
随后执行现有 Entra OBO Exchange。本次迁移不增加 OAuth Discovery、Dynamic
Client Registration 或 Browser Sign-in。
