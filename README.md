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

### Using the console script

```bash
janusgraph-mcp
```

### Or as a module

```bash
python -m janusgraph_mcp_server
```

## Additional tips

- Start MCP inspector: `npx @modelcontextprotocol/inspector`
- Allow to execute Power Shell scripts: `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`
- Example of `claude_desktop_config.json` configuration:

```
{
  "mcpServers": {
    "theo-server": {
      "command": "C:\\Users\\MALY022\\AppData\\Roaming\\Python\\Python312\\Scripts\\janusgraph-mcp.exe"
    }
  }
}
```

## Tool overview

See `src/janusgraph_mcp_server/tools/`:
- `vertices.py`: create/read/update/delete/list/find
- `domain.py`: create notion / notionGroup and connect via supported/challenged/refers
- `edges.py`: connect/add/delete edges between existing vertices

The tools use your **property** `id` as the public identifier, and also return JanusGraph's internal id
as `internal_id` in responses (useful for debugging).

## Notes

- Caption lookups can be ambiguous (multiple vertices with the same caption). In that case, provide a `label`
  or use `id` instead.
- gremlinpython must match your server's TinkerPop version. If you run into protocol errors, adjust the pinned
  version in `pyproject.toml` to match your JanusGraph distribution.


