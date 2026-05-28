from __future__ import annotations

from typing import Any

import graphviz
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession

from ..gremlin_client import AppContext, get_g
from ..gremlin_helpers import get_subgraph_by_captions


_NODE_STYLE: dict[str, dict[str, str]] = {
    "notion":       {"shape": "ellipse",    "fillcolor": "#fff3b0", "style": "filled"},
    "notionGroup":  {"shape": "folder",     "fillcolor": "#ffd6a5", "style": "filled"},
    "verse":        {"shape": "box",        "fillcolor": "#caffbf", "style": "filled,rounded"},
    "verseGroup":   {"shape": "folder",     "fillcolor": "#9bf6ff", "style": "filled"},
    "quotation":    {"shape": "note",       "fillcolor": "#bdb2ff", "style": "filled"},
    "book":         {"shape": "cylinder",   "fillcolor": "#a0c4ff", "style": "filled"},
    "person":       {"shape": "house",      "fillcolor": "#ffc6ff", "style": "filled"},
}
_DEFAULT_NODE_STYLE = {"shape": "box", "fillcolor": "#eeeeee", "style": "filled"}

_EDGE_STYLE: dict[str, dict[str, str]] = {
    "refersTo":       {"style": "dashed", "color": "#3a86ff"},
    "contains":       {"style": "bold",   "color": "#333333"},
    "isSupportedBy":  {"style": "solid",  "color": "#2a9d8f"},
    "isChallengedBy": {"style": "solid",  "color": "#e63946"},
    "isParallelTo":   {"style": "dotted", "color": "#6a4c93"},
    "next":           {"style": "solid",  "color": "#264653", "arrowhead": "vee"},
    "writtenBy":      {"style": "solid",  "color": "#8d99ae"},
}
_DEFAULT_EDGE_STYLE = {"style": "solid", "color": "#999999"}

_VALID_LAYOUTS = {"dot", "neato", "sfdp", "circo", "fdp", "twopi"}
_VALID_DIRECTIONS = {"LR", "TB", "RL", "BT"}


def _wrap_caption(text: str, width: int = 24) -> str:
    """Soft-wrap a caption into multiple lines for nicer node labels."""
    if text is None:
        return ""
    words = str(text).split()
    if not words:
        return ""
    lines: list[str] = []
    current = words[0]
    for w in words[1:]:
        if len(current) + 1 + len(w) <= width:
            current = f"{current} {w}"
        else:
            lines.append(current)
            current = w
    lines.append(current)
    return "\n".join(lines)


def _render_svg(
    vertices: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    layout: str,
    direction: str,
    include_edge_labels: bool,
) -> str:
    dot = graphviz.Digraph(engine=layout, format="svg")
    dot.attr(rankdir=direction, bgcolor="white", overlap="false", splines="true")
    dot.attr("node", fontname="Helvetica", fontsize="11")
    dot.attr("edge", fontname="Helvetica", fontsize="9")

    for v in vertices:
        node_id = str(v["internal_id"])
        label = _wrap_caption(v.get("caption") or node_id)
        style = _NODE_STYLE.get(v.get("label", ""), _DEFAULT_NODE_STYLE)
        dot.node(node_id, label=label, **style)

    for e in edges:
        style = _EDGE_STYLE.get(e["label"], _DEFAULT_EDGE_STYLE)
        edge_label = e["label"] if include_edge_labels else ""
        dot.edge(str(e["from_id"]), str(e["to_id"]), label=edge_label, **style)

    return dot.pipe(format="svg").decode("utf-8")


def register_diagram_tools(mcp: FastMCP) -> None:

    @mcp.tool()
    def create_diagram_by_captions(
        ctx: Context[ServerSession, AppContext],
        captions: list[str],
        layout: str = "dot",
        direction: str = "LR",
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
        if layout not in _VALID_LAYOUTS:
            raise ValueError(f"Invalid layout: {layout}. Must be one of: {', '.join(sorted(_VALID_LAYOUTS))}")
        if direction not in _VALID_DIRECTIONS:
            raise ValueError(f"Invalid direction: {direction}. Must be one of: {', '.join(sorted(_VALID_DIRECTIONS))}")
        if not captions:
            raise ValueError("captions must be a non-empty list")

        g = get_g(ctx)
        subgraph = get_subgraph_by_captions(g, captions)

        if subgraph["missing"]:
            raise ValueError(f"Vertices not found for captions: {subgraph['missing']}")
        if subgraph["ambiguous"]:
            raise ValueError(f"Ambiguous captions (multiple matches): {subgraph['ambiguous']}")

        return _render_svg(
            vertices=subgraph["vertices"],
            edges=subgraph["edges"],
            layout=layout,
            direction=direction,
            include_edge_labels=include_edge_labels,
        )
