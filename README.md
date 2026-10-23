# Theo MCP Server

An MCP server (Python) that provides CRUD tools for your JanusGraph (Gremlin) Theo schema plus edge operations, plus generating diagrams.

## Features

Vertex labels supported:
- `notion`
- `person`
- `scholarlyWork`
- `receptionWork`
- `receptionPassage`
- `verse`
- `quotation`
- `notionGroup`
- `verseGroup`

Edge labels supported:
- `refersTo`
- `contains`
- `isSupportedBy`
- `isChallengedBy`
- `isParallelTo`
- `next`
- `writtenBy`

Beyond graph CRUD, the server can render a part of the graph as an **SVG diagram** and return a
download link.

## Install

### Prerequisites

- Python 3.10+
- A reachable Gremlin endpoint (JanusGraph)
- **Graphviz** — required by the diagram tool (see below)

### Graphviz (required for diagrams)

The diagram tool uses the `graphviz` Python package (installed automatically as a dependency), but
that package is only a wrapper: it shells out to the **`dot` executable**, which must be installed
separately on the machine and be on `PATH`. Without it, `create_diagram_by_captions` fails with
`Graphviz executable not found`.

- Windows: `winget install Graphviz.Graphviz` (or the installer from <https://graphviz.org/download/>).
  Make sure "Add Graphviz to the system PATH" is selected; you may need to reopen the shell afterwards.
- macOS: `brew install graphviz`
- Debian/Ubuntu: `sudo apt-get install graphviz`

Verify:

```bash
dot -V
```

### Install the server

```bash
pip install -e .
```

## Configure

Environment variables:

- `GREMLIN_URL` (default: `ws://localhost:8182/gremlin`)
- `GREMLIN_TRAVERSAL_SOURCE` (default: `g`)
- `MCP_TRANSPORT` (default: `stdio`) — or `streamable-http`
- `OWNCLOUD_URL`, `OWNCLOUD_USERNAME`, `OWNCLOUD_TOKEN` — file storage for generated diagrams
  (see [Getting an ownCloud API token](#getting-an-owncloud-api-token))
- `OWNCLOUD_REMOTE_DIR` (default: `theo-diagrams`) — remote folder diagrams are uploaded into
- `OWNCLOUD_VERIFY_SSL` (default: `false`) — verify the ownCloud TLS certificate
- `BACKUP_DIR` — absolute path to the graph backup directory (see [Graph backup](#graph-backup))
- `BACKUP_EXCLUDED_VERTEX_LABELS` (default: `verse`) — comma-separated vertex labels to leave out
- `BACKUP_EXCLUDED_EDGE_LABELS` (default: `next`) — comma-separated edge labels to leave out

See `.env.example` for a full template.

Example:

```bash
export GREMLIN_URL="ws://localhost:8182/gremlin"
export GREMLIN_TRAVERSAL_SOURCE="g"
export MCP_TRANSPORT="stdio"
```

## Getting an ownCloud API token

Generated diagrams are uploaded to ownCloud (see `src/theo_mcp_server/cloud_storage.py`), which
authenticates with **HTTP Basic auth** using `OWNCLOUD_USERNAME` and `OWNCLOUD_TOKEN` — the token
is sent in place of the password. Never put your real account password in `OWNCLOUD_TOKEN`; create
a dedicated app token instead.

### ownCloud Infinite Scale (oCIS) — app token via `auth-app`

oCIS has no app-password UI out of the box; tokens come from the `auth-app` service, which does
**not** autostart. Enable it in the environment your oCIS runs with:

```bash
OCIS_ADD_RUN_SERVICES=auth-app
PROXY_ENABLE_APP_AUTH=true
```

Restart oCIS, then create a token on the docker:

```bash
docker exec -it ocis_runtime ocis auth-app create --user-name=admin --expiration=100000h
```

`--expiration` accepts `h`, `m`, `s` (e.g. `72h`, `720h`); it defaults to `72h`. The token is
printed once — copy it immediately. Put it into `.env` together with the matching user:

```bash
OWNCLOUD_URL=https://your-ocis-host:9200/
OWNCLOUD_USERNAME=admin
OWNCLOUD_TOKEN=<the printed token>
```

Tokens can also be managed over REST at `/auth-app/tokens`, using an existing OIDC access token
as a Bearer credential:

```bash
curl --request POST "https://your-ocis-host:9200/auth-app/tokens?expiry=720h" --header "Authorization: Bearer ${ACCESS_TOKEN}"
```

`GET /auth-app/tokens` lists tokens and `DELETE /auth-app/tokens?token=<token>` revokes one.
Creating a token for another user requires `AUTH_APP_ENABLE_IMPERSONATION=true` and is intended
for migrations, not for regular use.

### Verify the token

```bash
curl -k -u "$OWNCLOUD_USERNAME:$OWNCLOUD_TOKEN" -X PROPFIND -H "Depth: 1" "$OWNCLOUD_URL/remote.php/dav/files/$OWNCLOUD_USERNAME/"
```

A `207 Multi-Status` response means the token works; `401` means it does not. Use `PROPFIND` rather
than a plain `GET` — a `GET` on a WebDAV collection answers `405`, which says nothing about the
credentials. Note that oCIS serves HTTPS on port `9200`, so `http://` there fails with
"Client sent an HTTP request to an HTTPS server". Drop `-k` once your instance has a valid TLS
certificate — and then also set `OWNCLOUD_VERIFY_SSL=true`, which is off by default because the
reference deployment uses a self-signed cert.

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

## Graph backup

The `create_graph_backup` tool exports the knowledge graph to JSON files on the machine running the
MCP server, **overwriting the previous backup in place**. The backup directory is meant to be a
separate git repository: every run rewrites the same files deterministically, so `git diff` between
two runs shows exactly what changed in the graph.

### Configure

```bash
# Absolute path to an existing directory. The tool never creates it, so that a
# typo cannot send months of backups into the wrong place.
BACKUP_DIR=C:\Users\me\private_repos\theo-graph-backup
# What to leave out. Both are optional; empty means the default shown below.
BACKUP_EXCLUDED_VERTEX_LABELS=verse
BACKUP_EXCLUDED_EDGE_LABELS=next
```

Verse *vertices* are excluded by default: they are re-imported from the Bible source rather than
restored from a backup. Verse *edges* are a different matter — only `next`, the verse chain, is left
out, because the verse import rebuilds it. Everything else, including
`verse -isParallelTo-> verse`, is backed up: nothing else can reconstruct those links.

Recommended `.gitattributes` in the backup repository — the tool always writes LF, and this keeps
`core.autocrlf` from rewriting the line endings on checkout:

```
* text eol=lf
```

### Layout

```
manifest.json          export time, exported types, counts, health warnings
vertices/notion.json   one file per vertex type, vertices sorted by id
vertices/...
edges.json             every edge with at least one exported endpoint
```

Vertex record — properties are copied verbatim, so a schema addition never silently drops data:

```json
{
  "id": 122884320,
  "label": "notion",
  "properties": { "caption": "Тема \"Час Иисуса\"", "type": "notion" }
}
```

Edge record — sorted by source id, then target id, then edge label:

```json
{
  "label": "isSupportedBy",
  "source": { "id": 122884320, "type": "notion", "caption": "Тема \"Час Иисуса\"", "exported": true },
  "target": { "id": 15372320, "type": "verse", "caption": "Jn 1:1", "exported": false }
}
```

Every edge of the graph is exported except the excluded labels — those touching an excluded vertex
(`notion -> verse`) as well as those between two excluded vertices
(`verse -isParallelTo-> verse`). The type and caption of both endpoints are stored, which makes the
endpoints resolvable in another database and readable by a human reviewing the file.
`"exported": false` marks an endpoint that is not in this backup.

Only `manifest.json` carries `exported_at`; the data files hold no timestamps, so a run never dirties
a file whose content did not change.

### What the tool returns

Vertex counts by type, edge counts by label and by endpoint-type signature (`notion -refersTo-> verse`),
per-file sizes, removed stale files, run duration, and health warnings — vertices carrying no `type`
property (which are in the graph but not in the backup) and duplicate captions (which break every
caption-based tool in the server).

On failure it returns a structured diagnosis: the stage that broke, whether anything reached the disk,
and what had already been done. Reads all happen before any write, so a failing traversal leaves the
backup directory untouched. If a write fails, the diagnosis says so and the fix is
`git checkout -- .` in the backup repository.

### Restoring into another graph

1. For each `vertices/<type>.json`, create the vertices with `addV(label)` and the `properties` bag
   verbatim, dropping the backup `id`. Keep a map `backup_id -> new_id`.
2. Import the verses separately from the Bible source — that also rebuilds the `next` chain, which is
   the one thing the backup deliberately omits (`manifest.json` lists it under
   `edges.excluded_labels`).
3. For each edge in `edges.json`, resolve both endpoints: through the id map when `"exported": true`,
   and by `caption` lookup otherwise (that is the verse case, on either or both ends).

## Tool overview

See `src/theo_mcp_server/tools/`:
- `graph.py`: create/read/update/delete/list/find for notions, notionGroups, verses, verseGroups, quotations, scholarlyWorks, receptionWorks, receptionPassages; relationships; search; trees; caption rename
- `diagram.py`: `create_diagram_by_captions` — Graphviz SVG diagram, returned as a download link
  (see [Diagrams](#diagrams)); needs the system `dot` binary
- `backup.py`: `create_graph_backup` — JSON export of the whole graph (see [Graph backup](#graph-backup))

The tools use your **property** `id` as the public identifier, and also return JanusGraph's internal id
as `internal_id` in responses (useful for debugging).

## Notes

- Caption lookups can be ambiguous (multiple vertices with the same caption). In that case, provide a `label`
  or use `id` instead.
- gremlinpython must match your server's TinkerPop version. If you run into protocol errors, adjust the pinned
  version in `pyproject.toml` to match your JanusGraph distribution.

