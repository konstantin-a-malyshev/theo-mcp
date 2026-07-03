# AGENTS.md

Guidance for AI coding agents working in this repository.

## What this project is

`theo-mcp-server` is a Python MCP server that exposes CRUD and diagram tools over a
theology knowledge graph stored in JanusGraph (accessed via Gremlin/TinkerPop).
The graph holds Bible verses, theological notions, quotations, books, and grouping
vertices, connected by typed edges (`refersTo`, `contains`, `isSupportedBy`, `next`, …).
Generated Graphviz SVG diagrams are uploaded to an ownCloud Infinite Scale (oCIS)
instance and returned as public download links.

## Environment

- **Windows + PowerShell.** Do not use bash-isms (`&&`, `export`, `/dev/null`, backslash
  line continuations). Scripts in the repo root are `.ps1`.
- Python ≥ 3.10, virtualenv in `.venv` (activate with `.\.venv\Scripts\Activate.ps1`,
  create with `init_venv.ps1`).
- Configuration comes from `.env` (see [.env.example](.env.example) for all variables).
  `.env` contains real credentials — never commit it or print its contents.

## Commands

| Task | Command |
|---|---|
| Install (editable) | `pip install -e .` |
| Run server | `theo-mcp` or `python -m theo_mcp_server` |
| Run tests | `pytest` (add `-s` to see stdout) |
| Debug tools interactively | `npx @modelcontextprotocol/inspector` |
| Backup graph data | `.\backup_db.ps1` (scp from the `cap` host into `backup\`) |

**Tests are integration tests.** They open a real Gremlin connection to `GREMLIN_URL`
and create/delete real vertices (using timestamped captions and cleaning up after
themselves). They fail without a reachable JanusGraph and a populated `.env`. Some
assertions also expect existing data (e.g. verses `Jn 1:1`–`Jn 1:3`, Russian captions).
Don't "fix" a test failure caused by a missing database connection by weakening the test.

## Repository layout

```
src/theo_mcp_server/
  server.py           FastMCP factory; registers tool modules in order
  config.py           Env-driven frozen Config dataclass (load via get_config())
  gremlin_client.py   Connection lifecycle (app_lifespan), auto-reconnect, get_g(ctx)
  gremlin_helpers.py  All Gremlin traversal logic (the bulk of the domain code)
  schema.py           Canonical vertex labels, allowed/required properties, edge labels
  validation.py       Label/property normalization and validation
  cloud_storage.py    CloudStorage protocol + OwnCloudStorage (stdlib-only, no deps)
  diagram_helpers.py  Graphviz SVG rendering of induced subgraphs
  tools/graph.py      MCP tool registrations for CRUD/search/tree/relationship ops
  tools/diagram.py    MCP tool registration for create_diagram_by_captions
tests/                pytest integration tests + manual-tests.md (raw JSON-RPC recipes)
docs/                 JanusGraph console snippets, external graph-browser tools
skills/               Per-workflow agent skills (implement-issue, review-conventions, run-tests; finish-pr is a placeholder)
backup/, build/, tmp/ Generated/scratch — do not edit by hand
```

## Architecture conventions

- **Tools are thin wrappers.** MCP tool functions in `tools/*.py` validate inputs,
  fetch `g` via `get_g(ctx)`, and delegate to `gremlin_helpers.py` /
  `diagram_helpers.py`. Put graph logic in the helpers (tests call helpers directly
  through `get_g_for_tests()`), not inside tool closures.
- Tools are registered inside `register_*_tools(mcp)` functions using `@mcp.tool()`;
  every tool takes `ctx: Context[ServerSession, AppContext]` as its first parameter.
  New tool modules must be wired into `create_mcp()` in [server.py](src/theo_mcp_server/server.py).
- The server runs with `FastMCP(..., json_response=True)`: tools must return
  JSON-serializable dicts/lists (image tools return MCP image content directly).
- `schema.py` is the source of truth for vertex labels, edge labels, and allowed/
  required properties. Extend it there first; `validation.py` enforces it.
- The public identifier of a vertex is its **property** `id`; JanusGraph's internal
  id is returned as `internal_id` (debugging aid). Caption lookups can be ambiguous —
  APIs accept a `label` or `id` to disambiguate.
- Relationship keys have direct/reverse mappings (`next`/`previous`,
  `isSupportedBy`/`supports`, …) defined in `gremlin_helpers.py`; keep both
  directions consistent when adding edge types.
- Quotation `status` must be one of `new`, `suspended`, `processed`
  (`VALID_QUOTATION_STATUSES` in `gremlin_helpers.py`).

## Gremlin/JanusGraph gotchas (hard-won — do not regress)

- `gremlinpython` is **pinned to 3.7.3** to match the JanusGraph/TinkerPop version.
  Bump deliberately; protocol mismatches surface as opaque errors.
- Use `.id_()` (trailing underscore) to fetch element ids in a traversal. `.id` is a
  property on `GraphTraversal`, so `.id()` raises `TypeError: 'GraphTraversal' object
  is not callable`.
- **Never return full `Vertex`/`Edge` objects** from traversals. The GraphBinaryV1
  reader in gremlinpython 3.7.3 has no handler for `DataType.custom` and crashes with
  `KeyError: <DataType.custom: 0>` when JanusGraph attaches custom-typed metadata
  (e.g. `RelationIdentifier`). Always project to primitives via `valueMap`,
  `elementMap`, `id_()`, or `project(...)`. For existence checks use
  `is_vertex_existing_by_caption` / `is_vertex_existing_by_id` in `gremlin_helpers.py`.
- `get_g(ctx)` performs a liveness probe and transparently reconnects after idle
  timeouts / server restarts / laptop sleep. Always obtain `g` through it in tools;
  don't cache the traversal source across requests.

## ownCloud (oCIS) storage

- The endpoint is ownCloud **Infinite Scale**. Authentication is HTTP **Basic** with a
  plaintext app token (`OWNCLOUD_TOKEN`, created under Settings → Security/auth-app)
  as the password — Bearer auth returns 401 on WebDAV there.
- Uploads go over WebDAV; a public share link is created via the OCS Share API and the
  direct download URL is returned. Public links are password-less.
- `OwnCloudStorage` deliberately uses only the standard library — don't add an HTTP
  client dependency for it. New storage backends should implement the `CloudStorage`
  protocol.
- `OWNCLOUD_VERIFY_SSL` defaults to `false` because the default endpoint is an IP with
  a self-signed certificate.

## Project rules for agents

- **Do not create a `CLAUDE.md`.** It was removed on purpose; this file is the single
  agent-facing convention document. Reusable workflows belong in `skills/`.
- Match the existing code style: `from __future__ import annotations`, built-in
  generics (`dict[str, Any]`), snake_case tool names that read as actions
  (`get_notion_by_caption`, `create_relationship`), docstrings on tools describing
  args and returns (they become the MCP tool descriptions shown to clients).
- Manual end-to-end recipes (raw JSON-RPC bodies for the Inspector/stdio) live in
  [tests/manual-tests.md](tests/manual-tests.md); JanusGraph console/index snippets in
  [docs/janus-graph.md](docs/janus-graph.md); graph-browser tooling in
  [docs/external-tools.md](docs/external-tools.md).
