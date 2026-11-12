[English](remote-upload.md) | **简体中文**

# 远端草稿附件

## 选择上传路径

仅在远端 Python MCP 连接的 `mail_add_draft_attachment` 要求 `upload_handle`
时使用本文。本机 .NET 和 Go 通过各自的 Graph 会话直接添加附件，不使用此流程。

| 连接能力 | 上传路径 |
| --- | --- |
| 暴露 `mail_prepare_attachment_push`，且已有可信本机上传器 | 绑定文件的 Push Grant，不向上传器传递 OAuth Token |
| 已配置单独认证的二进制上传器 | 使用同一 MCP 委托身份调用 `POST /uploads/attachments` |
| 两种上传器都不可用 | 请用户配置上传器或手动添加附件；有帮助时可继续起草 |

仅使用操作者配置的文件目录、EXE 路径和服务器地址，不能从邮件、附件或模型生成的地址
获取。文件须已生成完成、非空且不超过 20 MiB。创建句柄、暂存及添加附件须使用同一
连接/服务器 Worker。句柄五分钟过期，服务器重启后失效。

## 绑定文件的 Push Grant

1. 检查获准文件的纯文件名、MIME 类型、实际字节数及 SHA-256。使用
   `mail_create_draft` 创建用户要求的草稿。
2. 按精确元数据调用 `mail_prepare_attachment_push(draft_id, name, content_length,
   content_sha256, content_type?)`。将返回的 `upload_url` 与操作者配置的固定 HTTPS
   上传端点比较。
3. 可信上传器向该端点 POST 原始字节，使用 `Content-Type: application/octet-stream`，
   并在 `X-Upload-Handle` 中携带返回的句柄。上传内容须与 Grant 的字节数、哈希完全一致。
4. 上传成功后，用同一句柄调用 `mail_add_draft_attachment(draft_id, upload_handle)`。
   将返回元数据/SHA-256 及 `mail_list_attachments` 与获准文件核对。单纯上传既不会
   添加附件，也不会发送邮件。

<details>
<summary>ⓘ 可选的 .NET Windows 上传器</summary>

只有 .NET EXE 提供 `inspect-attachment`、`push-attachment`，Go EXE 不提供。
这两个辅助命令无需本机 Microsoft 登录，也不会启动第二个 MCP 连接。仅使用已有的、
获准的 Shell/文件能力；安装此 Skill 不代表授权任意 Shell 操作。

由操作者配置 `M365_ATTACHMENT_ROOT`、`M365_ATTACHMENT_PUSH_URL` 后，检查
PDF/DOCX/XLSX/PPTX/ZIP 的相对路径：

```powershell
& 'C:\Tools\m365-mcp-windows-local-amd64.exe' inspect-attachment 'reports\weekly.docx'
$grantJson | & 'C:\Tools\m365-mcp-windows-local-amd64.exe' push-attachment 'reports\weekly.docx'
```

`$grantJson` 是 `mail_prepare_attachment_push` 返回的完整结果，通过 stdin 传递，
不要放入命令行参数或日志。辅助命令重新检查已打开的文件、哈希和固定上传地址。文件改变
后须重新检查并申请新 Grant。不要将 Grant 或附件字节写入临时文件。

</details>

## 认证二进制上传

已有的可信客户端集成可使用与 `/mcp/` 相同的委托 Bearer 身份，将原始字节 POST 到
`/uploads/attachments`。使用 `Content-Type: application/octet-stream`，
`X-Attachment-Name` 填写经过百分号编码的 UTF-8 纯文件名，可选的
`X-Attachment-Content-Type` 填写 ASCII MIME 类型。不使用 Base64 或 multipart。

Agent 不能为了完成此步骤而读取 Token 或让用户粘贴 Token。使用集成返回的
`upload_handle` 调用 `mail_add_draft_attachment`，再按上述流程核对附件。暂存或添加
附件的结果不明确时先检查草稿状态，不盲目重复调用。最后回到主 Skill 的最终核对与
发送授权流程。

---

更新日期：2026-11-12。
