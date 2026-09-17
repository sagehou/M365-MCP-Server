"""Internal mailbox service foundation built on the delegated Graph client."""

from collections.abc import Mapping
from typing import Any
from urllib.parse import quote

from ..auth.models import AuthContext
from .client import GraphClient, GraphResponse


class MailService:
    """Provide identity-scoped mailbox operations for future MCP tools."""

    def __init__(self, graph_client: GraphClient) -> None:
        self.graph_client = graph_client

    async def list_messages(
        self,
        context: AuthContext,
        *,
        params: Mapping[str, str | int | float | bool] | None = None,
    ) -> GraphResponse:
        return await self.graph_client.request(
            context,
            "GET",
            "/me/messages",
            params=params,
        )

    async def get_message(
        self,
        context: AuthContext,
        message_id: str,
        *,
        params: Mapping[str, str | int | float | bool] | None = None,
    ) -> GraphResponse:
        return await self.graph_client.request(
            context,
            "GET",
            f"/me/messages/{self._segment(message_id)}",
            params=params,
        )

    async def list_attachments(
        self,
        context: AuthContext,
        message_id: str,
    ) -> GraphResponse:
        return await self.graph_client.request(
            context,
            "GET",
            f"/me/messages/{self._segment(message_id)}/attachments",
        )

    @staticmethod
    def _segment(value: str) -> str:
        if not isinstance(value, str) or not value:
            raise ValueError("A non-empty Graph resource id is required")
        return quote(value, safe="")
