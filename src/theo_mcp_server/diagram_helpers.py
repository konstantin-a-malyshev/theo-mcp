from __future__ import annotations

import re
from typing import Any

import graphviz

from gremlin_python.process.graph_traversal import GraphTraversalSource

from .gremlin_helpers import get_subgraph_by_captions


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

VALID_LAYOUTS = {"dot", "neato", "sfdp", "circo", "fdp", "twopi"}
VALID_DIRECTIONS = {"LR", "TB", "RL", "BT"}


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


def render_svg(
    vertices: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    layout: str,
    direction: str,
    include_edge_labels: bool,
) -> str:
    dot = graphviz.Digraph(engine=layout, format="svg")
    dot.attr(rankdir=direction, bgcolor="white", overlap="false", splines="true", pad="0.4")
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

    try:
        svg = dot.pipe(format="svg").decode("utf-8")
    except graphviz.backend.execute.ExecutableNotFound:
        raise ValueError(
            "Graphviz executable not found. "
            "Please install Graphviz and make sure 'dot' is on your PATH: "
            "https://graphviz.org/download/"
        )

    # Make the SVG responsive: replace Graphviz's fixed pt dimensions with
    # width="100%" and no height so the SVG scales freely inside its container
    # while preserving aspect ratio via the existing viewBox attribute.
    svg = re.sub(r'\bwidth="[\d.]+pt"', 'width="100%"', svg)
    svg = re.sub(r'\s*height="[\d.]+pt"', '', svg)

    return svg


def create_diagram_by_captions(
    g: GraphTraversalSource,
    captions: list[str],
    layout: str = "dot",
    direction: str = "LR",
    include_edge_labels: bool = True,
) -> str:
    """Build an SVG diagram of the induced subgraph for the given vertex captions."""
    if layout not in VALID_LAYOUTS:
        raise ValueError(f"Invalid layout: {layout}. Must be one of: {', '.join(sorted(VALID_LAYOUTS))}")
    if direction not in VALID_DIRECTIONS:
        raise ValueError(f"Invalid direction: {direction}. Must be one of: {', '.join(sorted(VALID_DIRECTIONS))}")
    if not captions:
        raise ValueError("captions must be a non-empty list")

    subgraph = get_subgraph_by_captions(g, captions)

    if subgraph["missing"]:
        raise ValueError(f"Vertices not found for captions: {subgraph['missing']}")
    if subgraph["ambiguous"]:
        raise ValueError(f"Ambiguous captions (multiple matches): {subgraph['ambiguous']}")

    return render_svg(
        vertices=subgraph["vertices"],
        edges=subgraph["edges"],
        layout=layout,
        direction=direction,
        include_edge_labels=include_edge_labels,
    )
