"""Create a JanusGraph composite vertex index over one property key.

Index management needs the management API, which the Gremlin *traversal* protocol
does not expose — so this submits Groovy scripts through `gremlin_python`'s script
client, with the credentials from the environment. That makes it independent of
the state of `conf/remote.yaml` inside the console container, which is what the
Gremlin console depends on.

Class names are fully qualified on purpose: the server's script engine imports are
not guaranteed, unlike the console's `janusgraph.imports` plugin.

Dry run by default; `--apply` writes.

    python scripts/create_index.py --property sourceKey
    python scripts/create_index.py --property sourceKey --close-stale-instances --apply

Stale instances matter: `REGISTER_INDEX` waits for every open JanusGraph instance
to acknowledge the new index, and registrations left behind by earlier server runs
never will — the wait then simply never ends. `--close-stale-instances` force-closes
every instance except the live one, which is safe for a single-process backend.
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import Any

from gremlin_python.driver import client

from theo_mcp_server.config import get_config

VERTEX = "org.apache.tinkerpop.gremlin.structure.Vertex"
SCHEMA_ACTION = "org.janusgraph.core.schema.SchemaAction"
POLL_INTERVAL_SECONDS = 2
POLL_ATTEMPTS = 60


def submit(c: client.Client, script: str) -> Any:
    """Run a Groovy script server-side and return its single result."""
    rows = c.submit(script).all().result()
    return rows[0] if rows else None


def read_indexes(c: client.Client) -> str:
    return submit(
        c,
        "def m = graph.openManagement(); def s = m.printIndexes(); m.rollback(); s",
    )


def read_index_status(c: client.Client, index: str, property: str) -> str:
    """Status of `index` for `property`, or MISSING when the index does not exist."""
    return submit(
        c,
        "def m = graph.openManagement();"
        f" def i = m.getGraphIndex('{index}');"
        f" def k = m.getPropertyKey('{property}');"
        " def s = (i == null) ? 'MISSING' : i.getIndexStatus(k).toString();"
        " m.rollback(); s",
    )


def read_property_key(c: client.Client, property: str) -> str | None:
    key = submit(
        c,
        "def m = graph.openManagement();"
        f" def k = m.getPropertyKey('{property}');"
        " def s = (k == null) ? 'MISSING' :"
        " k.dataType().getSimpleName() + '/' + k.cardinality().toString();"
        " m.rollback(); s",
    )
    return None if key == "MISSING" else key


def read_instances(c: client.Client) -> tuple[list[str], str | None]:
    """Open instances as (stale, current)."""
    raw = submit(
        c,
        "def m = graph.openManagement();"
        " def s = m.getOpenInstances().join(',');"
        " m.rollback(); s",
    )
    instances = [part for part in (raw or "").split(",") if part]
    current = next((i for i in instances if "(current)" in i), None)
    stale = [i for i in instances if "(current)" not in i]
    return stale, current


def count_with_property(c: client.Client, property: str) -> int:
    """How many vertices already carry the property — decides reindex vs enable."""
    return int(submit(c, f"g.V().has('{property}').count()"))


def close_stale_instances(c: client.Client) -> int:
    return int(
        submit(
            c,
            "def m = graph.openManagement();"
            " def stale = m.getOpenInstances().findAll { !it.contains('(current)') };"
            " stale.each { m.forceCloseInstance(it) };"
            " m.commit(); stale.size()",
        )
    )


def create_index(c: client.Client, index: str, property: str, data_type: str) -> str:
    """Create the composite index, making the property key first if needed.

    No `indexOnly(label)`: a label-restricted index is only used by queries that
    also constrain the label, and the importer looks a passage up by `sourceKey`
    alone. No `unique()` either — it locks on every write, which a bulk import
    cannot afford; uniqueness is the importer's job.
    """
    return submit(
        c,
        "def m = graph.openManagement();"
        f" def k = m.getPropertyKey('{property}');"
        " if (k == null) {"
        f"   k = m.makePropertyKey('{property}').dataType({data_type}.class)"
        "        .cardinality(org.janusgraph.core.Cardinality.SINGLE).make() };"
        f" m.buildIndex('{index}', {VERTEX}.class).addKey(k).buildCompositeIndex();"
        " m.commit(); 'CREATED'",
    )


def update_index(c: client.Client, index: str, action: str) -> str:
    return submit(
        c,
        "def m = graph.openManagement();"
        f" m.updateIndex(m.getGraphIndex('{index}'), {SCHEMA_ACTION}.{action});"
        f" m.commit(); '{action} submitted'",
    )


def await_status(c: client.Client, index: str, property: str, wanted: str) -> str:
    """Poll the index status instead of using `awaitGraphIndexStatus`.

    A server-side wait would sit inside one request and hit the script evaluation
    timeout; polling keeps every request short.
    """
    for attempt in range(POLL_ATTEMPTS):
        status = read_index_status(c, index, property)
        print(f"  status: {status}")
        if status == wanted:
            return status
        if attempt < POLL_ATTEMPTS - 1:
            time.sleep(POLL_INTERVAL_SECONDS)
    raise RuntimeError(
        f"Index '{index}' did not reach {wanted} (stuck at {status}). "
        "If it is stuck at INSTALLED, stale instances are blocking the "
        "registration — re-run with --close-stale-instances."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--property", required=True, help="property key to index")
    parser.add_argument("--index", help="index name (default: by<Property>)")
    parser.add_argument(
        "--data-type", default="String", help="data type for a new property key"
    )
    parser.add_argument(
        "--close-stale-instances",
        action="store_true",
        help="force-close every open instance except the live one",
    )
    parser.add_argument("--apply", action="store_true", help="write (default: dry run)")
    args = parser.parse_args()

    property = args.property
    index = args.index or f"by{property[0].upper()}{property[1:]}"

    cfg = get_config()
    c = client.Client(
        cfg.gremlin_url,
        cfg.gremlin_traversal_source,
        username=cfg.gremlin_username or None,
        password=cfg.gremlin_password or None,
    )

    try:
        print(f"{cfg.gremlin_url}\n")
        print(read_indexes(c))

        status = read_index_status(c, index, property)
        key = read_property_key(c, property)
        stale, current = read_instances(c)
        existing = count_with_property(c, property)

        print(f"index '{index}'        : {status}")
        print(f"property key          : {key or 'does not exist yet'}")
        print(f"vertices with it      : {existing}")
        print(f"live instance         : {current}")
        print(f"stale instances       : {len(stale)}")

        action = "REINDEX" if existing else "ENABLE_INDEX"
        print(
            f"\nplan: {'close stale instances, ' if stale and args.close_stale_instances else ''}"
            f"create '{index}' over '{property}', await REGISTERED, {action}, await ENABLED"
        )
        if existing:
            print(
                f"  ({existing} vertices already carry '{property}', so the index "
                "has to be filled by a reindex scan)"
            )
        else:
            print(
                f"  (no vertex carries '{property}', so there is nothing to backfill "
                "and the index can be enabled directly)"
            )

        if status != "MISSING":
            print(f"\nNothing to do: index '{index}' already exists ({status}).")
            return 0

        if stale and not args.close_stale_instances:
            print(
                f"\n{len(stale)} stale instances would block REGISTER_INDEX. "
                "Re-run with --close-stale-instances."
            )
            if args.apply:
                return 1

        if not args.apply:
            print("\nDry run. Re-run with --apply to create the index.")
            return 0

        if stale and args.close_stale_instances:
            print(f"\nclosing {len(stale)} stale instances…")
            print(f"  closed: {close_stale_instances(c)}")

        print(f"\ncreating '{index}'…")
        print(f"  {create_index(c, index, property, args.data_type)}")

        print("awaiting REGISTERED…")
        await_status(c, index, property, "REGISTERED")

        print(f"{action}…")
        print(f"  {update_index(c, index, action)}")

        print("awaiting ENABLED…")
        await_status(c, index, property, "ENABLED")

        print()
        print(read_indexes(c))
        return 0
    finally:
        c.close()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
