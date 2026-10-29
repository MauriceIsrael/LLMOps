"""Revision ledger and citable references for ontology entries (Issue #172).

Guarantees:
- Every published/validated revision is recorded with its canonical SHA-256 hash in version-ledger.json.
- Changing content or projections without incrementing revision is strictly refused.
- An unregistered revision is strictly refused.
- Resolving an absent revision returns an explicit error, never falling back to current content.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pipelines import canonical
from pipelines.ontology.loader import (
    OntologyEntry,
    OntologyError,
)

DEFAULT_LEDGER_NAME = "version-ledger.json"


class OntologyLedgerError(OntologyError):
    """Raised when an entry's content hash does not match its recorded revision, or when unrecorded."""


class OntologyResolutionError(OntologyError):
    """Raised when an ontology entry reference or revision cannot be resolved."""

    def __init__(self, reason: str, message: str, **detail: Any):
        super().__init__(message)
        self.reason = reason
        self.detail = detail


def entry_content_sha256(entry: OntologyEntry | dict[str, Any]) -> str:
    """Compute the canonical-json v1 SHA-256 of an ontology entry."""
    if isinstance(entry, OntologyEntry):
        data = entry.to_dict()
    else:
        data = dict(entry)

    # Exclude non-semantic volatile fields if any (keep semantic fields, projections, relationships, revision)
    payload = {
        "id": data["id"],
        "term": data["term"],
        "concept_class": data["concept_class"],
        "definition": data["definition"],
        "synonyms": sorted(data.get("synonyms") or []),
        "relationships": data.get("relationships") or {},
        "projections": data.get("projections") or {},
        "status": data["status"],
        "revision": int(data["revision"]),
    }
    return canonical.sha256(payload)


def load_ontology_ledger(ledger_path: str | Path) -> dict[str, dict[str, str]]:
    """Load revisions dictionary from an ontology version-ledger.json file."""
    path = Path(ledger_path)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("revisions", {})
    except Exception as exc:
        raise OntologyLedgerError(f"Failed to read ontology version ledger at '{path}': {exc}") from exc


def write_ontology_ledger(ledger_path: str | Path, revisions: dict[str, dict[str, str]]) -> None:
    """Write revisions dictionary to an ontology version-ledger.json file."""
    path = Path(ledger_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sorted_revisions: dict[str, dict[str, str]] = {}
    for urn in sorted(revisions):
        sorted_revisions[urn] = dict(sorted(revisions[urn].items(), key=lambda kv: int(kv[0])))

    doc = {
        "description": (
            "Append-only record of canonical-json v1 SHA-256 content hashes for ontology revisions "
            "(cadre expérimental EDP, Issue #172). An entry's {urn, revision} always resolves to the exact same bytes."
        ),
        "revisions": sorted_revisions,
    }
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def verify_or_record_ontology_ledger(
    entries: list[OntologyEntry],
    ledger_path: str | Path,
    record: bool = False,
    validated_only: bool = True,
) -> dict[str, dict[str, str]]:
    """Verify entries against the ledger or record new revisions into it.

    Args:
        entries: List of loaded OntologyEntry objects.
        ledger_path: Path to version-ledger.json.
        record: If True, record previously unknown revisions into the returned ledger.
        validated_only: If True, only enforce/record entries with status 'validated'.

    Returns:
        Updated revisions dictionary.

    Raises:
        OntologyLedgerError: If content changed under an existing revision, or if a revision is unrecorded.
    """
    ledger = load_ontology_ledger(ledger_path)
    updated = {k: dict(v) for k, v in ledger.items()}
    problems: list[str] = []

    for entry in entries:
        if validated_only and entry.status != "validated":
            continue

        urn = entry.id
        rev_str = str(entry.revision)
        current_sha = entry_content_sha256(entry)

        known_revs = updated.get(urn, {})
        known_sha = known_revs.get(rev_str)

        if known_sha is None:
            if not record:
                problems.append(
                    f"Ontology entry '{urn}' revision {entry.revision} is not registered in version-ledger.json"
                )
            else:
                updated.setdefault(urn, {})[rev_str] = current_sha
        elif known_sha != current_sha:
            problems.append(
                f"Ontology entry '{urn}' revision {entry.revision}: content or projections changed without incrementing 'revision' "
                f"(ledger: {known_sha[:19]}..., current: {current_sha[:19]}...)"
            )

    if problems:
        raise OntologyLedgerError("; ".join(problems))

    return updated


def resolve_ontology_entry(
    entries: list[OntologyEntry],
    urn: str,
    revision: int | str | None = None,
) -> OntologyEntry:
    """Resolve an ontology entry by URN and optional revision.

    Refuses unknown URNs and absent revisions explicitly, never falling back to current content.
    """
    matching = [e for e in entries if e.id == urn]
    if not matching:
        raise OntologyResolutionError(
            reason="unknown_urn",
            message=f"Ontology entry with URN '{urn}' not found",
            urn=urn,
        )

    entry = matching[0]
    if revision is not None:
        target_rev = int(revision)
        if entry.revision != target_rev:
            raise OntologyResolutionError(
                reason="revision_not_found",
                message=(
                    f"Revision {target_rev} of ontology entry '{urn}' is not held "
                    f"(currently available revision is {entry.revision})"
                ),
                urn=urn,
                requested_revision=target_rev,
                available_revision=entry.revision,
            )

    return entry
