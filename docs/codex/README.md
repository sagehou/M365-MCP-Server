**English** | [简体中文](../zh-CN/codex/README.md)

# Codex Development Guide

This directory contains incremental development tasks.

Rules:

- Complete one task at a time.
- Keep changes reviewable.
- Do not bypass security boundaries.
- Do not add Microsoft Graph Application permissions.
- Keep user identity isolation through delegated permissions.

Recommended order:

1. Bootstrap project
2. Entra authentication and OBO
3. Microsoft Graph client
4. Mail MCP tools
5. Attachment extraction
6. Audit and security hardening
7. Container release
