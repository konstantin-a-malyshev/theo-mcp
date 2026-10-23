"""Import the biblIndex export into the graph as receptionWorks and receptionPassages.

Reads the three CSV files produced by `biblindex-importer` and creates:

    receptionWork -contains-> receptionPassage -refersTo-> verse | verseGroup

Missing `verseGroup` vertices are created, and every group the import links to is
itself linked to its verses (`verseGroup -contains-> verse`), including groups that
existed before — without those edges there is no way back from a verse to the
passages that quote it through a group. **Verses are never created** — they come
from the Bible import, so a reference to a verse that does not exist in the graph
is reported and left unlinked rather than invented. `corpusPath` and `ctsUrn` stay
empty: matching a work to the normalized corpus is a separate step.

Dry run by default; `--apply` writes.

    python scripts/import_biblindex.py --source-dir ../biblindex-importer/output
    python scripts/import_biblindex.py --work-id 7978 --apply          # one work first
    python scripts/import_biblindex.py --apply --log tmp/import.json   # everything

Identity and re-runs: every vertex carries `sourceKey` (`biblindex:<id>`), which is
backed by the `bySourceKey` composite index. A re-run skips what is already there,
so an interrupted import can simply be started again. Each passage is created
together with its edges in one traversal, so a passage never ends up without them.

Field semantics are documented in `docs/reception-schema.md`.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
from collections import Counter
from datetime import datetime
from typing import Any, Iterable, Iterator

from gremlin_python.process.graph_traversal import GraphTraversalSource, __
from gremlin_python.process.traversal import P, T

from theo_mcp_server.gremlin_client import get_g_for_tests
from theo_mcp_server.validation import validate_and_fix_properties

SOURCE = "biblindex"
SOURCE_BASE_URL = "https://www.biblindex.org"
DEFAULT_SOURCE_DIR = "../biblindex-importer/output"
VERTEX_BATCH_SIZE = 100
PASSAGE_BATCH_SIZE = 50

# `quotation_types` mixes several axes and 60% of its mass is undocumented
# typographic sigla (`<`, `>`, `]`, `/`). Only the labels whose meaning is plain
# are mapped; everything stays verbatim in `sourceTags`, so the rest can be
# derived later without re-importing. First match in this order wins.
REFERENCE_TYPE_TAGS = (
    ("lemma", "lemma"),
    ("quotation", "quotation"),
    ("paraphrase", "paraphrase"),
    ("allusion", "allusion"),
)
UNCERTAIN_TAGS = {"uncertainty", "one of the several references proposed"}
VERIFICATION_STATUSES = {"checked", "unchecked", "error"}


# --- reading the export ------------------------------------------------------


def read_csv(path: str) -> list[dict[str, str]]:
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def iter_quotations(path: str) -> Iterator[dict[str, str]]:
    with open(path, encoding="utf-8-sig", newline="") as fh:
        yield from csv.DictReader(fh)


def year_of(value: str) -> int | None:
    """Year out of a biblIndex date like `0370-01-01T12:44:49+00:09`."""
    head = (value or "").strip()[:4]
    return int(head) if head.isdigit() else None


# --- building vertex properties ----------------------------------------------


def work_caption(work: dict[str, str], collisions: set[str]) -> str:
    """`<author>. <latin title>`, with the source id appended when ambiguous.

    The suffix goes on *every* member of a colliding group rather than on the
    later ones, so the caption does not depend on iteration order.
    """
    title = work["latinName"] or work["name"]
    caption = f"{work['author_names']}. {title}".strip()
    return f"{caption} (bi:{work['id']})" if caption in collisions else caption


def work_props(
    work: dict[str, str], authors: dict[str, dict[str, str]], caption: str
) -> dict[str, Any]:
    own_authors = [authors[i.strip()] for i in work["authors_ids"].split(";")
                   if i.strip() in authors]

    props: dict[str, Any] = {
        "caption": caption,
        "title": work["name"],
        "titleLatin": work["latinName"],
        "abbreviation": work["abbreviation"],
        "language": work["transmissionLanguages"],
        "clavis": work["clavisNumbers"],
        "note": work["description"],
        "source": SOURCE,
        "sourceId": work["id"],
        "sourceKey": f"{SOURCE}:{work['id']}",
        "sourceUrl": f"{SOURCE_BASE_URL}{work['iri']}" if work["iri"] else "",
    }
    if work["fragment"]:
        props["fragmentary"] = work["fragment"]

    # A single identified author gives two things: the TLG number that the corpus
    # matching will start from, and a defensible dating — the work cannot predate
    # its author's birth nor outlive their death.
    if len(own_authors) == 1:
        author = own_authors[0]
        tlg = author["tlgId"].strip()
        if tlg.isdigit():
            props["tlgAuthorId"] = f"tlg{int(tlg):04d}"
        born = year_of(author["birthDateStart"])
        died = year_of(author["deathDateEnd"]) or year_of(author["deathDateStart"])
        if born is not None:
            props["dateNotBefore"] = born
        if died is not None:
            props["dateNotAfter"] = died

    return {k: v for k, v in props.items() if v != "" and v is not None}


def locus(row: dict[str, str], side: str) -> str:
    """The logical path as a dotted string, e.g. `OS.1.4` — empty when absent."""
    parts = [row[f"pos_{side}_{level}"].strip()
             for level in ("book", "chapter", "paragraph")]
    return ".".join(part for part in parts if part)


def as_int(value: str) -> int | None:
    value = (value or "").strip()
    return int(value) if value.lstrip("-").isdigit() else None


def tags_of(row: dict[str, str]) -> list[str]:
    return [t.strip() for t in (row["quotation_types"] or "").split(";") if t.strip()]


def passage_caption(row: dict[str, str], work_abbrev: str) -> str:
    """`[IO.COM] 1.4 p.86 l.25 — Jn 8:21 (bi:1608701)`.

    The source id is always part of it: captions have to be unique, and the same
    locus with the same reference does occur more than once in the export.
    """
    pieces = [f"[{work_abbrev}]" if work_abbrev else ""]
    pieces.append(locus(row, "start"))
    page, line = row["pos_start_page"].strip(), row["pos_start_line"].strip()
    subpage = row["pos_start_subpage"].strip()
    if page:
        pieces.append(f"p.{page}{subpage}")
    if line:
        pieces.append(f"l.{line}")
    head = " ".join(p for p in pieces if p)
    reference = row["reference"].strip()
    return f"{head} — {reference} (bi:{row['quotation_id']})".strip(" —")


def passage_props(
    row: dict[str, str], work: dict[str, str] | None, work_abbrev: str
) -> dict[str, Any]:
    tags = tags_of(row)
    reference_type = next(
        (value for tag, value in REFERENCE_TYPE_TAGS if tag in tags), ""
    )
    status = row["verification_status"].strip()

    props: dict[str, Any] = {
        "caption": passage_caption(row, work_abbrev),
        "reference": row["reference"].strip(),
        "referenceSystem": row["bible"].strip(),
        "referenceType": reference_type,
        # Absence of an uncertainty marker is not a claim of certainty, so
        # `certain` is never asserted here.
        "certainty": "uncertain" if UNCERTAIN_TAGS & set(tags) else "",
        "verificationStatus": status if status in VERIFICATION_STATUSES else "",
        "sourceTags": "; ".join(tags),
        "edition": row["edition"].strip(),
        "editionName": row["edition_name"].strip(),
        "locusStart": locus(row, "start"),
        "locusEnd": locus(row, "end"),
        "subpageStart": row["pos_start_subpage"].strip(),
        "subpageEnd": row["pos_end_subpage"].strip(),
        "citation": row["position"].strip(),
        "attributedTo": row["quoted_author"].strip(),
        "note": row["description"].strip(),
        "textOriginal": row["content"].strip(),
        "source": SOURCE,
        "sourceId": row["quotation_id"],
        "sourceKey": f"{SOURCE}:{row['quotation_id']}",
    }

    for name, column in (
        ("pageStart", "pos_start_page"),
        ("pageEnd", "pos_end_page"),
        ("lineStart", "pos_start_line"),
        ("lineEnd", "pos_end_line"),
    ):
        value = as_int(row[column])
        if value is not None:
            props[name] = value

    # The language of the quoted text is the work's, when the work has exactly one.
    if props["textOriginal"] and work and ";" not in work["transmissionLanguages"]:
        props["textLanguage"] = work["transmissionLanguages"].strip()

    return {k: v for k, v in props.items() if v != "" and v is not None}


# --- resolving the biblical target -------------------------------------------


def target_caption(row: dict[str, str]) -> tuple[str, str] | None:
    """`(kind, caption)` of the verse or verseGroup this passage refers to.

    Built from the structured `start_*`/`end_*` columns, not from `reference`:
    some references carry a stray space (`Jn 14: 23`) and would not match a
    caption. The shapes follow the verseGroup conventions of the graph tools.
    """
    book = row["start_book"].strip()
    start_chapter, start_verse = row["start_chapter"].strip(), row["start_verse"].strip()
    end_chapter, end_verse = row["end_chapter"].strip(), row["end_verse"].strip()
    kind = row["sequence_type"].strip()

    if not book:
        return None

    if kind == "verse" and start_chapter and start_verse:
        return "verse", f"{book} {start_chapter}:{start_verse}"

    if kind == "consecutive_verses" and start_chapter and start_verse and end_verse:
        if start_chapter == end_chapter:
            return "verseGroup", f"{book} {start_chapter}:{start_verse}-{end_verse}"
        return "verseGroup", f"{book} {start_chapter}:{start_verse}-{end_chapter}:{end_verse}"

    if kind == "chapter" and start_chapter:
        if start_chapter == end_chapter or not end_chapter:
            return "verseGroup", f"{book} {start_chapter}"
        return "verseGroup", f"{book} {start_chapter}-{end_chapter}"

    if kind == "book":
        return "verseGroup", book

    return None


def verse_sort_key(caption: str) -> tuple[int, int]:
    _, _, locus_part = caption.partition(" ")
    chapter, _, verse = locus_part.partition(":")
    return int(chapter), int(verse)


def group_members(caption: str, verses: list[str]) -> list[str]:
    """Verse captions covered by a verseGroup caption.

    `verses` must be the book's captions in canonical order. Every group gets its
    members, the whole-book one included: without `verseGroup -contains-> verse`
    there is no way back from a verse to the passages that quote it through a
    group, and a missing edge is invisible later while a present one can still be
    filtered out in a query.
    """
    book, _, locus_part = caption.partition(" ")
    in_book = [v for v in verses if v.startswith(f"{book} ")]
    if not locus_part:
        return in_book  # the whole book, e.g. `Jn`

    def bounds(part: str, default_verse: str | None) -> tuple[int, int] | None:
        chapter, _, verse = part.partition(":")
        if not chapter.isdigit():
            return None
        if verse.isdigit():
            return int(chapter), int(verse)
        if default_verse is None:
            return None
        return int(chapter), int(default_verse)

    if "-" in locus_part:
        left, _, right = locus_part.partition("-")
        start = bounds(left, "0")
        if ":" not in right:
            # `Jn 1-4` (whole chapters) or `Jn 1:3-4` (verses within the chapter)
            if ":" in left:
                chapter = left.partition(":")[0]
                right = f"{chapter}:{right}"
            else:
                right = f"{right}:9999"
        end = bounds(right, "9999")
        if not start or not end:
            return []
    else:
        start = bounds(locus_part, "0")
        end = bounds(locus_part, "9999") if ":" not in locus_part else start
        if not start or not end:
            return []

    return [v for v in in_book if start <= verse_sort_key(v) <= end]


# --- graph access ------------------------------------------------------------


def load_keyed_ids(g: GraphTraversalSource, type: str, key: str) -> dict[str, int]:
    """`{key property: internal id}` for every vertex of a type that carries it."""
    rows = (
        g.V().has("type", type).has(key)
        .project("k", "id").by(key).by(T.id)
        .toList()
    )
    return {row["k"]: int(row["id"]) for row in rows}


def load_verse_ids(g: GraphTraversalSource, books: Iterable[str]) -> dict[str, int]:
    rows = (
        g.V().has("type", "verse").has("bookShort", P.within(list(books)))
        .project("k", "id")
        .by(__.coalesce(__.values("caption"), __.constant("")))
        .by(T.id)
        .toList()
    )
    return {row["k"]: int(row["id"]) for row in rows}


def chunks(items: list[Any], size: int) -> Iterator[list[Any]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def create_vertices(
    g: GraphTraversalSource, label: str, rows: list[dict[str, Any]]
) -> None:
    """Create vertices of one label in batches, properties already validated."""
    for batch in chunks(rows, VERTEX_BATCH_SIZE):
        t = g
        for props in batch:
            t = t.add_v(label).property("type", label)
            for key, value in props.items():
                t = t.property(key, value)
        t.iterate()


def create_passages_with_edges(
    g: GraphTraversalSource, batch: list[dict[str, Any]]
) -> None:
    """Create passages together with their edges, one traversal per batch.

    Vertex and edges land in the same transaction, so an interrupted run never
    leaves a passage that is not attached to its work.
    """
    t = g
    for i, item in enumerate(batch):
        passage = f"p{i}"
        t = t.add_v("receptionPassage").property("type", "receptionPassage")
        for key, value in item["props"].items():
            t = t.property(key, value)
        t = t.as_(passage)
        t = t.V(item["work_id"]).as_(f"w{i}").add_e("contains").from_(f"w{i}").to(passage)
        if item["target_id"] is not None:
            t = (
                t.V(item["target_id"]).as_(f"t{i}")
                .add_e("refersTo").from_(passage).to(f"t{i}")
            )
    t.iterate()


def load_group_members(g: GraphTraversalSource) -> dict[str, set[str]]:
    """`{verseGroup caption: verse captions it already contains}`.

    `fold()` always yields a list, so a group with no members keeps its row —
    unlike a bare `values(...)`, which would drop it from the projection.
    """
    rows = (
        g.V().has("type", "verseGroup")
        .project("caption", "members")
        .by(__.coalesce(__.values("caption"), __.constant("")))
        .by(__.out("contains").has("type", "verse").values("caption").fold())
        .toList()
    )
    return {row["caption"]: set(row["members"]) for row in rows}


def missing_member_pairs(
    captions: Iterable[str],
    group_ids: dict[str, int],
    existing: dict[str, set[str]],
    verse_ids: dict[str, int],
    verses_in_order: list[str],
) -> list[tuple[int, int]]:
    """`(group id, verse id)` edges that are needed and not there yet.

    Covers the groups that already existed as well as the new ones: a group whose
    members were never linked is the same dead end for a `verse -> passage`
    traversal, whoever created it.
    """
    pairs: list[tuple[int, int]] = []
    for caption in sorted(set(captions)):
        group_id = group_ids.get(caption)
        if group_id is None:
            continue
        linked = existing.get(caption, set())
        for member in group_members(caption, verses_in_order):
            if member not in linked and member in verse_ids:
                pairs.append((group_id, verse_ids[member]))
    return pairs


def link_group_members(
    g: GraphTraversalSource, pairs: list[tuple[int, int]]
) -> int:
    """Create `verseGroup -contains-> verse` edges in batches."""
    created = 0
    for batch in chunks(pairs, PASSAGE_BATCH_SIZE):
        t = g
        for i, (group_id, verse_id) in enumerate(batch):
            t = t.V(group_id).as_(f"g{i}")
            t = t.V(verse_id).as_(f"v{i}").add_e("contains").from_(f"g{i}").to(f"v{i}")
        t.iterate()
        created += len(batch)
    return created


# --- the import --------------------------------------------------------------


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source-dir", default=DEFAULT_SOURCE_DIR,
                        help=f"directory with the three CSV files (default: {DEFAULT_SOURCE_DIR})")
    parser.add_argument("--work-id", action="append", dest="work_ids",
                        help="restrict to this biblIndex work id (repeatable)")
    parser.add_argument("--limit", type=int, help="import at most this many quotations")
    parser.add_argument("--apply", action="store_true", help="write (default: dry run)")
    parser.add_argument("--log", help="write a JSON report to this file")
    args = parser.parse_args()

    works_by_id = {w["id"]: w for w in read_csv(f"{args.source_dir}/biblindex-works.csv")}
    authors = {a["id"]: a for a in read_csv(f"{args.source_dir}/biblindex-authors.csv")}
    quotations_path = f"{args.source_dir}/biblindex-quotations.csv"

    wanted_works = set(args.work_ids or [])
    rows: list[dict[str, str]] = []
    for row in iter_quotations(quotations_path):
        if wanted_works and row["work_id"] not in wanted_works:
            continue
        rows.append(row)
        if args.limit and len(rows) >= args.limit:
            break

    print(f"quotations selected : {len(rows)}")
    if not rows:
        print("Nothing to import.")
        return 0

    used_work_ids = sorted({row["work_id"] for row in rows})
    unknown_works = [w for w in used_work_ids if w not in works_by_id]
    print(f"works referenced    : {len(used_work_ids)}"
          + (f" ({len(unknown_works)} missing from works.csv)" if unknown_works else ""))

    all_captions = Counter(
        f"{works_by_id[w]['author_names']}. {works_by_id[w]['latinName'] or works_by_id[w]['name']}".strip()
        for w in used_work_ids if w in works_by_id
    )
    collisions = {caption for caption, n in all_captions.items() if n > 1}

    g = await get_g_for_tests()

    existing_work_ids = load_keyed_ids(g, "receptionWork", "sourceKey")
    existing_passages = set(load_keyed_ids(g, "receptionPassage", "sourceKey"))
    group_ids = load_keyed_ids(g, "verseGroup", "caption")
    books = sorted({row["start_book"].strip() for row in rows if row["start_book"].strip()})
    verse_ids = load_verse_ids(g, books)
    verses_in_order = sorted(verse_ids, key=verse_sort_key)

    print(f"books referenced    : {', '.join(books)}")
    print(f"verses available    : {len(verse_ids)}")
    print(f"verseGroups present : {len(group_ids)}")
    print(f"works present       : {len(existing_work_ids)}")
    print(f"passages present    : {len(existing_passages)}\n")

    # --- plan ---------------------------------------------------------------
    works_to_create: list[dict[str, Any]] = []
    work_caption_by_id: dict[str, str] = {}
    for work_id in used_work_ids:
        work = works_by_id.get(work_id)
        if not work:
            continue
        caption = work_caption(work, collisions)
        work_caption_by_id[work_id] = caption
        if f"{SOURCE}:{work_id}" not in existing_work_ids:
            works_to_create.append(
                validate_and_fix_properties(
                    "receptionWork", work_props(work, authors, caption)
                )
            )

    planned: list[dict[str, Any]] = []
    groups_needed: set[str] = set()
    groups_used: set[str] = set()
    skipped_existing = 0
    unresolved: Counter[str] = Counter()
    unresolved_examples: dict[str, str] = {}
    unparsed_pages = 0

    for row in rows:
        source_key = f"{SOURCE}:{row['quotation_id']}"
        if source_key in existing_passages:
            skipped_existing += 1
            continue

        work = works_by_id.get(row["work_id"])
        abbrev = (row["work_abbreviation"].strip()
                  or (work["abbreviation"].strip() if work else "")
                  or (work["latinName"][:24] if work else ""))
        props = validate_and_fix_properties(
            "receptionPassage", passage_props(row, work, abbrev)
        )
        if row["pos_start_page"].strip() and "pageStart" not in props:
            unparsed_pages += 1

        target = target_caption(row)
        if target is None:
            unresolved["malformed reference"] += 1
            unresolved_examples.setdefault("malformed reference", row["reference"])
        elif target[0] == "verse" and target[1] not in verse_ids:
            unresolved["verse not in graph"] += 1
            unresolved_examples.setdefault("verse not in graph", target[1])
            target = None
        elif target[0] == "verseGroup":
            groups_used.add(target[1])
            if target[1] not in group_ids:
                groups_needed.add(target[1])

        planned.append({"row": row, "props": props, "target": target})

    # Member edges are counted for the groups this import links to, new and old
    # alike: an existing group that was never linked to its verses is the same
    # dead end for a `verse -> receptionPassage` traversal.
    existing_members = load_group_members(g)
    member_edges_needed = sum(
        1
        for caption in groups_used
        for member in group_members(caption, verses_in_order)
        if member not in existing_members.get(caption, set()) and member in verse_ids
    )
    groups_to_relink = sum(
        1
        for caption in groups_used - groups_needed
        if any(
            member not in existing_members.get(caption, set()) and member in verse_ids
            for member in group_members(caption, verses_in_order)
        )
    )

    print(f"works to create     : {len(works_to_create)}")
    print(f"verseGroups to create: {len(groups_needed)}")
    print(f"passages to create  : {len(planned)}")
    print(f"passages skipped    : {skipped_existing} (already in the graph)")
    print(f"edges to create     : {len(planned)} contains, "
          f"{sum(1 for p in planned if p['target'])} refersTo")
    print(f"                      {member_edges_needed} verseGroup -contains-> verse "
          f"over {len(groups_used)} groups"
          + (f", {groups_to_relink} of them pre-existing and unlinked"
             if groups_to_relink else ""))
    if unparsed_pages:
        print(f"non-numeric pages   : {unparsed_pages} (kept in `citation` only)")
    for reason, count in unresolved.most_common():
        print(f"unlinked            : {count} — {reason} (e.g. {unresolved_examples[reason]!r})")

    if not args.apply:
        print("\nDry run. Re-run with --apply to write.")
        return 0

    # --- apply --------------------------------------------------------------
    report: dict[str, Any] = {
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "quotations_selected": len(rows),
        "skipped_existing": skipped_existing,
        "unlinked": dict(unresolved),
    }

    if works_to_create:
        print(f"\ncreating {len(works_to_create)} works…")
        create_vertices(g, "receptionWork", works_to_create)
        existing_work_ids = load_keyed_ids(g, "receptionWork", "sourceKey")
    report["works_created"] = len(works_to_create)

    if groups_needed:
        print(f"creating {len(groups_needed)} verseGroups…")
        create_vertices(
            g,
            "verseGroup",
            [validate_and_fix_properties("verseGroup", {"caption": caption})
             for caption in sorted(groups_needed)],
        )
        group_ids = load_keyed_ids(g, "verseGroup", "caption")
    report["verse_groups_created"] = len(groups_needed)

    pairs = missing_member_pairs(
        groups_used, group_ids, existing_members, verse_ids, verses_in_order
    )
    if pairs:
        print(f"linking {len(pairs)} verseGroup -contains-> verse edges…")
        report["group_member_edges"] = link_group_members(g, pairs)

    batch: list[dict[str, Any]] = []
    for item in planned:
        target = item["target"]
        target_id = None
        if target:
            target_id = (verse_ids if target[0] == "verse" else group_ids).get(target[1])
        batch.append(
            {
                "props": item["props"],
                "work_id": existing_work_ids[f"{SOURCE}:{item['row']['work_id']}"],
                "target_id": target_id,
            }
        )

    print(f"creating {len(batch)} passages with their edges…")
    done = 0
    try:
        for part in chunks(batch, PASSAGE_BATCH_SIZE):
            create_passages_with_edges(g, part)
            done += len(part)
            print(f"  {done}/{len(batch)}", end="\r", flush=True)
    finally:
        print()
        report["passages_created"] = done
        report["finished_at"] = datetime.now().isoformat(timespec="seconds")
        if args.log:
            with open(args.log, "w", encoding="utf-8") as fh:
                json.dump(report, fh, ensure_ascii=False, indent=2, sort_keys=True)
            print(f"report written to {args.log}")

    print(f"\nDone. works +{len(works_to_create)}, verseGroups +{len(groups_needed)}, "
          f"passages +{done}, group member edges +{report.get('group_member_edges', 0)}.")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(asyncio.run(main()))
