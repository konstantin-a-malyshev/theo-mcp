import json
import pytest
import pytest_asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

server_params = StdioServerParameters(
    command="theo-mcp",
    # args=["run", "server", "fastmcp_quickstart", "stdio"],  # We're already in snippets dir
    # env={"UV_INDEX": os.environ.get("UV_INDEX", "")},
)

@pytest_asyncio.fixture
async def mcp_session():
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session

@pytest.mark.asyncio
async def test_get_verse_by_caption(mcp_session):
    result = await mcp_session.call_tool("get_verse_by_caption", {"caption": "Jn 1:1"})
    dict = result.structuredContent

    print(json.dumps(dict, indent=2, ensure_ascii=False))

    assert dict.get('caption') == "Jn 1:1"