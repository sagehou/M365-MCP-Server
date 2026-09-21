"""Internal mailbox service foundation built on the delegated Graph client."""

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

from ..auth.models import AuthContext
from ..errors import InvalidToolInputError
from .client import GraphClient, GraphResponse


MAX_DRAFT_RECIPIENTS_PER_FIELD = 50
MAX_DRAFT_RECIPIENTS_TOTAL = 100
MAX_DRAFT_SUBJECT_CHARS = 255
MAX_DRAFT_BODY_CHARS = 100_000


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

    async def search_messages(
        self,
        context: AuthContext,
        *,
        query: str = "",
        limit: int = 25,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> GraphResponse:
        if not 1 <= limit <= 100:
            raise InvalidToolInputError(
                "limit", "out_of_range", "limit must be between 1 and 100"
            )
        if len(query) > 2048:
            raise InvalidToolInputError(
                "query", "too_long", "query must not exceed 2048 characters"
            )
        start = self._date_value(date_from, "date_from") if date_from else None
        end = self._date_value(date_to, "date_to") if date_to else None
        if start and end and datetime.fromisoformat(start) > datetime.fromisoformat(end):
            raise InvalidToolInputError(
                "date_from", "invalid_range", "date_from must not be after date_to"
            )

        params: dict[str, str | int] = {
            "$top": limit,
            "$select": "id,subject,from,receivedDateTime,isRead,hasAttachments,bodyPreview",
        }
        search_text = query.replace('"', " ").strip()
        if search_text:
            terms = [f"({search_text})"]
            if start:
                terms.append(f"received>={start}")
            if end:
                terms.append(f"received<={end}")
            params["$search"] = '"' + " AND ".join(terms) + '"'
        else:
            params["$orderby"] = "receivedDateTime desc"
            filters: list[str] = []
            if start:
                filters.append(f"receivedDateTime ge {start}")
            if end:
                filters.append(f"receivedDateTime le {end}")
            if filters:
                params["$filter"] = " and ".join(filters)

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
            params={"$select": "id,name,contentType,size,isInline,lastModifiedDateTime"},
        )

    async def get_attachment(
        self,
        context: AuthContext,
        message_id: str,
        attachment_id: str,
    ) -> GraphResponse:
        return await self.graph_client.request(
            context,
            "GET",
            f"/me/messages/{self._segment(message_id)}/attachments/{self._segment(attachment_id)}",
        )

    async def create_draft(
        self,
        context: AuthContext,
        *,
        to_recipients: list[str],
        subject: str,
        body: str,
        cc_recipients: list[str] | None = None,
        bcc_recipients: list[str] | None = None,
    ) -> GraphResponse:
        to_payload = self._recipient_payload(
            to_recipients,
            "to_recipients",
            required=True,
        )
        cc_payload = self._recipient_payload(cc_recipients, "cc_recipients")
        bcc_payload = self._recipient_payload(bcc_recipients, "bcc_recipients")
        recipient_count = len(to_payload) + len(cc_payload) + len(bcc_payload)
        if recipient_count > MAX_DRAFT_RECIPIENTS_TOTAL:
            raise InvalidToolInputError(
                "to_recipients",
                "too_many_recipients",
                (
                    "a draft may contain at most "
                    f"{MAX_DRAFT_RECIPIENTS_TOTAL} recipients"
                ),
            )

        normalized_subject = self._draft_text(
            subject,
            "subject",
            max_chars=MAX_DRAFT_SUBJECT_CHARS,
            allow_newlines=False,
        ).strip()
        normalized_body = self._draft_text(
            body,
            "body",
            max_chars=MAX_DRAFT_BODY_CHARS,
            allow_newlines=True,
        )
        payload: dict[str, Any] = {
            "subject": normalized_subject,
            "body": {
                "contentType": "Text",
                "content": normalized_body,
            },
            "toRecipients": to_payload,
        }
        if cc_payload:
            payload["ccRecipients"] = cc_payload
        if bcc_payload:
            payload["bccRecipients"] = bcc_payload

        return await self.graph_client.request(
            context,
            "POST",
            "/me/messages",
            json_body=payload,
        )

    async def send_draft(
        self,
        context: AuthContext,
        draft_id: str,
    ) -> GraphResponse:
        return await self.graph_client.request(
            context,
            "POST",
            f"/me/messages/{self._segment(draft_id)}/send",
        )

    async def mark_read(
        self,
        context: AuthContext,
        message_id: str,
        *,
        is_read: bool,
    ) -> GraphResponse:
        return await self.update_message(
            context,
            message_id,
            {"isRead": is_read},
        )

    async def set_categories(
        self,
        context: AuthContext,
        message_id: str,
        categories: list[str],
    ) -> GraphResponse:
        return await self.update_message(
            context,
            message_id,
            {"categories": categories},
        )

    async def update_message(
        self,
        context: AuthContext,
        message_id: str,
        payload: Mapping[str, Any],
    ) -> GraphResponse:
        return await self.graph_client.request(
            context,
            "PATCH",
            f"/me/messages/{self._segment(message_id)}",
            json_body=dict(payload),
        )

    async def archive_message(
        self,
        context: AuthContext,
        message_id: str,
    ) -> GraphResponse:
        return await self.move_message(
            context,
            message_id,
            destination_folder_id="archive",
        )

    async def move_message(
        self,
        context: AuthContext,
        message_id: str,
        *,
        destination_folder_id: str,
    ) -> GraphResponse:
        if not destination_folder_id:
            raise ValueError("destination_folder_id must not be empty")
        return await self.graph_client.request(
            context,
            "POST",
            f"/me/messages/{self._segment(message_id)}/move",
            json_body={"destinationId": destination_folder_id},
        )

    @staticmethod
    def _segment(value: str) -> str:
        if not isinstance(value, str) or not value or value in {".", ".."}:
            raise ValueError("A non-empty Graph resource id is required")
        return quote(value, safe="")

    @staticmethod
    def _recipient_payload(
        values: list[str] | None,
        param: str,
        *,
        required: bool = False,
    ) -> list[dict[str, dict[str, str]]]:
        if values is None:
            values = []
        if not isinstance(values, list):
            raise InvalidToolInputError(
                param,
                "invalid_type",
                "must be a list of email addresses",
            )
        if required and not values:
            raise InvalidToolInputError(
                param,
                "missing_recipient",
                "at least one To recipient is required",
            )
        if len(values) > MAX_DRAFT_RECIPIENTS_PER_FIELD:
            raise InvalidToolInputError(
                param,
                "too_many_recipients",
                (
                    "must not contain more than "
                    f"{MAX_DRAFT_RECIPIENTS_PER_FIELD} recipients"
                ),
            )

        recipients: list[dict[str, dict[str, str]]] = []
        for value in values:
            if not isinstance(value, str):
                raise InvalidToolInputError(
                    param,
                    "invalid_address",
                    "every recipient must be a plain email address",
                )
            address = value.strip()
            if (
                not address
                or len(address) > 320
                or address.count("@") != 1
                or any(
                    character.isspace() or character in ",;<>"
                    for character in address
                )
            ):
                raise InvalidToolInputError(
                    param,
                    "invalid_address",
                    "every recipient must be a plain email address",
                )
            local_part, domain = address.rsplit("@", 1)
            if not local_part or not domain:
                raise InvalidToolInputError(
                    param,
                    "invalid_address",
                    "every recipient must be a plain email address",
                )
            recipients.append({"emailAddress": {"address": address}})
        return recipients

    @staticmethod
    def _draft_text(
        value: str,
        param: str,
        *,
        max_chars: int,
        allow_newlines: bool,
    ) -> str:
        if not isinstance(value, str):
            raise InvalidToolInputError(param, "invalid_type", "must be text")
        if not value.strip():
            raise InvalidToolInputError(param, "empty", "must not be empty")
        if len(value) > max_chars:
            raise InvalidToolInputError(
                param,
                "too_long",
                f"must not exceed {max_chars} characters",
            )
        permitted_controls = {"\t", "\r", "\n"} if allow_newlines else set()
        if any(
            (ord(character) < 32 and character not in permitted_controls)
            or ord(character) == 127
            for character in value
        ):
            raise InvalidToolInputError(
                param,
                "invalid_characters",
                "contains unsupported control characters",
            )
        return value

    @staticmethod
    def _date_value(value: str, param: str) -> str:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise InvalidToolInputError(
                param,
                "invalid_date_format",
                "must be an ISO 8601 timestamp with timezone",
            ) from exc
        if parsed.tzinfo is None:
            raise InvalidToolInputError(
                param, "missing_timezone", "must include a timezone offset"
            )
        return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
