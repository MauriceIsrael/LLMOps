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


def export_fixtures(engagement: str = "nordwave-mcx-2027", output_dir: Path | None = None) -> None:
    if output_dir is None:
        output_dir = Path(__file__).parent.parent / "fixtures"

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
    export_sealed_snapshot(output_fixtures_path=output_dir / "sealed_snapshot.json")

    gc.collect()


if __name__ == "__main__":
    export_fixtures()
    os._exit(0)
