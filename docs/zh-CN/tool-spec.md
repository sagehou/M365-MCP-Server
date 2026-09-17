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
