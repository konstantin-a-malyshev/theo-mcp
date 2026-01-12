from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .gremlin_client import app_lifespan
from .tools.domain import register_domain_tools
from .tools.edges import register_edge_tools
from .tools.vertices import register_vertex_tools


def create_mcp() -> FastMCP:
    mcp = FastMCP("janusgraph-mcp", lifespan=app_lifespan, json_response=True)
    
    # Register tools in a predictable order
    register_vertex_tools(mcp)
    register_domain_tools(mcp)
    register_edge_tools(mcp)

    return mcp


app = create_mcp()
