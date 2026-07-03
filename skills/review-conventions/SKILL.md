---
name: review-conventions
description: Review the current diff against the theo-mcp code-convention checklist. Use when asked to check conventions, review a change before commit/PR, or verify a diff follows project rules.
---

# Review conventions

Review the pending change against the project convention checklist below and report
violations. This is a conventions review, not a bug hunt — flag checklist violations
and obvious correctness problems you happen to see, nothing else.

## 1. Collect the diff

Determine what "the current diff" is, in this order:

1. Uncommitted work: `git diff` plus `git diff --staged`. If non-empty, review that.
2. Otherwise, the branch diff against main: `git diff main...HEAD`.
3. If both are empty, say so and stop.

Also run `git status` to catch new untracked files — review those too.

Read every changed file in full (not just hunks): conventions like layering and
registration order are only visible with surrounding context.

## 2. Checklist

Check each changed file against every applicable item. Skip items that the diff
cannot violate (e.g. no tool changes → skip tool items).

### Architecture & layering

- [ ] **Tools are thin wrappers.** Functions under `src/theo_mcp_server/tools/` only
      validate inputs, call `get_g(ctx)` / `get_cloud_storage(ctx)`, and delegate to
      `gremlin_helpers.py` or `diagram_helpers.py`. Traversal logic inside a tool
      closure is a violation — it belongs in the helpers, where tests can reach it
      via `get_g_for_tests()`.
- [ ] **Tool registration pattern.** New tools are defined inside a
      `register_*_tools(mcp)` function with `@mcp.tool()`, take
      `ctx: Context[ServerSession, AppContext]` as the **first** parameter, and new
      tool modules are wired into `create_mcp()` in `server.py`.
- [ ] **Tool error handling.** Every tool body is wrapped in
      `try: ... except Exception: raise ToolError(traceback.format_exc())` —
      matching the existing tools in `tools/graph.py`.
- [ ] **JSON-serializable returns.** The server uses `json_response=True`; tools
      return plain dicts/lists of primitives (image tools return MCP image content).
      No custom objects, no gremlin types in return values.
- [ ] **Docstrings are the API.** Every tool has a docstring describing arguments,
      allowed values, and the return shape — it becomes the tool description shown
      to MCP clients. A new/changed parameter without docstring coverage is a finding.

### Gremlin / JanusGraph safety

- [ ] **No `.id()`** — element ids are fetched with `.id_()` (trailing underscore).
      `.id()` raises `TypeError: 'GraphTraversal' object is not callable`.
- [ ] **No raw `Vertex`/`Edge` returns from traversals.** They crash the
      GraphBinaryV1 reader (`KeyError: <DataType.custom: 0>`). Traversals must
      project to primitives: `valueMap`, `elementMap`, `id_()`, or `project(...)`.
      Existence checks use `is_vertex_existing_by_caption` / `is_vertex_existing_by_id`.
- [ ] **`g` comes from `get_g(ctx)`** inside tools (it probes liveness and
      reconnects). The traversal source is never cached across requests or stored
      on module level.
- [ ] **`gremlinpython` stays pinned to 3.7.3** unless the change is explicitly a
      deliberate, tested version bump.

### Schema & domain rules

- [ ] **`schema.py` is the source of truth.** New vertex labels, edge labels, or
      properties are added to `LABELS_CANON` / `ALLOWED_EDGE_LABELS` /
      `ALLOWED_PROPS` / `REQUIRED_PROPS` first; enforcement goes through
      `validation.py`, not ad-hoc checks in tools.
- [ ] **Relationship mappings stay symmetric.** A new edge type is added to *both*
      `direct_reverse_mapping` and `backward_reverse_mapping` in
      `gremlin_helpers.py`, and to the relationship lists in the affected tool
      docstrings.
- [ ] **Public id vs internal id.** Responses expose the property `id` as the public
      identifier and JanusGraph's id only as `internal_id`. Caption-based lookups
      that can be ambiguous accept a `label` or `id` to disambiguate.
- [ ] **Quotation statuses** are validated against `VALID_QUOTATION_STATUSES`
      (`new`, `suspended`, `processed`) — no new hardcoded status strings elsewhere.

### Dependencies & configuration

- [ ] **No casual new dependencies.** `cloud_storage.py` is stdlib-only by design.
      A new runtime dependency must be justified and added to `pyproject.toml`
      dependencies (and `requirements.txt` if it is updated in the same change).
- [ ] **Config discipline.** New settings go through the frozen `Config` dataclass +
      `get_config()` in `config.py`, are read via `_env`/`_env_bool`, and are
      documented in `.env.example` with a placeholder value. Real secrets never
      appear in the diff — not in `.env.example`, tests, or docs.
- [ ] **Storage backends implement the `CloudStorage` protocol** rather than being
      called concretely from tools.

### Style

- [ ] `from __future__ import annotations` at the top of every module.
- [ ] Built-in generics (`dict[str, Any]`, `list[str] | None`), not
      `Dict`/`List`/`Optional`.
- [ ] Tool and helper names are snake_case actions that state object and access path:
      `get_notion_by_caption`, `delete_verse_group_by_caption`, `create_relationship`.
- [ ] Comments state constraints the code can't show (version pins, protocol quirks),
      not narration of what the next line does.

### Tests & docs

- [ ] **New helper logic has a test** in `tests/`, following the existing pattern:
      integration test against a live graph, timestamped/prefixed captions for test
      data, and explicit cleanup (delete what was created) at the end.
- [ ] **Tests were not weakened** to pass without a database — a connection failure
      is an environment problem, not a reason to loosen assertions.
- [ ] **README tool overview / conventions updated** when tools or hard-won gotchas
      change; new manual JSON-RPC recipes go to `tests/manual-tests.md`.
- [ ] **No `CLAUDE.md`** is added or restored; agent-facing conventions live in
      `AGENTS.md`, workflows in `skills/`.
- [ ] Any new shell script is PowerShell (`.ps1`) — this is a Windows-only repo,
      no bash scripts.

## 3. Report

Output a short report:

1. **Verdict first**: "No convention violations" or "N violations, M suggestions".
2. One entry per finding: `file:line` — which checklist item, what the code does,
   and the concrete fix. Order by severity: correctness-relevant items (Gremlin
   safety, error handling, schema) before style.
3. Do not report style preferences that are not on the checklist, and do not report
   pre-existing violations in lines the diff didn't touch — mention those at most as
   a one-line footnote.
4. Do not fix anything. This skill only reviews; apply changes only if the user asks
   afterwards.
