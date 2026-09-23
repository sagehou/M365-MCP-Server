[English](README.md) | **简体中文**

# M365 MCP Server

一个自托管的 Microsoft 365 MCP Gateway，采用受控工具面、Microsoft Entra
委托身份和按用户隔离，并重点保护 Outlook 邮件与附件处理边界。

> **已发布：**[`v0.1.0`](https://github.com/sagehou/M365-MCP-Server/releases/tag/v0.1.0)
> 已按 MIT 许可证发布。CI 验证了 Container Image 与 Windows x64 NativeAOT
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

Windows x64 NativeAOT 本地 Runtime 已包含在 v0.1.0 中。Release 提供：

- `m365-mcp-windows-x64.exe`
- SHA-256 校验文件
- Release 说明中的 MD5 和 SHA-1，供按精确文件哈希加杀毒软件白名单
- GitHub Artifact Attestation 来源证明
- `LICENSE` 许可声明文件（不是运行依赖）

目标机器无需安装 Python、.NET Runtime、Docker 或安装器。Authenticode
签名属于后续加固项。如安全软件隔离未签名 EXE，请按
[误报处置说明](docs/zh-CN/windows-local.md#杀毒软件误报)处理；Checksum 与
Attestation 可核验来源，但不会覆盖杀毒软件的判定。
MD5 和 SHA-1 仅用于兼容旧式白名单表单，不是可信性验证；EXE 改变后须重新计算
哈希并审核白名单。

## 发布与验证状态

| 范围 | 状态 |
|---|---|
| Python 测试与双语文档检查 | GitHub Actions 执行 |
| Production Docker Image 构建 | CI 覆盖 |
| Container Health Smoke Test | CI 覆盖 |
| Docker Compose 校验 | CI 覆盖 |
| Windows NativeAOT EXE 构建 | CI 覆盖 |
| Windows SHA-256 与 Provenance Attestation | 已随 v0.1.0 发布并核验 |
| 真实 WorkBuddy 与真实邮箱验收 | 维护者报告除受限自动发送外已完成；记录保存在仓库外 |
| 稳定版 `v0.1.0` GitHub Release | [已发布](https://github.com/sagehou/M365-MCP-Server/releases/tag/v0.1.0) |

GitHub Actions 是本仓库唯一的构建与测试环境。

## 后续工作

- 受限自动发送的真实验收。
- Search Continuation Cursor 与 Folder Discovery。
- Reply、Forward 工作流，以及 HTML 和附件撰写。
- OCR、Shared Mailbox、RBAC、Read-only Mode、Dynamic Tool Exposure 和 Rate
  Limiting。
- Calendar、OneDrive、SharePoint 和 Teams。
- Windows EXE 的 Authenticode 签名与 Clean VM 验收；可选 WAM 评估与本地富文档附件解析。

部署前请阅读 [v0.1.0 发布检查清单](docs/zh-CN/release-checklist.md)和
[发布说明](docs/zh-CN/releases/v0.1.0.md)。

## 许可证

项目源代码与文档按 [MIT 许可证](LICENSE)发布。第三方依赖仍适用其各自的许可证。
