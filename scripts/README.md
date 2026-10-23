# Scripts

One-off maintenance scripts that talk to the graph directly, outside the MCP
server. They are not MCP tools, so — unlike `src/theo_mcp_server/tools/` — they
build their own Gremlin traversals instead of delegating to `gremlin_helpers.py`;
migration logic has no place in the production helpers. They do reuse the
package's validation, so nothing reaches the graph that the server's own schema
would reject.

Shared conventions:

- **Dry run by default.** Every script prints what it would do and changes nothing
  until `--apply` is passed.
- Run them from the repository root with the venv interpreter:
  `.venv\Scripts\python.exe scripts\<name>.py …`
- The Gremlin endpoint and credentials come from `.env` through
  `theo_mcp_server.config`, the same as the server's.
- On exit `aiohttp` may print `Unclosed client session` / `WinError 87`. That is
  noise from the shared test connection helper, after the work is done — it does
  not mean the run failed. Trust the summary line instead.

---

## `import_biblindex.py`

Imports the biblIndex export into the graph:

```
receptionWork -contains-> receptionPassage -refersTo-> verse | verseGroup
```

Reads the three CSV files from `biblindex-importer/output` (`--source-dir` to point
elsewhere) and creates one `receptionWork` per work and one `receptionPassage` per
quotation, with the fields documented in [docs/reception-schema.md](../docs/reception-schema.md).

```bash
python scripts/import_biblindex.py                          # dry run, everything
python scripts/import_biblindex.py --work-id 7978 --apply   # one work first
python scripts/import_biblindex.py --apply --log tmp/import.json
```

What it does and does not do:

- **Missing `verseGroup` vertices are created** (1479 of them for the full export,
  on top of the 43 that already exist), and **every group the import links to is
  itself linked to its verses** with `verseGroup -contains-> verse` — 9512 edges
  over 1522 groups. This is not optional: without them there is no way back from a
  verse to the passages that quote it through a group, and
  `verse → in(contains) → in(refersTo)` is the traversal the whole import exists
  for. Groups that existed before are included, so a group left unlinked by
  whatever created it gets repaired; the 43 pre-existing ones turn out to be linked
  already. Re-runs add only what is missing.
- The whole-book group (`Jn`, used by 149 quotations that reference the gospel as a
  whole) gets all 879 verses as members, for the same reason. Worth knowing when
  querying: "who quotes Jn 3:16" will then also reach passages that merely
  referenced John. Filter by the group's caption when that matters.
- **Verses are never created** — they come from the Bible import, so a reference to
  a verse the graph does not have is counted, reported, and left unlinked rather
  than invented. In the current export that is 55 references, most of them biblIndex
  slips such as `Jn 49:11` in a commentary on Ecclesiastes, and 6 more references
  are malformed (`Jn:17`).
- **`corpusPath` and `ctsUrn` stay empty.** Matching a work to the normalized
  corpus is a separate step; `tlgAuthorId` is filled where biblIndex knows the
  author's TLG number (790 of 2401 works), which is what that matching will start from.
- **No `person` vertices and no `writtenBy` edges.** The author is only in the
  work's caption for now, the way `scholarlyWork` captions already work.
- The link target is built from the structured `start_*`/`end_*` columns, not from
  the `reference` string: some references carry a stray space (`Jn 14: 23`) and
  would not match a caption. `reference` is still stored verbatim.

Scale for the full export: 72 466 quotations over 2401 works, all of them
references to John — 72 466 passages, 2401 works, 1479 new verse groups and
154 383 edges (72 466 `contains`, 72 405 `refersTo`, 9512 group membership).

Identity and re-runs: every vertex carries `sourceKey` (`biblindex:<id>`), backed by
the `bySourceKey` composite index. A re-run skips what is already in the graph, so
an interrupted import can simply be started again. Each passage is created together
with its edges in one traversal, so a passage never ends up orphaned from its work.
Captions are composed to be unique and stable: works as `<author>. <latin title>`,
with ` (bi:<id>)` appended when two works would collide (14 cases, e.g. twelve
different `Anonyma. Euchologion`), and passages always carry `(bi:<id>)`.

---

## `create_index.py`

Creates a JanusGraph composite vertex index over one property key, through the
ordinary driver rather than the Gremlin console — so it does not depend on the
console container's `conf/remote.yaml`, which has to carry the server credentials
and loses them whenever the container is rebuilt.

```bash
python scripts/create_index.py --property sourceKey
python scripts/create_index.py --property sourceKey --close-stale-instances --apply
```

The dry run prints the current indexes, the state of the property key, how many
vertices already carry it, and the live and stale instances. Then it creates the
index, waits for `REGISTERED`, and either reindexes or — when nothing carries the
key yet — enables it directly, which needs no scan.

`--close-stale-instances` force-closes every open JanusGraph instance except the
live one. This is not optional housekeeping: `REGISTER_INDEX` waits for every open
instance to acknowledge the new index, and registrations left behind by earlier
server runs never will, so the wait never ends. 28 of them had piled up by October
2026. Safe while the backend is single-process (`berkeleyje`).

Index status is polled with short requests instead of the server-side
`awaitGraphIndexStatus`, which would sit inside one request and hit the script
evaluation timeout.

---

## `retype_vertices.py`

Changes the type (and Gremlin label) of existing vertices, keeping their properties
and all their edges. Used for `book` → `scholarlyWork`, and meant for moving single
works into another type later — a patristic author that landed in `scholarlyWork`
belongs in `receptionWork`.

```bash
python scripts/retype_vertices.py --from book --to scholarlyWork
python scripts/retype_vertices.py --from scholarlyWork --to receptionWork \
    --caption "Justin Martyr. The First Apology" --apply
```

JanusGraph vertex labels are immutable, so every vertex is re-created under the new
label, its properties and incident edges are copied, the edge counts are verified,
and only then is the original dropped. **Internal ids change**; `--log` writes the
old-to-new mapping. Caption references are unaffected.

Properties are copied verbatim, deliberately bypassing `validation.py`: live
vertices carry properties that `ALLOWED_PROPS` does not list (23 of the 27 books
had a `name`), and a validating copy would drop them.
