from __future__ import annotations

# Canonical label mapping (case-insensitive inputs)
LABELS_CANON: dict[str, str] = {
    "notion": "notion",
    "person": "person",
    "book": "book",
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
    "isChallengedBy",
    "isParallelTo",
    "next",
    "writtenBy",
}

ALLOWED_PROPS: dict[str, set[str]] = {
    "notion": {"caption", "description", "quotation"},
    "person": {"caption"},
    "book": {"caption"},
    "verse": {"chapter", "RST", "bookShort", "book", "caption", "importIndex", "verse"},
    "notionGroup": {"caption"},
    "verseGroup": {"caption"},
}

REQUIRED_PROPS: dict[str, set[str]] = {
    "notion": {"caption"},
    "person": {"caption"},
    "book": {"caption"},
    "verse": {"caption"},
    "notionGroup": {"caption"},
    "verseGroup": {"caption"},
}
