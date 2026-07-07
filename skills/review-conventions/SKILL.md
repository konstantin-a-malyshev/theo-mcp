---
name: review-conventions
description: Review the current diff against this repo's code-convention checklist. Use when asked to review conventions, check a diff before commit, or verify that changes follow project rules. Reports violations with file:line references; does not fix them.
---

# Review conventions

Review the pending changes against the checklist below and report violations.
This is a **conventions** review, not a bug hunt — flag rule violations even in
code that works, and skip style opinions that are not on the list.

## Workflow

1. **Collect the diff.** Review everything that differs from the main branch:
   - `git diff main...HEAD` (committed on this branch)
   - `git diff HEAD` (staged + unstaged)
   - `git status --porcelain` for untracked files; read new files in full.

   If the working tree and branch are clean, say so and stop.

2. **Skip artifact paths.** Ignore changes under `build/`, `tmp/`, `backup/`,
   `.venv/`, `src/theo_mcp_server.egg-info/`, `.pytest_cache/`.

3. **Read enough context.** For each changed hunk, read the surrounding
   function/file so you judge the final state of the code, not the diff text.

4. **Check every item in the checklist** against the changed code only —
   pre-existing violations in untouched lines are out of scope (mention them
   at most as a side note).

5. **Report** using the output format at the bottom.

## Checklist

### Architecture & layering

- [ ] **A1 — Thin tools.** Functions under `src/theo_mcp_server/tools/` only
  normalize input, call helpers, and wrap errors. Gremlin traversals belong in
  `gremlin_helpers.py`, rendering in `diagram_helpers.py`. Flag any `g.V()`,
  traversal chain, or Graphviz call written directly inside a tool body.
- [ ] **A2 — Tool registration pattern.** New MCP tools are `@mcp.tool()`
  closures inside a `register_*_tools(mcp: FastMCP)` function, and new tool
  modules are registered in `server.py`'s `create_mcp()`.
- [ ] **A3 — Schema is centralized.** New vertex labels, edge labels, or
  properties are declared in `schema.py` (`LABELS_CANON`,
  `ALLOWED_EDGE_LABELS`, `ALLOWED_PROPS`, `REQUIRED_PROPS`). Flag label or
  edge-label string literals hardcoded in tools/helpers when a normalizer from
  `validation.py` (`normalize_label`, `normalize_edge_label`,
  `validate_and_fix_properties`) should be used.
- [ ] **A4 — Config through `config.py`.** No hardcoded URLs, usernames,
  passwords, tokens, or hostnames in code or tests; new settings go into the
  `Config` dataclass + `get_config()` + `.env.example`. `.env` itself must
  never appear in the diff.
- [ ] **A5 — `cloud_storage.py` stays stdlib-only.** No `requests`, `httpx`,
  or other HTTP-client dependency added for cloud storage.

### MCP tool contract

- [ ] **M1 — Docstrings are the tool UI.** Every `@mcp.tool()` function has a
  docstring that describes purpose, parameters, and any caption/format
  conventions (e.g. verse captions `{bookAbbrev} {chapter}:{verse}`). The
  docstring is what MCP clients see — treat a missing or stale one as a
  violation.
- [ ] **M2 — Error wrapping.** Graph tools catch `Exception` and re-raise as
  `ToolError(traceback.format_exc())` so clients get the full trace. New tools
  follow the same pattern.
- [ ] **M3 — JSON-serializable returns.** The server runs with
  `json_response=True`: tools return dicts/lists of primitives (image tools
  return MCP image content). Flag returns of custom objects, sets, or
  datetimes.
- [ ] **M4 — IDs convention.** Responses expose JanusGraph's internal id as
  `internal_id`; the `id` **property** is the public identifier. Don't mix
  them up or rename the keys.

### Gremlin correctness rules

- [ ] **G1 — `.id_()` not `.id()`.** In traversals, element ids are fetched
  with `.id_()` (trailing underscore). `.id()` is a runtime `TypeError`.
- [ ] **G2 — No full `Vertex`/`Edge` returns.** Traversals must project to
  primitives (`valueMap`, `elementMap`, `id_()`, `project(...)`). Returning
  raw elements crashes GraphBinaryV1 against JanusGraph
  (`KeyError: <DataType.custom: 0>`). For existence checks use
  `is_vertex_existing_by_caption` / `is_vertex_existing_by_id`.
- [ ] **G3 — Always `get_g(ctx)`.** Tools obtain the traversal source via
  `get_g(ctx)` (it probes liveness and reconnects). Flag caching `g` on
  module/closure level or building a `DriverRemoteConnection` outside
  `gremlin_client.py`.
- [ ] **G4 — Pinned driver.** `gremlinpython==3.7.3` stays pinned; any version
  bump in the diff needs an explicit justification in the change.

### Dependencies & packaging

- [ ] **D1 — Dual declaration.** Dependencies added/removed in
  `pyproject.toml` are mirrored in `requirements.txt` and vice versa.
- [ ] **D2 — No stray artifacts.** Nothing under `build/`, `tmp/`, `backup/`,
  `.venv/`, or `*.egg-info/` is added to git.

### Code style

- [ ] **S1 — `from __future__ import annotations`** at the top of every new
  module under `src/`, matching the existing files.
- [ ] **S2 — Type hints.** Public functions have parameter and return
  annotations in the style of the surrounding code
  (`dict[str, Any]`, `list[str]`, `| None`).
- [ ] **S3 — Unicode-safe output.** `json.dumps` of graph content intended for
  humans uses `ensure_ascii=False` (data is partly Russian).
- [ ] **S4 — PowerShell only.** Shell scripts and documented commands are
  PowerShell (`.ps1`), not bash. No `&&`, `export`, or POSIX paths in docs or
  scripts.
- [ ] **S5 — Vendor independence.** No `CLAUDE.md` is (re)introduced;
  agent-facing conventions belong in `AGENTS.md`, workflows in `skills/`.

### Tests

- [ ] **T1 — Self-cleaning integration tests.** Tests that create vertices
  delete them at the end (`delete_vertex_by_id`) and use unique, timestamped
  captions (`{prefix}_{timestamp}`) so reruns don't collide.
- [ ] **T2 — Pattern conformance.** New tool tests go through the MCP client
  fixture (`mcp_session` calling `call_tool`); helper tests use the `g`
  fixture from `get_g_for_tests()`. Pure logic (like validation) gets plain
  unit tests.
- [ ] **T3 — No live-data assumptions.** Flag new assertions against specific
  production content (magic internal ids, existing captions) unless the test
  creates that data itself.

## Output format

Group findings by severity, most severe first. For each finding give:

```
- [<checklist id>] <file>:<line> — <one-sentence violation> 
  Fix: <one-sentence suggested remedy>
```

Severities:
- **Blocker** — will break at runtime or corrupt behavior (G1, G2, M3) or
  leaks secrets (A4 with credentials).
- **Should fix** — violates architecture/contract rules (A1–A3, M1, M2, G3,
  D1, T1).
- **Nit** — style-level items (S1–S3), minor doc drift.

End with a one-line verdict: `PASS` (no blockers/should-fix) or `FAIL` with
the count per severity. Do **not** modify any files — this skill only reports.
