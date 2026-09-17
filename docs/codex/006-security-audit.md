**English** | [简体中文](../zh-CN/codex/006-security-audit.md)

# Task 006 - Security and Audit

## Goal

Harden the MCP server for enterprise deployment.

## Requirements

- Audit tool invocation.
- Record tenant and user identity.
- Do not log email body or attachments.
- Protect against prompt injection from email content.
- Add security documentation.

## Deliverables

- Audit logger
- Security middleware
- Logging policy
- Tests

## Non goals

- No SIEM integration initially.

## Implementation notes

Mail tool wrappers emit structured audit events containing only tenant, user,
tool, outcome, duration, and safe exception type. They never log tool arguments
or Graph payloads. HTTP responses receive defensive security headers.

Message previews, message bodies, and extracted attachment text carry an
untrusted-content marker and explicit handling warning. The server does not
attempt to interpret instructions in email-derived content; clients must treat
it as data only. SIEM integration remains out of scope.
