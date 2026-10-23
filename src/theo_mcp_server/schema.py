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
    "scholarlyWork": {"caption"},
    "verse": {"chapter", "RST", "bookShort", "book", "caption", "importIndex", "verse"},
    "quotation": {"caption", "text", "book", "position", "status", "importIndex"},
    "notionGroup": {"caption"},
    "verseGroup": {"caption"},
}

REQUIRED_PROPS: dict[str, set[str]] = {
    "notion": {"caption"},
    "person": {"caption"},
    "scholarlyWork": {"caption"},
    "verse": {"caption"},
    "quotation": {"caption", "text", "book", "position", "importIndex"},
    "notionGroup": {"caption"},
    "verseGroup": {"caption"},
}
