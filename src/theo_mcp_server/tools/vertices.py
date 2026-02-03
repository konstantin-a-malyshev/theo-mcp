from __future__ import annotations

from typing import Any

import traceback 

from gremlin_python.process.graph_traversal import __
from gremlin_python.process.traversal import T, Order
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession
from mcp.server.fastmcp.exceptions import ToolError
from ..gremlin_client import AppContext, get_g
from ..gremlin_helpers import (
    create_vertex_and_connect_by_captions,
    filter_direct_relationships,
    filter_backward_relationships,
    get_vertices_by_captions,
    get_vertices_by_type,
    reverse_backward_relationship_keys,
    read_vertex_with_edges,
    delete_vertex_by_id,
    get_unique_vertex_by_caption,
    create_edge,
    search_vertices,
    flatten_value_map
)
from ..validation import normalize_edge_label, normalize_label, validate_and_fix_properties


def register_vertex_tools(mcp: FastMCP) -> None:

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
            props = validate_and_fix_properties(canon, set_properties, require_required=False)
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
    def create_notion(ctx: Context[ServerSession, AppContext], caption: str, relationships: dict[str, list[str]] | None = None) -> dict[str, Any]:
        """
            Create a notion vertex.
            
            The following relationships can be specified in the `relationships` parameter:
            - isSupportedBy
            - supports
            - isChallengedBy
            - challenges
            - refersTo
            - isReferredBy
            - contains
            - isContainedIn

            Each relationship should map to a list of captions of existing notions, verses, notionGroups, books, verseGroups, or persons.       
        """
        try:
            edges_in = filter_backward_relationships(relationships or {})
            edges_in = reverse_backward_relationship_keys(edges_in)
            edges_out = filter_direct_relationships(relationships or {})
            g = get_g(ctx)
            return create_vertex_and_connect_by_captions(g, "notion", {"caption": caption}, edges_out, edges_in)
        except Exception:
            raise ToolError(traceback.format_exc())

    @mcp.tool()
    def create_notion_group(ctx: Context[ServerSession, AppContext], caption: str, relationships: dict[str, list[str]] | None = None) -> dict[str, Any]:
        """
            Create a notion group vertex.
            
            The following relationships can be specified in the `relationships` parameter:
            - isSupportedBy
            - supports
            - isChallengedBy
            - challenges
            - refersTo
            - isReferredBy
            - contains
            - isContainedIn

            Each relationship should map to a list of captions of existing notions, verses, notionGroups, books, verseGroups, or persons.       
        """
        try:
            edges_in = filter_backward_relationships(relationships or {})
            edges_in = reverse_backward_relationship_keys(edges_in)
            edges_out = filter_direct_relationships(relationships or {})
            g = get_g(ctx)
            return create_vertex_and_connect_by_captions(g, "notionGroup", {"caption": caption}, edges_out, edges_in)
        except Exception:
            raise ToolError(traceback.format_exc())

    @mcp.tool()
    def get_verses_by_captions(ctx: Context[ServerSession, AppContext], captions: list[str]) -> list[dict[str, Any]]:
        """
        Get verses by exact caption matches. 
        
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

        try:
            g = get_g(ctx)
            return get_vertices_by_captions(g, captions)
        except Exception:
            raise ToolError(traceback.format_exc())

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
        try:
            g = get_g(ctx)
            ids = g.V().has("caption", caption).hasLabel("verse").id_().toList()
            if not ids:
                raise ValueError(f"Verse not found: caption={caption}")
            
            return read_vertex_with_edges(g, ids[0])
        except Exception:
            raise ToolError(traceback.format_exc())

    @mcp.tool()
    def get_notion_by_id(ctx: Context[ServerSession, AppContext], id: int) -> dict[str, Any]:
        """
        Get notion by id.
        """
        try:
            g = get_g(ctx)
            return read_vertex_with_edges(g, id)
        except Exception:
            raise ToolError(traceback.format_exc())
        
    @mcp.tool()
    def get_notion_by_caption(ctx: Context[ServerSession, AppContext], caption: str) -> dict[str, Any]:
        """
        Get notion by caption.
        """
        try:
            g = get_g(ctx)
            ids = g.V().has("caption", caption).hasLabel("notion").id_().toList()
            if not ids:
                raise ValueError(f"Notion not found: caption={caption}")

            return read_vertex_with_edges(g, ids[0])
        except Exception:
            raise ToolError(traceback.format_exc())

    @mcp.tool()
    def delete_notion_by_caption(ctx: Context[ServerSession, AppContext], caption: str) -> dict[str, Any]:
        """
        Delete notion by caption.
        """
        try:
            g = get_g(ctx)
            ids = g.V().has("caption", caption).hasLabel("notion").id_().toList()
            if not ids:
                raise ValueError(f"Notion not found: caption={caption}")
            return delete_vertex_by_id(g, ids[0])
        except Exception:
            raise ToolError(traceback.format_exc())

    @mcp.tool()
    def delete_notion_group_by_caption(ctx: Context[ServerSession, AppContext], caption: str) -> dict[str, Any]:
        """
        Delete notion group by caption.
        """
        try:
            g = get_g(ctx)
            ids = g.V().has("caption", caption).hasLabel("notionGroup").id_().toList()
            if not ids:
                raise ValueError(f"Notion group not found: caption={caption}")
            return delete_vertex_by_id(g, ids[0])
        except Exception:
            raise ToolError(traceback.format_exc())

    @mcp.tool()
    def get_notion_group_by_caption(ctx: Context[ServerSession, AppContext], caption: str) -> dict[str, Any]:
        """
        Read notion group by caption.
        """
        try:
            g = get_g(ctx)
            ids = g.V().has("caption", caption).hasLabel("notionGroup").id_().toList()
            if not ids:
                raise ValueError(f"Notion group not found: caption={caption}")
            return read_vertex_with_edges(g, ids[0])
        except Exception:
            raise ToolError(traceback.format_exc())
        
    @mcp.tool()
    def create_relationship(
        ctx: Context[ServerSession, AppContext],
        relationship: str,
        sourceCaption: str,
        targetCaption: str,
    ) -> dict[str, Any]:
        """Create a relationship of type `relationship` going from a vertex with `sourceCaption` to a vertex with `targetCaption."""
        try:
            g = get_g(ctx)
            source = get_unique_vertex_by_caption(g, sourceCaption)
            target = get_unique_vertex_by_caption(g, targetCaption)
            return create_edge(g, relationship, source["internal_id"], target["internal_id"])
        except Exception:
            raise ToolError(traceback.format_exc())
        
    @mcp.tool()
    def search_notion_groups_and_notions(
        ctx: Context[ServerSession, AppContext],
        searchText: str,
        limit: int = 100
    ) -> list[dict[str, Any]]:
        """Search for notion groups and notions by substring."""
        try:
            g = get_g(ctx)
            return search_vertices(g, ["notion", "notionGroup"], searchText, limit)
        except Exception:
            raise ToolError(traceback.format_exc())
        
    @mcp.tool()
    def get_quotation_by_caption(
        ctx: Context[ServerSession, AppContext],
        caption: str
    ) -> dict[str, Any]:
        """Get quotation by caption."""
        try:
            g = get_g(ctx)
            ids = g.V().has("caption", caption).hasLabel("quotation").id_().toList()
            if not ids:
                raise ValueError(f"Quotation not found: caption={caption}")
            return read_vertex_with_edges(g, ids[0])
        except Exception:
            raise ToolError(traceback.format_exc())
        
    @mcp.tool()
    def create_quotation(
        ctx: Context[ServerSession, AppContext],
        caption: str,
        text: str,
        book: str,
        position: str,
        relationships: dict[str, list[str]] | None = None
    ) -> dict[str, Any]:
        """
            Create a quotation.
            
            The following relationships can be specified in the `relationships` parameter:
            - isContainedIn

            Each relationship should map to a list of captions of existing books or persons.       
        """
        try:
            edges_in = filter_backward_relationships(relationships or {})
            edges_in = reverse_backward_relationship_keys(edges_in)
            edges_out = filter_direct_relationships(relationships or {})
            g = get_g(ctx)
            return create_vertex_and_connect_by_captions(g, "quotation", {"caption": caption, "text": text, "book": book, "position": position}, edges_out, edges_in)
        except Exception:
            raise ToolError(traceback.format_exc())
        
    @mcp.tool()
    def get_new_quotations(ctx: Context[ServerSession, AppContext], limit: int) -> list[dict[str, Any]]:
        """Get newly created quotations."""
        try:
            g = get_g(ctx)
            t = g.V().has('type', "quotation").order().by("importIndex", Order.desc)
            raw_list = t.limit(limit).valueMap(True).toList()
            return [flatten_value_map(r) for r in raw_list]
        except Exception:
            raise ToolError(traceback.format_exc())

    @mcp.tool()    
    def delete_quotation_by_caption(
        ctx: Context[ServerSession, AppContext],
        caption: str
    ) -> dict[str, Any]:
        """
        Delete quotation by caption.
        """
        try:
            g = get_g(ctx)
            ids = g.V().has("caption", caption).hasLabel("quotation").id_().toList()
            if not ids:
                raise ValueError(f"Quotation not found: caption={caption}")
            return delete_vertex_by_id(g, ids[0])
        except Exception:
            raise ToolError(traceback.format_exc())
        
    @mcp.tool()    
    def get_book_by_caption(
        ctx: Context[ServerSession, AppContext],
        caption: str
    ) -> dict[str, Any]:
        """Get book by caption."""
        try:
            g = get_g(ctx)
            ids = g.V().has("caption", caption).hasLabel("book").id_().toList()
            if not ids:
                raise ValueError(f"Book not found: caption={caption}")
            return read_vertex_with_edges(g, ids[0])
        except Exception:
            raise ToolError(traceback.format_exc())