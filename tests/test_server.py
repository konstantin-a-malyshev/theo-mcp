import datetime
import json
import os
import sys
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

_SRC = os.path.join(os.path.dirname(__file__), "..", "src")
sys.path.insert(0, _SRC)

from theo_mcp_server.cloud_storage import OwnCloudStorage
from theo_mcp_server.config import get_config

_env = os.environ.copy()
_env["PYTHONPATH"] = _SRC

server_params = StdioServerParameters(
    command=os.path.join(".venv", "Scripts", "python.exe"),
    args=["-m", "theo_mcp_server"],
    env=_env,
)

@pytest.fixture
async def mcp_session():
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session

@pytest.fixture
def cloud_storage():
    return OwnCloudStorage.from_config(get_config())

@pytest.mark.anyio
async def test_get_verse_by_caption(mcp_session):
    result = await mcp_session.call_tool("get_verse_by_caption", {"caption": "Jn 9:22"})
    dict = result.structuredContent

    # print(json.dumps(dict, indent=2, ensure_ascii=False))

    assert dict.get('caption') == "Jn 9:22"

@pytest.mark.anyio
async def test_get_notion_by_id(mcp_session):
    result = await mcp_session.call_tool("get_notion_by_id", {"id": 122884320})
    dict = result.structuredContent
    print(json.dumps(dict, indent=2, ensure_ascii=False))
    assert dict.get('internal_id') == 122884320


@pytest.mark.anyio
async def test_get_notion_by_caption(mcp_session):
    result = await mcp_session.call_tool("get_notion_by_caption", {"caption": "Тема \"Час Иисуса\""})
    dict = result.structuredContent
    print(json.dumps(dict, indent=2, ensure_ascii=False))
    assert dict.get('caption') == "Тема \"Час Иисуса\""

@pytest.mark.anyio
async def test_create_notion(mcp_session):
    prefix = "test_create_notion"
    timestamp = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")

    to_caption = f"{prefix}_TO_{timestamp}"
    from_caption = f"{prefix}_FROM_{timestamp}"
    test_caption = f"{prefix}_TEST_{timestamp}"

    to_result   = await mcp_session.call_tool("create_notion", {"caption": to_caption})
    from_result = await mcp_session.call_tool("create_notion", {"caption": from_caption})
    test_result = await mcp_session.call_tool("create_notion", {"caption": test_caption, "relationships": {"isSupportedBy": [to_caption], "supports": [from_caption]}})

    to_caption =  to_result.structuredContent["created"]["caption"]
    from_caption = from_result.structuredContent["created"]["caption"]
    test_caption = test_result.structuredContent["created"]["caption"]

    test_id = test_result.structuredContent["created"]["internal_id"]

    test_vertex = await mcp_session.call_tool("get_notion_by_id", {"id": test_id})

    assert test_vertex.structuredContent["caption"] == test_caption
    assert any(edge for edge in test_vertex.structuredContent["relationships"]['isSupportedBy'] if edge["caption"] == to_caption)
    assert any(edge for edge in test_vertex.structuredContent["relationships"]['supports']      if edge["caption"] == from_caption)

    # print(json.dumps(test_vertex.structuredContent, indent=2, ensure_ascii=False))

    result = await mcp_session.call_tool("delete_notion_by_caption", {"caption": to_caption})
    assert result.structuredContent["deleted"] is True
    result = await mcp_session.call_tool("delete_notion_by_caption", {"caption": from_caption})
    assert result.structuredContent["deleted"] is True
    result = await mcp_session.call_tool("delete_notion_by_caption", {"caption": test_caption})
    assert result.structuredContent["deleted"] is True

@pytest.mark.anyio
async def test_create_notion_with_description(mcp_session):
    prefix = "test_create_notion_with_description"
    timestamp = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    test_caption = f"{prefix}_TEST_{timestamp}"

    test_result = await mcp_session.call_tool(
        "create_notion", {"caption": test_caption, "description": "initial description"}
    )
    assert test_result.structuredContent["created"]["description"] == "initial description"

    test_id = test_result.structuredContent["created"]["internal_id"]

    updated = await mcp_session.call_tool(
        "change_notion_description", {"caption": test_caption, "description": "updated description"}
    )
    assert updated.structuredContent["description"] == "updated description"

    test_vertex = await mcp_session.call_tool("get_notion_by_id", {"id": test_id})
    assert test_vertex.structuredContent["description"] == "updated description"

    result = await mcp_session.call_tool("delete_notion_by_caption", {"caption": test_caption})
    assert result.structuredContent["deleted"] is True

