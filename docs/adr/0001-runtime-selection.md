**English** | [简体中文](../zh-CN/adr/0001-runtime-selection.md)

# ADR-0001: Runtime Selection

## Status

Accepted (amended for Windows local mode)

## Decision

Use Python 3.12 as the primary runtime for the hosted HTTP/OBO server and
container delivery.

Use a separate .NET 8 NativeAOT executable for Windows local mode. The local
host runs beside the agent over MCP stdio and uses Microsoft Entra public-client
authorization code + PKCE. It is not a replacement for the hosted Python
server.

## Context

This project is an enterprise Microsoft 365 MCP Server. The core workload is:

- MCP protocol handling
- Microsoft Entra OAuth/OBO authentication
- Microsoft Graph API calls
- Document extraction for email attachments
- AI agent integration

The hosted workload is network and integration focused rather than CPU
intensive. Its deployment target is a container, where Python provides a mature
MCP and document-processing ecosystem.

Windows local mode has a different distribution constraint: the user receives
one executable that does not require a preinstalled Python or .NET runtime and
does not unpack an application tree beside the executable or into a temporary
directory. The agent owns the process lifetime and communicates over stdio.

## Options considered

### Python 3.12 for every mode

Advantages:

- Strong MCP and AI tooling ecosystems
- Mature document processing libraries
- One implementation language

Disadvantages:

- Common Python single-file packagers extract an embedded runtime and
  dependencies at startup
- That extraction behavior does not satisfy the Windows no-runtime,
  no-extraction distribution contract

### .NET 8 for every mode

Advantages:

- First-class Microsoft ecosystem support
- Excellent Entra ID and Graph integration
- Strong enterprise adoption

Disadvantages:

- Rewriting the hosted server would discard the established Python MCP,
  attachment-processing, and container implementation
- A broad rewrite would add release risk without improving the hosted contract

### Split runtime: Python hosted server plus .NET 8 NativeAOT local host

Advantages:

- Preserves the established hosted implementation
- Produces a self-contained native Windows executable without a managed runtime
  dependency or startup extraction directory
- Fits public-client authentication and MCP stdio process ownership

Disadvantages:

- Two implementations must keep overlapping MCP tool contracts aligned
- NativeAOT requires ahead-of-time-compatible libraries and explicit
  serialization metadata
- Windows code signing and a stable release asset remain separate delivery
  gates

## Decision rationale

The deployment contracts differ enough to justify two entry points. Python
remains the best fit for the hosted integration layer and rich attachment
processing. .NET 8 NativeAOT is used only for the constrained Windows local
distribution, where a genuine self-contained executable is a product
requirement.

Both modes call Microsoft Graph through standards-based OAuth flows. The hosted
server retains confidential-client/OBO behavior; the local host uses a
dedicated Entra public-client application and stores refresh state with
current-user DPAPI.

## Consequences

Positive:

- No hosted-server rewrite
- Fast Python iteration remains available
- Windows users receive one executable with no separately installed runtime
- Local credentials remain scoped to the signed-in Windows user

Negative:

- Shared behavior must be covered by contract tests and documented explicitly
- Local mode initially exposes a narrower tool set than the hosted service
- Release engineering must produce, scan, sign, and publish the Windows binary
