[English](../review-status.md) | **简体中文**

# 实现复核跟进

## 已修正问题

- 配置：环境变量模板中的空替代凭据；Runtime Limit 必须为正且有边界；Required Scopes 不允许为空。
- 身份认证：Signing Key Rollover Refresh，并设置一分钟 Miss Cooldown；补充 Signature/Audience/Issuer/Expiry/Application-token 负向测试。
- Runtime：每个请求使用 Stateless MCP HTTP Identity；OBO 移出 Event Loop；补充 initialize、tools/list 和两个并发用户 tools/call 集成测试。
- Graph/Mail：分离 KQL Search 与 OData Filtering；Move/Archive 后保留新 ID；不重放语义不明确的写操作；不缩短 Retry-After；拒绝 Path Traversal 并限制 Response Bytes。
- Audit：默认 Logging 下输出真实 JSON Event，包含 Timestamp 与 Identity；进入 Framework 前清理错误信息。
- Attachments：列表只返回 Metadata；增加 Pre-decode / Expanded Archive Limits；Parser 使用受监督的进程，并配置 Resource、Timeout 和 Cancellation Limits。
- Delivery：从 Docker Context 排除 Credentials；测试可配置端口 Health Check、Non-root Worker Startup；Compose 私有绑定，并在发布前 Smoke-test 精确镜像。
- 发布加固：固定 Hosted Runner 和 Action 主版本；验证安全 MCP Error Reference 与
  Audit Event ID 完全一致；将接受的日期输入明确为带时区的 ISO 8601 Timestamp。
- 发布交付：要求 Tag 与 Project Version 一致并存在双语 Notes；Smoke-test 精确
  Linux x64 Image、校验 Compose、发布明确的 Semantic Image Tag，并只在 Image
  发布后创建 GitHub Release。
- 本地 Runtime 基础：使用 Provider Interface 隔离 Graph Token 获取，并允许 Tool
  身份上下文在没有 HTTP Request 时注入；现有 HTTP/OBO 行为仍是托管 Runtime。
- OAuth 完成页体验：WorkBuddy Callback 使用 No-store、CSP 保护的完成页启动
  Private Callback URI，尝试自动关闭标签页，从可见浏览器历史中移除 Callback
  参数，并保留手动返回入口；Loopback 与 HTTPS Client 仍使用正常 Redirect。
- Windows 本地集成构建：增加 .NET 8 NativeAOT MCP stdio Host，支持 Public-client
  PKCE 登录、当前用户 DPAPI 状态、Ephemeral Mode、十个有边界的邮件工具，以及
  CI 生成的单个 Windows x64 可执行文件。

## CI 能证明什么

Unit Tests 和 Integration Tests 使用 Mocked Entra Metadata、OBO 和 Graph
Transport，对真实 ASGI/FastMCP Stack 进行测试。Mock WorkBuddy Client Flow
会从 401 Discovery Challenge 开始，依次覆盖 DCR、S256 Authorization、Entra
Callback、Local Token Exchange、Authenticated MCP Initialization、
Refresh-token Rotation 以及刷新后的再次认证调用。Connector Package Tests
还会检查官方目录结构、无嵌入凭据的 OAuth 模式和四个最小权限 Skills。
Docker Smoke Test 使用安装后的 Non-root Production Image。构建和测试全部在
GitHub Actions 执行。

Windows Workflow 只在 Publish Directory 恰好包含一个 `m365-mcp.exe` 时发布
NativeAOT 集成产物。隔离烟测只在 `PATH` 中保留 Windows 系统目录，执行
`doctor --ephemeral`、MCP `initialize` 和 `tools/list`，核对预期的十个
Tools，并检查隔离 Data Root 没有产生文件。

这些测试不会读取或修改生产邮箱数据。CI 能证明 Artifact 形态与 Mock/Protocol
行为，但不能证明真实 Tenant Consent、真实 Graph 行为、代码签名信任或目标
Agent 兼容性。

## 生产前仍需完成

- 选择并发布第一个批准的 Release Version；验证 GHCR Visibility 与 Pull Access。Docker Build 成功不等于已经发布镜像。
- 配置 Entra Applications/Consent，并使用两个真实用户、受支持 MCP Clients、Certificate 或 Secret Credential 以及代表性附件做验证。
- OAuth Discovery、Dynamic Public-client Registration、MSAL Interactive Authorization、S256 PKCE、一次性 Local Authorization-code Exchange，以及带 Rotation/Replay Prevention 的 Persistent Encrypted Refresh Session 已在默认关闭的 Feature Flag 后实现；WorkBuddy Connector 与 CI Client-flow Coverage 也已提供。真实 WorkBuddy Automatic Sign-in/Refresh、Restart、真实邮箱与跨租户验收仍是兼容 WorkBuddy 的 v0.1 Release Blocker。
- Search 只返回一个有边界的 Page 和 `next_link` Hint，不是全邮箱导出。Tool 当前还不接受 Continuation Cursor。Keyword Search 受 Graph Search Ordering/Result Limits 约束；仅日期查询使用 Received Time。
- 已实现纯文本 Draft 创建和发送。Client/Agent 层必须逐封确认或具有明确的受限
  自动化授权。v0.1 契约有意不提供一步式 Direct Send、HTML/附件撰写和自动重试。
- OCR、Reply、Forward、Shared Mailboxes、Enterprise RBAC / Rate Limiting /
  Observability、Calendar、Drive、SharePoint 和 Teams 仍属于 Roadmap。
- Windows EXE 目前是未签名的 Integration Artifact，而不是 Stable Release。
  真实 Public-client 登录、Refresh/Restart/Logout、真实邮箱 Tools、目标 Agent
  生命周期、Authenticode 签名、扫描、Provenance/SBOM 和 Stable Release 发布
  仍未完成。
- Windows 本地模式有意不提供 `mail_download_attachment` 和丰富二进制文档提取。
  它不会安装 Windows Service：stdio 进程由 Agent 启动并管理。Service Mode
  需要独立 IPC 与安全设计。

Tasks 001–007 或本次 Review 都不能把上述待办视为已完成。
