[English](../review-status.md) | **简体中文**

# 实现复核

## 实现范围

| 版本 | 接入方式 | 工具 | 附件读取 |
| --- | --- | --- | --- |
| Python 服务器版 | 认证的 Streamable HTTP | 11 个核心工具；开启 OAuth 后另提供下载及上传授权工具 | 在隔离的 Linux Worker 中解析 PDF、DOCX、XLSX、PPTX、TXT、Markdown |
| Windows .NET 版 | stdio | 11 个邮件工具 | 有大小限制的 UTF-8 文本、JSON、CSV、XML |
| Windows Go 版 | stdio；带认证的本机回环 Streamable HTTP | 12 个邮件工具，包含本机下载 | 在 Windows Job Object Worker 中解析 PDF、DOCX、XLSX、PPTX、TXT、Markdown |

三套实现均支持纯文本草稿及最多 20 MiB 的草稿附件。发送结果只表示 Graph 已接受请求，
不表示已送达；逐封确认或受限自动化授权仍由客户端或 Agent 负责。搜索只返回一个有边界的
分页；续页游标、回复、转发、共享邮箱、OCR、Calendar、Drive、SharePoint、Teams 尚未实现。
最新已发布版本为 `v0.1.3`；本次复核对应
[PR #60](https://github.com/sagehou/M365-MCP-Server/pull/60) 中的源码变更。

## 发现与修正

- .NET 的关键词加日期查询改为在 KQL 中组合日期；仅日期查询使用 OData 过滤及收件时间排序。
  拒绝不带时区的日期和类型错误的可选参数。
- .NET 允许使用空分类数组清空分类；为草稿文本、收件人、资源 ID、MIME 类型补充明确的校验和边界。
- .NET 列出附件时只请求元数据，避免下载文件内容；Graph 返回异常数据、JSON-RPC 请求格式错误时，
  返回错误并保持 stdio 继续可用。
- .NET 拒绝格式错误的令牌响应和无效有效期，限制加密状态文件读取大小，并在浏览器显示登录成功前保存状态。
- 删除未使用的 Python `MailService.list_messages` 包装、`tenant_id` 配置字段、未使用导入，
  以及从未被赋值的 .NET 用户资料字段。移除实际不可用的第 1 版缓存解析分支；旧缓存不可读时需
  退出并重新登录，有效的第 2 版缓存保持兼容。
- 更新 Python 直接及传递依赖。容器改用应用系统安全更新的 Alpine，去掉存在未修复公告且应用
  不需要的 Debian 工具，安装完成后移除 `pip`、`uv`。详见[依赖审计](runtime-dependency-audit.md)。

OAuth 服务、附件 Worker、令牌提供器接口及非 Windows Go 适配代码都有实际调用或平台/测试用途，
予以保留。两套 HTTP 客户端均有用途：项目 Graph/OIDC 请求使用 `httpx`，FastMCP/MCP 使用
`httpx2`。历史发布修复流水线继续作为明确的手动工具保留。

## GitHub Actions 验证

PR 检查覆盖以下路径；CI、测试镜像发布和稳定版发布使用各自产物所需的依赖与安全检查。

| 检查 | 覆盖范围 |
| --- | --- |
| Python 测试及 `pip-audit` | 应用工厂、两代 MCP 协议、全部核心邮件工具、身份隔离、JWT/OBO、OAuth 发现/PKCE/刷新轮换/重放防护、上传下载句柄及 Worker 限额 |
| Ruff、Vulture | 未使用导入、未定义名称、重复定义、不可达代码及置信度 100% 的未使用变量；三个 SDK 协议关键字参数使用逐行排除标注 |
| Docker 烟测及 Trivy | 安装后的确切非 root 镜像、健康检查、认证、OAuth 存储、附件 Worker、Compose；阻止所有严重程度的已知容器问题，包括尚无修复的项目 |
| Windows .NET 功能检查 | 通过 stdio 和模拟 Graph 覆盖全部 11 个工具，日期/搜索/分类/草稿校验，小附件及分块上传，错误脱敏、不重放结果不明确的写操作，DPAPI 绑定/临时状态、刷新及异常令牌响应 |
| Windows .NET 产物 | NativeAOT 单文件、Windows 详细信息、默认及覆盖 Client ID、PATH 无运行时时的启动 |
| Windows Go 检查 | Windows/Linux 竞态测试、模块校验、vet、应用不可达函数检查，以及 Windows AMD64/ARM64 漏洞分析 |
| Windows Go 产物 | AMD64/ARM64 单文件构建、详细信息、ZIP/校验值、AMD64 无外部运行时启动 |

---

已知漏洞扫描和静态分析反映被检查的快照，不能证明缺陷或漏洞绝对为零。这些检查未验证真实租户同意、真实 Graph 投递、目标 Agent 集成、Windows ARM64 实机运行、交互式文件选择框及杀毒/代码签名信任。本次未在本地测试、构建、安装依赖或创建虚拟环境。更新日期：2026-11-11。
