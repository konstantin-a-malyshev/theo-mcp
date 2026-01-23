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
