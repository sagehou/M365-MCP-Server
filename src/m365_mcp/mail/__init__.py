"""Outlook mail MCP tools."""

from .downloads import (
    AttachmentDownloadStore,
    DownloadPayload,
    DownloadTicket,
    create_attachment_download_router,
)
from .tools import MailToolService, register_mail_tools

__all__ = [
    "AttachmentDownloadStore",
    "DownloadPayload",
    "DownloadTicket",
    "MailToolService",
    "create_attachment_download_router",
    "register_mail_tools",
]
