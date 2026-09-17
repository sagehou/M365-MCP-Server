[English](../codex-guide.md) | **简体中文**

# Codex 开发指南

## 开发要求

增量实现，不要一次生成整个项目。

优先顺序：

1. 项目初始化
2. 身份认证层
3. Microsoft Graph Client
4. MCP Server Framework
5. Mail Tools
6. 附件提取
7. 企业级功能

## 编码要求

- Python 3.12
- 全面使用 Type Hints
- Async First
- 使用 Pydantic Models
- 每个 Service 都需要 Unit Tests
- 支持 Docker 部署
- 禁止提交 Secrets

## 架构规则

保持各层分离：

```text
api/
  MCP protocol handlers

auth/
  Entra authentication

graph/
  Microsoft Graph clients

services/
  business logic

extractors/
  attachment parsing
```

避免让 MCP Tools 直接耦合 Microsoft Graph SDK 调用。
