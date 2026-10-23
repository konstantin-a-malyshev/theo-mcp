"""Change the type (and Gremlin label) of existing vertices, keeping props and edges.

JanusGraph vertex labels are immutable, so a vertex cannot be relabelled in
place: every vertex is re-created under the new label, its properties and all
incident edges are copied, and only then is the original dropped.

The script deliberately bypasses `validation.py`: live `book` vertices carry a
`name` property that is not in `ALLOWED_PROPS`, and the target type is not
registered in `schema.py` yet. Whatever is on the vertex is copied verbatim,
except `type`, which becomes the new type.

Dry run by default; `--apply` writes.

    python scripts/retype_vertices.py --from book --to scholarlyWork
    python scripts/retype_vertices.py --from book --to scholarlyWork --apply
    python scripts/retype_vertices.py --from scholarlyWork --to receptionWork \
        --caption "Justin Martyr. The First Apology" --apply
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter
from datetime import datetime
from typing import Any

from gremlin_python.process.graph_traversal import GraphTraversalSource, __
from gremlin_python.process.traversal import P, T

from theo_mcp_server.gremlin_client import get_g_for_tests

EDGE_BATCH_SIZE = 50


def read_vertices(
    g: GraphTraversalSource, type_: str, captions: list[str] | None
) -> list[dict[str, Any]]:
    """Read vertices of a type with their properties and all incident edges.

    Everything is projected to primitives - returning Vertex/Edge objects from
    gremlin_python 3.7.3 against JanusGraph crashes the GraphBinary reader.
    """
    t = g.V().has("type", type_)
    if captions:
        t = t.has("caption", P.within(captions) if len(captions) > 1 else captions[0])

    return (
        t.project("internal_id", "label", "props", "out", "in")
        .by(T.id)
        .by(__.label())
        .by(__.valueMap())
        .by(
            __.outE()
            .project("edge_label", "other_id", "props")
            .by(__.label())
            .by(__.inV().id_())
            .by(__.valueMap())
            .fold()
        )
        .by(
            __.inE()
            .project("edge_label", "other_id", "props")
            .by(__.label())
            .by(__.outV().id_())
            .by(__.valueMap())
            .fold()
        )
        .toList()
    )


def _single(value: Any) -> Any:
    """valueMap returns every property as a list; keep multi-valued ones as lists."""
    if isinstance(value, list):
        return value[0] if len(value) == 1 else value
    return value


def create_vertex_with_props(
    g: GraphTraversalSource, label: str, props: dict[str, Any]
) -> int:
    """Create a vertex under `label` with `props` copied verbatim (`type` = label)."""
    t = g.add_v(label).property("type", label)
    for key, raw in props.items():
        if key == "type":
            continue
        value = _single(raw)
        for item in value if isinstance(value, list) else [value]:
            t = t.property(key, item)
    return int(t.id_().next())


def copy_edges(
    g: GraphTraversalSource,
    new_id: int,
    out_edges: list[dict[str, Any]],
    in_edges: list[dict[str, Any]],
) -> None:
    """Re-create all incident edges on the new vertex, in batches."""
    work = [("out", e) for e in out_edges] + [("in", e) for e in in_edges]

    for start in range(0, len(work), EDGE_BATCH_SIZE):
        batch = work[start : start + EDGE_BATCH_SIZE]
        t = g.V(new_id).as_("n")
        for i, (direction, edge) in enumerate(batch):
            other = f"o{i}"
            t = t.V(edge["other_id"]).as_(other)
            t = t.add_e(edge["edge_label"])
            t = t.from_("n").to(other) if direction == "out" else t.from_(other).to("n")
            for key, raw in edge.get("props", {}).items():
                t = t.property(key, _single(raw))
        t.iterate()


def retype_vertex(
    g: GraphTraversalSource, vertex: dict[str, Any], to_type: str
) -> dict[str, Any]:
    """Re-create one vertex under `to_type`, copy edges, verify, drop the original."""
    old_id = int(vertex["internal_id"])
    caption = _single(vertex["props"].get("caption", ""))
    expected_out = len(vertex["out"])
    expected_in = len(vertex["in"])

    new_id = create_vertex_with_props(g, to_type, vertex["props"])
    copy_edges(g, new_id, vertex["out"], vertex["in"])

    actual_out = g.V(new_id).outE().count().next()
    actual_in = g.V(new_id).inE().count().next()
    if actual_out != expected_out or actual_in != expected_in:
        raise RuntimeError(
            f"edge count mismatch for '{caption}': "
            f"expected out={expected_out} in={expected_in}, "
            f"got out={actual_out} in={actual_in}. "
            f"Old vertex {old_id} kept, new vertex {new_id} left in place for inspection."
        )

    g.V(old_id).drop().iterate()

    return {
        "caption": caption,
        "old_internal_id": old_id,
        "new_internal_id": new_id,
        "out_edges": expected_out,
        "in_edges": expected_in,
    }


def report_plan(vertices: list[dict[str, Any]], from_type: str, to_type: str) -> None:
    prop_keys: Counter[str] = Counter()
    edge_labels: Counter[str] = Counter()
    captions: Counter[str] = Counter()

    for v in vertices:
        prop_keys.update(k for k in v["props"] if k != "type")
        edge_labels.update(f"{e['edge_label']} ->" for e in v["out"])
        edge_labels.update(f"-> {e['edge_label']}" for e in v["in"])
        captions[str(_single(v["props"].get("caption", "")))] += 1

    print(f"{from_type} -> {to_type}: {len(vertices)} vertices")
    print(f"  property keys : {dict(prop_keys)}")
    print(f"  edges         : {dict(edge_labels)}")
    print(f"  labels seen   : {dict(Counter(v['label'] for v in vertices))}")

    duplicates = {c: n for c, n in captions.items() if n > 1}
    if duplicates:
        print(f"  WARNING duplicate captions: {duplicates}")

    print()
    for v in sorted(vertices, key=lambda v: int(v["internal_id"])):
        print(
            f"  {v['internal_id']:>12} | out {len(v['out']):>4} | in {len(v['in']):>3} |"
            f" {_single(v['props'].get('caption', ''))}"
        )


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--from", dest="from_type", required=True, help="current type")
    parser.add_argument("--to", dest="to_type", required=True, help="new type")
    parser.add_argument(
        "--caption",
        action="append",
        dest="captions",
        help="restrict to this caption (repeatable); default: every vertex of --from",
    )
    parser.add_argument("--apply", action="store_true", help="write (default: dry run)")
    parser.add_argument("--log", help="write the id mapping to this JSON file")
    args = parser.parse_args()

    if args.from_type == args.to_type:
        parser.error("--from and --to are the same type")

    g = await get_g_for_tests()

    vertices = read_vertices(g, args.from_type, args.captions)
    if not vertices:
        print(
            f"Nothing to do: no vertices with type={args.from_type}"
            + (f" and captions {args.captions}" if args.captions else "")
        )
        return 0

    report_plan(vertices, args.from_type, args.to_type)

    if not args.apply:
        print(f"\nDry run. Re-run with --apply to retype these {len(vertices)} vertices.")
        return 0

    print(
        f"\nApplying. {len(vertices)} vertices, "
        f"{sum(len(v['out']) + len(v['in']) for v in vertices)} edges to copy."
    )

    migrated: list[dict[str, Any]] = []
    try:
        for v in vertices:
            result = retype_vertex(g, v, args.to_type)
            migrated.append(result)
            print(
                f"  ok {result['old_internal_id']} -> {result['new_internal_id']}"
                f" ({result['out_edges']}+{result['in_edges']} edges)"
                f" | {result['caption']}"
            )
    finally:
        if args.log and migrated:
            with open(args.log, "w", encoding="utf-8") as fh:
                json.dump(
                    {
                        "created_at": datetime.now().isoformat(timespec="seconds"),
                        "from_type": args.from_type,
                        "to_type": args.to_type,
                        "vertices": migrated,
                    },
                    fh,
                    ensure_ascii=False,
                    indent=2,
                )
            print(f"\nid mapping written to {args.log}")

    left = g.V().has("type", args.from_type).count().next()
    now = g.V().has("type", args.to_type).count().next()
    edges = g.V().has("type", args.to_type).bothE().count().next()
    print(
        f"\nDone. type={args.from_type}: {left} left, "
        f"type={args.to_type}: {now} vertices, {edges} incident edges."
    )
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(asyncio.run(main()))
