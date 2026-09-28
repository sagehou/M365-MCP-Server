[English](../tool-spec.md) | **简体中文**

# MCP Tool 规范

## Mail Tools

### mail_search

搜索当前用户邮箱。

输入：

- query
- limit
- date range

### mail_get

获取邮件 Metadata 与 Body。

### mail_create_draft

在当前登录用户邮箱中创建一封纯文本草稿，但不发送。

输入：

- `to_recipients`：必填，至少包含一个纯邮件地址
- `subject`：必填非空文本，最多 255 个字符
- `body`：必填非空纯文本，最多 100,000 个字符
- `cc_recipients`：可选的纯邮件地址列表
- `bcc_recipients`：可选的纯邮件地址列表

每个收件人字段最多 50 个地址，一封草稿总计最多 100 个收件人。结果返回新的
`draft_id` 和 `created=true`。交互 Client 必须展示完整草稿供用户审核；自动化
必须把完整草稿与用户已经记录的受限授权逐项比较。

### mail_send_draft

在用户逐封明确确认，或已经明确授予有边界的自动化授权后，按 `draft_id` 发送
一封现有草稿。自动化授权必须约束收件人/域名、触发条件、内容生成规则与可信数据
源、获准的附件名称与内容、单次和每日发送量以及到期时间；任何越界都需要确认。

Server 只接收 `draft_id`，无法证明 Client 使用了哪种授权路径；集成 Client 或
Agent 必须在调用前执行该策略。`send_accepted=true` 表示 Microsoft Graph 已接受
请求；`delivery_confirmed=false` 明确表示尚未证明最终投递成功。对结果不明确的
失败不得自动重试。

### mail_add_draft_attachment

为现有草稿添加一个文件，不发送邮件。未发布构建的远端 Server 和 Windows
本地 EXE 均支持；不属于已发布的 v0.1.0。每个文件调用一次，随后才能调用
`mail_send_draft`。

输入为 `draft_id`、普通文件名 `name`、`content_base64` 以及可选的 ASCII
`content_type`（默认 `application/octet-stream`）。解码后单个文件须为 1 字节至
20 MiB。小于 3 MB 使用 Graph 直接添加，更大文件使用顺序分块上传。附件字节由
MCP Client 提供；两种 Runtime 都不读取任意文件路径，也不写临时附件文件。
20 MiB 文件在单次 MCP 请求中会膨胀至约 27 MiB Base64，远端反向代理须允许
高于此值的请求体。结果含 `attached=true`、`content_length`、SHA-256；Graph
通过小文件 POST 返回附件 ID 时也返回 ID（大文件结果中的 `attachment_id` 为
null），但绝不返回字节或敏感的上传 URL。失败后先检查草稿及
附件列表，再决定是否重试，因为上传结果可能不明确。

发送前核对完整草稿及 `mail_list_attachments`。交互模式的单独发送确认须包含附件；
受限自动化授权须明确限定附件来源和内容。

### mail_list_attachments

列出邮件附件。
`size` 是 Microsoft Graph 提供的 Metadata，只用于展示和选择附件，不是完整性校验值。列表操作不会为了重新计算大小而读取文件内容。

### mail_read_attachment

提取附件内容供 AI 处理。
返回的 Attachment `content_length` 是解码后的实际字节数，对本次返回内容具有权威性。不得与 Metadata-only 列表中的值比较后决定是否接受附件。

支持格式：

- PDF
- DOCX
- XLSX
- PPTX
- TXT
- Markdown

### mail_download_attachment

获取一个受大小限制的 Outlook File Attachment，并返回临时 HTTPS 下载 URL。URL 是不可猜测、单次使用且会在配置 TTL 后过期的 Capability。Attachment Bytes 只会保留在受限的 Process Memory 中，不会通过 MCP JSON 返回。
返回的 Attachment `content_length` 是解码后的实际字节数，对本次下载具有权威性。不得与 Metadata-only 列表中的值比较后决定是否接受附件。

### mail_mark_read

标记邮件为已读/未读。

### mail_archive

把邮件移动到 Outlook Archive Folder。

### mail_move

把邮件移动到其他 Folder。

### mail_set_category

更新 Outlook Categories。

## 后续 Tools

- calendar_search
- drive_search
- sharepoint_search
- teams_search
