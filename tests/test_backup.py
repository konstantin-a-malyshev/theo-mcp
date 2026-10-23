import json
import os
import sys

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

_SRC = os.path.join(os.path.dirname(__file__), "..", "src")
sys.path.insert(0, _SRC)

from theo_mcp_server import backup as backup_module
from theo_mcp_server.backup import (
    BACKUP_FORMAT,
    BackupError,
    build_statistics,
    find_duplicate_captions,
    resolve_backup_dir,
    resolve_excluded_edge_labels,
    resolve_types,
    sort_edge_records,
    sort_vertex_records,
    write_backup,
    _edge_record,
    _vertex_record,
)

_env = os.environ.copy()
_env["PYTHONPATH"] = _SRC

server_params = StdioServerParameters(
    command=os.path.join(".venv", "Scripts", "python.exe"),
    args=["-m", "theo_mcp_server"],
    env=_env,
)


@pytest.fixture
async def mcp_session():
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


def _vertex(id, type, caption, **props):
    return {"internal_id": id, "label": type, "type": type, "caption": caption, **props}


def _edge(label, source_id, source_type, target_id, target_type):
    return {
        "label": label,
        "source_id": source_id,
        "source_type": source_type,
        "source_caption": f"caption-{source_id}",
        "target_id": target_id,
        "target_type": target_type,
        "target_caption": f"caption-{target_id}",
    }


def _collected(vertices_by_type, edge_rows, exported_types, untyped=0):
    vertices_by_type = {
        type: sort_vertex_records([_vertex_record(r) for r in rows])
        for type, rows in vertices_by_type.items()
    }
    return {
        "vertices_by_type": vertices_by_type,
        "edges": sort_edge_records(
            [_edge_record(r, set(exported_types)) for r in edge_rows]
        ),
        "untyped_or_unknown_vertices": untyped,
        "duplicate_captions": find_duplicate_captions(vertices_by_type),
    }


def _write(tmp_path, collected, types, excluded_edge_labels=("next",)):
    statistics = build_statistics(collected, types, list(excluded_edge_labels))
    return write_backup(
        tmp_path, collected, types, statistics, "2026-08-04T14:30:00+03:00"
    )


# --- sorting -----------------------------------------------------------------


def test_vertices_are_sorted_by_id():
    rows = [_vertex(30, "notion", "c"), _vertex(10, "notion", "a"), _vertex(20, "notion", "b")]
    records = sort_vertex_records([_vertex_record(r) for r in rows])
    assert [r["id"] for r in records] == [10, 20, 30]


def test_edges_are_sorted_by_source_then_target_then_label():
    rows = [
        _edge("refersTo", 2, "notion", 1, "verse"),
        _edge("contains", 1, "notionGroup", 5, "notion"),
        _edge("refersTo", 1, "notionGroup", 5, "notion"),
        _edge("contains", 1, "notionGroup", 3, "notion"),
    ]
    records = sort_edge_records([_edge_record(r, {"notion", "notionGroup"}) for r in rows])
    assert [(r["source"]["id"], r["target"]["id"], r["label"]) for r in records] == [
        (1, 3, "contains"),
        (1, 5, "contains"),
        (1, 5, "refersTo"),
        (2, 1, "refersTo"),
    ]


def test_multi_valued_properties_are_sorted():
    record = _vertex_record({"internal_id": 1, "label": "notion", "tags": ["b", "a", "c"]})
    assert record["properties"]["tags"] == ["a", "b", "c"]


# --- file writing ------------------------------------------------------------


def test_written_files_are_byte_identical_across_runs(tmp_path):
    collected = _collected(
        {"notion": [_vertex(2, "notion", "второй"), _vertex(1, "notion", "первый")]},
        [_edge("refersTo", 1, "notion", 99, "verse")],
        {"notion"},
    )

    _write(tmp_path, collected, ["notion"])
    first = (tmp_path / "vertices" / "notion.json").read_bytes()
    _write(tmp_path, collected, ["notion"])
    second = (tmp_path / "vertices" / "notion.json").read_bytes()

    assert first == second


