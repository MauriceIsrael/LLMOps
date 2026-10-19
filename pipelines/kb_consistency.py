"""Is the compiled knowledge graph the one the knowledge base files describe? (issue #85)

The option judge reads its check clauses from the graph (``data/knowledge.lbug``), not from ``data/kb/**/*.md``. A clause
added or amended in a file stays invisible to the judge until the graph is rebuilt, and nothing used to say so. Every asset
now carries in the graph the fingerprint of the whole file it was ingested from (``file_sha256``); this module compares it
with the file as it is today.

It only **reports**. It never rebuilds the graph: a silent rebuild would change what the judge says without a maintainer
deciding it, and would hide the drift this check exists to show.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from pipelines.ingestion.discovery import kb_source_files
from pipelines.ingestion.markdown_parser import MarkdownDocParser

ExecuteCypher = Callable[[str, dict[str, Any] | None], list[dict[str, Any]]]

REBUILD_HINT = "Rebuild the graph from the files: `poetry run ingest --kb-dir data/kb` (or `kb publish`), then commit it with them."
LIST_LIMIT = 50


def _rows(execute: ExecuteCypher, label: str) -> dict[str, str | None]:
    """``id -> file_sha256`` of the nodes of one table; ``None`` when the graph predates the fingerprint."""
    try:
        found = execute(f"MATCH (n:{label}) RETURN n.id AS id, n.file_sha256 AS sha", None)
        return {str(r["id"]): (str(r["sha"]) if r.get("sha") else None) for r in found}
    except Exception:
        try:
            found = execute(f"MATCH (n:{label}) RETURN n.id AS id", None)
        except Exception:
            return {}
        return {str(r["id"]): None for r in found}


def check_compiled_base(kb_dir: Path | str, execute: ExecuteCypher) -> dict[str, Any]:
    """Compare the files of ``kb_dir`` with the graph read through ``execute``.

    ``status``: ``ok`` (every asset matches), ``stale`` (a file changed, is new, or was removed since the graph was built:
    the judge works on another knowledge base than the files) or ``unverified`` (the graph predates the fingerprint, so
    nothing can be said until it is rebuilt)."""
    in_base = {**_rows(execute, "Asset"), **_rows(execute, "Control")}
    parser = MarkdownDocParser()
    on_disk: dict[str, str] = {}
    for path in kb_source_files(kb_dir):
        parsed = parser.parse_file(path)
        if parsed:
            on_disk[parsed["id"]] = parsed.get("file_sha256", "")
    changed = sorted(i for i, sha in on_disk.items() if i in in_base and in_base[i] and in_base[i] != sha)
    new_files = sorted(i for i in on_disk if i not in in_base)
    removed = sorted(i for i in in_base if i not in on_disk)
    unverified = sorted(i for i, sha in in_base.items() if i in on_disk and not sha)
    if changed or new_files or removed:
        status = "stale"
    elif unverified:
        status = "unverified"
    else:
        status = "ok"
    report: dict[str, Any] = {
        "status": status,
        "files": len(on_disk),
        "assets_in_base": len(in_base),
        "changed_since_build": {"count": len(changed), "ids": changed[:LIST_LIMIT]},
        "not_in_base": {"count": len(new_files), "ids": new_files[:LIST_LIMIT]},
        "removed_from_files": {"count": len(removed), "ids": removed[:LIST_LIMIT]},
        "unverified": {"count": len(unverified), "ids": unverified[:LIST_LIMIT]},
    }
    if status != "ok":
        report["reason"] = (
            "The compiled graph does not describe the current files: the option judge reads the graph, so a clause "
            "added or amended in a file is not applied. " if status == "stale" else
            "The compiled graph carries no file fingerprint (built before issue #85): it cannot be compared with the files. "
        ) + REBUILD_HINT
    return report
