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
    owncloud_url: str = "https://localhost:9200/"
    owncloud_username: str = ""
    owncloud_password: str = ""
    owncloud_token: str = ""  # oCIS app token / OIDC bearer token
    owncloud_remote_dir: str = "theo-diagrams"
    owncloud_verify_ssl: bool = False

def _env(name: str, default: str) -> str:
    v = os.getenv(name)
    return v if v not in (None, "") else default

def _env_bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v in (None, ""):
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")

def get_config() -> Config:
    return Config(
        gremlin_url=_env("GREMLIN_URL", "ws://localhost:8182/gremlin"),
        gremlin_traversal_source=_env("GREMLIN_TRAVERSAL_SOURCE", "g"),
        gremlin_username=_env("GREMLIN_USERNAME", "username"),
        gremlin_password=_env("GREMLIN_PASSWORD", "password"),
        mcp_transport=_env("MCP_TRANSPORT", "stdio"),
        owncloud_url=_env("OWNCLOUD_URL", "https://localhost:9200/"),
        owncloud_username=_env("OWNCLOUD_USERNAME", ""),
        owncloud_password=_env("OWNCLOUD_PASSWORD", ""),
        owncloud_token=_env("OWNCLOUD_TOKEN", ""),
        owncloud_remote_dir=_env("OWNCLOUD_REMOTE_DIR", "theo-diagrams"),
        owncloud_verify_ssl=_env_bool("OWNCLOUD_VERIFY_SSL", False),
    )
