from __future__ import annotations

from typing import Any

from gremlin_python.process.graph_traversal import __
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession

from ..gremlin_client import AppContext, get_g
from ..gremlin_helpers import get_unique_vertex_by_caption
from ..validation import normalize_edge_label


def register_edge_tools(mcp: FastMCP) -> None:
    # @mcp.tool()
    def delete_edge(ctx: Context[ServerSession, AppContext], edge_label: str, out_vertex: dict[str, Any], in_vertex: dict[str, Any]) -> dict[str, Any]:
        """Delete all edges of type edge_label going from out_vertex -> in_vertex."""
        g = get_g(ctx)
        e = normalize_edge_label(edge_label)
        out_v = get_unique_vertex_by_caption(ctx, out_vertex)
        in_v = get_unique_vertex_by_caption(ctx, in_vertex)

        count = (
            g.V(out_v["internal_id"])
            .outE(e)
            .where(__.inV().hasId(in_v["internal_id"]))
            .count()
            .next()
        )

        (
            g.V(out_v["internal_id"])
            .outE(e)
            .where(__.inV().hasId(in_v["internal_id"]))
            .drop()
            .iterate()
        )

        return {
            "deleted_edges": int(count),
            "edge_label": e,
            "out": {"label": out_v["label"], "id": out_v.get("id"), "caption": out_v.get("caption")},
            "in": {"label": in_v["label"], "id": in_v.get("id"), "caption": in_v.get("caption")},
        }
