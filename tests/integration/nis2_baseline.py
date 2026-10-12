"""NIS2 as it was before its first full ingestion, for the tests that replay that ingestion.

The repository knowledge base has NIS2 published and declared covered (19 requirements);
the ingestion tests start from the 10 historical controls, without a coverage declaration.
"""

from pathlib import Path

import yaml

INGESTED = ("NIS2-ART20-1", "NIS2-ART20-2", "NIS2-ART21-1", "NIS2-ART21-3", "NIS2-ART21-4",
            "NIS2-ART23-1", "NIS2-ART23-2", "NIS2-ART23-3", "NIS2-ART23-4")


def rewind_nis2(kb: Path) -> None:
    folder = kb / "controls" / "NIS2"
    for rid in INGESTED:
        (folder / f"{rid}.md").unlink(missing_ok=True)
    for control in folder.glob("NIS2-*.md"):  # the historical controls had not been validated yet
        text = control.read_text(encoding="utf-8")
        control.write_text(text.replace("validated_by: ['@maintainers']", "validated_by: []"), encoding="utf-8")
    manifest_path = folder / "_manifest.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["coverage_declared_by"] = None
    manifest["coverage_declared_at"] = None
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True), encoding="utf-8")
