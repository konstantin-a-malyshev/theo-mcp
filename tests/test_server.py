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

    # print(json.dumps(dict, indent=2, ensure_ascii=False))


@pytest.mark.anyio
async def test_create_notion(mcp_session):
    timestamp = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    test_caption = f"test_create_notion_{timestamp}"
    result = await mcp_session.call_tool("create_notion", {"caption": test_caption, "relationships": {"isSupportedBy": ["Jn 1:1"]}})
    dict = result.structuredContent

    print("HELLO")
    print(json.dumps(dict, indent=2, ensure_ascii=False))