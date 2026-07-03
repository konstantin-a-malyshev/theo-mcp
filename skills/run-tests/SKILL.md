---
name: run-tests
description: Run the theo-mcp test suite correctly (PowerShell, live JanusGraph/ownCloud) and report results in a bug-fixing-friendly way. Use when asked to run tests, verify a change, or investigate a test failure.
---

# Run tests

Run the pytest suite the way this repo needs it, classify every failure, and report
findings so a bug can be fixed directly from the report.

## How to invoke pytest

- Always run from the **repo root** (`tests/test_server.py` spawns the server via the
  relative path `.venv\Scripts\python.exe`; from any other cwd it fails to start).
- Use the venv interpreter directly — no activation needed and it works in a
  non-interactive shell:

  ```powershell
  .\.venv\Scripts\python.exe -m pytest
  ```

- Useful variants:
  - Single file: `.\.venv\Scripts\python.exe -m pytest tests\test_gremlin.py`
  - Single test: `... -m pytest tests\test_gremlin.py::test_search_vertices`
  - Show prints + full tracebacks (best for debugging): add `-s --tb=long`
  - Stop at first failure: add `-x`
- `pytest.ini` already sets `pythonpath = src` and silences gremlinpython
  deprecation warnings — do not add ad-hoc `sys.path` hacks or warning filters.
- These are network integration tests; a full run can take a while. If a run seems
  stuck, suspect a dead service, not pytest.

## What each test file needs

| File | Needs | Notes |
|---|---|---|
| `test_validation.py` | nothing | Pure unit tests; always runnable |
| `test_gremlin.py` | live JanusGraph (`GREMLIN_URL` in `.env`) | Calls helpers via `get_g_for_tests()`; creates timestamped vertices and deletes them; some tests expect **existing data** (verses `Jn 1:1`–`Jn 1:3`, search hit for `Иоан`) |
| `test_server.py` | live JanusGraph + installed package | Spawns the real MCP server over stdio; expects existing data (`Jn 9:22`, a notion with internal id `122884320`) |
| `test_cloud_storage.py` | live ownCloud/oCIS (`OWNCLOUD_*` in `.env`) | Uploads real files with unique names and deletes them in `finally` |

## Procedure

1. **Preflight.** Confirm `.env` exists in the repo root (never print its contents).
   If it is missing, only `test_validation.py` is meaningful — say so up front.
2. **Scope the run.** If the user is working on a specific area, run the matching
   file(s) first, then the full suite. Otherwise run the full suite.
3. **On failures, rerun just the failing tests** with `-s --tb=long` to capture
   prints and the complete traceback before diagnosing.
4. **Classify every failure** (see below) — this is the core value of the report.
5. **Never weaken a test to make it pass.** Loosening assertions, adding skips, or
   catching exceptions in tests to survive a missing service is a bug, not a fix.
   Fixing product code or the environment is fine; changing a test is only correct
   when the test itself asserts the wrong thing — call that out explicitly.

## Classifying failures

Put each failure in exactly one bucket:

- **Environment** — the service isn't reachable or credentials are wrong. Signatures:
  `Connection refused`, `Connection was already closed`, timeouts, TLS errors,
  HTTP 401 from ownCloud, `.env` missing. Not a code bug; report which service and
  which variable to check.
- **Data-dependent** — the graph doesn't contain the fixture data the test expects
  (missing `Jn 1:1`, no `Иоан` matches, stale hardcoded internal id `122884320` in
  `test_server.py` — internal ids change when the database is rebuilt). Not a code
  bug either; say what data is missing.
- **Real failure** — the code misbehaves. Diagnose using the traceback and the
  known failure signatures below.

### Known failure signatures (fast diagnosis)

- `TypeError: 'GraphTraversal' object is not callable` → someone wrote `.id()`
  instead of `.id_()` in a traversal.
- `KeyError: <DataType.custom: 0>` → a traversal returned a raw `Vertex`/`Edge`;
  it must project to primitives (`valueMap`, `elementMap`, `id_()`, `project(...)`).
- Opaque protocol/serialization errors after a dependency change → check that
  `gremlinpython` is still pinned to `3.7.3`.
- `test_server.py` fails to even initialize the session → the server subprocess
  died on startup; run `.\.venv\Scripts\python.exe -m theo_mcp_server` manually
  from the repo root to see the import/startup error.

## Report format

End with a single consolidated report:

1. **Summary line first**: `X passed, Y failed, Z errors — N real failures,
   M environment, K data-dependent`.
2. For each **real failure**: test name, the decisive traceback lines (not the full
   dump), the classification reasoning, the suspected cause as `file:line` in the
   product code, and a concrete suggested fix. Point into
   `src/theo_mcp_server/` — the bug is almost never in the test.
3. Environment and data-dependent failures: one line each, grouped, with what to
   check or restore. Do not propose code changes for these.
4. If tests created data but crashed before cleanup, note it: test vertices carry
   the test name + timestamp in their caption; leftover ownCloud files start with
   `test_cloud_storage_`.
