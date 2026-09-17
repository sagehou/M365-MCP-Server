"""Agent-friendly Outlook mail tools backed by the internal mail service."""

from collections.abc import Mapping
from typing import Any

from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_request

from ..auth.context import get_auth_context
from ..auth.models import AuthContext
from ..graph.client import GraphResponse
from ..graph.mail import MailService


class MailToolService:
    """Translate mailbox service responses into bounded MCP tool results."""

    def __init__(self, mail_service: MailService) -> None:
        self.mail_service = mail_service

    async def search(
        self,
        context: AuthContext,
        *,
        query: str = "",
        limit: int = 25,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> dict[str, Any]:
        response = await self.mail_service.search_messages(
            context,
            query=query,
            limit=limit,
            date_from=date_from,
            date_to=date_to,
        )
        messages, next_link = _collection(response.data)
        return {"messages": messages, "next_link": next_link}

    async def get(self, context: AuthContext, message_id: str) -> dict[str, Any]:
        response = await self.mail_service.get_message(context, message_id)
        return {"message": response.data}

    async def list_attachments(
        self, context: AuthContext, message_id: str
    ) -> dict[str, Any]:
        response = await self.mail_service.list_attachments(context, message_id)
        attachments, next_link = _collection(response.data)
        return {
            "attachments": [_attachment_metadata(item) for item in attachments],
            "next_link": next_link,
        }

    async def mark_read(
        self, context: AuthContext, message_id: str, is_read: bool
    ) -> dict[str, Any]:
        await self.mail_service.mark_read(context, message_id, is_read=is_read)
        return {"message_id": message_id, "is_read": is_read}

    async def archive(self, context: AuthContext, message_id: str) -> dict[str, Any]:
        await self.mail_service.archive_message(context, message_id)
        return {"message_id": message_id, "archived": True}

    async def move(
        self,
        context: AuthContext,
        message_id: str,
        destination_folder_id: str,
    ) -> dict[str, Any]:
        await self.mail_service.move_message(
            context,
            message_id,
            destination_folder_id=destination_folder_id,
        )
        return {
            "message_id": message_id,
            "destination_folder_id": destination_folder_id,
        }

    async def set_category(
        self,
        context: AuthContext,
        message_id: str,
        categories: list[str],
    ) -> dict[str, Any]:
        await self.mail_service.set_categories(context, message_id, categories)
        return {"message_id": message_id, "categories": categories}


def register_mail_tools(mcp: FastMCP, service: MailToolService) -> None:
    """Register the initial mail tool set on a FastMCP server."""

    def context() -> AuthContext:
        return get_auth_context(get_http_request())

    @mcp.tool(
        name="mail_search",
        description="Search the signed-in user's Outlook mailbox.",
    )
    async def mail_search(
        query: str = "",
        limit: int = 25,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> dict[str, Any]:
        return await service.search(
            context(),
            query=query,
            limit=limit,
            date_from=date_from,
            date_to=date_to,
        )

    @mcp.tool(
        name="mail_get",
        description="Retrieve one message from the signed-in user's mailbox.",
    )
    async def mail_get(message_id: str) -> dict[str, Any]:
        return await service.get(context(), message_id)

    @mcp.tool(
        name="mail_list_attachments",
        description="List metadata for one message's attachments without returning file bytes.",
    )
    async def mail_list_attachments(message_id: str) -> dict[str, Any]:
        return await service.list_attachments(context(), message_id)

    @mcp.tool(
        name="mail_mark_read",
        description="Mark one message read or unread in the signed-in user's mailbox.",
    )
    async def mail_mark_read(message_id: str, is_read: bool = True) -> dict[str, Any]:
        return await service.mark_read(context(), message_id, is_read)

    @mcp.tool(
        name="mail_archive",
        description="Move one message to the signed-in user's Outlook Archive folder.",
    )
    async def mail_archive(message_id: str) -> dict[str, Any]:
        return await service.archive(context(), message_id)

    @mcp.tool(
        name="mail_move",
        description="Move one message to a folder in the signed-in user's mailbox.",
    )
    async def mail_move(message_id: str, destination_folder_id: str) -> dict[str, Any]:
        return await service.move(context(), message_id, destination_folder_id)

    @mcp.tool(
        name="mail_set_category",
        description="Replace the Outlook categories on one message.",
    )
    async def mail_set_category(
        message_id: str, categories: list[str]
    ) -> dict[str, Any]:
        return await service.set_category(context(), message_id, categories)


def _collection(data: Any) -> tuple[list[Any], str | None]:
    if not isinstance(data, Mapping):
        return [], None
    values = data.get("value")
    items = values if isinstance(values, list) else []
    next_link = data.get("@odata.nextLink")
    return items, next_link if isinstance(next_link, str) else None


def _attachment_metadata(item: Any) -> Any:
    if not isinstance(item, Mapping):
        return item
    metadata = dict(item)
    if "contentBytes" in metadata:
        metadata.pop("contentBytes", None)
        metadata["has_content"] = True
    return metadata
