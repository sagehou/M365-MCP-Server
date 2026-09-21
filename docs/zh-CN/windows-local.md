[English](../windows-local.md) | **简体中文**

# Windows 本地单文件版本路线图

## 决策

完成 v0.1 发布加固门禁后，下一条交付线是 Windows 本地 MCP Server。在该交付线通过验收前，不开始 Calendar、Drive、SharePoint 和 Teams 扩展。

本地 Server 与 Agent 运行在同一台 PC。Agent 把 Server 作为子进程启动，并通过 MCP stdio 通信。Agent 与本地 Server 之间不使用 HTTP、OAuth、JWT、OBO、Client Secret 或证书。

Microsoft Graph 使用独立的 Desktop/Public Client App 和委托权限。Windows Web Account Manager（WAM）为首选认证方式，系统浏览器 Authorization Code + PKCE 为回退方式。远端 Server 现有的 Confidential Client 与 OBO 流程保持不变。

## 分发约束

- 用户只获取并运行一个 `m365-mcp.exe`。
- Python、原生扩展和应用模块必须直接从 EXE 加载，不能在临时目录解压 Runtime Tree。
- 首选验证 PyOxidizer。会在运行时解包的 PyInstaller/Nuitka One-file 不视为满足本约束。
- 正常 stdio 运行不得创建 Service、Registry、Scheduled Task、Startup Entry、日志文件或 Runtime 解压目录。
- 诊断信息只写 `stderr`；`stdout` 只能输出 MCP 消息。
- 持久模式最多创建一个有明确说明、受 DPAPI 保护的 `%LOCALAPPDATA%\M365-MCP-Server\state.bin`。
- `--ephemeral` 不得持久化认证或应用状态。
- 安装系统服务只能由显式兼容命令触发，不能成为正常运行的副作用。

## 交付顺序

### P0 — 发布加固

- Linux Workflow 固定到 `ubuntu-24.04`，Action 升级到兼容 Node 24 的主版本。
- 断言工具失败响应中的 Reference 与安全审计事件 ID 完全一致。
- 发布首个稳定服务端版本前，完成真实 WorkBuddy、真实邮箱、双用户、重启和跨租户验收。

### W0 — 打包可行性

- 增加仅 Windows 使用的可选依赖/构建 Profile，不扩大远端容器的 Runtime Surface。
- 只在 GitHub Actions 构建 x64 EXE。
- 验证 `cryptography`、`pydantic-core`、`lxml`、FastMCP、MSAL 和受支持附件解析器可从内存加载。
- 在 PATH 中没有 Python 的干净 Windows Runner 上运行 EXE。
- 正常退出或强制终止后只要残留 Runtime 解压产物，门禁即失败。

### W1 — 本地 Runtime 边界

- 增加明确的 `stdio` 入口；现有 HTTP 入口调整为 `serve`。
- Tool 通过注入获得认证用户上下文，不再在 Tool 内部直接读取 FastAPI Request。
- 引入 Graph Token Provider 边界，让远端 OBO 和本地 Public Client 复用同一套有边界的 Graph/Mail Service。
- 两种模式都保留 `/me` 路径约束、响应大小限制、脱敏、审计关联、写操作不确定性警告和附件隔离。

### W2 — Windows 委托认证

- 使用 MSAL `PublicClientApplication`，不得分发 Client Secret 或私钥。
- 优先使用当前 Windows 用户的 WAM，系统浏览器 PKCE 作为回退。
- 可选持久 Token Cache 使用 Current-user DPAPI，并放入唯一的 `state.bin`。
- 支持 `login`、`logout`、`status`、`doctor`、`stdio` 和 `--ephemeral`。

### W3 — 签名发布

- 仅通过 GitHub Actions 和固定 Windows Runner 生成 EXE。
- 增加 Authenticode 签名、时间戳、SHA-256 校验和 SBOM。
- 将实际通过 Smoke Test 的同一个 EXE 作为 GitHub Release Asset 发布。
- 提供使用绝对 EXE 路径与 stdio 的 Agent 配置说明。

## 验收门禁

在没有安装 Python、Docker、Git 或开发工具的干净 Windows x64 VM 上：

1. 单个 EXE 以 MCP stdio Server 启动，并列出预期邮件工具。
2. 第一次访问 Graph 时登录当前 Windows 用户且不需要应用密钥；选择持久模式后，后续调用使用受保护 Cache。
3. 使用委托权限对真实邮箱完成搜索、读取、附件解析和一个代表性写操作。
4. EXE 不创建未声明文件或系统改动；持久模式只创建约定的状态文件，临时模式不留下状态。
5. Token、邮件正文、附件内容和 Provider Error Detail 不得进入日志、stderr 诊断或 MCP Error Text。
6. 远端/容器回归保持绿色，证明本地模式没有削弱 HTTP/OBO 隔离。

## 停止条件

如果必需的原生扩展不能可靠地从 EXE 加载，必须替换不兼容依赖，或使用 Windows 原生技术实现本地 Host。不得静默引入 Runtime 解压并将其描述为真正的单文件构建。
