from __future__ import annotations

# Canonical label mapping (case-insensitive inputs)
LABELS_CANON: dict[str, str] = {
    "notion": "notion",
    "person": "person",
    "book": "Book",
    "Book": "Book",
    "verse": "verse",
    "notiongroup": "notionGroup",
    "notionGroup": "notionGroup",
    "versegroup": "verseGroup",
    "verseGroup": "verseGroup",
}

# Edge labels allowed by your schema (support both spellings where schema differed)
ALLOWED_EDGE_LABELS: set[str] = {
    "refersTo",
    "contains",
    "isSupportedBy",
    "supportedBy",
    "isChallengedBy",
    "challengedBy",
    "isParallelTo",
    "next",
    "writtenBy",
}

ALLOWED_PROPS: dict[str, set[str]] = {
    "notion": {"id", "caption", "description", "quotation"},
    "person": {"id", "caption"},
    "Book": {"id", "caption"},
    "verse": {"id", "chapter", "RST", "bookShort", "book", "caption", "importIndex", "verse"},
    "notionGroup": {"id", "caption"},
    "verseGroup": {"id", "caption"},
}

REQUIRED_PROPS: dict[str, set[str]] = {
    "notion": {"id", "caption"},
    "person": {"id", "caption"},
    "Book": {"id", "caption"},
    "verse": {"id", "caption"},
    "notionGroup": {"id", "caption"},
    "verseGroup": {"id", "caption"},
}
