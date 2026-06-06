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

from .cloud_storage import CloudStorage, OwnCloudStorage
from .config import get_config


@dataclass
class AppContext:
    connection: DriverRemoteConnection
    g: Any  # GraphTraversalSource (gremlin-python type)
    cloud_storage: CloudStorage


def _make_connection() -> DriverRemoteConnection:
    cfg = get_config()
    return DriverRemoteConnection(
        cfg.gremlin_url,
        cfg.gremlin_traversal_source,
        username=cfg.gremlin_username if cfg.gremlin_username else None,
        password=cfg.gremlin_password if cfg.gremlin_password else None,
        transport_factory=lambda: AiohttpTransport(call_from_event_loop=True),
    )


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Create & close the Gremlin remote connection once per server lifecycle."""
    conn = _make_connection()
    g = traversal().with_remote(conn)
    cloud_storage = OwnCloudStorage.from_config(get_config())

    try:
        yield AppContext(connection=conn, g=g, cloud_storage=cloud_storage)
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
        username=cfg.gremlin_username if cfg.gremlin_username else None,
        password=cfg.gremlin_password if cfg.gremlin_password else None,
        transport_factory=lambda: AiohttpTransport(call_from_event_loop=True)
    )
    
    g = traversal().withRemote(conn)
    
    return g

def _reconnect(app_ctx: AppContext) -> None:
    try:
        app_ctx.connection.close()
    except Exception:
        pass
    app_ctx.connection = _make_connection()
    app_ctx.g = traversal().with_remote(app_ctx.connection)


def _is_closed_connection_error(exc: BaseException) -> bool:
    msg = str(exc)
    if "Connection was already closed" in msg or "Connection refused" in msg:
        return True
    cause = exc.__cause__ or exc.__context__
    return cause is not None and cause is not exc and _is_closed_connection_error(cause)


def get_g(ctx: Context[ServerSession, AppContext]):
    app_ctx = ctx.request_context.lifespan_context
    # Cheap liveness probe; rebuild the connection if the socket has dropped
    # (idle timeout, server restart, laptop sleep/resume).
    try:
        app_ctx.g.inject(0).toList()
    except Exception as e:
        if _is_closed_connection_error(e):
            _reconnect(app_ctx)
        else:
            raise
    return app_ctx.g


def get_cloud_storage(ctx: Context[ServerSession, AppContext]) -> CloudStorage:
    return ctx.request_context.lifespan_context.cloud_storage
