from __future__ import annotations

import datetime
import json
import os
import time
from pathlib import Path
from typing import Any

from gremlin_python.process.graph_traversal import GraphTraversalSource

from .config import get_config
from .gremlin_helpers import (
    count_vertices,
    export_edges_for_types,
    export_vertices_by_type,
)
from .schema import LABELS_CANON
from .validation import normalize_edge_label, normalize_label

# Bump when the on-disk layout changes in a way a restore script must notice.
BACKUP_FORMAT = "theo-graph-backup/1"

# Vertex labels never included by default: verses are re-imported from the Bible
# source, not restored from the backup.
DEFAULT_EXCLUDED_VERTEX_LABELS = ("verse",)

# Edge labels never included by default. `next` is the verse chain — one edge per
# verse, rebuilt by the verse import. Every other edge between two excluded
# vertices (notably `verse -isParallelTo-> verse`) *is* backed up, because
# nothing else can reconstruct it.
DEFAULT_EXCLUDED_EDGE_LABELS = ("next",)

VERTICES_SUBDIR = "vertices"
EDGES_FILENAME = "edges.json"
MANIFEST_FILENAME = "manifest.json"

ALL_KNOWN_TYPES: list[str] = sorted(set(LABELS_CANON.values()))

# Reported as a warning rather than a full listing, to keep the manifest small.
MAX_REPORTED_DUPLICATE_CAPTIONS = 20


class BackupError(RuntimeError):
    """A backup run that failed, carrying enough context to act on it.

    `report` is what the MCP tool hands back to the caller: which stage broke,
    whether anything reached the disk, and what had already been done.
    """

    def __init__(self, message: str, *, report: dict[str, Any]) -> None:
        super().__init__(message)
        self.report = report


def resolve_backup_dir(directory: str | None = None) -> Path:
    """Resolve and validate the backup directory.

    The directory must already exist: it is meant to be a separate git
    repository, and silently creating a mistyped path would mean months of
    committing backups into the wrong place.
    """
    raw = directory if directory else get_config().backup_dir
    if not raw:
        raise ValueError(
            "Backup directory is not configured. Set BACKUP_DIR to an absolute "
            "path, or pass `directory` to the tool."
        )

    path = Path(raw)
    if not path.is_absolute():
        raise ValueError(f"Backup directory must be an absolute path, got: {raw}")
    if not path.exists():
        raise ValueError(
            f"Backup directory does not exist: {path}. Create it (and its git "
            f"repository) first — the backup tool never creates it for you."
        )
    if not path.is_dir():
        raise ValueError(f"Backup directory is not a directory: {path}")
    return path


def resolve_types(excluded_vertex_labels: list[str] | None = None) -> list[str]:
    """Resolve which vertex types to export, from an override or the config.

    `None` means "use the configuration"; an explicit empty list means "export
    every vertex label", verses included.
    """
    if excluded_vertex_labels is None:
        configured = get_config().backup_excluded_vertex_labels
        if not configured:
            excluded_vertex_labels = list(DEFAULT_EXCLUDED_VERTEX_LABELS)
        else:
            excluded_vertex_labels = [
                part.strip() for part in configured.split(",") if part.strip()
            ]

    excluded = {normalize_label(label) for label in excluded_vertex_labels}
    types = sorted(set(ALL_KNOWN_TYPES) - excluded)
    if not types:
        raise ValueError("Every vertex label is excluded — there is nothing to back up.")
    return types


def resolve_excluded_edge_labels(excluded: list[str] | None = None) -> list[str]:
    """Resolve which edge labels to leave out, from an override or the config.

    `None` means "use the configuration"; an explicit empty list means "export
    every edge label", including the verse chain.
    """
    if excluded is None:
        configured = get_config().backup_excluded_edge_labels
        if not configured:
            return list(DEFAULT_EXCLUDED_EDGE_LABELS)
        excluded = [part.strip() for part in configured.split(",") if part.strip()]

    return sorted({normalize_edge_label(label) for label in excluded})


