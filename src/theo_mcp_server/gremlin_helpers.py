from __future__ import annotations

from typing import Any

from gremlin_python.process.graph_traversal import __
from gremlin_python.process.traversal import T, P, TextP
from gremlin_python.process.graph_traversal import GraphTraversalSource
from mcp.server.fastmcp import Context
from mcp.server.session import ServerSession

from .gremlin_client import AppContext, get_g
from .schema import LABELS_CANON
from .validation import normalize_label, normalize_edge_label, validate_and_fix_properties

# Valid quotation statuses
VALID_QUOTATION_STATUSES = ["new", "suspended", "processed"]

def validate_quotation_status(status: str) -> None:
    """Validate that the given status is a valid quotation status."""
    if status not in VALID_QUOTATION_STATUSES:
        raise ValueError(f"Invalid status: {status}. Must be one of: {', '.join(VALID_QUOTATION_STATUSES)}")

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

def search_vertices(g: GraphTraversalSource, types: list[str], search_text: str, limit: int = 10) -> list[dict[str, Any]]:
    """Search for vertices by substring within specified types."""
    t = g.V().has('type', P.within(types)).has('caption', TextP.containing(search_text))

    raw_list = t.limit(limit).valueMap(True).toList()
    return [flatten_value_map(r) for r in raw_list]

def get_vertices_by_type(g: GraphTraversalSource, type: str, limit: int = 10) -> list[dict[str, Any]]:
    """Get vertices of a given type."""
    t = g.V().has('type', type)
    raw_list = t.limit(limit).valueMap(True).toList()
    return [flatten_value_map(r) for r in raw_list]

def get_vertices_by_captions(g: GraphTraversalSource, captions: list[str]) -> list[dict[str, Any]]:
    t = g.V().has("caption", P.within(captions))
    raw_list = t.valueMap(True).toList()
    return [flatten_value_map(r) for r in raw_list]

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
            for cap in captions:
                get_unique_vertex_by_caption(g, cap)
    if edges_in:
        for edge_label, captions in edges_in.items():
            for cap in captions:
                get_unique_vertex_by_caption(g, cap)
            
    # Now create the edges
    if edges_out:
        for edge_label, captions in edges_out.items():
            for cap in captions:
                target = get_unique_vertex_by_caption(g, cap)
                result = create_edge(g, edge_label, new_internal_id, target["internal_id"])
                results["edges_created"].append(result)

    if edges_in:
        for edge_label, captions in edges_in.items():
            for cap in captions:
                source = get_unique_vertex_by_caption(g, cap)
                result = create_edge(g, edge_label, source["internal_id"], new_internal_id)
                results["edges_created"].append(result)
    return results

def is_vertex_existing_by_caption(
    g: GraphTraversalSource, caption: str, label: str | None = None
) -> bool:
    """Return True if any vertex with the given caption (and optional label) exists.

    Only the vertex id is fetched to avoid GraphBinary deserialization of full
    Vertex objects, which can fail with `KeyError: DataType.custom` against
    JanusGraph.
    """
    t = g.V().has("caption", caption)
    if label is not None:
        t = t.hasLabel(label)
    return bool(t.limit(1).id_().toList())


def create_vertex(g: GraphTraversalSource, label: str, properties: dict[str, Any]) -> dict[str, Any]:
    label = normalize_label(label)
    props = validate_and_fix_properties(label, properties, require_required=True)

    if is_vertex_existing_by_caption(g, props["caption"], label):
        raise ValueError(f"Vertex already exists: label={label} caption={props['caption']}")

    t = g.addV(label).property("type", label)
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

# Fields of the containing receptionWork that are returned alongside a passage.
RECEPTION_WORK_SUMMARY_PROPS = ("caption", "tlgAuthorId", "corpusPath", "ctsUrn")


def read_reception_passage_with_work(g: GraphTraversalSource, id: int) -> dict[str, Any]:
    """Read a receptionPassage with its edges, plus a summary of its receptionWork.

    The summary carries just enough to locate the text in the normalized corpus.
    Every property read is wrapped in `coalesce` because most of them are empty
    until the work is matched to the corpus, and a `by()` that yields nothing
    would drop the whole row.
    """
    passage = read_vertex_with_edges(g, id)

    t = (
        g.V(id)
        .in_("contains")
        .has("type", "receptionWork")
        .project("internal_id", *RECEPTION_WORK_SUMMARY_PROPS)
        .by(T.id)
    )
    for prop in RECEPTION_WORK_SUMMARY_PROPS:
        t = t.by(__.coalesce(__.values(prop), __.constant("")))

    works = t.toList()
    passage["receptionWork"] = works[0] if works else None
    return passage


