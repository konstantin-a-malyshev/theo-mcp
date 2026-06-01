from __future__ import annotations

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession

from ..gremlin_client import AppContext, get_g
from .. import diagram_helpers


def register_diagram_tools(mcp: FastMCP) -> None:

    @mcp.tool()
    def create_diagram_by_captions(
        ctx: Context[ServerSession, AppContext],
        captions: list[str],
        layout: str = "dot",
        direction: str = "TB",
        include_edge_labels: bool = True,
    ) -> str:
        """
        Build an SVG diagram of the induced subgraph for the given vertex captions.

        Fetches the vertices identified by `captions` and all edges that connect them
        to each other (edges to vertices outside the set are excluded), then renders
        the result as an SVG string using Graphviz.

        Args:
            captions: vertex captions to include in the diagram.
            layout: Graphviz layout engine. One of dot, neato, sfdp, circo, fdp, twopi.
            direction: graph orientation for the `dot` engine. One of LR, TB, RL, BT.
            include_edge_labels: whether to print edge type next to each edge.

        Returns:
            SVG source as a string.
        """
        g = get_g(ctx)
        return diagram_helpers.create_diagram_by_captions(
            g,
            captions=captions,
            layout=layout,
            direction=direction,
            include_edge_labels=include_edge_labels,
        )
