from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .gremlin_client import app_lifespan
from .tools.diagram import register_diagram_tools
from .tools.graph import register_graph_tools


def create_mcp() -> FastMCP:
    mcp = FastMCP("theo-mcp", lifespan=app_lifespan, json_response=True)

    # Register tools in a predictable order
    register_graph_tools(mcp)
    register_diagram_tools(mcp)

    return mcp


app = create_mcp()
