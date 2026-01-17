from __future__ import annotations

from typing import Any

from gremlin_python.process.graph_traversal import __
from gremlin_python.process.traversal import T
from mcp.server.fastmcp import Context
from mcp.server.session import ServerSession

from .gremlin_client import AppContext, get_g
from .validation import normalize_label

def reverse_relationship_keys(data: dict[str, Any]) -> dict[str, Any]:
    reverse_mapping = {
        "next"          : "previous",
        "previous"      : "next",
        "isSupportedBy" : "supports",
        "supports"      : "isSupportedBy",
        "isChallengedBy": "challenges",
        "challenges"    : "isChallengedBy",
    }

    reversed_dict = {}
    for key, value in data.items():
        new_key = reverse_mapping.get(key, key)  # Use original key if not in mapping
        reversed_dict[new_key] = value
    return reversed_dict

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


def read_vertex_with_edges(ctx: Context[ServerSession, AppContext], id: int) -> dict[str, Any]:
    """Read vertex by id and include all in/out edges with their vertexes."""
    g = get_g(ctx)

    raw = g.V(id).valueMap(True).toList()
    if not raw:
        raise ValueError(f"Vertex not found: id={id}")

    vertex = flatten_value_map(raw[0])

    out_edges = (
        g.V(id).outE().group()
        .by(__.label())
        .by(__.inV().project("label", "id", "caption")
            .by(__.label())
            .by(T.id)
            .by(__.values("caption"))
            .fold()
        )
        .toList()
    )

    in_edges = (
        g.V(id).inE().group()
        .by(__.label())
        .by(__.outV().project("label", "id", "caption")
            .by(__.label())
            .by(T.id)
            .by(__.values("caption"))
            .fold()
        )
        .toList()
    )

    vertex['relationships'] = {**out_edges[0], **reverse_relationship_keys(in_edges[0])}

    return vertex