def delete_vertex_by_id(g: GraphTraversalSource, id: int) -> dict[str, Any]:
    """Delete a vertex (and all incident edges) by id."""
    raw = g.V(id).valueMap(True).toList()
    if not raw:
        raise ValueError(f"Vertex not found: id={id}")

    g.V(id).drop().iterate()
    return {"deleted": True, "id": int(id)}

def is_vertex_existing_by_id(g: GraphTraversalSource, id: int, label: str | None = None) -> bool:
    """Check if a vertex exists by id."""
    raw = g.V(id).valueMap(True).toList()
    return bool(raw)

def get_vertex_by_id(g: GraphTraversalSource, id: int) -> dict[str, Any]:
    """Get a vertex by id."""
    raw = g.V(id).valueMap(True).toList()
    if not raw:
        raise ValueError(f"Vertex not found: id={id}")
    return flatten_value_map(raw[0])

def create_edge(g: GraphTraversalSource, edge_label: str, source_vertex_id: int, target_vertex_id: int) -> dict[str, Any]:
    """Connect two existing vertices with an edge."""
    e = normalize_edge_label(edge_label)

    source = get_vertex_by_id(g, source_vertex_id)
    target = get_vertex_by_id(g, target_vertex_id)

    g.V(source_vertex_id).as_("a") \
        .V(target_vertex_id).as_("b") \
        .add_e(e).from_("a").to("b") \
        .iterate()

    return {
        "edge_created": {
            "edge_label": e,
            "source": {"label": source["label"], "internal_id": source.get("id"), "caption": source.get("caption")},
            "target": {"label": target["label"], "internal_id": target.get("id"), "caption": target.get("caption")},
        }
    }

def build_notion_groups_tree(g: GraphTraversalSource, includeNotions: bool) -> dict[str, Any]:
    """Get a multiple-level tree of all parentless "notionGroup" vertices with their nested "notionGroups" without nested notions."""
    
    if includeNotions:
        paths = (
            g.V().has('type',P.within('notionGroup', 'notion')).not_(__.inE('contains')).as_('root')
                .union(
                    __.identity().path().by('caption'),
                    __.repeat(__.out('contains').has('type', P.within('notionGroup', 'notion'))).emit().path().by('caption')
                )
        ).toList()
    else:
        paths = (
            g.V().has('type','notionGroup').not_(__.inE('contains')).as_('root')
                .union(
                    __.identity().path().by('caption'),
                    __.repeat(__.out('contains').has('type', 'notionGroup')).emit().path().by('caption')
                )
        ).toList()

    def build_tree(paths):
        tree = {}
        for item in paths:
            methods = dir(item)
            path = item.objects
            current = tree
            
            for vertex in path:
                if vertex not in current:
                    current[vertex] = {}
                current = current[vertex]
        
        return tree

    return build_tree(paths)

