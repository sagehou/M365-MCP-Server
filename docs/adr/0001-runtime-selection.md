# ADR-0001: Runtime Selection

## Status

Accepted

## Decision

Use Python 3.12 as the primary implementation runtime.

## Context

This project is an enterprise Microsoft 365 MCP Server. The core workload is:

- MCP protocol handling
- Microsoft Entra OAuth/OBO authentication
- Microsoft Graph API calls
- Document extraction for email attachments
- AI agent integration

The workload is network and integration focused rather than CPU intensive.

## Options considered

### .NET 8

Advantages:

- First-class Microsoft ecosystem support
- Excellent Entra ID and Graph SDK integration
- Strong enterprise adoption

Disadvantages:

- MCP ecosystem and examples are less mature than Python
- Higher development complexity for rapid agent tooling iteration

### Python 3.12

Advantages:

- Strong MCP ecosystem
- Excellent AI tooling ecosystem
- Mature document processing libraries
- Easier Codex-assisted development
- Simple container deployment

Disadvantages:

- Less native Microsoft ecosystem alignment

## Decision rationale

Python is selected because the project is an MCP integration layer rather than a Microsoft management platform. Docker deployment removes most runtime concerns, while Python provides faster iteration and easier maintenance.

Microsoft Graph and Entra integration will use official SDKs and standards-based OAuth flows.

## Consequences

Positive:

- Faster development
- Easier onboarding
- Rich AI ecosystem

Negative:

- More application-level responsibility for authentication middleware
- Must maintain Graph integration abstractions carefully
