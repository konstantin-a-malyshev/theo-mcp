from __future__ import annotations

from typing import Any

from gremlin_python.process.graph_traversal import __
from gremlin_python.process.traversal import T
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession

from ..gremlin_client import AppContext, get_g
from ..gremlin_helpers import (
    read_vertex_with_edges,
    resolve_unique_vertex,
)
from ..validation import normalize_edge_label, normalize_label, validate_properties


def register_vertex_tools(mcp: FastMCP) -> None:
    # @mcp.tool()
    def create_vertex(ctx: Context[ServerSession, AppContext], label: str, properties: dict[str, Any]) -> dict[str, Any]:
        """Create a vertex of any allowed label."""
        g = get_g(ctx)
        canon = normalize_label(label)
        props = validate_properties(canon, properties, require_required=True)

        existing = g.V().hasLabel(canon).has("id", props["id"]).limit(1).toList()
        if existing:
            raise ValueError(f"Vertex already exists: label={canon} id={props['id']}")

        t = g.addV(canon)
        for k, v in props.items():
            t = t.property(k, v)
        created_raw = t.valueMap(True).next()
        from ..gremlin_helpers import flatten_value_map
        return {"created": flatten_value_map(created_raw)}

    # @mcp.tool()
    def create_vertex_and_connect_by_captions(
        ctx: Context[ServerSession, AppContext],
        label: str,
        properties: dict[str, Any],
        edges_out: dict[str, list[str]] | None = None,
        edges_in: dict[str, list[str]] | None = None,
        target_label: str | None = None,
    ) -> dict[str, Any]:
        """
        Create a vertex, then connect it to existing vertices identified by their *captions*.

        - edges_out: new -> targets
        - edges_in:  sources -> new
        """
        created = create_vertex(ctx, label=label, properties=properties)["created"]
        new_internal_id = created["internal_id"]

        results: dict[str, Any] = {"created": created, "edges_created": []}

        def _resolve_by_caption(caption: str) -> dict[str, Any]:
            ref: dict[str, Any] = {"caption": caption}
            if target_label:
                ref["label"] = target_label
            return resolve_unique_vertex(ctx, ref)

        g = get_g(ctx)

        if edges_out:
            for edge_label, captions in edges_out.items():
                e = normalize_edge_label(edge_label)
                for cap in captions:
                    target = _resolve_by_caption(cap)
                    eid = (
                        g.V(new_internal_id)
                        .as_("a")
                        .V(target["internal_id"])
                        .addE(e)
                        .from_("a")
                        .id()
                        .next()
                    )
                    results["edges_created"].append(
                        {
                            "edge_label": e,
                            "out": {"label": created["label"], "id": created.get("id"), "caption": created.get("caption")},
                            "in": {"label": target["label"], "id": target.get("id"), "caption": target.get("caption")},
                            "edge_internal_id": eid,
                        }
                    )

        if edges_in:
            for edge_label, captions in edges_in.items():
                e = normalize_edge_label(edge_label)
                for cap in captions:
                    source = _resolve_by_caption(cap)
                    eid = (
                        g.V(source["internal_id"])
                        .as_("a")
                        .V(new_internal_id)
                        .addE(e)
                        .from_("a")
                        .id()
                        .next()
                    )
                    results["edges_created"].append(
                        {
                            "edge_label": e,
                            "out": {"label": source["label"], "id": source.get("id"), "caption": source.get("caption")},
                            "in": {"label": created["label"], "id": created.get("id"), "caption": created.get("caption")},
                            "edge_internal_id": eid,
                        }
                    )

        return results

    # @mcp.tool()
    def read_vertex_by_id(ctx: Context[ServerSession, AppContext], label: str, id: int) -> dict[str, Any]:
        """Read a vertex (by your 'id' property) plus all its incoming/outgoing edges."""
        return read_vertex_with_edges(ctx, label=label, vertex_id=int(id))

    # @mcp.tool()
    def update_vertex_by_id(
        ctx: Context[ServerSession, AppContext],
        label: str,
        id: int,
        set_properties: dict[str, Any] | None = None,
        unset_properties: list[str] | None = None,
    ) -> dict[str, Any]:
        """Update a vertex by label + id (set and/or unset properties)."""
        g = get_g(ctx)
        canon = normalize_label(label)

        exists = g.V().hasLabel(canon).has("id", int(id)).limit(1).toList()
        if not exists:
            raise ValueError(f"Vertex not found: label={canon} id={id}")

        if set_properties:
            props = validate_properties(canon, set_properties, require_required=False)
            t = g.V().hasLabel(canon).has("id", int(id))
            for k, v_ in props.items():
                t = t.property(k, v_)
            t.iterate()

        if unset_properties:
            from ..schema import ALLOWED_PROPS
            for k in unset_properties:
                if k not in ALLOWED_PROPS[canon]:
                    raise ValueError(f"Cannot unset unknown property '{k}' for label '{canon}'")
                g.V().hasLabel(canon).has("id", int(id)).properties(k).drop().iterate()

        return read_vertex_with_edges(ctx, label=canon, vertex_id=int(id))

    # @mcp.tool()
    def delete_vertex_by_id(ctx: Context[ServerSession, AppContext], label: str, id: int) -> dict[str, Any]:
        """Delete a vertex (and all incident edges) by label + id."""
        g = get_g(ctx)
        canon = normalize_label(label)
        exists = g.V().hasLabel(canon).has("id", int(id)).limit(1).toList()
        if not exists:
            return {"deleted": False, "reason": "not_found", "label": canon, "id": int(id)}

        g.V().hasLabel(canon).has("id", int(id)).drop().iterate()
        return {"deleted": True, "label": canon, "id": int(id)}

    # @mcp.tool()
    def list_vertices_by_label(ctx: Context[ServerSession, AppContext], label: str, limit: int = 1000, offset: int = 0) -> list[dict[str, Any]]:
        """List vertices (id + caption) for a given label."""
        g = get_g(ctx)
        canon = normalize_label(label)
        return (
            g.V()
            .hasLabel(canon)
            .range(offset, offset + limit)
            .project("label", "id", "caption", "internal_id")
            .by(__.label())
            .by(__.values("id"))
            .by(__.values("caption"))
            .by(__.id())
            .toList()
        )

    # @mcp.tool()
    def find_vertices_by_caption(ctx: Context[ServerSession, AppContext], caption: str, label: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        """Find vertices by exact caption match (optionally filtered by label)."""
        g = get_g(ctx)
        t = g.V().has("caption", caption)
        if label:
           t = t.hasLabel(normalize_label(label))
        return (
            t.limit(limit)
            .project("id", "label", "caption")
            .by(T.id)
            .by(__.label())
            .by(__.values("caption"))
            .toList()
        )

    @mcp.tool()
    def get_verse_by_caption(ctx: Context[ServerSession, AppContext], caption: str) -> dict[str, Any]:
        """
        Get verse by exact caption match. 
        
        The verse caption has the format `{book} {chapter}:{verse number}`, e. g. Jn 1:11 or 2Pet 2:13.

        The book is a short abbreviation of a bible book. Here is a complete list of possible book abbreviations:

        - Acts (for Acts),
        - 2Pet (for II Peter),
        - Gal (for Galatians),
        - 1Kgs (for I Kings),
        - Ps (for Psalms),
        - 1Mac (for I Maccabees),
        - Esth (for Esther),
        - Hab (for Habakkuk),
        - Hag (for Haggai),
        - Jdt (for Judith),
        - Bar (for Baruch),
        - Zech (for Zechariah),
        - 1Cor (for I Corinthians),
        - Hos (for Hosea),
        - 1Mac (for III Maccabees),
        - Lk (for Luke),
        - 1Sam (for I Samuel),
        - Judg (for Judges),
        - Eccl (for Ecclesiastes),
        - Jonah (for Jonah),
        - Jn (for John),
        - Mt (for Matthew),
        - Prov (for Proverbs),
        - Lam (for Lamentations),
        - 2Kgs (for II Kings),
        - 1Chr (for I Chronicles),
        - Amos (for Amos),
        - 1Th (for I Thessalonians),
        - Phlm (for Philemon),
        - 2Tim (for II Timothy),
        - Zeph (for Zephaniah),
        - Nah (for Nahum),
        - Joel (for Joel),
        - Rom (for Romans),
        - Gen (for Genesis),
        - Jude (for Jude),
        - 2Cor (for II Corinthians),
        - Heb (for Hebrews),
        - 2Mac (for II Maccabees),
        - Wis (for Wisdom),
        - 2Jn (for II John),
        - Tob (for Tobit),
        - Sir (for Sirach),
        - Deut (for Deuteronomy),
        - Mal (for Malachi),
        - PrMan (for Prayer of Manasses),
        - 2Chr (for II Chronicles),
        - Ezr (for Ezra),
        - Dan (for Daniel),
        - 1Jn (for I John),
        - Ruth (for Ruth),
        - Col (for Colossians),
        - SS (for Song of Solomon),
        - Job (for Job),
        - EpJer (for Epistle of Jeremiah),
        - Mic (for Micah),
        - Jas (for James),
        - Phil (for Philippians),
        - Eph (for Ephesians),
        - 1Tim (for I Timothy),
        - Ex (for Exodus),
        - 3Jn (for III John),
        - Tit (for Titus),
        - Ez (for Ezekiel),
        - Num (for Numbers),
        - Mk (for Mark),
        - 2Th (for II Thessalonians),
        - Obad (for Obadiah),
        - 1Esd (for I Esdras),
        - 2Esd (for II Esdras),
        - 2Sam (for II Samuel),
        - 1Pet (for I Peter),
        - Josh (for Joshua),
        - Lev (for Leviticus),
        - Rev (for Revelation of John),
        - Jer (for Jeremiah),
        - Is (for Isaiah),
        - Neh (for Nehemiah).

        """
        g = get_g(ctx)
        t = g.V().has("caption", caption)
        return (
            t.limit(1)
            .project("id", "label", "caption", "RST")
            .by(T.id)
            .by(__.label())
            .by(__.values("caption"))
            .by(__.values("RST"))
            .next()
        )