def get_subgraph_by_captions(g: GraphTraversalSource, captions: list[str]) -> dict[str, Any]:
    """Return induced subgraph for the given vertex captions.

    Output:
        {
            "vertices": [ {internal_id, label, caption, ...}, ... ],
            "edges":    [ {label, from_id, to_id}, ... ],
            "missing":  [caption, ...],          # captions with no match
            "ambiguous": {caption: count, ...},  # captions with >1 match
        }

    Only edges whose both endpoints belong to the requested set are returned.
    """
    if not captions:
        raise ValueError("captions must be a non-empty list")

    raw_vertices = g.V().has("caption", P.within(captions)).valueMap(True).toList()
    vertices = [flatten_value_map(r) for r in raw_vertices]

    counts: dict[str, int] = {}
    for v in vertices:
        cap = v.get("caption")
        if cap is not None:
            counts[cap] = counts.get(cap, 0) + 1

    missing = [c for c in captions if c not in counts]
    ambiguous = {c: n for c, n in counts.items() if n > 1}

    # TODO: ids is built from ALL matched vertices, including duplicates when a caption
    #   is ambiguous. The edge traversal below will then find edges between those phantom
    #   duplicates and include them in the returned `edges` list. The sole current caller
    #   (create_diagram_by_captions) guards against this by checking `ambiguous` before
    #   consuming `edges`, but any future caller that skips that check will get a corrupted
    #   subgraph with no exception raised. Consider clearing `edges` or raising inside
    #   this helper when `ambiguous` is non-empty.
    ids = [int(v["internal_id"]) for v in vertices]
    edges: list[dict[str, Any]] = []
    if len(ids) >= 2:
        raw_edges = (
            g.V(*ids).as_("from")
            .outE().as_("e")
            .inV().as_("to")
            .where(__.select("to").hasId(P.within(ids)))
            .select("from", "e", "to")
            .by(T.id)
            .by(__.label())
            .by(T.id)
            .dedup()
            .toList()
        )
        # TODO: The dedup key is (edge_label, from_id, to_id), not the edge element id.
        #   This silently collapses parallel edges of the same type between the same vertex
        #   pair into one. JanusGraph allows multiple edges with the same label between the
        #   same vertices (create_edge() has no duplicate guard), so this data loss can
        #   occur in practice. Fix: use the edge element id as the dedup key, or at minimum
        #   document this limitation clearly.
        seen: set[tuple] = set()
        for row in raw_edges:
            key = (row["e"], int(row["from"]), int(row["to"]))
            if key not in seen:
                seen.add(key)
                edges.append({
                    "label": row["e"],
                    "from_id": int(row["from"]),
                    "to_id": int(row["to"]),
                })

    return {
        "vertices": vertices,
        "edges": edges,
        "missing": missing,
        "ambiguous": ambiguous,
    }


def change_caption(g: GraphTraversalSource, old_caption: str, new_caption: str) -> dict[str, Any]:
    """Change the caption of a vertex."""
    vertex = get_unique_vertex_by_caption(g, old_caption)
    g.V(vertex["internal_id"]).property("caption", new_caption).iterate()
    return {"updated": True, "internal_id": vertex["internal_id"], "new_caption": new_caption}

def update_vertex_properties_by_caption(
    g: GraphTraversalSource,
    label: str,
    caption: str,
    properties: dict[str, Any],
) -> dict[str, Any]:
    """Update properties of the unique vertex with the given caption and label."""
    label = normalize_label(label)
    props = validate_and_fix_properties(label, properties, require_required=False)
    if not props:
        raise ValueError("No properties to update")

    id = get_unique_vertex_id_by_caption(g, caption, label)
    t = g.V(id)
    for k, v in props.items():
        t = t.property(k, v)
    t.iterate()
    return read_vertex_with_edges(g, id)

def get_unique_vertex_id_by_caption(g: GraphTraversalSource, caption: str, label: str) -> int:
    """Return the unique vertex id for a given caption and label, or raise."""
    ids = g.V().has("caption", caption).hasLabel(label).id_().toList()
    if not ids:
        raise ValueError(f"Vertex not found: label={label} caption={caption}")
    if len(ids) > 1:
        raise ValueError(f"Ambiguous vertex caption={caption} label={label}")
    return ids[0]

EDGE_EXPORT_KEYS = (
    "label",
    "source_id",
    "source_type",
    "source_caption",
    "target_id",
    "target_type",
    "target_caption",
)


def _by_edge_export(t: Any) -> Any:
    """Attach the endpoint projections used by `export_edges_for_types`.

    `coalesce` is mandatory on every `values(...)`: inside `project(...)` a `by()`
    traversal that yields nothing drops the *whole row* silently, so a vertex
    without a `caption` (or without `type`) would make its edges vanish from the
    backup without any error.
    """
    return (
        t.by(__.label())
        .by(__.outV().id_())
        .by(__.coalesce(__.outV().values("type"), __.outV().label()))
        .by(__.coalesce(__.outV().values("caption"), __.constant("")))
        .by(__.inV().id_())
        .by(__.coalesce(__.inV().values("type"), __.inV().label()))
        .by(__.coalesce(__.inV().values("caption"), __.constant("")))
    )


def export_vertices_by_type(g: GraphTraversalSource, type: str) -> list[dict[str, Any]]:
    """Read every vertex of the given `type` with all its properties.

    Selection goes through the `type` property rather than `hasLabel`, because
    JanusGraph does not index vertex labels.
    """
    raw = g.V().has("type", type).valueMap(True).toList()
    return [flatten_value_map(r) for r in raw]


