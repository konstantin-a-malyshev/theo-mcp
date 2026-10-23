# Reception types: `receptionWork` and `receptionPassage`

Two vertex types for the pre-critical reception of Scripture: a work that receives
Scripture (patristic, rabbinic, medieval — any author read as a witness of
reception rather than as modern scholarship) and a passage of such a work that
quotes Scripture or alludes to it.

```
receptionWork -contains-> receptionPassage -refersTo-> verse | verseGroup
receptionWork -writtenBy-> person
```

No new edge labels: `contains`, `refersTo` and `writtenBy` already exist.

The three sibling types are `scholarlyWork` (modern academic study of the Bible,
holding `quotation` vertices), `receptionWork` (this document) and the planned
`biblicalBook`.

## The point of the field set

The task these fields have to solve is: given a passage, find it quickly in the
normalized corpus (`NORMALIZED_CORPUS_DIR`, format in
`corpus-normalization/docs/format.md`). That is harder than it looks, and the
field set is shaped by four facts about the first source, biblIndex:

1. biblIndex knows TLG only at the **author** level (`tlgId`, filled for 102 of
   437 authors, 70 of which exist in the corpus). There is no TLG work number, so
   the work-to-corpus link has to be built separately, by hand or semi-automatically.
2. Its locus is tied to a **printed edition**, not to the logical structure:
   page and line are filled for 99% of rows, while book/chapter/paragraph are
   filled for 38%/31%/25%, and a third of the rows carry nothing but page+line.
3. The editions often differ from the corpus ones (biblIndex cites GCS4 for
   Origen's commentary on John, the corpus is set from Blanc's SC 120/157/222),
   so page and line numbers frequently do not transfer at all. 874 distinct
   editions appear in the export.
4. There is no text: `content` is filled in 22 rows out of 72 466.

Hence two rules:

- **`corpusPath` is the proof of resolution.** It holds the path of the work's
  file from the corpus root, e.g.
  `tlg2042_ORIGENES/tlg2042.005_Commentarii_in_evangelium_Joannis_(lib._1,_2,_4,_5,_6,_10,_13)/tlg2042.005_Commentarii_in_evangelium_Joannis_(lib._1,_2,_4,_5,_6,_10,_13).xml`.
  It cannot be derived from the URN — the title segment comes from the TLG canon
  through filename sanitisation — so it is stored, with forward slashes (a
  backslash is an escape character in the backup JSON, in Gremlin strings and in
  regexes). Empty `corpusPath` means the work is not matched yet; that emptiness
  is the status, no extra flag needed.
- **The locus as printed stays apart from the resolved pointer.** `edition` +
  `locus*`/`page*`/`subpage*`/`line*` is what the source said; `ctsUrn` +
  `ctsUrnStatus` is where it actually lands in the corpus. Merging them would
  make unresolved passages look resolved.

## `receptionWork`

| property | type | from biblIndex | notes |
|---|---|---|---|
| `caption` | str, required | — | identity in the graph, e.g. `Origen. Commentarii in Iohannem` |
| `title` | str | `name` | title as given |
| `titleLatin` | str | `latinName` (100%) | the scholarly standard for identifying a work |
| `abbreviation` | str | `abbreviation` (54%) | sigla, e.g. `IO.COM`; appears in `citation` |
| `language` | str | `transmissionLanguages` | `grc`, `la`, `syc`, `cop`; several separated by `"; "` |
| `ctsUrn` | str | — | work level, e.g. `urn:cts:greekLit:tlg2042.tlg005`. **Read from the file's `<idno type="CTS-URN">`, never guessed** |
| `tlgAuthorId` | str | `tlgId` of the author | padded with the prefix: `tlg2042`, `tlg0645` — the form that prefixes both the corpus folder and the URN. **Temporary**: denormalised from the author so bulk matching need not walk edges; the source of truth moves to `person` once it carries fields |
| `corpusPath` | str | — | see above |
| `clavis` | str | `clavisNumbers` (92%) | e.g. `CPG5208`, an external authority id |
| `dateNotBefore` | int | from the author | reception cannot be ordered in time without it |
| `dateNotAfter` | int | from the author | |
| `fragmentary` | bool | `fragment` | survives only in fragments, which limits what a locus can mean |
| `source` | str | `biblindex` | |
| `sourceId` | str | `id` | |
| `sourceUrl` | str | `iri` | |
| `note` | str | `description` (14%) | |

