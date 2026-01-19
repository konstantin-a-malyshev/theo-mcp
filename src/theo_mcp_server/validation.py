from __future__ import annotations

from typing import Any

from .schema import ALLOWED_EDGE_LABELS, ALLOWED_PROPS, LABELS_CANON, REQUIRED_PROPS


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
    if label == "verse":
        for k in ("chapter", "importIndex", "verse"):
            if k in out and out[k] is not None:
                out[k] = int(out[k])

    return out
