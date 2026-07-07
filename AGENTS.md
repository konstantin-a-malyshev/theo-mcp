# AGENTS.md

Guidance for AI coding agents working in this repository.

## What this project is

**theo-mcp** is a Python MCP server exposing CRUD, search, and diagram tools over a
JanusGraph (Gremlin/TinkerPop) database that models a theological knowledge graph:
notions, notion groups, Bible verses, verse groups, quotations, books, and persons,
connected by edges like `isSupportedBy`, `isChallengedBy`, `refersTo`, `contains`.
Generated diagrams (Graphviz SVG) are uploaded to an ownCloud Infinite Scale (oCIS)
instance and returned as public download links.

## Environment

- **Windows 11, PowerShell.** Use PowerShell syntax for shell commands — no
  `&&`, no bash-isms, no `/dev/null`.
- Python virtual env lives in `.venv`. Activate with `.\.venv\Scripts\Activate.ps1`.
- Runtime config comes from `.env` (loaded via `python-dotenv` in `config.py`).
  `.env.example` documents all variables; `.env` exists locally and holds real
  credentials — never commit or print its contents.

## Commands

| Task | Command |
|---|---|
| Install (editable) | `pip install -e .` |
| Run server | `theo-mcp` or `python -m theo_mcp_server` |
| Run tests | `pytest` (add `-s` for stdout) |
| Single test | `pytest tests/test_gremlin.py::test_search_vertices` |
| MCP inspector | `npx @modelcontextprotocol/inspector` |
| Backup graph data | `.\backup_db.ps1` (scp from the `cap` host into `backup\`) |

**Tests are integration tests.** Everything except `tests/test_validation.py`
requires a live JanusGraph at `GREMLIN_URL` and (for storage/diagram tests) a
reachable oCIS instance. They create and delete real vertices. Don't treat test
failures as code bugs before checking connectivity. Manual curl/Inspector recipes
are in `tests/manual-tests.md`.

## Layout

```
src/theo_mcp_server/
  __main__.py        entry point; runs FastMCP with transport from config
  server.py          create_mcp(): builds FastMCP, registers tool modules
  config.py          frozen Config dataclass, get_config() reads env/.env
  schema.py          single source of truth: vertex labels, edge labels,
                     allowed/required properties per label
  validation.py      label/edge normalization + property validation against schema.py
  gremlin_client.py  connection lifecycle (app_lifespan), AppContext,
                     get_g() liveness probe + auto-reconnect, get_cloud_storage()
  gremlin_helpers.py all Gremlin traversal logic (create/read/delete vertices,
                     edges, search, trees, subgraphs)
  diagram_helpers.py Graphviz SVG rendering of caption-induced subgraphs
  cloud_storage.py   CloudStorage Protocol + OwnCloudStorage (WebDAV upload,
                     OCS public share link; stdlib urllib only)
  tools/
    graph.py         MCP tools for graph CRUD/search/trees
    diagram.py       MCP tool create_diagram_by_captions
docs/                JanusGraph console recipes, external graph-viewer tools
skills/              reusable agent workflows (one folder per skill, SKILL.md inside)
tests/               pytest integration tests + manual-tests.md
```

## Conventions

- **Tool registration pattern:** each `tools/*.py` exposes a
  `register_*_tools(mcp: FastMCP)` function containing `@mcp.tool()`-decorated
  closures. New tool modules follow this pattern and get registered in
  `server.py`.
- **Tools stay thin.** Traversal logic belongs in `gremlin_helpers.py` /
  `diagram_helpers.py`; tools just normalize input, call helpers, and wrap
  errors. Graph tools catch `Exception` and re-raise as
  `ToolError(traceback.format_exc())` so the MCP client sees the full trace.
- **Schema changes go through `schema.py`.** New labels, edges, or properties
  are added there; `validation.py` enforces it. Don't hardcode label strings in
  tools.
- **Captions are the public keys.** Users address vertices by `caption`
  (unique-ish, human-readable); verse captions have the format
  `{bookAbbrev} {chapter}:{verse}` (e.g. `Jn 1:11`). Caption lookups can be
  ambiguous — helpers like `get_unique_vertex_by_caption` raise on duplicates.
- **IDs:** responses expose JanusGraph's internal vertex id as `internal_id`
  (debugging aid); the property `id` is the public identifier where present.
- **Relationships in create-tools** accept both directions ("isSupportedBy" and
  "supports", etc.); backward keys are reversed into incoming edges via
  `filter_backward_relationships` / `reverse_backward_relationship_keys`.
- The server runs with `FastMCP(..., json_response=True)`: tools must return
  JSON-serializable dicts/lists (image tools return MCP image content directly).
- Data content is partly **Russian** (captions, quotation text); keep
  `ensure_ascii=False` when JSON-dumping for humans.

## gremlinpython gotchas (cause real breakage)

- `gremlinpython` is **pinned to 3.7.3** to match the JanusGraph/TinkerPop
  version. Bump deliberately — protocol mismatches surface as opaque errors.
- Use `.id_()` (trailing underscore) to fetch element ids in traversals.
  `.id` is a property on `GraphTraversal`, so `.id()` raises
  `TypeError: 'GraphTraversal' object is not callable`.
- **Never return full `Vertex`/`Edge` objects** from traversals against
  JanusGraph: the GraphBinaryV1 reader crashes with
  `KeyError: <DataType.custom: 0>` on custom-typed metadata (e.g.
  `RelationIdentifier`). Project to primitives with `valueMap`, `elementMap`,
  `id_()`, or `project(...)`. For existence checks use
  `is_vertex_existing_by_caption` / `is_vertex_existing_by_id` in
  `gremlin_helpers.py`.
- Connections drop on idle/sleep; `get_g()` in `gremlin_client.py` probes with
  `g.inject(0).toList()` and reconnects automatically. Always obtain `g` via
  `get_g(ctx)` inside tools, never cache it.

## ownCloud / oCIS specifics

- The endpoint is **ownCloud Infinite Scale**. Auth is HTTP **Basic** with the
  username and a plaintext **app token** as password (`OWNCLOUD_TOKEN`);
  Bearer auth returns 401 on WebDAV.
- Default endpoint is an IP with a self-signed cert, so
  `OWNCLOUD_VERIFY_SSL=false` by default.
- `cloud_storage.py` deliberately uses only the standard library (urllib) —
  don't add an HTTP client dependency for it.

## Repo policies

- This repo is intentionally **AI-vendor-independent**: conventions live in this
  `AGENTS.md`, reusable agent workflows in `skills/` (e.g.
  `skills/review-conventions/` checks a diff against the convention checklist).
  Do **not** create a `CLAUDE.md`.
- Dependencies are declared in both `pyproject.toml` and `requirements.txt` —
  keep them in sync when adding/removing packages.
- `build/`, `tmp/`, `backup/`, `.venv/`, and `src/theo_mcp_server.egg-info/`
  are artifacts — don't edit or commit content there.
