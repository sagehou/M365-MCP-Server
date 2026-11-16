"""Folder discovery is read-only and its pagination stays inside one mailbox path."""

import asyncio
from typing import Any
from urllib.parse import quote, urlencode

import pytest

from m365_mcp.auth import Settings
from m365_mcp.errors import InvalidToolInputError
from m365_mcp.graph.client import GraphResponse
from m365_mcp.graph.mail import FOLDER_FIELDS, MailService
from m365_mcp.mail import MailToolService
from test_mail import StubGraphClient, make_context


BASE = "https://graph.microsoft.com/v1.0"


def page_link(path="/me/mailFolders", **cursor):
    return BASE + path + "?" + urlencode({"$top": "100", "$select": FOLDER_FIELDS, **cursor})


class FolderGraph(StubGraphClient):
    def __init__(self, *pages: Any):
        super().__init__()
        self.settings = Settings()
        self.pages = list(pages)

    async def request(self, context, method, path, **kwargs):
        await super().request(context, method, path, **kwargs)
        return GraphResponse(200, self.pages.pop(0), None, {})


@pytest.mark.parametrize("parent", ["", "parent/a?b#c", "parent+=="])
@pytest.mark.parametrize("cursor", [{"$skip": "100"}, {"$skiptoken": "a+b/== &中文..token"}])
def test_folders_list_pages_and_use_returned_id_for_move(parent, cursor):
    path = "/me/mailFolders" + (f"/{quote(parent, safe='')}/childFolders" if parent else "")
    link = page_link(path.replace("%2B", "+").replace("%3D", "="), **cursor)
    folders = [
        {
            "id": identifier, "displayName": '项目 "归档"', "parentFolderId": parent,
            "childFolderCount": 1, "totalItemCount": 20, "unreadItemCount": 2,
        }
        for identifier in ("folder-one", "folder-two")
    ]
    graph = FolderGraph({"value": folders, "@odata.nextLink": link}, {"value": []}, {"id": "new-message"})
    service = MailToolService(MailService(graph))  # type: ignore[arg-type]
    context = make_context()

    async def exercise():
        result = await service.list_folders(context, parent)
        assert set(result) == {"folders", "next_link", "content_metadata"}
        assert result["folders"] == folders  # Same-name folders must remain distinct.
        assert result["next_link"] == link
        assert result["content_metadata"]["trust"] == "untrusted"
        last = await service.list_folders(context, parent, result["next_link"])
        assert last["folders"] == [] and last["next_link"] is None
        assert all(call["method"] == "GET" for call in graph.calls)
        moved = await service.move(context, "message", result["folders"][1]["id"])
        assert moved["message_id"] == "new-message"

    asyncio.run(exercise())
    assert graph.calls[0] == {
        "context": context, "method": "GET", "path": path,
        "params": {"$top": "100", "$select": FOLDER_FIELDS},
    }
    assert graph.calls[1]["path"] == path
    assert graph.calls[1]["params"] == {"$top": "100", "$select": FOLDER_FIELDS, **cursor}
    assert graph.calls[2]["json_body"] == {"destinationId": "folder-two"}


GOOD_LINK = page_link(**{"$skip": "100"})


@pytest.mark.parametrize("link", [
    "https://evil.example/v1.0/me/mailFolders?x=1",
    GOOD_LINK.replace("/me/mailFolders?", "/users/other/mailFolders?"),
    GOOD_LINK.replace("/me/mailFolders?", "/me/messages?"),
    GOOD_LINK.replace("/me/mailFolders?", "/me/mailFolders/other/childFolders?"),
    GOOD_LINK.replace("/me/mailFolders?", "/me/mailFolders/../messages?"),
    GOOD_LINK + "&$skip=200", GOOD_LINK + "&$skiptoken=token",
    GOOD_LINK + "&$filter=anything", GOOD_LINK + "#fragment", GOOD_LINK + "\\x",
    GOOD_LINK + "\n", GOOD_LINK + " ", "x" * 8193,
    page_link(**{"$skip": ""}), page_link(**{"$skip": "-1"}),
    page_link(**{"$skip": "١"}), page_link(**{"$skiptoken": ""}),
    page_link(**{"$top": "101", "$skip": "100"}),
    page_link(**{"$top": "0", "$skip": "100"}),
    page_link(**{"$top": "+10", "$skip": "100"}),
    page_link(**{"$select": "id", "$skip": "100"}),
    page_link(),
])
def test_invalid_folder_pagination_never_calls_graph(link):
    graph = FolderGraph()
    with pytest.raises(InvalidToolInputError) as raised:
        asyncio.run(MailService(graph).list_folders(make_context(), next_link=link))  # type: ignore[arg-type]
    assert raised.value.param == "next_link"
    assert graph.calls == []


def test_continuation_must_use_same_parent():
    graph = FolderGraph()
    with pytest.raises(InvalidToolInputError):
        asyncio.run(MailService(graph).list_folders(  # type: ignore[arg-type]
            make_context(), parent_folder_id="parent", next_link=GOOD_LINK,
        ))
    assert graph.calls == []


@pytest.mark.parametrize("parent", [".", "..", "bad\x00id", "x" * 2049])
def test_invalid_parent_never_calls_graph(parent):
    graph = FolderGraph()
    with pytest.raises(InvalidToolInputError):
        asyncio.run(MailService(graph).list_folders(make_context(), parent_folder_id=parent))  # type: ignore[arg-type]
    assert graph.calls == []


@pytest.mark.parametrize("data", [
    [], {}, {"value": None}, {"value": {}}, {"value": [None]},
    {"value": [{"id": "", "displayName": "name"}]},
    {"value": [{"id": "id", "displayName": 42}]},
    {"value": [{"id": "id", "displayName": "name"}] * 101},
    {"value": [], "@odata.nextLink": 42},
    {"value": [], "@odata.nextLink": "https://evil.example/SECRET_PROVIDER_BODY"},
])
def test_invalid_folder_responses_are_rejected(data):
    graph = FolderGraph(data)
    with pytest.raises(ValueError) as raised:
        asyncio.run(MailService(graph).list_folders(make_context()))  # type: ignore[arg-type]
    assert "SECRET_PROVIDER_BODY" not in str(raised.value)
    assert len(graph.calls) == 1 and graph.calls[0]["method"] == "GET"
