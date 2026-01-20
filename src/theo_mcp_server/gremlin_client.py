from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from gremlin_python.driver.driver_remote_connection import DriverRemoteConnection
from gremlin_python.driver.aiohttp.transport import AiohttpTransport
from gremlin_python.process.anonymous_traversal import traversal
from gremlin_python.process.graph_traversal import GraphTraversalSource
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession

from .config import get_config


@dataclass
class AppContext:
    connection: DriverRemoteConnection
    g: Any  # GraphTraversalSource (gremlin-python type)


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Create & close the Gremlin remote connection once per server lifecycle."""
    cfg = get_config()

    conn = DriverRemoteConnection(
        cfg.gremlin_url, 
        cfg.gremlin_traversal_source,
        transport_factory=lambda: AiohttpTransport(call_from_event_loop=True))
    
    g = traversal().withRemote(conn)

    try:
        yield AppContext(connection=conn, g=g)
    finally:
        try:
            conn.close()
        except Exception:
            pass

async def get_g_for_tests() -> GraphTraversalSource:
    cfg = get_config()
    
    conn = DriverRemoteConnection(
        cfg.gremlin_url,
        cfg.gremlin_traversal_source,
        transport_factory=lambda: AiohttpTransport(call_from_event_loop=True)
    )
    
    g = traversal().withRemote(conn)
    
    return g

def get_g(ctx: Context[ServerSession, AppContext]):
    return ctx.request_context.lifespan_context.g