# --- serialization -----------------------------------------------------------


def _sorted_property_value(value: Any) -> Any:
    """Sort multi-valued properties: JanusGraph does not guarantee their order,
    and an unstable order would show up as a phantom diff on every backup."""
    if isinstance(value, list):
        return sorted(value, key=str)
    return value


def _vertex_record(row: dict[str, Any]) -> dict[str, Any]:
    """Turn a flattened valueMap row into a backup record.

    Properties are kept verbatim so that a schema addition does not silently
    drop data from the backup.
    """
    properties = {
        key: _sorted_property_value(value)
        for key, value in row.items()
        if key not in ("internal_id", "label")
    }
    return {
        "id": int(row["internal_id"]),
        "label": row["label"],
        "properties": properties,
    }


def _edge_record(row: dict[str, Any], exported_types: set[str]) -> dict[str, Any]:
    source_type = row["source_type"]
    target_type = row["target_type"]
    return {
        "label": row["label"],
        "source": {
            "id": int(row["source_id"]),
            "type": source_type,
            "caption": row["source_caption"],
            "exported": source_type in exported_types,
        },
        "target": {
            "id": int(row["target_id"]),
            "type": target_type,
            "caption": row["target_caption"],
            "exported": target_type in exported_types,
        },
    }


def sort_vertex_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort vertices by id. Ids grow monotonically, so new vertices land at the
    end of the file and edits stay local — which is what makes the git diff
    between two backups readable."""
    return sorted(records, key=lambda r: r["id"])


def sort_edge_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort edges by source id, then target id, then edge label."""
    return sorted(
        records,
        key=lambda r: (r["source"]["id"], r["target"]["id"], r["label"]),
    )


def build_vertices_payload(type: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "format": BACKUP_FORMAT,
        "type": type,
        "count": len(records),
        "vertices": records,
    }


def build_edges_payload(records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "format": BACKUP_FORMAT,
        "count": len(records),
        "edges": records,
    }


def find_duplicate_captions(
    vertices_by_type: dict[str, list[dict[str, Any]]]
) -> dict[str, int]:
    """Captions occurring more than once across the exported vertices.

    Ambiguous captions break every caption-based tool in the server, so the
    backup doubles as a health check for them.
    """
    counts: dict[str, int] = {}
    for records in vertices_by_type.values():
        for record in records:
            caption = record["properties"].get("caption")
            if isinstance(caption, str):
                counts[caption] = counts.get(caption, 0) + 1
    return {caption: n for caption, n in sorted(counts.items()) if n > 1}


# --- reading -----------------------------------------------------------------


def collect_backup(
    g: GraphTraversalSource,
    types: list[str],
    excluded_edge_labels: list[str],
) -> dict[str, Any]:
    """Read the whole backup into memory.

    Everything is read before anything is written, so a failing traversal leaves
    the backup directory untouched instead of mixing a half-new export into the
    previous one.
    """
    read_types: list[str] = []
    vertices_by_type: dict[str, list[dict[str, Any]]] = {}

    for type in types:
        try:
            rows = export_vertices_by_type(g, type)
        except Exception as exc:
            raise BackupError(
                f"Gremlin read failed for vertices of type '{type}': {exc}",
                report={
                    "stage": f"read_vertices:{type}",
                    "completed": {"read_types": read_types, "written_files": []},
                },
            ) from exc
        vertices_by_type[type] = sort_vertex_records([_vertex_record(r) for r in rows])
        read_types.append(type)

    exported_types = set(types)
    try:
        edge_rows = export_edges_for_types(g, types, excluded_edge_labels)
    except Exception as exc:
        raise BackupError(
            f"Gremlin read failed for edges: {exc}",
            report={
                "stage": "read_edges",
                "completed": {"read_types": read_types, "written_files": []},
            },
        ) from exc
    edges = sort_edge_records([_edge_record(r, exported_types) for r in edge_rows])

    try:
        total_vertices_in_graph = count_vertices(g)
        known_vertices_in_graph = count_vertices(g, ALL_KNOWN_TYPES)
    except Exception as exc:
        raise BackupError(
            f"Gremlin read failed while counting vertices: {exc}",
            report={
                "stage": "read_counts",
                "completed": {"read_types": read_types, "written_files": []},
            },
        ) from exc

    return {
        "vertices_by_type": vertices_by_type,
        "edges": edges,
        "untyped_or_unknown_vertices": total_vertices_in_graph - known_vertices_in_graph,
        "duplicate_captions": find_duplicate_captions(vertices_by_type),
    }