Deliberately absent: `quotations_count` and the other counters (derivable from the
graph, and stale the moment they are written), `native` (a boolean of unclear
meaning, not a language), `keywords` (always `John` in this export), and `edition`
— a work has several editions in biblIndex while a passage has one, so edition
belongs to the passage.

Author metadata — `pinakesUrl`, `wikidataUrl`, `bnfUrl`, `cerlUrl`, life dates,
`saint`/`blessed`, the biographical note — belongs to `person`, which currently
allows `caption` only. Extending it is a separate task; until then
`dateNotBefore`/`dateNotAfter` stay empty.

## `receptionPassage`

**Identity**

| property | type | from biblIndex | notes |
|---|---|---|---|
| `caption` | str, required | composed | e.g. `[IO.COM] 1.4 p.86 l.25 — Jn 8:21 (bi:1608701)` |
| `sourceKey` | str | `biblindex:{quotation_id}` | identity for re-import and deduplication |

The source id belongs in the caption as well: captions must be unique
(`create_vertex` refuses a duplicate), and the same locus with the same reference
does occur more than once (`reference which occurs several times`, 1158 rows).
`sourceKey` has a composite JanusGraph index, `bySourceKey` (created October 2026,
ENABLED) — without it every re-import row would scan the graph. See
`scripts/create_index.py` and `docs/janus-graph.md`.

**Locus as the source prints it**

| property | type | from biblIndex |
|---|---|---|
| `edition` / `editionName` | str | `edition` / `edition_name`, e.g. `SC130` |
| `locusStart` / `locusEnd` | str | logical path, dotted: `OS.1.4`, `1.1`, or empty |
| `pageStart` / `pageEnd` | int | `pos_*_page` (99%) |
| `subpageStart` / `subpageEnd` | str | `pos_*_subpage` — column, e.g. `A` of PL col. 312A (19%) |
| `lineStart` / `lineEnd` | int | `pos_*_line` (99% / 86%) |
| `citation` | str | `position`, verbatim: `[SERM.] OS.1.4 (p.86, l.25) - OS.1.4 (p.86, l.26)` |

The twelve `pos_start_*`/`pos_end_*` columns are folded into two dotted `locus*`
properties: more than a dozen different level combinations occur in the data, so
one column per level would leave two thirds of every row empty. A dotted path is
also how classicists cite, and it supports prefix search
(`TextP.startingWith("3.")` finds book 3). The cost is that chapters cannot be
sorted numerically.

**Resolved pointer into the corpus**

| property | type | notes |
|---|---|---|
| `ctsUrn` | str | full URN with passage and range, e.g. `urn:cts:greekLit:tlg2042.tlg005:1.4.25-1.4.26` |
| `ctsUrnStatus` | str | `exact`, `approximate`, `unresolved` |

`approximate` means it resolved to a chapter or section but not to a line — which
will be the normal case. Strict CTS has a version slot between work and passage
(`tlg0645.tlg001.goodspeed-grc1:2.1`); the corpus does not use it because it holds
one edition per work. When a second edition of the same work appears, page and
line numbers will mean different things under the same URN, and the slot will have
to be filled.

**The biblical reference as the source states it**

