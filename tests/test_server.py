import datetime
import json
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

server_params = StdioServerParameters(command="theo-mcp")

@pytest.fixture
async def mcp_session():
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session

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
async def test_get_new_quotations(mcp_session):
    result = await mcp_session.call_tool("get_new_quotations", {"since_id": 0, "limit": 5})
    dicts = result.structuredContent.get("result")

    print(json.dumps(dicts, indent=2, ensure_ascii=False))

    assert len(dicts) >= 0

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