# --- statistics --------------------------------------------------------------


def build_statistics(
    collected: dict[str, Any],
    types: list[str],
    excluded_edge_labels: list[str],
) -> dict[str, Any]:
    vertices_by_type = collected["vertices_by_type"]
    edges = collected["edges"]

    by_label: dict[str, int] = {}
    by_signature: dict[str, int] = {}
    external_endpoints: dict[str, int] = {}

    for edge in edges:
        label = edge["label"]
        source, target = edge["source"], edge["target"]
        by_label[label] = by_label.get(label, 0) + 1

        signature = f"{source['type']} -{label}-> {target['type']}"
        by_signature[signature] = by_signature.get(signature, 0) + 1

        for endpoint in (source, target):
            if not endpoint["exported"]:
                endpoint_type = endpoint["type"]
                external_endpoints[endpoint_type] = (
                    external_endpoints.get(endpoint_type, 0) + 1
                )

    vertex_counts = {type: len(records) for type, records in vertices_by_type.items()}

    return {
        "vertices": {
            "total": sum(vertex_counts.values()),
            "by_type": dict(sorted(vertex_counts.items())),
            "skipped_types": sorted(set(ALL_KNOWN_TYPES) - set(types)),
        },
        "edges": {
            "total": len(edges),
            "excluded_labels": list(excluded_edge_labels),
            "by_label": dict(sorted(by_label.items())),
            "by_signature": dict(sorted(by_signature.items())),
            "external_endpoints": dict(sorted(external_endpoints.items())),
        },
    }


def build_warnings(collected: dict[str, Any]) -> list[str]:
    warnings: list[str] = []

    untyped = collected["untyped_or_unknown_vertices"]
    if untyped:
        warnings.append(
            f"{untyped} vertices carry no 'type' property or an unknown type — "
            f"they are in the graph but not in this backup."
        )

    duplicates = collected["duplicate_captions"]
    if duplicates:
        shown = list(duplicates.items())[:MAX_REPORTED_DUPLICATE_CAPTIONS]
        listed = ", ".join(f"'{caption}' x{n}" for caption, n in shown)
        suffix = "" if len(shown) == len(duplicates) else ", ..."
        warnings.append(f"duplicate captions ({len(duplicates)}): {listed}{suffix}")

    return warnings


# --- writing -----------------------------------------------------------------


def _write_json(path: Path, payload: dict[str, Any]) -> int:
    """Write `payload` atomically and byte-deterministically.

    Written as bytes on purpose: text mode on Windows would translate the
    newlines to CRLF and turn every backup into a whole-file diff.
    """
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    data = text.encode("utf-8")

    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_bytes(data)
    os.replace(tmp_path, path)
    return len(data)


def _remove_stale_files(vertices_dir: Path, types: list[str]) -> list[str]:
    """Drop vertex files for types no longer exported, plus leftover temp files.

    Only files matching the layout this module owns are touched — the backup
    directory is a git repository, so it is never cleared wholesale.
    """
    removed: list[str] = []
    keep = {f"{type}.json" for type in types}

    for entry in sorted(vertices_dir.iterdir()):
        if not entry.is_file():
            continue
        is_stale_vertex_file = entry.suffix == ".json" and entry.name not in keep
        is_leftover_tmp = entry.name.endswith(".json.tmp")
        if is_stale_vertex_file or is_leftover_tmp:
            entry.unlink()
            removed.append(f"{VERTICES_SUBDIR}/{entry.name}")

    return removed


