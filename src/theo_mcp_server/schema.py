from __future__ import annotations

# Canonical label mapping (case-insensitive inputs)
LABELS_CANON: dict[str, str] = {
    "notion": "notion",
    "person": "person",
    "scholarlywork": "scholarlyWork",
    "scholarlyWork": "scholarlyWork",
    "verse": "verse",
    "quotation": "quotation",
    "notiongroup": "notionGroup",
    "notionGroup": "notionGroup",
    "versegroup": "verseGroup",
    "verseGroup": "verseGroup",
    "receptionwork": "receptionWork",
    "receptionWork": "receptionWork",
    "receptionpassage": "receptionPassage",
    "receptionPassage": "receptionPassage",
}

# Edge labels allowed by your schema (support both spellings where schema differed)
ALLOWED_EDGE_LABELS: set[str] = {
    "refersTo",
    "contains",
    "isSupportedBy",
    "isChallengedBy",
    "isParallelTo",
    "next",
    "writtenBy",
}

# A pre-critical work that receives Scripture (patristic, rabbinic, medieval …).
# `corpusPath` is the one field that proves the link to the normalized corpus is
# established; `ctsUrn` is read out of that file, never guessed. `tlgAuthorId` is
# **temporary** — raw material for the semi-automatic corpus matching, duplicated
# from the author; the source of truth moves to `person` once it carries fields.
RECEPTION_WORK_PROPS: set[str] = {
    "caption",
    "title",
    "titleLatin",
    "abbreviation",
    "language",
    "ctsUrn",
    "tlgAuthorId",
    "corpusPath",
    "clavis",
    "dateNotBefore",
    "dateNotAfter",
    "fragmentary",
    "source",
    "sourceId",
    "sourceUrl",
    "note",
}

# A passage of a receptionWork that quotes or alludes to Scripture.
# The locus as the source gives it (`edition` + `locus*`/`page*`/`line*`) is kept
# apart from `ctsUrn`, the resolved pointer into the normalized corpus, so that an
# unresolved passage cannot pass for a resolved one — see `ctsUrnStatus`.
RECEPTION_PASSAGE_PROPS: set[str] = {
    "caption",
    # locus as printed in the source's edition
    "edition",
    "editionName",
    "locusStart",
    "locusEnd",
    "pageStart",
    "pageEnd",
    "subpageStart",
    "subpageEnd",
    "lineStart",
    "lineEnd",
    "citation",
    # resolved pointer into the normalized corpus
    "ctsUrn",
    "ctsUrnStatus",
    # the biblical reference as the source states it
    "reference",
    "referenceSystem",
    "referenceType",
    "certainty",
    "verificationStatus",
    "sourceTags",
    # text and translations
    "textOriginal",
    "textLanguage",
    "textNormalized",
    "textEn",
    "textRu",
    "textDe",
    # provenance and notes
    "attributedTo",
    "note",
    "source",
    "sourceId",
    "sourceKey",
}

ALLOWED_PROPS: dict[str, set[str]] = {
    "notion": {"caption", "description", "quotation"},
    "person": {"caption"},
    "scholarlyWork": {"caption"},
    "verse": {"chapter", "RST", "bookShort", "book", "caption", "importIndex", "verse"},
    "quotation": {"caption", "text", "book", "position", "status", "importIndex"},
    "notionGroup": {"caption"},
    "verseGroup": {"caption"},
    "receptionWork": RECEPTION_WORK_PROPS,
    "receptionPassage": RECEPTION_PASSAGE_PROPS,
}

REQUIRED_PROPS: dict[str, set[str]] = {
    "notion": {"caption"},
    "person": {"caption"},
    "scholarlyWork": {"caption"},
    "verse": {"caption"},
    "quotation": {"caption", "text", "book", "position", "importIndex"},
    "notionGroup": {"caption"},
    "verseGroup": {"caption"},
    "receptionWork": {"caption"},
    "receptionPassage": {"caption"},
}

# Values accepted by the controlled-vocabulary properties of receptionPassage.
# `sourceTags` keeps the source's own vocabulary verbatim instead.
RECEPTION_PASSAGE_ENUMS: dict[str, set[str]] = {
    "ctsUrnStatus": {"exact", "approximate", "unresolved"},
    "referenceType": {"quotation", "allusion", "lemma", "paraphrase"},
    "certainty": {"certain", "uncertain"},
    "verificationStatus": {"checked", "unchecked", "error"},
}
