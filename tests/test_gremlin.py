import datetime
import json
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from theo_mcp_server.gremlin_client import get_g_for_tests
from theo_mcp_server.gremlin_helpers import create_vertex_and_connect_by_captions

server_params = StdioServerParameters(command="theo-mcp")

@pytest.fixture
async def g():
    g = await get_g_for_tests()
    yield g

@pytest.mark.anyio
async def test_create_vertex_and_connect_by_captions(g):
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    test_caption = f"test_create_vertex_and_connect_by_captions_{timestamp}"

    result = create_vertex_and_connect_by_captions(g, "notion", {"caption": test_caption}, {"isSupportedBy": ["Jn 1:1"]}, {})

    print(json.dumps(result, indent=2, ensure_ascii=False))