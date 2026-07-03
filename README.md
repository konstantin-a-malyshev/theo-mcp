# Theo MCP Server

An MCP server (Python) that provides CRUD tools for your JanusGraph (Gremlin) Theo schema plus edge operations.

## Features

Vertex labels supported:
- `notion`
- `person`
- `Book`
- `verse`
- `notionGroup`
- `verseGroup`

Edge labels supported:
- `refersTo`
- `contains`
- `isSupportedBy` and `supportedBy`
- `isChallengedBy` and `challengedBy`
- `isParallelTo`
- `next`
- `writtenBy`

> Your schema mentions both `isSupportedBy`/`isChallengedBy` and `supportedBy`/`challengedBy`.
> This server supports both. Choose which label you want to create per call.

## Install

```bash
pip install -e .
```

## Configure

Environment variables:

- `GREMLIN_URL` (default: `ws://localhost:8182/gremlin`)
- `GREMLIN_TRAVERSAL_SOURCE` (default: `g`)
- `MCP_TRANSPORT` (default: `stdio`) — or `streamable-http`

Example:

```bash
export GREMLIN_URL="ws://localhost:8182/gremlin"
export GREMLIN_TRAVERSAL_SOURCE="g"
export MCP_TRANSPORT="stdio"
```

## Run

### Activate Virtual Environment

```bash
.\.venv\Scripts\Activate.ps1
```

### Using the console script

```bash
theo-mcp
```

### Or as a module

```bash
python -m theo_mcp_server
```

## Run Tests

```
pytest
```

or with stdout output

```
pytest -s
```

## Additional tips

- Start MCP inspector: `npx @modelcontextprotocol/inspector`
- Allow to execute Power Shell scripts: `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`
- Example of `claude_desktop_config.json` configuration:

```
{
  "mcpServers": {
    "theo-server": {
      "command": "C:\\Users\\MALY022\\AppData\\Roaming\\Python\\Python312\\Scripts\\theo-mcp.exe"
    }
  }
}
```

## Tool overview

See `src/theo_mcp_server/tools/`:
- `graph.py`: create/read/update/delete/list/find for notions, notionGroups, verses, verseGroups, quotations, books; relationships; search; trees; caption rename
- `diagram.py`: Graphviz SVG diagram generation

The tools use your **property** `id` as the public identifier, and also return JanusGraph's internal id
as `internal_id` in responses (useful for debugging).

## Notes and Conventions

- Caption lookups can be ambiguous (multiple vertices with the same caption). In that case, provide a `label`
  or use `id` instead.
- `gremlinpython` is pinned to `3.7.3` to match the target JanusGraph/TinkerPop version. Bump deliberately — protocol mismatches surface as opaque errors.
- In `gremlin_python`, the traversal step for fetching element ids is `.id_()` (trailing underscore), not `.id()`. `.id` is a property on `GraphTraversal`, so calling `.id()` raises `TypeError: 'GraphTraversal' object is not callable`. Always use `.id_()`.
- Avoid returning full `Vertex` / `Edge` objects from `gremlin_python` 3.7.3 against JanusGraph — the GraphBinaryV1 reader has no handler for `DataType.custom` (0x00) and crashes with `KeyError: <DataType.custom: 0>` when JanusGraph attaches custom-typed property metadata (e.g. `RelationIdentifier`). For existence checks use `is_vertex_existing_by_caption` / `is_vertex_existing_by_id` in [gremlin_helpers.py](src/theo_mcp_server/gremlin_helpers.py); for other reads project to primitives via `valueMap`, `elementMap`, `id_()`, or `project(...)`.
- The server uses `FastMCP(..., json_response=True)`, so tools should return JSON-serializable dicts/lists; image tools return MCP image content directly.
- Manual test recipes (curl/Inspector flows) are in [tests/manual-tests.md](tests/manual-tests.md).



