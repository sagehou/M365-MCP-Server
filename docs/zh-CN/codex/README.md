[English](../../codex/README.md) | **简体中文**

# Codex 开发任务指南

本目录包含增量开发任务。

规则：

- 一次完成一个任务。
- 保持改动可审核。
- 不得绕过安全边界。
- 不得添加 Microsoft Graph Application Permissions。
- 通过 Delegated Permissions 保持用户身份隔离。

推荐顺序：

1. Bootstrap Project
2. Entra Authentication and OBO
3. Microsoft Graph Client
4. Mail MCP Tools
5. Attachment Extraction
6. Audit and Security Hardening
7. Container Release