def write_backup(
    backup_dir: Path,
    collected: dict[str, Any],
    types: list[str],
    statistics: dict[str, Any],
    exported_at: str,
) -> dict[str, Any]:
    """Overwrite the backup files in place. Returns per-file info."""
    vertices_dir = backup_dir / VERTICES_SUBDIR
    vertices_dir.mkdir(exist_ok=True)

    files: list[dict[str, Any]] = []
    written_files: list[str] = []
    pending_files = [f"{VERTICES_SUBDIR}/{type}.json" for type in types]
    pending_files += [EDGES_FILENAME, MANIFEST_FILENAME]

    def _write(relative_path: str, payload: dict[str, Any], records: int) -> None:
        try:
            size = _write_json(backup_dir / relative_path, payload)
        except Exception as exc:
            raise BackupError(
                f"Failed to write {relative_path}: {exc}",
                report={
                    "stage": f"write:{relative_path}",
                    "completed": {
                        "read_types": types,
                        "written_files": written_files,
                        "pending_files": pending_files,
                    },
                },
            ) from exc
        files.append({"path": relative_path, "records": records, "bytes": size})
        written_files.append(relative_path)
        pending_files.remove(relative_path)

    for type in types:
        records = collected["vertices_by_type"][type]
        _write(
            f"{VERTICES_SUBDIR}/{type}.json",
            build_vertices_payload(type, records),
            len(records),
        )

    edges = collected["edges"]
    _write(EDGES_FILENAME, build_edges_payload(edges), len(edges))

    manifest = {
        "format": BACKUP_FORMAT,
        "exported_at": exported_at,
        "types": types,
        "vertices": statistics["vertices"],
        "edges": statistics["edges"],
        "untyped_or_unknown_vertices": collected["untyped_or_unknown_vertices"],
        "duplicate_captions": collected["duplicate_captions"],
    }
    _write(MANIFEST_FILENAME, manifest, len(types))

    removed = _remove_stale_files(vertices_dir, types)

    return {"files": files, "removed_stale_files": removed}


# --- orchestration -----------------------------------------------------------


def create_backup(
    g: GraphTraversalSource,
    directory: str | None = None,
    excluded_vertex_labels: list[str] | None = None,
    excluded_edge_labels: list[str] | None = None,
) -> dict[str, Any]:
    """Export the graph into the backup directory, overwriting the previous run."""
    started = time.perf_counter()
    backup_dir = resolve_backup_dir(directory)
    types = resolve_types(excluded_vertex_labels)
    excluded = resolve_excluded_edge_labels(excluded_edge_labels)

    try:
        collected = collect_backup(g, types, excluded)
        statistics = build_statistics(collected, types, excluded)
        exported_at = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
        written = write_backup(backup_dir, collected, types, statistics, exported_at)
    except BackupError as exc:
        exc.report.setdefault("backup_dir", str(backup_dir))
        stage = exc.report.get("stage", "")
        was_written = stage.startswith("write:")
        exc.report.setdefault("written", was_written)
        exc.report.setdefault(
            "hint",
            "The backup directory is in a mixed state — restore it with "
            "`git checkout -- .` in the backup repository."
            if was_written
            else "The backup directory was left untouched.",
        )
        raise

    return {
        "backup_dir": str(backup_dir),
        "exported_at": exported_at,
        "duration_seconds": round(time.perf_counter() - started, 3),
        "vertices": statistics["vertices"],
        "edges": statistics["edges"],
        "files": written["files"],
        "removed_stale_files": written["removed_stale_files"],
        "warnings": build_warnings(collected),
    }
