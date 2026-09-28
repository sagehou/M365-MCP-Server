[English](../development-plan.md) | **简体中文**

# 开发计划

## 当前交付顺序

1. `v0.1.0` 已按 MIT 许可证[发布](https://github.com/sagehou/M365-MCP-Server/releases/tag/v0.1.0)，
   包含容器镜像和 Windows 单文件 EXE。
2. 当前源码增加最多 20 MiB 的草稿文件附件：远端客户端使用二进制暂存，Windows
   可用受限的产物相对路径或原生文件选择框。此能力不在已发布的 v0.1.0 产物中。
3. 后续范围包括丰富附件提取、Search 翻页、回复与转发及更广泛的 M365 工作负载。
   签名和杀毒误报处理属于独立的 Windows 分发事项。

每个部署的验收记录保存在源码仓库之外。

## Windows 本地模式实现状态

已发布的 Windows 实现位于 `windows/M365Mcp.Local`，使用方式见
[Windows 本地模式指南](windows-local.md)。

v0.1.0 已交付：

- .NET 8 NativeAOT 自包含 Windows x64 可执行文件
- GitHub Actions 单文件产物检查和无 Runtime 隔离烟测
- 由 Agent 作为子进程启动的 MCP stdio Server
- 面向独立 Entra Public Client 的系统浏览器授权码 + S256 PKCE
- 当前用户 DPAPI 保护的刷新状态，以及不持久化的 `--ephemeral` 模式
- 十个有边界的邮件工具，包括创建草稿和发送草稿
- 明确不进行任意附件文件写入

当前设计边界：

- 本地丰富附件提取及下载能力尚未与远端对齐
- SHA-256 与 GitHub 构建来源证明已发布；可选 Authenticode 签名和 SBOM 是独立分发改进
- 是否增加 Windows Web Account Manager 取决于部署需求

Windows Service 安装不属于当前 stdio 契约。stdio MCP Host 的生命周期由
Agent 进程管理；若要提供 Service Mode，需要独立 IPC Transport，以及明确的
生命周期与安全设计。

## Phase 0 - 项目初始化

- Python Project
- FastAPI
- FastMCP
- Docker Support
- Health Endpoint

## Phase 1 - 身份认证

- Microsoft Entra ID Integration
- JWT Validation
- Tenant Allowlist
- OBO Token Exchange
- Graph Client Abstraction

## Phase 2 - Mail MVP

Tools：

- mail_search
- mail_get
- mail_create_draft
- mail_send_draft
- mail_list_attachments
- mail_read_attachment
- mail_download_attachment
- mail_mark_read
- mail_archive
- mail_move
- mail_set_category

Windows 本地模式当前实现了以上除 `mail_download_attachment` 之外的全部项目；
本地 `mail_read_attachment` 仅支持有边界的文本类内容。

## Phase 3 - 附件处理

支持：

- PDF Extraction
- DOCX Extraction
- XLSX Extraction
- PPTX Extraction
- OCR Interface

## Phase 4 - 企业能力

- Audit Logging
- Shared Mailbox
- RBAC
- Rate Limiting
- Observability

## Phase 5 - M365 扩展

- Calendar
- OneDrive
- SharePoint
- Teams
