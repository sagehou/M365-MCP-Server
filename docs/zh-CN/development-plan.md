[English](../development-plan.md) | **简体中文**

# 开发计划

## 当前交付顺序

1. `v0.1.0` 已按 MIT 许可证[发布](https://github.com/sagehou/M365-MCP-Server/releases/tag/v0.1.0)，
   包含经测试的容器镜像和 Windows 单文件 EXE。维护者将 WorkBuddy 与邮箱真实
   验收记录保存在仓库外。
2. 完成发布后加固：具体部署启用受限自动发送前进行真实测试，在 Clean VM 验证
   Windows EXE，推进杀毒误报申诉与签名，并决定是否需要 WAM。
3. 本地运行时基础通过验收后，再继续更丰富的附件处理和 M365 扩展。

自动化发布流程已在 GitHub Actions 通过。维护者报告核心 WorkBuddy 与邮箱真实
检查已通过；受限自动发送仍是具体部署的门禁，不能宣称已经完成真实测试。区别见
[v0.1.0 发布检查清单](release-checklist.md)。

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

后续加固与部署检查：

- 已发布 EXE 在 Clean VM 的 Public-client 登录、重启/刷新、登出与真实邮箱验收
- 受支持 PC 上目标 Agent 的配置与生命周期验收
- 对丰富附件提取和下载行为做功能对齐决策
- 杀毒误报申诉、可选 Authenticode 签名和 SBOM；SHA-256 与 GitHub 构建来源
  证明已经发布
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