def test_files_use_lf_newlines_and_readable_unicode(tmp_path):
    collected = _collected(
        {"notion": [_vertex(1, "notion", "Час Иисуса")]}, [], {"notion"}
    )
    _write(tmp_path, collected, ["notion"])

    raw = (tmp_path / "vertices" / "notion.json").read_bytes()
    assert b"\r\n" not in raw
    assert raw.endswith(b"\n")
    assert "Час Иисуса" in raw.decode("utf-8")


def test_no_temp_files_are_left_behind(tmp_path):
    collected = _collected({"notion": [_vertex(1, "notion", "a")]}, [], {"notion"})
    _write(tmp_path, collected, ["notion"])

    assert not list(tmp_path.rglob("*.tmp"))


def test_manifest_contents(tmp_path):
    collected = _collected(
        {
            "notion": [_vertex(1, "notion", "a"), _vertex(2, "notion", "b")],
            "notionGroup": [_vertex(3, "notionGroup", "g")],
        },
        [
            _edge("contains", 3, "notionGroup", 1, "notion"),
            _edge("refersTo", 1, "notion", 99, "verse"),
        ],
        {"notion", "notionGroup"},
        untyped=2,
    )
    _write(tmp_path, collected, ["notion", "notionGroup"])

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["format"] == BACKUP_FORMAT
    assert manifest["exported_at"] == "2026-08-04T14:30:00+03:00"
    assert manifest["vertices"]["by_type"] == {"notion": 2, "notionGroup": 1}
    assert manifest["vertices"]["total"] == 3
    assert "verse" in manifest["vertices"]["skipped_types"]
    assert manifest["edges"]["by_label"] == {"contains": 1, "refersTo": 1}
    assert manifest["edges"]["by_signature"]["notion -refersTo-> verse"] == 1
    assert manifest["edges"]["external_endpoints"] == {"verse": 1}
    assert manifest["untyped_or_unknown_vertices"] == 2


def test_vertex_files_carry_no_timestamp(tmp_path):
    """Only the manifest holds the export time; a timestamp in every file would
    make each backup dirty the whole tree in git."""
    collected = _collected({"notion": [_vertex(1, "notion", "a")]}, [], {"notion"})
    _write(tmp_path, collected, ["notion"])

    payload = json.loads((tmp_path / "vertices" / "notion.json").read_text(encoding="utf-8"))
    assert "exported_at" not in payload
    assert set(payload) == {"format", "type", "count", "vertices"}


# --- stale files -------------------------------------------------------------


def test_stale_vertex_files_are_removed_but_foreign_files_survive(tmp_path):
    (tmp_path / "vertices").mkdir()
    (tmp_path / "vertices" / "person.json").write_text("{}", encoding="utf-8")
    # Left over from a run that died mid-write, for a type not exported now.
    (tmp_path / "vertices" / "quotation.json.tmp").write_text("{}", encoding="utf-8")
    (tmp_path / "vertices" / "notes.md").write_text("keep me", encoding="utf-8")
    (tmp_path / "README.md").write_text("keep me", encoding="utf-8")
    (tmp_path / ".git").mkdir()

    collected = _collected({"notion": [_vertex(1, "notion", "a")]}, [], {"notion"})
    result = _write(tmp_path, collected, ["notion"])

    assert not (tmp_path / "vertices" / "person.json").exists()
    assert not (tmp_path / "vertices" / "quotation.json.tmp").exists()
    assert (tmp_path / "vertices" / "notes.md").exists()
    assert (tmp_path / "README.md").exists()
    assert (tmp_path / ".git").is_dir()
    assert sorted(result["removed_stale_files"]) == [
        "vertices/person.json",
        "vertices/quotation.json.tmp",
    ]


# --- edges -------------------------------------------------------------------