@pytest.mark.anyio
async def test_get_notion_group_by_caption(mcp_session):
    result = await mcp_session.call_tool("get_notion_group_by_caption", {"caption": "Евангелие от Иоанна"})
    dict = result.structuredContent
    print(json.dumps(dict, indent=2, ensure_ascii=False))
    assert dict.get('caption') == "Евангелие от Иоанна"

@pytest.mark.anyio
async def test_create_relationship(mcp_session):
    prefix = "test_create_relationship"
    timestamp = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")

    from_caption = f"{prefix}_FROM_{timestamp}"
    to_caption = f"{prefix}_TO_{timestamp}"

    from_result = await mcp_session.call_tool("create_notion", {"caption": from_caption})
    to_result   = await mcp_session.call_tool("create_notion", {"caption": to_caption})

    result = await mcp_session.call_tool("create_relationship", {
        "relationship": "refersTo",
        "sourceCaption": from_caption,
        "targetCaption": to_caption
    })

    from_vertex = await mcp_session.call_tool("get_notion_by_caption", {"caption": from_caption})
    from_vertex = from_vertex.structuredContent

    print(json.dumps(from_vertex, indent=2, ensure_ascii=False))

    assert any(edge for edge in from_vertex["relationships"]['refersTo'] if edge["caption"] == to_caption)

    result = await mcp_session.call_tool("delete_notion_by_caption", {"caption": from_caption})
    assert result.structuredContent["deleted"] is True
    result = await mcp_session.call_tool("delete_notion_by_caption", {"caption": to_caption})
    assert result.structuredContent["deleted"] is True

@pytest.mark.anyio
async def test_create_relationships(mcp_session):
    prefix = "test_create_relationships"
    timestamp = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")

    from_caption = f"{prefix}_FROM_{timestamp}"
    to_caption = f"{prefix}_TO_{timestamp}"

    from_result = await mcp_session.call_tool("create_notion", {"caption": from_caption})
    to_result   = await mcp_session.call_tool("create_notion", {"caption": to_caption})

    result = await mcp_session.call_tool("create_relationships", {
        "relationships": [{
        "relationship": "refersTo",
        "sourceCaption": from_caption,
        "targetCaption": to_caption
    }]})
    from_vertex = await mcp_session.call_tool("get_notion_by_caption", {"caption": from_caption})
    from_vertex = from_vertex.structuredContent

    print(json.dumps(from_vertex, indent=2, ensure_ascii=False))

    assert any(edge for edge in from_vertex["relationships"]['refersTo'] if edge["caption"] == to_caption)

    result = await mcp_session.call_tool("delete_notion_by_caption", {"caption": from_caption})
    assert result.structuredContent["deleted"] is True
    result = await mcp_session.call_tool("delete_notion_by_caption", {"caption": to_caption})
    assert result.structuredContent["deleted"] is True

@pytest.mark.anyio
async def test_delete_relationship(mcp_session):
    prefix = "test_delete_relationship"
    timestamp = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")

    from_caption = f"{prefix}_FROM_{timestamp}"
    to_caption = f"{prefix}_TO_{timestamp}"

    await mcp_session.call_tool("create_notion", {"caption": from_caption})
    await mcp_session.call_tool("create_notion", {"caption": to_caption})

    await mcp_session.call_tool(
        "create_relationship",
        {
            "relationship": "refersTo",
            "sourceCaption": from_caption,
            "targetCaption": to_caption,
        },
    )

    delete_result = await mcp_session.call_tool(
        "delete_relationship",
        {
            "relationship": "refersTo",
            "sourceCaption": from_caption,
            "targetCaption": to_caption,
        },
    )
    delete_payload = delete_result.structuredContent
    assert delete_payload["deleted_edges"] >= 1

    from_vertex = await mcp_session.call_tool("get_notion_by_caption", {"caption": from_caption})
    from_vertex = from_vertex.structuredContent

    assert not any(edge for edge in from_vertex.get("relationships", {}).get("refersTo", []) if edge["caption"] == to_caption)

    result = await mcp_session.call_tool("delete_notion_by_caption", {"caption": from_caption})
    assert result.structuredContent["deleted"] is True
    result = await mcp_session.call_tool("delete_notion_by_caption", {"caption": to_caption})
    assert result.structuredContent["deleted"] is True

