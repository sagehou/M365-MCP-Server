[English](../../codex/006-security-audit.md) | **简体中文**

# Task 006 - 安全与审计

## 目标

为企业部署加固 MCP Server。

## 要求

- Audit Tool Invocation。
- 记录 Tenant 与 User Identity。
- 不记录 Email Body 或 Attachments。
- 防范来自 Email Content 的 Prompt Injection。
- 增加 Security Documentation。

## 交付物

- Audit Logger
- Security Middleware
- Logging Policy
- Tests

## 非目标

- 初期不集成 SIEM。

## 实现说明

Mail Tool Wrapper 输出 Structured Audit Event，只包含 Tenant、User、Tool、Outcome、Duration 和安全的 Exception Type；永远不记录 Tool Arguments 或 Graph Payloads。HTTP Response 会添加 Defensive Security Headers。

Message Preview、Message Body 和 Extracted Attachment Text 都带 Untrusted-content Marker 和明确的 Handling Warning。Server 不解释 Email-derived Content 中的指令；Client 必须只把这些内容当作 Data。SIEM Integration 仍不在 Scope 内。
