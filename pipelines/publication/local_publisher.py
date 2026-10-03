"""Publication written on the server's file system (decision D2: no git round trip).

``publish`` re-ingests ``data/kb`` into a fresh graph database built next to the served one and
swapped in atomically, exports the sealed snapshot and lets ``CandidateService.publish`` write the
changelog, notify the consumers and mark the candidates ``published``. What the server writes
lives on its disk: with persistent storage the maintainer commits it as before; on an ephemeral
demo deployment it is lost at the next restart (``storage_status`` says so).
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

from pipelines.kb_candidates.service import CandidateService


def storage_status() -> dict[str, Any]:
    """``persistent`` is false on the demo deployment (``LLMOPS_STORAGE_PERSISTENT=false``)."""
    persistent = os.getenv("LLMOPS_STORAGE_PERSISTENT", "true").strip().lower() not in ("false", "0", "no")
    return {"persistent": persistent, "mode": "normal" if persistent else "demo"}


def storage_warnings() -> list[str]:
    return [] if storage_status()["persistent"] else ["ephemeral-storage"]


def _remove(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def rebuild_and_swap(kb_dir: Path, db_path: Path) -> None:
    """Build the graph at ``<db>.building`` then replace the served database with it."""
    from pipelines.cli import ingest
    from tools.adapters.ladybug_store import LadybugGraphStore

    building = db_path.with_name(db_path.name + ".building")
    _remove(building)
    try:
        ingest(kb_dir=kb_dir, db_path=building)
    except SystemExit:
        pass
    if not building.exists():
        raise RuntimeError("the knowledge graph could not be rebuilt; the served database is unchanged.")
    LadybugGraphStore.clear_cache(str(db_path))
    _remove(db_path)
    os.replace(building, db_path)
    LadybugGraphStore.clear_cache(str(db_path))


def publish(service: CandidateService, kb_dir: Path, db_path: Path, snapshot_dir: Path, actor: str) -> dict[str, Any]:
    from scripts.export_sealed_snapshot import export_sealed_snapshot

    fixture = snapshot_dir / "sealed_snapshot.json"
    return service.publish(
        ingest=lambda: rebuild_and_swap(kb_dir, db_path),
        snapshot=lambda: export_sealed_snapshot(output_fixtures_path=fixture, output_snapshot_dir=snapshot_dir,
                                                db_path=db_path, ledger_path=kb_dir / "version-ledger.json",
                                                record_revisions=True),  # publishing records the new revisions
        actor=actor,
    )
