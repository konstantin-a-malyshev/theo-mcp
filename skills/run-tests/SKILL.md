---
name: run-tests
description: Run the test suite (venv, live JanusGraph/oCIS preflight) and report results in a bug-fixing-friendly form. Use when asked to run tests, verify a change, or diagnose test failures.
---

# Run tests

Run the pytest suite of this repo the right way, separate **environment
failures** from **code failures**, and report results so a bug can be fixed
directly from the report.

## Key facts about this suite

- **Almost all tests are integration tests.** They need a live JanusGraph at
  `GREMLIN_URL` and (for storage/diagram tests) a reachable oCIS instance —
  both configured via `.env`. Only `tests/test_validation.py` is pure unit.
- `tests/test_server.py` spawns the MCP server as a subprocess via
  `.venv\Scripts\python.exe -m theo_mcp_server`, so the `.venv` must exist and
  the package must be importable from `src/` (handled by `pytest.ini`
  `pythonpath = src`; no editable install required).
- Tests create and delete **real vertices** in the graph. Never run them
  against a database you are not allowed to write to.
- This is Windows/PowerShell: no `&&`, no `export`, no POSIX paths.

## Workflow

### 1. Preflight (fail fast with a clear message)

Run these checks first; if one fails, report it as an **environment problem**
and don't blame the code:

```powershell
# venv exists
Test-Path .venv\Scripts\python.exe

# .env exists (holds GREMLIN_URL, oCIS credentials)
Test-Path .env

# JanusGraph reachable (adjust host/port if GREMLIN_URL in .env differs
# from the default ws://localhost:8182/gremlin)
Test-NetConnection localhost -Port 8182 -InformationLevel Quiet
```

Do **not** print the contents of `.env`.

### 2. Run

Invoke pytest through the venv's interpreter — no activation needed, works in
any shell:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Useful variants:

| Goal | Command |
|---|---|
| Full run, quiet + summary of all outcomes | `.\.venv\Scripts\python.exe -m pytest -q -ra` |
| See test stdout (tests print JSON dumps) | add `-s` |
| One file | `... -m pytest tests/test_gremlin.py` |
| One test | `... -m pytest tests/test_gremlin.py::test_search_vertices` |
| Filter by keyword | `... -m pytest -k "notion"` |
| Unit tests only (no live services needed) | `... -m pytest tests/test_validation.py` |
| Stop at first failure (fast bug loop) | add `-x` |
| Full tracebacks for debugging | add `--tb=long` |

When fixing a specific bug, prefer the tightest scope (`-k` / node id, plus
`-x --tb=long -s`) and re-run just that test after each change; run the full
suite once at the end.

### 3. Classify failures

Match failures against these known signatures **before** treating them as
code bugs:

| Signature in output | Meaning | Kind |
|---|---|---|
| `Connection refused` / `Cannot connect to host ...:8182` | JanusGraph down or wrong `GREMLIN_URL` | environment |
| `Connection was already closed` | dropped websocket (idle/sleep); `get_g()` should auto-reconnect — if it appears in a test using the raw `g` fixture, just re-run | environment |
| HTTP `401` from oCIS / ownCloud | `OWNCLOUD_TOKEN` missing or expired; oCIS needs Basic auth with an app token | environment |
| `TypeError: 'GraphTraversal' object is not callable` | someone wrote `.id()` instead of `.id_()` | **code** |
| `KeyError: <DataType.custom: 0>` | a traversal returns raw `Vertex`/`Edge` instead of projecting to primitives (`valueMap`, `elementMap`, `id_()`, `project`) | **code** |
| Assertion on a caption / `internal_id` that doesn't exist | test assumes live production data that this graph doesn't have | test-data |
| Duplicate-caption errors from `get_unique_vertex_by_caption` | leftover vertices from an earlier aborted run | test-data (clean up the leftovers) |

Anything else with a traceback into `src/theo_mcp_server/` is a **code**
failure — that's the interesting kind.

### 4. Report

Structure the report so the reader can start fixing immediately:

```
## Test report

Command: <exact command run>
Result: <N passed, N failed, N errored, N skipped in Xs>

### Environment / test-data failures (not code bugs)
- <test id> — <signature> → <what to fix in the environment>

### Code failures
For each:
- **<test id>**
  - Error: <exception type + message, one line>
  - Where: <file:line the traceback points to in src/>
  - Likely cause: <one sentence, referencing the classification table if it matched>
  - Suggested next step: <one sentence>
```

Rules:
- Quote the **decisive lines** of a traceback (deepest frame in
  `src/theo_mcp_server/` + the exception line), not the whole wall of text.
- If everything passed, say so in one line and stop — no empty sections.
- If preflight failed, report only the environment problem and how to fix it
  (start JanusGraph, create `.env` from `.env.example`, run
  `.\init_venv.ps1` / `pip install -e .`), and don't run the suite.
- If tests created vertices but failed before their cleanup ran, list the
  probable leftover captions (tests use `{prefix}_{timestamp}` naming) so they
  can be deleted.
