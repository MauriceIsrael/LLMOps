"""Script to export standard JSON fixtures for third-party integrators."""

import gc
import json
import os
from pathlib import Path

from mcp_server.engagement.tools import (
    get_board,
    get_diagram_graph,
    get_engagement_export,
    get_render_payload,
)
from mcp_server.knowledge.tools import get_graph_summary


def export_fixtures(
    engagement: str = "nordwave-mcx-2027",
    output_dir: Path | None = None,
    snapshot_dir: Path | None = None,
) -> None:
    """Export fixtures to ``output_dir``.

    ``snapshot_dir`` receives the ``latest.json`` / versioned sealed snapshot copies.
    It defaults to ``data/snapshots`` when exporting to the committed ``fixtures/``
    directory, and to ``<output_dir>/snapshots`` otherwise, so that exporting to a
    temporary directory (e.g. from tests) never touches the repository.
    """
    if output_dir is None:
        output_dir = Path(__file__).parent.parent / "fixtures"
    elif snapshot_dir is None:
        snapshot_dir = output_dir / "snapshots"

    output_dir.mkdir(parents=True, exist_ok=True)

    fixtures = {
        "knowledge_snapshot.json": get_graph_summary(),
        "engagement_snapshot.json": get_engagement_export(engagement=engagement),
        "get_render_payload.json": get_render_payload(engagement=engagement),
        "get_board.json": get_board(engagement=engagement),
        "get_diagram_graph.json": get_diagram_graph(engagement=engagement, format="mermaid"),
    }

    for filename, content in fixtures.items():
        filepath = output_dir / filename
        filepath.write_text(json.dumps(content, indent=2, default=str) + "\n", encoding="utf-8")
        print(f"Exported fixture: {filepath.relative_to(output_dir.parent)}")

    from scripts.export_sealed_snapshot import export_sealed_snapshot
    export_sealed_snapshot(
        output_fixtures_path=output_dir / "sealed_snapshot.json",
        output_snapshot_dir=snapshot_dir,
    )

    gc.collect()


if __name__ == "__main__":
    export_fixtures()
    os._exit(0)
