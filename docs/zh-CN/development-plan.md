[English](../development-plan.md) | **简体中文**

# 开发计划

## 当前交付顺序

1. 完成 P0 发布加固门禁。自动化 CI 与镜像门禁已经实现；仍需记录 WorkBuddy
   真实成功路径和失败路径的验收证据。
2. 将 Windows 本地模式集成构建推进到 Release Candidate：验证真实 Entra
   公共客户端登录和真实邮箱、对齐剩余 Tool 契约、判断是否需要 WAM、增加代码
   签名，并发布稳定下载资产。
3. 本地运行时基础通过验收后，再继续更丰富的附件处理和 M365 扩展。

P0 自动化部分由 GitHub Actions 执行；WorkBuddy 与 Windows/Entra 真实验收
不能由单元测试替代，仍然是发布门禁。创建 Stable Tag 前，必须在
[v0.1.0 发布检查清单](release-checklist.md)中记录自动化与真实验收证据。

## Windows 本地模式实现状态

首个集成实现位于 `windows/M365Mcp.Local`，使用方式见
[Windows 本地模式指南](windows-local.md)。

集成分支已完成：

- .NET 8 NativeAOT 自包含 Windows x64 可执行文件
- GitHub Actions 单文件产物检查和无 Runtime 隔离烟测
- 由 Agent 作为子进程启动的 MCP stdio Server
- 面向独立 Entra Public Client 的系统浏览器授权码 + S256 PKCE
- 当前用户 DPAPI 保护的刷新状态，以及不持久化的 `--ephemeral` 模式
- 十个有边界的邮件工具，包括创建草稿和发送草稿
- 明确不进行任意附件文件写入

剩余发布门禁：

- 真实 Public-client 登录、重启/刷新、登出和真实邮箱验收
- WorkBuddy 或目标 Agent 配置与生命周期验收
- 对丰富附件提取和下载行为做功能对齐决策
- Authenticode 签名、恶意软件扫描、Provenance/SBOM 和 Stable Release 发布
- 根据真实部署证据判断系统浏览器 PKCE 是否足够，或是否需要 Windows Web
  Account Manager

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