@pytest.mark.anyio
async def test_search_notion_groups_and_notions(mcp_session):
    prefix = "test_search_notion_groups_and_notions"
    timestamp = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")

    notion_group_caption = f"{prefix}_GROUP_{timestamp}"
    notion_caption       = f"{prefix}_NOTION_{timestamp}"

    group_result = await mcp_session.call_tool("create_notion_group", {"caption": notion_group_caption})
    notion_result = await mcp_session.call_tool("create_notion", {"caption": notion_caption})

    search_result = await mcp_session.call_tool("search_notion_groups_and_notions", {
        "searchText": timestamp,
        "limit": 10
    })

    dicts = search_result.structuredContent

    print(json.dumps(dicts, indent=2, ensure_ascii=False))

    found = dicts.get("result")

    print(json.dumps(found, indent=2, ensure_ascii=False))


    assert any(d for d in found if d["caption"] == notion_group_caption or d["caption"] == notion_caption)

    result = await mcp_session.call_tool("delete_notion_by_caption", {"caption": notion_caption})
    assert result.structuredContent["deleted"] is True
    result = await mcp_session.call_tool("delete_notion_group_by_caption", {"caption": notion_group_caption})
    assert result.structuredContent["deleted"] is True

@pytest.mark.anyio
async def test_get_verses_by_captions(mcp_session):
    captions = ["Jn 1:1", "Jn 1:2", "Jn 1:3"]
    result = await mcp_session.call_tool("get_verses_by_captions", {"captions": captions})
    dicts = result.structuredContent.get("result")

    print(json.dumps(dicts, indent=2, ensure_ascii=False))

    assert len(dicts) == 3

@pytest.mark.anyio
async def test_get_quotations_by_status(mcp_session):
    result = await mcp_session.call_tool("get_quotations_by_status", {"status": "new", "limit": 5})
    dicts = result.structuredContent.get("result")

    print(json.dumps(dicts, indent=2, ensure_ascii=False))

    assert len(dicts) >= 0

@pytest.mark.anyio
async def test_quotation_lifecycle(mcp_session):
    prefix = "test_quotation_lifecycle"
    timestamp = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")

    caption = f"{prefix}_{timestamp}"
    text = f"Quotation text {timestamp}"
    book = "Test Book"
    position = "p. 1"

    create_result = await mcp_session.call_tool(
        "create_quotation",
        {
            "caption": caption,
            "text": text,
            "book": book,
            "position": position,
        },
    )
    created = create_result.structuredContent["created"]

    assert created["caption"] == caption
    assert created["text"] == text
    assert created["book"] == book
    assert created["position"] == position
    assert created["status"] == "new"

    get_result = await mcp_session.call_tool("get_quotation_by_caption", {"caption": caption})
    quotation = get_result.structuredContent

    assert quotation["caption"] == caption
    assert quotation["text"] == text
    assert quotation["book"] == book
    assert quotation["position"] == position
    assert quotation["status"] == "new"

    set_status_result = await mcp_session.call_tool(
        "set_quotation_status",
        {"caption": caption, "status": "processed"},
    )
    updated = set_status_result.structuredContent

    assert updated["caption"] == caption
    assert updated["status"] == "processed"

    get_updated_result = await mcp_session.call_tool("get_quotation_by_caption", {"caption": caption})
    updated_quotation = get_updated_result.structuredContent

    assert updated_quotation["caption"] == caption
    assert updated_quotation["status"] == "processed"

    list_result = await mcp_session.call_tool(
        "get_quotations_by_status",
        {"status": "processed", "limit": 50},
    )
    quotations = list_result.structuredContent.get("result")

    assert isinstance(quotations, list)
    assert len(quotations) >= 0

    delete_result = await mcp_session.call_tool("delete_quotation_by_caption", {"caption": caption})
    assert delete_result.structuredContent["deleted"] is True

@pytest.mark.anyio
async def test_get_verse_group_by_caption(mcp_session):
    result = await mcp_session.call_tool("get_verse_group_by_caption", {"caption": "Jn 11:51-53"})
    dict = result.structuredContent
    print(json.dumps(dict, indent=2, ensure_ascii=False))
    assert dict.get('caption') == "Jn 11:51-53"

@pytest.mark.anyio
async def test_create_verse_group(mcp_session):
    prefix = "test_create_verse_group Jn 1:1-2 "
    timestamp = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")

    caption = f"{prefix}_{timestamp}"

    result = await mcp_session.call_tool("create_verse_group", {"caption": caption, "verses": ["Jn 1:1", "Jn 1:2"]})
    created_caption = result.structuredContent["created"]["caption"]

    print(json.dumps(result.structuredContent, indent=2, ensure_ascii=False))

    assert created_caption == caption

    result = await mcp_session.call_tool("delete_verse_group_by_caption", {"caption": caption})
    assert result.structuredContent["deleted"] is True

@pytest.mark.anyio
async def test_get_notion_groups_tree(mcp_session):
    result = await mcp_session.call_tool("get_notion_groups_tree")
    print(json.dumps(result.structuredContent, indent=2, ensure_ascii=False))
    dicts = result.structuredContent
    assert len(dicts) > 0

    result = await mcp_session.call_tool("get_notions_tree")
    print(json.dumps(result.structuredContent, indent=2, ensure_ascii=False))
    dicts = result.structuredContent
    assert len(dicts) > 0

