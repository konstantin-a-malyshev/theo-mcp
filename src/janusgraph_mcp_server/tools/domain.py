from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession

from ..gremlin_client import AppContext, get_g
from ..gremlin_helpers import resolve_unique_vertex
from ..validation import normalize_edge_label


def register_domain_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    def create_notion_and_connect(
        ctx: Context[ServerSession, AppContext],
        properties: dict[str, Any],
        supported_by: list[dict[str, Any]] | None = None,
        challenged_by: list[dict[str, Any]] | None = None,
        refers_to: list[dict[str, Any]] | None = None,
        supported_edge_label: str = "supportedBy",
        challenged_edge_label: str = "challengedBy",
        refers_edge_label: str = "refersTo",
    ) -> dict[str, Any]:
        """
        Create a new 'notion' vertex and connect it to other vertices (resolved by id or caption)
        using supportedBy / challengedBy / refersTo edges (labels configurable).
        """
        # Import tool from vertices registration (already registered),
        # but we can call the underlying gremlin ourselves to avoid coupling.
        from ..validation import validate_properties
        from ..gremlin_helpers import flatten_value_map
        from ..validation import normalize_label

        g = get_g(ctx)

        canon = normalize_label("notion")
        props = validate_properties(canon, properties, require_required=True)

        existing = g.V().hasLabel(canon).has("id", props["id"]).limit(1).toList()
        if existing:
            raise ValueError(f"Vertex already exists: label={canon} id={props['id']}")

        t = g.addV(canon)
        for k, v in props.items():
            t = t.property(k, v)
        created = flatten_value_map(t.valueMap(True).next())
        new_internal = created["internal_id"]

        results: dict[str, Any] = {"created": created, "edges_created": []}

        def _connect(edge_label: str, targets: list[dict[str, Any]] | None):
            if not targets:
                return
            e = normalize_edge_label(edge_label)
            for ref in targets:
                target = resolve_unique_vertex(ctx, ref)
                eid = (
                    g.V(new_internal)
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

        _connect(supported_edge_label, supported_by)
        _connect(challenged_edge_label, challenged_by)
        _connect(refers_edge_label, refers_to)

        return results

    @mcp.tool()
    def create_notion_group_and_connect(
        ctx: Context[ServerSession, AppContext],
        properties: dict[str, Any],
        supported_by: list[dict[str, Any]] | None = None,
        challenged_by: list[dict[str, Any]] | None = None,
        refers_to: list[dict[str, Any]] | None = None,
        supported_edge_label: str = "supportedBy",
        challenged_edge_label: str = "challengedBy",
        refers_edge_label: str = "refersTo",
    ) -> dict[str, Any]:
        """Create a new 'notionGroup' vertex and connect it similarly to create_notion_and_connect."""
        from ..validation import validate_properties
        from ..gremlin_helpers import flatten_value_map
        from ..validation import normalize_label

        g = get_g(ctx)

        canon = normalize_label("notionGroup")
        props = validate_properties(canon, properties, require_required=True)

        existing = g.V().hasLabel(canon).has("id", props["id"]).limit(1).toList()
        if existing:
            raise ValueError(f"Vertex already exists: label={canon} id={props['id']}")

        t = g.addV(canon)
        for k, v in props.items():
            t = t.property(k, v)
        created = flatten_value_map(t.valueMap(True).next())
        new_internal = created["internal_id"]

        results: dict[str, Any] = {"created": created, "edges_created": []}

        def _connect(edge_label: str, targets: list[dict[str, Any]] | None):
            if not targets:
                return
            e = normalize_edge_label(edge_label)
            for ref in targets:
                target = resolve_unique_vertex(ctx, ref)
                eid = (
                    g.V(new_internal)
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

        _connect(supported_edge_label, supported_by)
        _connect(challenged_edge_label, challenged_by)
        _connect(refers_edge_label, refers_to)

        return results
