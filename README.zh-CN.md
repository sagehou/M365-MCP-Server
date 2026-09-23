[English](README.md) | **简体中文**

# M365 MCP Server

一个自托管的 Microsoft 365 MCP Gateway，采用受控工具面、Microsoft Entra
委托身份和按用户隔离，并重点保护 Outlook 邮件与附件处理边界。

> **发布状态：**请在 [GitHub Releases](https://github.com/sagehou/M365-MCP-Server/releases)
> 查看已发布的 `v0.1.0` 产物。CI 覆盖 Container Image 与 Windows x64 NativeAOT
> EXE。维护者报告核心流程已通过真实客户端验收；受限自动发送尚未完成真实客户端
> 测试，具体部署启用前必须验收。

## 当前已经可用

### 远端 MCP Server

- FastMCP Streamable HTTP Endpoint：`/mcp/`。
- Microsoft Entra Bearer Token 校验，并执行 Tenant 与 Scope 约束。
- 通过 On-Behalf-Of（OBO）使用 Microsoft Graph 委托权限。
- 每个请求独立绑定用户身份；Graph 调用被限制在 `/me`。
- 可选的 OAuth Discovery、Dynamic Public-client Registration、Interactive
  Sign-in、S256 PKCE、加密 Refresh Session、Rotation 和 Replay Rejection。
- `workbuddy/` 中提供 WorkBuddy Connector Package，CI 覆盖完整的 Mock
  Client Flow。
- 结构化脱敏 Audit Event；安全错误会返回可关联的 Event ID。

### Windows 本地 EXE

Windows x64 NativeAOT 本地 Runtime 已纳入 v0.1.0 Release 目标。
Release 流程会发布：

- `m365-mcp-windows-x64.exe`
- SHA-256 校验文件
- GitHub Artifact Attestation 来源证明

目标机器无需安装 Python、.NET Runtime、Docker 或安装器。Authenticode
签名属于后续加固项。

## 发布与验证状态

| 范围 | 状态 |
|---|---|
| Python 测试与双语文档检查 | GitHub Actions 执行 |
| Production Docker Image 构建 | CI 覆盖 |
| Container Health Smoke Test | CI 覆盖 |
| Docker Compose 校验 | CI 覆盖 |
| Windows NativeAOT EXE 构建 | CI 覆盖 |
| Windows SHA-256 与 Provenance Attestation | 纳入 v0.1.0 Release 流程 |
| 真实 WorkBuddy 与真实邮箱验收 | 维护者报告除受限自动发送外已完成；记录保存在仓库外 |
| 稳定版 `v0.1.0` GitHub Release | 见 [Releases 页面](https://github.com/sagehou/M365-MCP-Server/releases) |

GitHub Actions 是本仓库唯一的构建与测试环境。

## 尚未实现

- 真实 Client 与真实 Tenant 的发布验收。
- Search Continuation Cursor 与 Folder Discovery。
- Reply、Forward 工作流，以及 HTML 和附件撰写。
- OCR、Shared Mailbox、RBAC、Read-only Mode、Dynamic Tool Exposure 和 Rate
  Limiting。
- Calendar、OneDrive、SharePoint 和 Teams。
- Windows EXE 的 Authenticode 签名与 Clean VM 验收；可选 WAM 评估与本地富文档附件解析。

发布前请阅读 [v0.1.0 发布检查清单](docs/zh-CN/release-checklist.md)。

## 许可证

项目源代码与文档按 [MIT 许可证](LICENSE)发布。第三方依赖仍适用其各自的许可证。
