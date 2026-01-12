from __future__ import annotations

from .config import get_config
from .server import app


def main() -> None:
    cfg = get_config()
    app.run(transport=cfg.mcp_transport)


if __name__ == "__main__":
    main()