@pytest.mark.anyio
async def test_create_diagram_by_captions(mcp_session, cloud_storage):
    prefix = "test_create_diagram_by_captions"
    timestamp = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    a_caption = f"{prefix}_A_{timestamp}"
    b_caption = f"{prefix}_B_{timestamp}"

    await mcp_session.call_tool("create_notion", {"caption": a_caption})
    await mcp_session.call_tool(
        "create_notion",
        {"caption": b_caption, "relationships": {"isSupportedBy": [a_caption]}},
    )

    try:
        result = await mcp_session.call_tool(
            "create_diagram_by_captions",
            {"captions": [a_caption, b_caption]},
        )
        data = result.structuredContent
        filename = data.get("filename")
        download_url = data.get("download_url")
        assert isinstance(filename, str) and filename.endswith(".svg")
        assert isinstance(download_url, str) and download_url.startswith("http")

        # Clean up the uploaded file from the cloud after a successful check.
        cloud_storage.delete(filename)
    finally:
        await mcp_session.call_tool("delete_notion_by_caption", {"caption": b_caption})
        await mcp_session.call_tool("delete_notion_by_caption", {"caption": a_caption})


@pytest.mark.anyio
async def test_create_book(mcp_session):
    prefix = "test_create_book"
    timestamp = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")

    caption = f"{prefix}_{timestamp}"

    result = await mcp_session.call_tool("create_book", {"caption": caption})
    created = result.structuredContent["created"]

    print(json.dumps(result.structuredContent, indent=2, ensure_ascii=False))

    assert created["caption"] == caption
    assert created["label"] == "book"

    get_result = await mcp_session.call_tool("get_book_by_caption", {"caption": caption})
    assert get_result.structuredContent.get("caption") == caption

    delete_result = await mcp_session.call_tool("delete_book_by_caption", {"caption": caption})
    assert delete_result.structuredContent["deleted"] is True

@pytest.mark.anyio
async def test_move_notion_to_group(mcp_session):
    prefix = "test_move_notion_to_group"
    timestamp = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")

    notion_caption = f"{prefix}_NOTION_{timestamp}"
    group_a_caption = f"{prefix}_GROUP_A_{timestamp}"
    group_b_caption = f"{prefix}_GROUP_B_{timestamp}"

    await mcp_session.call_tool("create_notion_group", {"caption": group_a_caption})
    await mcp_session.call_tool("create_notion_group", {"caption": group_b_caption})
    await mcp_session.call_tool(
        "create_notion",
        {"caption": notion_caption, "relationships": {"isContainedIn": [group_a_caption]}},
    )

    try:
        move_result = await mcp_session.call_tool(
            "move_notion_to_group",
            {"notionCaption": notion_caption, "notionGroupCaption": group_b_caption},
        )
        payload = move_result.structuredContent
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        assert payload["moved"] is True
        assert payload["removed_previous_group_edges"] == 1

        notion_vertex = await mcp_session.call_tool("get_notion_by_caption", {"caption": notion_caption})
        rels = notion_vertex.structuredContent.get("relationships", {})
        contained_in = rels.get("isContainedIn", [])
        assert any(e["caption"] == group_b_caption for e in contained_in)
        assert not any(e["caption"] == group_a_caption for e in contained_in)
    finally:
        await mcp_session.call_tool("delete_notion_by_caption", {"caption": notion_caption})
        await mcp_session.call_tool("delete_notion_group_by_caption", {"caption": group_a_caption})
        await mcp_session.call_tool("delete_notion_group_by_caption", {"caption": group_b_caption})

@pytest.mark.anyio
async def test_change_caption(mcp_session):
    prefix = "test_change_caption"
    timestamp = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")

    old_caption = f"{prefix}_OLD_{timestamp}"
    new_caption = f"{prefix}_NEW_{timestamp}"

    create_result = await mcp_session.call_tool("create_notion", {"caption": old_caption})
    created_id = create_result.structuredContent["created"]["internal_id"]

    change_result = await mcp_session.call_tool("change_caption", {"oldCaption": old_caption, "newCaption": new_caption})
    print(json.dumps(change_result.structuredContent, indent=2, ensure_ascii=False))
    assert change_result.structuredContent["updated"] is True
    assert change_result.structuredContent["internal_id"] == created_id
    assert change_result.structuredContent["new_caption"] == new_caption

    delete_result = await mcp_session.call_tool("delete_notion_by_caption", {"caption": new_caption})
    assert delete_result.structuredContent["deleted"] is True
