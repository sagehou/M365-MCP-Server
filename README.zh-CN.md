[English](README.md) | **简体中文**

# M365 MCP Server

## 开始使用

| 运行方式 | 指南 | 交付形式 |
| --- | --- | --- |
| 服务器 | [服务器版](docs/zh-CN/mcp-server.md) | Python 容器、HTTPS Streamable HTTP、Entra/OBO，可选浏览器 OAuth |
| Windows 本地 | [本地版：.NET 与 Go](docs/zh-CN/windows-local.md) | 单用户 EXE、浏览器 PKCE、stdio；Go 另提供本机鉴权 HTTP |

可选 AI 工作流：[安装通用 m365-mail Skill](workbuddy/skills/m365-mail/README.zh-CN.md)，
服务器版、.NET 和 Go 连接共用。

## 邮件能力

- 通过委托 `/me` 权限搜索、读取登录用户的 Outlook 邮箱。
- 创建纯文本草稿、添加附件，并在客户端执行确认或受限授权后发送。
- 标记已读/未读、归档、移动、设置分类。
- 读取有界的附件文本；各版本的提取格式和下载能力统一列在对应指南中。
- 两种本地版通过 `mail_save_attachment` 流式保存原附件：默认 Windows 下载目录下的
  M365-MCP，可选 `download_dir` 覆盖，默认上限 150 MiB 且可配置，无需浏览器或 Shell。

服务器默认提供 11 项工具，启用服务器管理的 OAuth 后为 13 项；.NET 本地版为 12 项，
Go 本地版为 13 项。

## 发布

[下载 v0.1.7](https://github.com/sagehou/M365-MCP-Server/releases/tag/v0.1.7)。

| 产物 | 名称 |
| --- | --- |
| 容器镜像 | `ghcr.io/sagehou/m365-mcp-server:v0.1.7` |
| .NET NativeAOT，Windows x64 | `m365-mcp-windows-local-amd64.exe` |
| Go，Windows x64 / ARM64 | `m365-mcp-windows-local-go-amd64.exe`、`m365-mcp-windows-local-go-arm64.exe` |
| Go 双语指南压缩包 | `m365-mcp-windows-local-go-amd64.zip`、`m365-mcp-windows-local-go-arm64.zip` |
| 双语通用邮件 Skill | `m365-mail-skill.zip` |

Release 包含 SHA-256 校验文件及说明中的 EXE 哈希。三个 EXE 均提供 GitHub Artifact
Attestation。两套本地版内置同一个公开 Client ID，也支持自建应用，配置步骤统一写在
本地版指南中。

## 开发

测试、依赖审计、容器构建和 Windows 构建全部通过 GitHub Actions 执行。编辑环境不得
创建测试虚拟环境、安装测试依赖或执行本地测试/构建。

<details>
<summary>ⓘ 开发参考与发布记录</summary>

- [架构](docs/zh-CN/architecture.md)
- [工具契约](docs/zh-CN/tool-spec.md)
- [安全设计](docs/zh-CN/security.md)
- [开发计划](docs/zh-CN/development-plan.md)
- [发布验收清单](docs/zh-CN/release-checklist.md)
- [v0.1.7 发布说明](docs/zh-CN/releases/v0.1.7.md)

后续工作包括搜索翻页、回复/转发、HTML 撰写、OCR、共享邮箱、企业策略能力，以及
Calendar/OneDrive/SharePoint/Teams。Windows Authenticode 签名和可选 WAM 集成也属于
后续事项。

</details>

## 许可证

源代码和文档使用 [MIT 许可证](LICENSE)，第三方依赖仍适用其各自许可证。

---

真实租户同意和客户端行为需在部署环境验收。Windows EXE 尚未签名；哈希和来源证明
不保证杀毒软件放行。更新日期：2026-11-12。
