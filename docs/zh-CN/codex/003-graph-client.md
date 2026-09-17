[English](../../codex/003-graph-client.md) | **简体中文**

# Task 003 - Microsoft Graph Client

## 目标

实现 Microsoft Graph Integration Layer。

## 要求

- 创建可复用 Graph Client Abstraction。
- 使用通过 OBO 获取的 Delegated Tokens。
- 支持 Microsoft Graph Retry Handling。
- 处理 Throttling Responses。
- Graph Operations 与 MCP Tools 保持隔离。

## 交付物

- Graph Client Wrapper
- Mail Service Foundation
- Error Handling
- Unit Tests

## 非目标

- 不暴露 MCP Tools。
- 不做 Document Extraction。
