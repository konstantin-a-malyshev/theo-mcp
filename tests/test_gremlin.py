import datetime
import json
from unittest import result
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from theo_mcp_server.gremlin_client import get_g_for_tests
from theo_mcp_server.gremlin_helpers import create_vertex_and_connect_by_captions, delete_vertex_by_id, get_vertices_by_captions, read_vertex_with_edges, search_vertices

server_params = StdioServerParameters(command="theo-mcp")

@pytest.fixture
async def g():
    g = await get_g_for_tests()
    yield g

@pytest.mark.anyio
async def test_create_vertex_and_connect_by_captions(g):
    prefix = "test_create_vertex_and_connect_by_captions"
    timestamp = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    to_caption = f"{prefix}_TO_{timestamp}"
    from_caption = f"{prefix}_FROM_{timestamp}"
    test_caption = f"{prefix}_TEST_{timestamp}"

    to_result   = create_vertex_and_connect_by_captions(g, "notion", {"caption": to_caption}, None, None)
    from_result = create_vertex_and_connect_by_captions(g, "notion", {"caption": from_caption}, None, None)
    test_result = create_vertex_and_connect_by_captions(g, "notion", {"caption": test_caption}, {"isSupportedBy": [to_caption]}, {"isSupportedBy": [from_caption]})

    to_id   = to_result  ["created"]["internal_id"]
    from_id = from_result["created"]["internal_id"]
    test_id = test_result["created"]["internal_id"]

    test_vertex = read_vertex_with_edges(g, test_id)

    assert test_vertex["caption"] == test_caption
    assert any(edge for edge in test_vertex["relationships"]['isSupportedBy'] if edge["caption"] == to_caption)
    assert any(edge for edge in test_vertex["relationships"]['supports']      if edge["caption"] == from_caption)

    # print(json.dumps(test_vertex, indent=2, ensure_ascii=False))

    result = delete_vertex_by_id(g, to_id)
    assert result["deleted"] is True
    result = delete_vertex_by_id(g, from_id)
    assert result["deleted"] is True
    result = delete_vertex_by_id(g, test_id)
    assert result["deleted"] is True

@pytest.mark.anyio
async def test_search_vertices(g):
    results = search_vertices(g, ["notion"], "Иоан", limit=10)
    print(json.dumps(results, indent=2, ensure_ascii=False))
    assert len(results) > 0

@pytest.mark.anyio
async def test_get_vertices_by_captions(g):
    results = get_vertices_by_captions(g, ["Jn 1:1", "Jn 1:2", "Jn 1:3"])
    print(json.dumps(results, indent=2, ensure_ascii=False))
    assert len(results) == 3