| property | type | from biblIndex | notes |
|---|---|---|---|
| `reference` | str | `reference` | `Jn 8:21` — the same format as a `verse` caption, and all abbreviations in the export are inside the 77 the server knows |
| `referenceSystem` | str | `bible` | `JB` (54 507), `NTG` (11 892), `Vg` (6053), `NTS`, `RST`. Formal for John, decisive for Psalms and Daniel, where LXX/Vg and MT/RST numbering diverge |
| `referenceType` | str | mapped | `quotation`, `allusion`, `lemma`, `paraphrase` |
| `certainty` | str | mapped | `certain`, `uncertain` |
| `verificationStatus` | str | `verification_status` | `checked` (40 345), `unchecked` (32 030), `error` (60) |
| `sourceTags` | str | `quotation_types`, verbatim | the source's own vocabulary, separated by `"; "` |

The structured `start_*`/`end_*` columns are not stored: the range is expressed by
the `refersTo` edge to a `verse` or a `verseGroup` (10% of rows are ranges, 7450
of them; none crosses a book boundary).

`quotation_types` mixes at least four orthogonal axes — kind of reference,
certainty, biblical text version (`Vetus Latina`, `Theodotion`, `Aquila`) and
synoptic parallels — and 60% of its mass is undocumented typographic sigla: `<`
(14 061), `]` (5021), `>` (4030), `/` (2971), `(`, `)`, `[`. So the normalised
properties are filled from the labels whose meaning is known, and `sourceTags`
keeps everything verbatim. Mapping the sigla by guesswork would put fiction into
the data; they can be re-derived from `sourceTags` once the legend is known.

**Text**

| property | type | notes |
|---|---|---|
| `textOriginal` | str | not in biblIndex, to be added |
| `textLanguage` | str | `grc`, `la`; defaults to the work's language |
| `textNormalized` | str | accent-folded, hyphenation removed — the key for finding the passage in the corpus when the locus does not resolve, which is most of the time |
| `textEn` / `textRu` / `textDe` | str | translations |

Flat translation fields are enough for three or four languages. If more arrive, or
if the translator and the edition of the translation have to be recorded, a
separate `translation` vertex becomes the honest model.

**Provenance and notes**

| property | type | from biblIndex |
|---|---|---|
| `attributedTo` | str | `quoted_author` (515 rows) — the earlier author this passage is reported to quote; the chains of transmission |
| `source` / `sourceId` | str | `biblindex` / `quotation_id` |
| `note` | str | `description` (4%) |

## Before a bulk import

- The export is **John only**: all 72 466 rows have `start_book = Jn`, across 2401
  works and 437 authors.
- 72 466 passages is twice everything non-verse now in the graph, which is why
  `receptionPassage` is excluded from the backup by default
  (`DEFAULT_EXCLUDED_VERTEX_LABELS`), like `verse`: both are re-imported from
  their own source, and a file of tens of megabytes rewritten in full on every
  run would make the diff useless. Note that the *edges* of excluded vertices are
  are excluded by *shape* rather than by label, through
  `DEFAULT_EXCLUDED_EDGE_TRIPLES_BY_TYPE`: `receptionWork -contains->
  receptionPassage` and `receptionPassage -refersTo-> verse|verseGroup`, around
  145 000 records for a full import, which the import itself re-creates.
  The filter runs inside the traversal, so those rows never cross the wire.

  It is a shape and not a label on purpose. `contains` and `refersTo` also carry
  the notion tree and the hand-made links from notions and quotations to verses —
  1711 such edges today — and "any edge touching an excluded vertex type" would
  silently drop all of them, including `verse -isParallelTo-> verse`, which
  nothing but the backup can reconstruct. A shape is dropped only while the
  vertex type it belongs to is excluded: export the passages and their edges come
  back with them.
- Build the work-to-corpus table first: without `corpusPath` and `ctsUrn` the
  passages cannot be located, however many fields they carry. Match `titleLatin`
  against the folder names under the author's `tlgAuthorId`, then review by hand.
  Importing only the Greek works that exist in the corpus keeps this tractable —
  Latin works are not in the corpus at all, which holds TLG alone.
