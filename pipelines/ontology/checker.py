"""Integrity and quality checker for ontology entries (Issue #169).

Performs:
1. Referential integrity: all URNs cited in relationships exist in the loaded ontology.
2. Symmetry and non-reflexivity of isolated_from.
3. Global uniqueness of synonyms across entries.
4. Review requirements on validated entries (reviewed_by and reviewed_at).
5. Projection shape compliance for target tools.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pipelines.ontology.loader import (
    OntologyDuplicateIdError,
    OntologyEntry,
    OntologyError,
    OntologySchemaError,
    load_ontology_entries,
)


@dataclass
class OntologyCheckReport:
    status: str  # "ok" | "error"
    entries_count: int
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "entries_count": self.entries_count,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


def check_ontology(
    ontology_dir: str | Path = "data/kb/ontology",
    schema_path: str | Path | None = None,
    strict: bool = False,
) -> OntologyCheckReport:
    """Run all integrity, quality and referential checks on an ontology directory."""
    errors: list[str] = []
    warnings: list[str] = []

    try:
        kwargs: dict[str, Any] = {}
        if schema_path is not None:
            kwargs["schema_path"] = schema_path
        entries = load_ontology_entries(ontology_dir, **kwargs)
    except (OntologySchemaError, OntologyDuplicateIdError, OntologyError) as exc:
        return OntologyCheckReport(
            status="error",
            entries_count=0,
            errors=[str(exc)],
            warnings=[],
        )

    urn_map: dict[str, OntologyEntry] = {e.id: e for e in entries}

    # 1. Referential integrity on relationships
    for entry in entries:
        rels = entry.relationships
        all_targets: list[tuple[str, str]] = []
        for target in rels.isolated_from:
            all_targets.append(("isolated_from", target))
        for target in rels.forbids_substrate:
            all_targets.append(("forbids_substrate", target))
        for target in rels.requires_capabilities:
            all_targets.append(("requires_capabilities", target))
        for target in rels.allowed_traffic_classes:
            all_targets.append(("allowed_traffic_classes", target))

        for rel_name, target_urn in all_targets:
            if target_urn not in urn_map:
                errors.append(
                    f"Referential integrity: entry '{entry.id}' references unknown URN '{target_urn}' in '{rel_name}'"
                )

    # 2. isolated_from symmetry and non-reflexivity
    for entry in entries:
        for target_urn in entry.relationships.isolated_from:
            if target_urn == entry.id:
                errors.append(f"Non-reflexivity: entry '{entry.id}' cannot be isolated from itself")
            elif target_urn in urn_map:
                target_entry = urn_map[target_urn]
                # Check if asymmetry is explicitly declared in projections or metadata
                is_asymmetric = (
                    entry.projections.get("_meta", {}).get("asymmetric_isolation") is True
                    or target_entry.projections.get("_meta", {}).get("asymmetric_isolation") is True
                )
                if not is_asymmetric and entry.id not in target_entry.relationships.isolated_from:
                    errors.append(
                        f"Asymmetric isolation: '{entry.id}' is isolated from '{target_urn}', but '{target_urn}' does not declare isolation from '{entry.id}'"
                    )

    # 3. Global uniqueness of synonyms across entries
    synonym_owners: dict[str, str] = {}
    for entry in entries:
        # Check normalized synonyms
        for syn in entry.synonyms:
            norm = syn.strip().lower()
            if not norm:
                continue
            if norm in synonym_owners and synonym_owners[norm] != entry.id:
                errors.append(
                    f"Duplicate synonym: '{syn}' in '{entry.id}' is already claimed by '{synonym_owners[norm]}'"
                )
            else:
                synonym_owners[norm] = entry.id

    # 4. Review requirements on validated entries
    for entry in entries:
        if entry.status == "validated":
            if not entry.reviewed_by or not str(entry.reviewed_by).strip():
                errors.append(f"Review requirement: validated entry '{entry.id}' must declare 'reviewed_by'")
            if not entry.reviewed_at or not str(entry.reviewed_at).strip():
                errors.append(f"Review requirement: validated entry '{entry.id}' must declare 'reviewed_at'")

    # 5. Projection tool shapes
    tool_key_re = re.compile(r"^[a-z0-9_]+$")
    for entry in entries:
        for tool_name, tool_data in entry.projections.items():
            if tool_name.startswith("_"):
                continue  # internal metadata
            if not tool_key_re.match(tool_name):
                errors.append(
                    f"Projection tool name: key '{tool_name}' in '{entry.id}' must be snake_case"
                )
            if not isinstance(tool_data, dict):
                errors.append(
                    f"Projection shape: projection '{tool_name}' in '{entry.id}' must be a mapping"
                )
                continue
            if len(tool_data) == 0:
                warnings.append(
                    f"Projection shape: empty projection for tool '{tool_name}' in '{entry.id}'"
                )

    status = "error" if errors or (strict and warnings) else "ok"
    return OntologyCheckReport(
        status=status,
        entries_count=len(entries),
        errors=errors,
        warnings=warnings,
    )
