[English](../development-plan.md) | **简体中文**

# 开发计划

## 当前交付顺序

1. 先完成 P0 发布加固门禁：固定 CI 运行环境和 Actions 主版本、精确关联审计错误
   事件，以及 WorkBuddy 真实成功路径和失败路径的验收证据。
2. P0 之后立即交付 Windows 本地模式。它与 Agent 同机、通过 MCP stdio 通信，
   使用公共客户端方式登录 Microsoft Graph，并以不产生解压目录的真正单文件程序
   交付。详见 [Windows 本地模式路线图](windows-local.md)。
3. 本地运行时基础通过验收后，再继续附件处理和更广泛的 M365 扩展。

P0 的自动化部分由 GitHub Actions 执行；WorkBuddy 真实联调不能由单元测试替代，
仍然是发布门禁。
创建 Stable Tag 前，必须在 [v0.1.0 发布检查清单](release-checklist.md)中记录
自动化与真实验收证据。

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
- mail_list_attachments
- mail_read_attachment
- mail_download_attachment
- mail_mark_read
- mail_archive
- mail_move
- mail_set_category

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
