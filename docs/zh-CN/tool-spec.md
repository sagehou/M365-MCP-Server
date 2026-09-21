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
`draft_id` 和 `created=true`。Caller 必须先展示完整草稿供用户审核，再另行取得
明确发送确认。

### mail_send_draft

只在用户另行明确确认后，按 `draft_id` 发送一封现有草稿。
`send_accepted=true` 表示 Microsoft Graph 已接受请求；
`delivery_confirmed=false` 明确表示尚未证明最终投递成功。对结果不明确的失败
不得自动重试。

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
