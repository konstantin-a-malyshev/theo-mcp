from __future__ import annotations

from typing import Any

from gremlin_python.process.graph_traversal import __
from gremlin_python.process.traversal import T
from mcp.server.fastmcp import Context
from mcp.server.session import ServerSession

from .gremlin_client import AppContext, get_g
from .validation import normalize_label


def flatten_value_map(raw: dict[Any, Any]) -> dict[str, Any]:
    """Flatten valueMap(True) output into JSON-friendly keys/values."""
    out: dict[str, Any] = {}
    for k, v in raw.items():
        if k == T.id:
            out["internal_id"] = v
        elif k == T.label:
            out["label"] = v
        else:
            key = str(k)
            if isinstance(v, list) and len(v) == 1:
                out[key] = v[0]
            else:
                out[key] = v
    return out


def resolve_vertices(ctx: Context[ServerSession, AppContext], ref: dict[str, Any], limit: int = 10) -> list[dict[str, Any]]:
    """Resolve a vertex reference into up to `limit` matches."""
    g = get_g(ctx)
    t = g.V()

    if "label" in ref and ref["label"]:
        t = t.hasLabel(normalize_label(str(ref["label"])))

    if "id" in ref and ref["id"] is not None:
        t = t.has("id", int(ref["id"]))
    elif "caption" in ref and ref["caption"] is not None:
        t = t.has("caption", str(ref["caption"]))
    else:
        raise ValueError("Vertex ref must include either 'id' or 'caption' (and optionally 'label').")

    raw_list = t.limit(limit).valueMap(True).toList()
    return [flatten_value_map(r) for r in raw_list]


def resolve_unique_vertex(ctx: Context[ServerSession, AppContext], ref: dict[str, Any]) -> dict[str, Any]:
    matches = resolve_vertices(ctx, ref, limit=2)
    if not matches:
        raise ValueError(f"Vertex not found for ref={ref}")
    if len(matches) > 1:
        raise ValueError(
            f"Ambiguous vertex ref={ref}. Matches: {matches}. Please add 'label' or use 'id'."
        )
    return matches[0]


def read_vertex_with_edges(ctx: Context[ServerSession, AppContext], label: str, vertex_id: int) -> dict[str, Any]:
    """Read vertex by (label + property id) and include all in/out edges."""
    g = get_g(ctx)
    canon = normalize_label(label)

    base = g.V().hasLabel(canon).has("id", int(vertex_id))
    raw = base.limit(1).valueMap(True).toList()
    if not raw:
        raise ValueError(f"Vertex not found: label={canon} id={vertex_id}")

    vertex = flatten_value_map(raw[0])

    in_edges = (
        base.inE()
        .project("edge_label", "from")
        .by(__.label())
        .by(
            __.outV()
            .project("label", "id", "caption", "internal_id")
            .by(__.label())
            .by(__.values("id"))
            .by(__.values("caption"))
            .by(__.id())
        )
        .toList()
    )
    out_edges = (
        base.outE()
        .project("edge_label", "to")
        .by(__.label())
        .by(
            __.inV()
            .project("label", "id", "caption", "internal_id")
            .by(__.label())
            .by(__.values("id"))
            .by(__.values("caption"))
            .by(__.id())
        )
        .toList()
    )

    return {"vertex": vertex, "in_edges": in_edges, "out_edges": out_edges}
