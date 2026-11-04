"""Sealed export of ontology entries into ontology_export.json (Issue #173).

Guarantees:
- Validated entries only (draft and rejected are excluded).
- Strictly sorted by URN.
- Content hash (canonical-json v1) on each entry.
- Sealed by payload_sha256 according to canonical-json v1.
- Emitter channel envelope matching the Hub's snapshot standard.
- Deterministic: two runs on identical content produce identical bytes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pipelines import canonical
from pipelines.ontology.ledger import (
    DEFAULT_LEDGER_NAME,
    entry_content_sha256,
    verify_or_record_ontology_ledger,
)
from pipelines.ontology.loader import (
    OntologyEntry,
    load_ontology_entries,
)

DEFAULT_EXPORT_PATH = Path("data/snapshots/ontology_export.json")


def build_ontology_payload(entries: list[OntologyEntry]) -> dict[str, Any]:
    """Build the deterministic payload containing only validated entries."""
    validated = [e for e in entries if e.status == "validated"]
    validated.sort(key=lambda e: e.id)

    entries_data: list[dict[str, Any]] = []
    for entry in validated:
        item = entry.to_dict()
        item["content_sha256"] = entry_content_sha256(entry)
        entries_data.append(item)

    return {
        "entries": entries_data,
        "export_kind": "ontology",
        "schema_version": "1.0",
    }


def export_ontology_snapshot(
    ontology_dir: str | Path = "data/kb/ontology",
    output_path: str | Path | None = None,
    ledger_path: str | Path | None = None,
) -> dict[str, Any]:
    """Export and seal validated ontology entries into an envelope.

    Args:
        ontology_dir: Directory containing ontology YAML files.
        output_path: Optional path to write ontology_export.json.
        ledger_path: Optional path to version-ledger.json (defaults to ontology_dir/version-ledger.json).

    Returns:
        The sealed envelope dictionary.
    """
    ont_dir = Path(ontology_dir)
    entries = load_ontology_entries(ont_dir)
    l_path = Path(ledger_path) if ledger_path is not None else ont_dir / DEFAULT_LEDGER_NAME

    # Check that all validated entries are registered and unchanged in the ledger
    if l_path.is_file():
        verify_or_record_ontology_ledger(entries, l_path, record=False, validated_only=True)

    payload = build_ontology_payload(entries)
    payload_sha256 = canonical.sha256(payload)

    envelope: dict[str, Any] = {
        "export_kind": "ontology",
        "sourceId": "knowledge-hub",
        "emitter": "knowledge-hub",
        "schema_version": "1.0",
        "payload_sha256": payload_sha256,
        "checksum": payload_sha256,
        "rebuiltByEmitterTest": True,
        "regenerate": "kb ontology export",
        "entries_count": len(payload["entries"]),
        "payload": payload,
    }

    if output_path is not None:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        # Write canonical formatted json with newline
        formatted = json.dumps(envelope, indent=2, ensure_ascii=False) + "\n"
        out.write_text(formatted, encoding="utf-8")

    return envelope
