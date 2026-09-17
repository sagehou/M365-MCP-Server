[English](../../adr/0001-runtime-selection.md) | **简体中文**

# ADR-0001：运行时选择

## 状态

已接受

## 决策

使用 Python 3.12 作为主要实现运行时。

## 背景

本项目是企业级 Microsoft 365 MCP Server，核心工作负载包括：

- MCP Protocol Handling
- Microsoft Entra OAuth/OBO Authentication
- Microsoft Graph API Calls
- Email Attachment Document Extraction
- AI Agent Integration

该工作负载主要是网络和系统集成，而不是 CPU Intensive Computing。

## 考虑过的方案

### .NET 8

优点：

- Microsoft 生态第一方支持
- Entra ID 与 Graph SDK 集成优秀
- 企业采用广泛

缺点：

- MCP 生态与示例成熟度低于 Python
- 快速迭代 Agent Tooling 时开发复杂度更高

### Python 3.12

优点：

- MCP 生态成熟
- AI Tooling 生态优秀
- 文档处理库成熟
- 更适合 Codex 辅助开发
- 容器部署简单

缺点：

- 与 Microsoft 原生企业技术栈的贴合度低于 .NET

## 决策理由

选择 Python，是因为本项目本质上是 MCP Integration Layer，而不是 Microsoft Management Platform。Docker 已经隔离了大部分 Runtime 差异，而 Python 能提供更快的迭代速度和更低的维护成本。

Microsoft Graph 与 Entra 集成仍使用官方 SDK 或 Standards-based OAuth Flow。

## 影响

正面：

- 开发更快
- 更容易上手
- AI 生态丰富

负面：

- Authentication Middleware 需要承担更多 Application-level Responsibility
- 必须谨慎维护 Graph Integration Abstraction
