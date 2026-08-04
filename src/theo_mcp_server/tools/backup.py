from __future__ import annotations

import json
import traceback
from typing import Any

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.server.session import ServerSession

from ..backup import BackupError, create_backup
from ..gremlin_client import AppContext, get_g


def _tool_error(report: dict[str, Any]) -> ToolError:
    """Return a ToolError carrying a structured diagnosis plus the traceback."""
    return ToolError(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n\n" + traceback.format_exc()
    )


def register_backup_tools(mcp: FastMCP) -> None:

    @mcp.tool()
    def create_graph_backup(
        ctx: Context[ServerSession, AppContext],
        directory: str | None = None,
        excluded_vertex_labels: list[str] | None = None,
        excluded_edge_labels: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Export the knowledge graph to JSON files in the local backup directory,
        overwriting the previous backup in place.

        The backup directory is meant to be a separate git repository: files are
        written deterministically (vertices sorted by id, edges sorted by source
        id, then target id, then edge label) so that `git diff` between two runs
        shows exactly what changed in the graph.

        Layout, relative to the backup directory:
            manifest.json           export time, exported types, counts, health warnings
            vertices/<type>.json    one file per vertex type, vertices sorted by id
            edges.json              every edge with at least one exported endpoint

        Every edge of the graph is exported, except the excluded labels — including
        edges between two excluded vertices, such as `verse -isParallelTo-> verse`.
        Edges keep the id, type and caption of both endpoints, and a flag telling
        whether that endpoint is part of the backup, so links to excluded vertices
        are restorable by caption once those vertices are re-imported.

        Args:
            directory: absolute path to write into. Defaults to the BACKUP_DIR
                setting. The directory must already exist.
            excluded_vertex_labels: vertex labels to leave out. Defaults to the
                BACKUP_EXCLUDED_VERTEX_LABELS setting, which itself defaults to
                `verse` — verses are re-imported from the Bible source. Pass an
                empty list to export every vertex label.
            excluded_edge_labels: edge labels to leave out. Defaults to the
                BACKUP_EXCLUDED_EDGE_LABELS setting, which itself defaults to
                `next` — the verse chain, rebuilt by the verse import. Pass an
                empty list to export every edge label.

        Returns:
            A dict with the backup directory, export time, duration, vertex
            counts by type, edge counts by label and by endpoint-type signature,
            per-file sizes, removed stale files, and health warnings.
        """
        try:
            g = get_g(ctx)
            return create_backup(
                g,
                directory=directory,
                excluded_vertex_labels=excluded_vertex_labels,
                excluded_edge_labels=excluded_edge_labels,
            )
        except BackupError as exc:
            raise _tool_error({"error": str(exc), **exc.report})
        except Exception as exc:
            raise _tool_error(
                {
                    "error": str(exc),
                    "stage": "setup",
                    "written": False,
                    "hint": "The backup directory was left untouched.",
                }
            )