def test_edges_to_excluded_vertices_are_kept_with_captions(tmp_path):
    collected = _collected(
        {"notion": [_vertex(1, "notion", "Час Иисуса")]},
        [_edge("refersTo", 1, "notion", 99, "verse")],
        {"notion"},
    )
    _write(tmp_path, collected, ["notion"])

    edges = json.loads((tmp_path / "edges.json").read_text(encoding="utf-8"))["edges"]
    assert len(edges) == 1
    assert edges[0]["source"] == {
        "id": 1,
        "type": "notion",
        "caption": "caption-1",
        "exported": True,
    }
    assert edges[0]["target"] == {
        "id": 99,
        "type": "verse",
        "caption": "caption-99",
        "exported": False,
    }


def test_edges_between_two_excluded_vertices_are_kept(tmp_path):
    """`verse -isParallelTo-> verse` has no exported endpoint at all, and nothing
    but the backup can reconstruct it."""
    collected = _collected(
        {"notion": [_vertex(1, "notion", "a")]},
        [_edge("isParallelTo", 90, "verse", 91, "verse")],
        {"notion"},
    )
    _write(tmp_path, collected, ["notion"])

    edges = json.loads((tmp_path / "edges.json").read_text(encoding="utf-8"))["edges"]
    assert len(edges) == 1
    assert edges[0]["source"]["exported"] is False
    assert edges[0]["target"]["exported"] is False

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["edges"]["by_signature"] == {"verse -isParallelTo-> verse": 1}
    assert manifest["edges"]["excluded_labels"] == ["next"]


def test_parallel_edges_are_not_collapsed():
    rows = [_edge("refersTo", 1, "notion", 2, "notion")] * 2
    records = sort_edge_records([_edge_record(r, {"notion"}) for r in rows])
    assert len(records) == 2


# --- health checks -----------------------------------------------------------


def test_duplicate_captions_are_detected():
    collected = _collected(
        {
            "notion": [_vertex(1, "notion", "Слава"), _vertex(2, "notion", "Час")],
            "notionGroup": [_vertex(3, "notionGroup", "Слава")],
        },
        [],
        {"notion", "notionGroup"},
    )
    assert collected["duplicate_captions"] == {"Слава": 2}


# --- configuration -----------------------------------------------------------


def test_resolve_backup_dir_rejects_relative_path():
    with pytest.raises(ValueError, match="absolute"):
        resolve_backup_dir("backup/graph")


def test_resolve_backup_dir_rejects_missing_directory(tmp_path):
    with pytest.raises(ValueError, match="does not exist"):
        resolve_backup_dir(str(tmp_path / "typo"))


def test_resolve_backup_dir_requires_configuration(monkeypatch):
    monkeypatch.setattr(backup_module, "get_config", _config_with(backup_dir=""))
    with pytest.raises(ValueError, match="not configured"):
        resolve_backup_dir(None)


def test_resolve_backup_dir_accepts_existing_directory(tmp_path):
    assert resolve_backup_dir(str(tmp_path)) == tmp_path


def _config_with(**attrs):
    return lambda: type("C", (), attrs)()


def test_excluded_vertex_labels_default_to_verse(monkeypatch):
    monkeypatch.setattr(
        backup_module,
        "get_config",
        _config_with(backup_excluded_vertex_labels=""),
    )
    types = resolve_types(None)
    assert "verse" not in types
    assert {"notion", "notionGroup", "quotation", "scholarlyWork", "person", "verseGroup"} == set(types)


def test_excluded_vertex_labels_read_from_config(monkeypatch):
    monkeypatch.setattr(
        backup_module,
        "get_config",
        _config_with(backup_excluded_vertex_labels="verse, quotation"),
    )
    types = resolve_types(None)
    assert "verse" not in types and "quotation" not in types
    assert "notion" in types


def test_empty_excluded_vertex_labels_exports_every_label():
    assert "verse" in resolve_types([])


def test_excluded_vertex_labels_normalize_case():
    assert "notionGroup" not in resolve_types(["NOTIONGROUP"])


def test_resolve_types_rejects_unknown_label():
    with pytest.raises(ValueError, match="Unknown label"):
        resolve_types(["sermon"])


def test_resolve_types_rejects_excluding_everything():
    with pytest.raises(ValueError, match="nothing to back up"):
        resolve_types(sorted(set(backup_module.ALL_KNOWN_TYPES)))


