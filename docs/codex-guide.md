**English** | [简体中文](zh-CN/codex-guide.md)

# Codex Development Guide

## Instructions

Implement incrementally. Do not generate the whole project at once.

Priority order:

1. Project bootstrap
2. Authentication layer
3. Microsoft Graph client
4. MCP server framework
5. Mail tools
6. Attachment extraction
7. Enterprise features

## Coding Requirements

- Python 3.12
- Type hints everywhere
- Async first
- Pydantic models
- Unit tests for every service
- Docker deployment support
- No secrets committed

## Architecture Rules

Keep these layers separated:

```
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

Avoid coupling MCP tools directly with Graph SDK calls.
