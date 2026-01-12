from __future__ import annotations

import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Config:
    gremlin_url: str = "ws://localhost:8182/gremlin"
    gremlin_traversal_source: str = "g"
    mcp_transport: str = "stdio"  # or "streamable-http"

def _env(name: str, default: str) -> str:
    v = os.getenv(name)
    return v if v not in (None, "") else default

def get_config() -> Config:
    return Config(
        gremlin_url=_env("GREMLIN_URL", "ws://localhost:8182/gremlin"),
        gremlin_traversal_source=_env("GREMLIN_TRAVERSAL_SOURCE", "g"),
        mcp_transport=_env("MCP_TRANSPORT", "stdio"),
    )
