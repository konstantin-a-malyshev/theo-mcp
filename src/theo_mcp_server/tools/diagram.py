from __future__ import annotations

import uuid

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession

from ..gremlin_client import AppContext, get_cloud_storage, get_g
from ..config import get_config
from .. import diagram_helpers


def register_diagram_tools(mcp: FastMCP) -> None:

    @mcp.tool()
    def create_diagram_by_captions(
        ctx: Context[ServerSession, AppContext],
        captions: list[str],
        layout: str = "dot",
        direction: str = "TB",
        include_edge_labels: bool = True,
    ) -> dict[str, str]:
        """
        Build an SVG diagram of the induced subgraph for the given vertex captions,
        store it in the configured file cloud, and return a download link.

        Fetches the vertices identified by `captions` and all edges that connect them
        to each other (edges to vertices outside the set are excluded), renders the
        result as an SVG using Graphviz, uploads the SVG to the cloud storage, and
        returns a public download link instead of the SVG source itself.

        Args:
            captions: vertex captions to include in the diagram.
            layout: Graphviz layout engine. One of dot, neato, sfdp, circo, fdp, twopi.
            direction: graph orientation for the `dot` engine. One of LR, TB, RL, BT.
            include_edge_labels: whether to print edge type next to each edge.

        Returns:
            A dict with the uploaded `filename` and its public `download_url`.
        """
        g = get_g(ctx)
        svg = diagram_helpers.create_diagram_by_captions(
            g,
            captions=captions,
            layout=layout,
            direction=direction,
            include_edge_labels=include_edge_labels,
        )

        cloud_storage = get_cloud_storage(ctx)
        filename = f"diagram-{uuid.uuid4().hex}.svg"
        download_url = cloud_storage.upload(filename, svg, content_type="image/svg+xml")

        result = {"filename": filename, "download_url": download_url}
        # If public links are password-protected, the recipient needs the password.
        share_password = get_config().owncloud_share_password
        if share_password:
            result["password"] = share_password
        return result
