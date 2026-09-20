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

### mail_read_attachment

提取附件内容供 AI 处理。

支持格式：

- PDF
- DOCX
- XLSX
- PPTX
- TXT
- Markdown

### mail_download_attachment

获取一个受大小限制的 Outlook File Attachment，并返回临时 HTTPS 下载 URL。URL 是不可猜测、单次使用且会在配置 TTL 后过期的 Capability。Attachment Bytes 只会保留在受限的 Process Memory 中，不会通过 MCP JSON 返回。

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
