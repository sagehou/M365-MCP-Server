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

### mail_list_attachments

列出邮件附件。
`size` 是 Microsoft Graph 提供的 Metadata，只用于展示和选择附件，不是完整性校验值。列表操作不会为了重新计算大小而读取文件内容。

### mail_read_attachment

提取附件内容供 AI 处理。
返回的 Attachment `size` 是解码后的实际字节数，对本次返回内容具有权威性。不得与 Metadata-only 列表中的值比较后决定是否接受附件。

支持格式：

- PDF
- DOCX
- XLSX
- PPTX
- TXT
- Markdown

### mail_download_attachment

获取一个受大小限制的 Outlook File Attachment，并返回临时 HTTPS 下载 URL。URL 是不可猜测、单次使用且会在配置 TTL 后过期的 Capability。Attachment Bytes 只会保留在受限的 Process Memory 中，不会通过 MCP JSON 返回。
返回的 Attachment `size` 是解码后的实际字节数，对本次下载具有权威性。不得与 Metadata-only 列表中的值比较后决定是否接受附件。

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
