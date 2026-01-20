from __future__ import annotations

from typing import Any

from gremlin_python.process.graph_traversal import __
from gremlin_python.process.traversal import T
from gremlin_python.process.graph_traversal import GraphTraversalSource
from mcp.server.fastmcp import Context
from mcp.server.session import ServerSession

from .gremlin_client import AppContext, get_g
from .validation import normalize_label, normalize_edge_label, validate_and_fix_properties

direct_reverse_mapping = {
    "next"          : "previous",
    "isSupportedBy" : "supports",
    "isChallengedBy": "challenges",
    "refersTo"      : "isReferredBy",
    "contains"      : "isContainedIn",
}

backward_reverse_mapping = {
    "previous"      : "next",
    "supports"      : "isSupportedBy",
    "challenges"    : "isChallengedBy",
    "isReferredBy"  : "refersTo",
    "isContainedIn" : "contains",
}

def reverse_direct_relationship_keys(data: dict[str, Any]) -> dict[str, Any]:
    reversed_dict = {}
    for key, value in data.items():
        new_key = direct_reverse_mapping.get(key, key)  # Use original key if not in mapping
        reversed_dict[new_key] = value
    return reversed_dict

def reverse_backward_relationship_keys(data: dict[str, Any]) -> dict[str, Any]:
    reversed_dict = {}
    for key, value in data.items():
        new_key = backward_reverse_mapping.get(key, key)  # Use original key if not in mapping
        reversed_dict[new_key] = value
    return reversed_dict

def filter_direct_relationships(data: dict[str, Any]) -> dict[str, Any]:
    filtered_dict = {}
    for key, value in data.items():
        if key in direct_reverse_mapping:
            filtered_dict[key] = value
    return filtered_dict

def filter_backward_relationships(data: dict[str, Any]) -> dict[str, Any]:
    filtered_dict = {}
    for key, value in data.items():
        if key in backward_reverse_mapping:
            filtered_dict[key] = value
    return filtered_dict

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

def get_vertices_by_caption(g: GraphTraversalSource, caption: str, limit: int = 10) -> list[dict[str, Any]]:
    """Resolve a vertex caption into up to `limit` matches."""
    t = g.V().has("caption", caption)

    raw_list = t.limit(limit).valueMap(True).toList()
    return [flatten_value_map(r) for r in raw_list]

def get_unique_vertex_by_caption(g: GraphTraversalSource, caption: str) -> dict[str, Any]:
    matches = get_vertices_by_caption(g, caption, limit=2)
    if not matches:
        raise ValueError(f"Vertex not found for caption={caption}")
    if len(matches) > 1:
        raise ValueError(
            f"Ambiguous vertex caption={caption}. Matches: {matches}."
        )
    return matches[0]

def create_vertex_and_connect_by_captions(
    g: GraphTraversalSource,
    label: str,
    properties: dict[str, Any],
    edges_out : dict[str, list[str]] | None = None,
    edges_in  : dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    """
    Create a vertex, then connect it to existing vertices identified by their *captions*.

    - edges_out: new -> targets
    - edges_in:  sources -> new
    """

    created = create_vertex(g, label=label, properties=properties)["created"]
    new_internal_id = int(created["internal_id"])

    results: dict[str, Any] = {"created": created, "edges_created": []}

    # Try to ensure that all the targets/sources exist first
    if edges_out:
        for edge_label, captions in edges_out.items():
            e = normalize_edge_label(edge_label)
            for cap in captions:
                get_unique_vertex_by_caption(g, cap)
    if edges_in:
        for edge_label, captions in edges_in.items():
            e = normalize_edge_label(edge_label)
            for cap in captions:
                get_unique_vertex_by_caption(g, cap)
            
    # Now create the edges
    if edges_out:
        for edge_label, captions in edges_out.items():
            e = normalize_edge_label(edge_label)
            for cap in captions:
                target = get_unique_vertex_by_caption(g, cap)
                g.V(target["internal_id"]).as_("a") \
                    .V(target["internal_id"]).as_("b") \
                    .add_e(e).from_("a").to("b") \
                    .iterate()
                
                results["edges_created"].append(
                    {
                        "edge_label": e,
                        "out": {"label": created["label"], "internalid": created.get("internal_id"), "caption": created.get("caption")},
                        "in": {"label": target["label"], "internalid": target.get("internal_id"), "caption": target.get("caption")},
                    }
                )

    if edges_in:
        for edge_label, captions in edges_in.items():
            e = normalize_edge_label(edge_label)
            for cap in captions:
                source = get_unique_vertex_by_caption(g, cap)
                g.V(source["internal_id"]).as_("a") \
                    .V(new_internal_id).as_("b") \
                    .addE(e).from_("a").to("b") \
                    .iterate()
                
                results["edges_created"].append(
                    {
                        "edge_label": e,
                        "out": {"label": source["label"], "id": source.get("id"), "caption": source.get("caption")},
                        "in": {"label": created["label"], "id": created.get("id"), "caption": created.get("caption")},
                    }
                )
    return results

def create_vertex(g: GraphTraversalSource, label: str, properties: dict[str, Any]) -> dict[str, Any]:
    label = normalize_label(label)
    props = validate_and_fix_properties(label, properties, require_required=True)

    existing = g.V().hasLabel(label).has("caption", props["caption"]).limit(1).toList()
    if existing:
        raise ValueError(f"Vertex already exists: label={label} caption={props['caption']}")

    t = g.addV(label)
    for k, v in props.items():
        t = t.property(k, v)
    created_raw = t.valueMap(True).next()
    return {"created": flatten_value_map(created_raw)}

def read_vertex_with_edges(g: GraphTraversalSource, id: int) -> dict[str, Any]:
    """Read vertex by id and include all in/out edges with their vertexes."""

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

    vertex['relationships'] = {**out_edges[0], **reverse_direct_relationship_keys(in_edges[0])}

    return vertex
