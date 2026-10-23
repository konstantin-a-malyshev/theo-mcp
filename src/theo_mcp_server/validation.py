from __future__ import annotations

from typing import Any

from .schema import (
    ALLOWED_EDGE_LABELS,
    ALLOWED_PROPS,
    LABELS_CANON,
    RECEPTION_PASSAGE_ENUMS,
    REQUIRED_PROPS,
)

# Properties stored as integers, per label.
INT_PROPS: dict[str, tuple[str, ...]] = {
    "verse": ("chapter", "importIndex", "verse"),
    "quotation": ("importIndex",),
    "receptionWork": ("dateNotBefore", "dateNotAfter"),
    "receptionPassage": ("pageStart", "pageEnd", "lineStart", "lineEnd"),
}

# Properties stored as booleans, per label.
BOOL_PROPS: dict[str, tuple[str, ...]] = {
    "receptionWork": ("fragmentary",),
}

_TRUE = {"true", "1", "yes"}
_FALSE = {"false", "0", "no"}


def _coerce_bool(key: str, value: Any) -> bool:
    """Parse a boolean property. Strings are explicit: bool('False') is True."""
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in _TRUE:
        return True
    if text in _FALSE:
        return False
    raise ValueError(f"Property '{key}' must be a boolean, got {value!r}")


def normalize_label(label: str) -> str:
    key = label if label in LABELS_CANON else label.lower()
    if key not in LABELS_CANON:
        raise ValueError(f"Unknown label '{label}'. Allowed: {sorted(set(LABELS_CANON.values()))}")
    return LABELS_CANON[key]


def normalize_edge_label(edge_label: str) -> str:
    if edge_label not in ALLOWED_EDGE_LABELS:
        # try case-insensitive match
        for e in ALLOWED_EDGE_LABELS:
            if e.lower() == edge_label.lower():
                return e
        raise ValueError(f"Unknown edge label '{edge_label}'. Allowed: {sorted(ALLOWED_EDGE_LABELS)}")
    return edge_label


def validate_and_fix_properties(label: str, props: dict[str, Any], require_required: bool = True) -> dict[str, Any]:
    allowed = ALLOWED_PROPS[label]
    required = REQUIRED_PROPS[label]

    unknown = set(props.keys()) - allowed
    if unknown:
        raise ValueError(f"Unknown properties for label '{label}': {sorted(unknown)}. Allowed: {sorted(allowed)}")

    if require_required:
        missing = required - set(props.keys())
        if missing:
            raise ValueError(f"Missing required properties for '{label}': {sorted(missing)}")

    out: dict[str, Any] = dict(props)

    # Coerce ints where expected
    for k in INT_PROPS.get(label, ()):
        if k in out and out[k] is not None:
            out[k] = int(out[k])

    for k in BOOL_PROPS.get(label, ()):
        if k in out and out[k] is not None:
            out[k] = _coerce_bool(k, out[k])

    if label == "receptionPassage":
        for k, allowed_values in RECEPTION_PASSAGE_ENUMS.items():
            value = out.get(k)
            if value is not None and value != "" and value not in allowed_values:
                raise ValueError(
                    f"Invalid {k}: {value!r}. Must be one of: {', '.join(sorted(allowed_values))}"
                )

    return out