def _drop_edge_labels(t: Any, excluded_edge_labels: list[str]) -> Any:
    """Filter unwanted edge labels *server-side*.

    This must happen before `project(...)`: the excluded set is dominated by the
    `next` chain between verses, which is one edge per verse and would otherwise
    be shipped over the wire only to be thrown away.
    """
    if not excluded_edge_labels:
        return t
    return t.not_(__.hasLabel(*excluded_edge_labels))


def _drop_edge_triples(
    t: Any, excluded_edge_triples: list[tuple[str, str, str]]
) -> Any:
    """Filter out whole `(source type, label, target type)` shapes *server-side*.

    Same reason as `_drop_edge_labels`: these shapes are the ones an import of an
    excluded vertex type rebuilds by itself, and they are dominated by the
    reception passages — one `contains` and one `refersTo` each, tens of thousands
    of both — which must not cross the wire only to be thrown away.

    The filter matches on the *shape*, not on the label alone, because `contains`
    and `refersTo` also carry the notion structure and the hand-made links from
    notions to verses, which no import can rebuild.
    """
    for source_type, label, target_type in excluded_edge_triples:
        t = t.not_(
            __.hasLabel(label)
            .where(__.outV().has("type", source_type))
            .where(__.inV().has("type", target_type))
        )
    return t


def export_edges_for_types(
    g: GraphTraversalSource,
    types: list[str],
    excluded_edge_labels: list[str] | None = None,
    excluded_edge_triples: list[tuple[str, str, str]] | None = None,
) -> list[dict[str, Any]]:
    """Read every edge of the graph except the excluded labels and shapes.

    Three disjoint passes, all driven by the indexed `type` property:

    1. outgoing edges of the exported vertices;
    2. incoming ones whose source is *not* exported (`verse -> notion`);
    3. edges between two non-exported vertices (`verse -isParallelTo-> verse`),
       which neither of the first two passes can see.

    No dedup — parallel edges are real data and must survive the round trip.
    """
    types = list(types)
    excluded = list(excluded_edge_labels or [])
    triples = list(excluded_edge_triples or [])
    other_types = sorted(set(LABELS_CANON.values()) - set(types))

    def _filtered(t: Any) -> Any:
        return _drop_edge_triples(_drop_edge_labels(t, excluded), triples)

    outgoing = _by_edge_export(
        _filtered(g.V().has("type", P.within(types)).outE())
        .project(*EDGE_EXPORT_KEYS)
    ).toList()

    incoming = _by_edge_export(
        _filtered(g.V().has("type", P.within(types)).inE())
        .where(__.not_(__.outV().has("type", P.within(types))))
        .project(*EDGE_EXPORT_KEYS)
    ).toList()

    between_others: list[Any] = []
    if other_types:
        between_others = _by_edge_export(
            _filtered(g.V().has("type", P.within(other_types)).outE())
            .where(__.inV().has("type", P.within(other_types)))
            .project(*EDGE_EXPORT_KEYS)
        ).toList()

    return [dict(row) for row in outgoing + incoming + between_others]


def count_vertices(g: GraphTraversalSource, types: list[str] | None = None) -> int:
    """Count all vertices, or only those carrying one of the given `type` values."""
    t = g.V() if types is None else g.V().has("type", P.within(list(types)))
    return int(t.count().next())


def move_notion_to_group(
    g: GraphTraversalSource, notion_caption: str, notion_group_caption: str
) -> dict[str, Any]:
    """Move a notion to another notionGroup. Removes any existing incoming
    `contains` edges from notionGroups and adds a `contains` edge from the
    target group to the notion.
    """
    notion_id = get_unique_vertex_id_by_caption(g, notion_caption, "notion")
    group_id = get_unique_vertex_id_by_caption(g, notion_group_caption, "notionGroup")

    removed = (
        g.V(notion_id)
        .inE("contains")
        .where(__.outV().hasLabel("notionGroup"))
        .count()
        .next()
    )
    (
        g.V(notion_id)
        .inE("contains")
        .where(__.outV().hasLabel("notionGroup"))
        .drop()
        .iterate()
    )

    create_edge(g, "contains", group_id, notion_id)

    return {
        "moved": True,
        "notion": {"caption": notion_caption, "internal_id": notion_id},
        "notionGroup": {"caption": notion_group_caption, "internal_id": group_id},
        "removed_previous_group_edges": int(removed),
    }