def test_excluded_edge_labels_default_to_next(monkeypatch):
    monkeypatch.setattr(
        backup_module, "get_config", _config_with(backup_excluded_edge_labels="")
    )
    assert resolve_excluded_edge_labels(None) == ["next"]


def test_excluded_edge_labels_read_from_config(monkeypatch):
    monkeypatch.setattr(
        backup_module,
        "get_config",
        _config_with(backup_excluded_edge_labels="next, refersTo"),
    )
    assert resolve_excluded_edge_labels(None) == ["next", "refersTo"]


def test_empty_excluded_edge_labels_exports_every_label():
    assert resolve_excluded_edge_labels([]) == []


def test_excluded_edge_labels_reject_unknown_label():
    with pytest.raises(ValueError, match="Unknown edge label"):
        resolve_excluded_edge_labels(["nextVerse"])


def test_write_failure_reports_partial_state(tmp_path, monkeypatch):
    collected = _collected(
        {"notion": [_vertex(1, "notion", "a")], "book": [_vertex(2, "book", "b")]},
        [],
        {"notion", "book"},
    )

    original = backup_module._write_json

    def failing(path, payload):
        if path.name == "book.json":
            raise OSError("disk full")
        return original(path, payload)

    monkeypatch.setattr(backup_module, "_write_json", failing)

    with pytest.raises(BackupError) as exc_info:
        _write(tmp_path, collected, ["book", "notion"])

    report = exc_info.value.report
    assert report["stage"] == "write:vertices/book.json"
    assert report["completed"]["written_files"] == []
    assert "vertices/notion.json" in report["completed"]["pending_files"]


# --- integration -------------------------------------------------------------


@pytest.mark.anyio
async def test_create_graph_backup(mcp_session, tmp_path):
    result = await mcp_session.call_tool(
        "create_graph_backup",
        {"directory": str(tmp_path), "excluded_vertex_labels": ["verse", "quotation"]},
    )
    payload = result.structuredContent
    print(json.dumps(payload, indent=2, ensure_ascii=False))

    assert payload["backup_dir"] == str(tmp_path)
    assert payload["duration_seconds"] >= 0
    assert payload["vertices"]["by_type"]["notionGroup"] > 0
    assert sorted(payload["vertices"]["skipped_types"]) == ["quotation", "verse"]

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert "quotation" not in manifest["types"] and "verse" not in manifest["types"]
    assert "notionGroup" in manifest["types"]

    vertices = json.loads(
        (tmp_path / "vertices" / "notionGroup.json").read_text(encoding="utf-8")
    )["vertices"]
    ids = [v["id"] for v in vertices]
    assert ids == sorted(ids)
    assert all(v["properties"].get("caption") for v in vertices)

    edges = json.loads((tmp_path / "edges.json").read_text(encoding="utf-8"))["edges"]
    keys = [(e["source"]["id"], e["target"]["id"], e["label"]) for e in edges]
    assert keys == sorted(keys)
    assert any(
        not e["source"]["exported"] or not e["target"]["exported"] for e in edges
    ), "edges to non-exported vertices must be kept"
    assert any(
        not e["source"]["exported"] and not e["target"]["exported"] for e in edges
    ), "edges between two non-exported vertices must be kept"
    assert not any(e["label"] == "next" for e in edges)


@pytest.mark.anyio
async def test_create_graph_backup_reports_missing_directory(mcp_session, tmp_path):
    result = await mcp_session.call_tool(
        "create_graph_backup", {"directory": str(tmp_path / "typo")}
    )
    message = result.content[0].text
    print(message)

    assert result.isError
    assert "does not exist" in message
    # The diagnosis is structured, so the caller can tell the disk was untouched.
    # FastMCP prefixes the error text, and the traceback follows a blank line.
    head = message.split("\n\n")[0]
    diagnosis = json.loads(head[head.index("{"):])
    assert diagnosis["stage"] == "setup"
    assert diagnosis["written"] is False
