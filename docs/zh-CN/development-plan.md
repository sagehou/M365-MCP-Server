[English](../development-plan.md) | **简体中文**

# 开发计划

## 当前交付顺序

1. `v0.1.7` 按 MIT 许可证交付容器镜像、Windows .NET/Go 单文件 EXE 及通用双语
   `m365-mail` Skill。
2. 草稿文件附件能力已包含在 v0.1.1：远端客户端可用二进制暂存和一次性推送
   凭据，Windows 本地 stdio 可用受限的产物相对路径或原生文件选择框，单文件
   最多 20 MiB。
3. 后续范围包括丰富附件提取、Search 翻页、回复与转发及更广泛的 M365 工作负载。
   签名和杀毒误报处理属于独立的 Windows 分发事项。

每个部署的验收记录保存在源码仓库之外。

## Windows 本地模式实现状态

已发布的 Windows 实现位于 `windows/M365Mcp.Local` 和 `native`，使用方式见
[Windows 本地模式指南](windows-local.md)。

v0.1.0 已交付：

- .NET 8 NativeAOT 自包含 Windows x64 可执行文件
- GitHub Actions 单文件产物检查和无 Runtime 隔离烟测
- 由 Agent 作为子进程启动的 MCP stdio Server
- 面向独立 Entra Public Client 的系统浏览器授权码 + S256 PKCE
- 当前用户 DPAPI 保护的刷新状态，以及不持久化的 `--ephemeral` 模式
- 十个有边界的邮件工具，包括创建草稿和发送草稿
- 明确不进行任意附件文件写入

v0.1.1 新增：

- 11 个本地邮件工具，包括受限的草稿文件附件
- `M365_ATTACHMENT_ROOT` 下的相对路径附件自动化
- 远端 Connector 使用的 `inspect-attachment` 和 `push-attachment` 命令

v0.1.2 起陆续新增：

- .NET 10 NativeAOT 与 Go AMD64/ARM64 单文件；共用 `stdio` 及租户/账户选项
- Go PDF/Office 提取及临时下载 URL
- 两版均通过 `mail_save_attachment` 流式保存原附件；v0.1.7 默认 Windows 下载目录下
  的 M365-MCP，可选 `download_dir`、自动创建目录，默认上限 150 MiB 且可配置

当前设计边界：

- .NET 读取 UTF-8 文本/CSV/JSON/XML，没有 PDF/Office 解析器或下载 URL 端点；两版
  均可直接保存原文件
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

Windows Go 实现上述全部项目；.NET 不提供 `mail_download_attachment`，其
`mail_read_attachment` 限于有边界的 UTF-8 文本类内容。两版另提供
`mail_save_attachment` 和有大小限制的草稿附件。

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
