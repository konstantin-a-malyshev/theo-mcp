# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Conventions

- Use short git commit comments.

## Project

`theo-mcp-server` is a Python MCP server that exposes CRUD + edge operations against a JanusGraph (Gremlin) graph holding a domain schema of theological notions, verses, books, persons, quotations, and groups. It is invoked over stdio (default) or `streamable-http` by an MCP client (Claude Desktop, MCP Inspector, tests).

## Commands

PowerShell on Windows is the primary shell.

- Activate venv: `.\.venv\Scripts\Activate.ps1`
- Install (editable): `pip install -e .`
- Run server (console script): `theo-mcp`
- Run server (module): `python -m theo_mcp_server`
- Run all tests: `pytest` (or `pytest -s` for stdout)
- Run a single test: `pytest tests/test_server.py::test_get_verse_by_caption -s`
- MCP Inspector: `npx @modelcontextprotocol/inspector`
- Restart Claude Desktop after server changes: `.\restart-claude.ps1`
- DB backup helper: `.\backup_db.ps1`

The integration tests in [tests/test_server.py](tests/test_server.py) spawn the server via `python -m theo_mcp_server` using `.venv\Scripts\python.exe` — they require the venv at `.venv\` and a running Gremlin endpoint.

## Configuration

Read from environment (via `python-dotenv`, so a `.env` at repo root is honored). See [config.py](src/theo_mcp_server/config.py):

- `GREMLIN_URL` (default `ws://localhost:8182/gremlin`)
- `GREMLIN_TRAVERSAL_SOURCE` (default `g`)
- `GREMLIN_USERNAME`, `GREMLIN_PASSWORD`
- `MCP_TRANSPORT` — `stdio` (default) or `streamable-http`

## Architecture

Entry point [\_\_main\_\_.py](src/theo_mcp_server/__main__.py) calls `app.run(transport=…)` on the `FastMCP` app built in [server.py](src/theo_mcp_server/server.py). `create_mcp()` wires the lifespan and registers tool groups in order: graph → diagram.

The Gremlin connection is opened **once per server lifecycle** by `app_lifespan` in [gremlin_client.py](src/theo_mcp_server/gremlin_client.py), which yields an `AppContext(connection, g)` where `g` is a `GraphTraversalSource`. Tools obtain `g` via `get_g(ctx)` from `ctx.request_context.lifespan_context`. There is also `get_g_for_tests()` that opens an independent connection for direct (non-MCP) tests like [tests/test_gremlin.py](tests/test_gremlin.py).

Schema (vertex labels, allowed/required props, edge labels) is centralized in [schema.py](src/theo_mcp_server/schema.py). All user-supplied labels and properties flow through [validation.py](src/theo_mcp_server/validation.py) (`normalize_label`, `normalize_edge_label`, `validate_and_fix_properties`) before reaching Gremlin. Label inputs are case-insensitive; canonical forms are defined by `LABELS_CANON`.

Tool implementations live in [src/theo_mcp_server/tools/](src/theo_mcp_server/tools):

- `graph.py` — all graph MCP tools: CRUD for notions/notionGroups/verses/verseGroups/quotations/books, relationships, search, trees, caption rename.
- `diagram.py` — Graphviz-based SVG diagram generation (`create_diagram_by_captions`, `change_caption`). Depends on the `graphviz` Python package and the system `dot` binary being on PATH.

Shared Gremlin query/transformation logic is in [gremlin_helpers.py](src/theo_mcp_server/gremlin_helpers.py) (e.g., `create_vertex_and_connect_by_captions`, `read_vertex_with_edges`, `build_notion_groups_tree`, `flatten_value_map`, `filter_direct_relationships` / `filter_backward_relationships`, `reverse_backward_relationship_keys`). Edits to vertex/edge behavior should typically go here rather than being duplicated across tool modules.

### Identity convention

Each vertex has a domain **property** named `id` that is the public identifier returned to callers. JanusGraph's internal vertex id is also surfaced as `internal_id` in responses for debugging. Caption lookups can be ambiguous; tools accept an optional `label` to disambiguate or fall back to `id`.

### Edge label duality

The schema historically used both `isSupportedBy`/`supportedBy` and `isChallengedBy`/`challengedBy`. The canonical set in `ALLOWED_EDGE_LABELS` uses the `is…By` forms; `normalize_edge_label` maps the alternates. When building queries that traverse "backward" edges, use the `filter_backward_relationships` / `reverse_backward_relationship_keys` helpers so the public API stays directionally consistent.

## Notes

- `gremlinpython` is pinned to `3.7.3` to match the target JanusGraph/TinkerPop version. Bump deliberately — protocol mismatches surface as opaque errors.
- In `gremlin_python`, the traversal step for fetching element ids is `.id_()` (trailing underscore), not `.id()`. `.id` is a property on `GraphTraversal`, so calling `.id()` raises `TypeError: 'GraphTraversal' object is not callable`. Always use `.id_()`.
- Avoid returning full `Vertex` / `Edge` objects from `gremlin_python` 3.7.3 against JanusGraph — the GraphBinaryV1 reader has no handler for `DataType.custom` (0x00) and crashes with `KeyError: <DataType.custom: 0>` when JanusGraph attaches custom-typed property metadata (e.g. `RelationIdentifier`). For existence checks use `is_vertex_existing_by_caption` / `is_vertex_existing_by_id` in [gremlin_helpers.py](src/theo_mcp_server/gremlin_helpers.py); for other reads project to primitives via `valueMap`, `elementMap`, `id_()`, or `project(...)`.
- The server uses `FastMCP(..., json_response=True)`, so tools should return JSON-serializable dicts/lists; image tools return MCP image content directly.
- Manual test recipes (curl/Inspector flows) are in [tests/manual-tests.md](tests/manual-tests.md).
