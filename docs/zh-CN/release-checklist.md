[English](../release-checklist.md) | **简体中文**

# v0.1.0 发布检查清单

目标：

- Project Version：`0.1.0`
- Git Tag：`v0.1.0`
- Container Platform：`linux/amd64`
- Stable Image：`ghcr.io/sagehou/m365-mcp-server:v0.1.0`
- Windows Asset：`m365-mcp-windows-x64.exe`

以下所有 Tag 前检查项必须有证据，之后才能创建或推送 Stable Tag。证据中不得保存
Token、Secret、邮件正文、附件内容或未经脱敏的 Tenant/User Identifier。

## 1. 已 Review 的 Candidate

- [ ] Release Preparation PR 已合并到 `main`。
- [ ] 已记录 Candidate Commit 的完整 SHA。
- [ ] Required PR Check 全部为绿色。
- [ ] `pyproject.toml` 中的版本是 `0.1.0`。
- [ ] 仓库 `LICENSE` 与 Python 包元数据均声明 MIT 许可证。
- [ ] 中英文 `v0.1.0` Release Notes 已 Review。
- [ ] 支持范围和已知限制与 README 一致。

证据：

- Candidate SHA：
- PR / Checks URL：
- Reviewer：
- 日期（UTC）：

## 2. 真实 WorkBuddy OAuth

使用全新 WorkBuddy Profile 和 Candidate Deployment。

- [ ] Protected Resource Metadata Discovery 成功。
- [ ] Authorization Server Metadata Discovery 成功。
- [ ] Dynamic Client Registration 成功。
- [ ] Entra Interactive Sign-in 通过注册的 WorkBuddy Callback 完成。
- [ ] MCP 初始化成功并列出预期的十一个 Mail Tool。
- [ ] Token 过期后成功 Refresh，并执行一次性 Rotation。
- [ ] 旧 Refresh Token Replay 被拒绝。
- [ ] Server 重启后认证状态仍然可用。
- [ ] 用户不需要手工复制或粘贴 Bearer Token。

证据：

- WorkBuddy Version：
- Candidate Deployment Identifier：
- 已脱敏 Audit/Event Reference：
- Result/Evidence URL：
- Tester 与日期（UTC）：

## 3. 身份隔离

使用两个真实用户；跨租户验证需要两个真实 Tenant。

- [ ] User A 只能访问 User A 的邮箱。
- [ ] User B 只能访问 User B 的邮箱。
- [ ] 并发 Session 不发生 Identity 串线。
- [ ] Caller 不能选择其他用户的邮箱。
- [ ] Tenant A 与 Tenant B 保持隔离。
- [ ] OBO 使用当前 Caller 的 Tenant。
- [ ] Session、Refresh Token 和 Cache 不跨用户或跨 Tenant。

证据：

- 脱敏后的 Account/Tenant Label：
- 已脱敏 Audit/Event Reference：
- Result/Evidence URL：
- Tester 与日期（UTC）：

## 4. 真实邮箱与附件

- [ ] Search 和 Message Read 成功。
- [ ] 一个代表性写操作成功，并在邮箱中确认结果。
- [ ] `mail_create_draft` 按已审核的纯文本收件人、主题和正文创建 Draft，且没有
  发送邮件。
- [ ] 交互模式另行取得明确确认后才调用 `mail_send_draft`；邮件只在 Sent Items
  中出现一次，并且受控测试收件人只收到一次。
- [ ] 自动化模式记录的授权包含收件人/域名、触发条件、内容规则与可信数据源、单次
  和每日限额以及到期时间；一封符合策略的 Draft 无需逐封提示即可发送。
- [ ] 收件人越界、内容改变、超过限额或授权过期时，在 `mail_send_draft` 前停止
  并请求确认。
- [ ] 发送结果不明确时没有自动重试。
- [ ] 验证 PDF、DOCX、XLSX、PPTX、TXT、ZIP 和普通 Binary Attachment。
- [ ] 超大和不支持的附件安全失败。
- [ ] Metadata `size` 与解码后的 `content_length` 正确。
- [ ] Parser Timeout/Crash 不会终止 Server。
- [ ] Download Link 只能使用一次并会过期。
- [ ] Server 重启后旧 Download Link 失效。
- [ ] Error 中的安全 Reference 精确对应一个 Audit Event。
- [ ] Token、Provider Body、邮件正文和附件内容不会泄漏到 Client Error 或
  Diagnostics。

证据：

- 脱敏后的 Test-message Identifier：
- 已脱敏 Audit/Event Reference：
- Result/Evidence URL：
- Tester 与日期（UTC）：

## 5. 创建并验证 Release

完成第 1–4 节后执行：

```bash
git switch main
git pull --ff-only origin main
git tag -a v0.1.0 -m "M365 MCP Server v0.1.0"
git push origin v0.1.0
```

Tag Workflow 必须完成：

- [ ] Tag / Version / Ancestry Validation 通过。
- [ ] 双语文档检查通过。
- [ ] Python Test Suite 通过。
- [ ] 精确 Production Image 构建成功并通过 Health Smoke Test。
- [ ] Compose Validation 通过。
- [ ] Windows x64 NativeAOT EXE 构建成功，并通过最终 Release Smoke Test。
- [ ] `m365-mcp-windows-x64.exe.sha256` 能正确校验已发布 EXE。
- [ ] `m365-mcp-windows-x64.exe` 已生成 GitHub Artifact Attestation，且可验证来源为本仓库。
- [ ] GHCR 包含 `v0.1.0`、`0.1.0`、`0.1` 和 `latest`。
- [ ] GitHub Release `v0.1.0` 已创建，并包含 Review 后的 Notes 与两个 Windows Release Asset。
- [ ] 如果 Package 预期公开，Anonymous `docker pull` 成功。
- [ ] 部署的 Image Digest 与已发布 Candidate 一致。

证据：

- Tag Workflow URL：
- GitHub Release URL：
- GHCR Digest：
- Windows EXE SHA-256：
- Windows Attestation 验证结果：
- Anonymous Pull Result：
- Release Operator 与日期（UTC）：

## 失败处理

不得移动或覆盖 `v0.1.0`。如果发布只完成了一部分，应保留日志、明确标记不完整
Release、在 `main` 修复 Workflow，并发布新的 Patch Version。不得用 Mock Evidence
替代失败的真实 Client Gate。
