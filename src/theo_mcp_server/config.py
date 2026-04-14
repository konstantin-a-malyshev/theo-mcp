from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Config:
    gremlin_url: str = "ws://localhost:8182/gremlin"
    gremlin_traversal_source: str = "g"
    gremlin_username: str = "username"
    gremlin_password: str = "password"
    mcp_transport: str = "stdio"  # or "streamable-http"

def _env(name: str, default: str) -> str:
    v = os.getenv(name)
    return v if v not in (None, "") else default

def get_config() -> Config:
    return Config(
        gremlin_url=_env("GREMLIN_URL", "ws://localhost:8182/gremlin"),
        gremlin_traversal_source=_env("GREMLIN_TRAVERSAL_SOURCE", "g"),
        gremlin_username=_env("GREMLIN_USERNAME", "username"),
        gremlin_password=_env("GREMLIN_PASSWORD", "password"),
        mcp_transport=_env("MCP_TRANSPORT", "stdio"),
    )
