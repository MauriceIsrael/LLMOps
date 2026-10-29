"""Deterministic ontology entries loader for LLMOps Knowledge Hub (Issue #168).

Reads YAML files in data/kb/ontology/, validates each entry against
schemas/ontology_entry.schema.json, and returns typed, deterministically sorted objects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any
import jsonschema
import yaml

ROOT = Path(__file__).parent.parent.parent
DEFAULT_SCHEMA_PATH = ROOT / "schemas" / "ontology_entry.schema.json"


class OntologyError(Exception):
    """Base error for ontology operations."""


class OntologySchemaError(OntologyError):
    """Raised when an ontology entry fails schema validation."""

    def __init__(self, message: str, file_path: str, entry_id: str | None = None, field: str | None = None):
        super().__init__(message)
        self.file_path = file_path
        self.entry_id = entry_id
        self.field = field


class OntologyDuplicateIdError(OntologyError):
    """Raised when the same ontology identifier is defined in multiple places."""

    def __init__(self, urn: str, first_file: str, second_file: str):
        message = f"Duplicate ontology ID '{urn}' declared in '{first_file}' and '{second_file}'"
        super().__init__(message)
        self.urn = urn
        self.first_file = first_file
        self.second_file = second_file


def to_knowledge_key(urn: str) -> str:
    """Convert URN 'urn:llmops:ontology:<class>:<slug>' to knowledgeKey 'ontology:<class>:<slug>'."""
    prefix = "urn:llmops:"
    if urn.startswith(prefix):
        return urn[len(prefix):]
    return urn


def to_urn(key: str) -> str:
    """Convert knowledgeKey 'ontology:<class>:<slug>' to URN 'urn:llmops:ontology:<class>:<slug>'."""
    if key.startswith("ontology:"):
        return f"urn:llmops:{key}"
    return key


@dataclass(frozen=True)
class OntologyRelationships:
    isolated_from: list[str] = field(default_factory=list)
    forbids_substrate: list[str] = field(default_factory=list)
    requires_capabilities: list[str] = field(default_factory=list)
    allowed_traffic_classes: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> OntologyRelationships:
        if not data:
            return cls()
        return cls(
            isolated_from=list(data.get("isolated_from") or []),
            forbids_substrate=list(data.get("forbids_substrate") or []),
            requires_capabilities=list(data.get("requires_capabilities") or []),
            allowed_traffic_classes=list(data.get("allowed_traffic_classes") or []),
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        if self.isolated_from:
            result["isolated_from"] = list(self.isolated_from)
        if self.forbids_substrate:
            result["forbids_substrate"] = list(self.forbids_substrate)
        if self.requires_capabilities:
            result["requires_capabilities"] = list(self.requires_capabilities)
        if self.allowed_traffic_classes:
            result["allowed_traffic_classes"] = list(self.allowed_traffic_classes)
        return result


@dataclass(frozen=True)
class OntologyEntry:
    id: str
    term: str
    concept_class: str
    definition: str
    synonyms: list[str]
    relationships: OntologyRelationships
    projections: dict[str, Any]
    status: str
    revision: int
    reviewed_by: str | None = None
    reviewed_at: str | None = None
    review_source: str | None = None
    source_file: str | None = None

    @property
    def knowledge_key(self) -> str:
        return to_knowledge_key(self.id)

    @classmethod
    def from_dict(cls, data: dict[str, Any], source_file: str | None = None) -> OntologyEntry:
        rel_data = data.get("relationships")
        relationships = OntologyRelationships.from_dict(rel_data) if isinstance(rel_data, dict) else OntologyRelationships()
        projections = dict(data.get("projections") or {})
        synonyms = [str(s) for s in (data.get("synonyms") or [])]
        return cls(
            id=str(data["id"]),
            term=str(data["term"]),
            concept_class=str(data["concept_class"]),
            definition=str(data["definition"]),
            synonyms=synonyms,
            relationships=relationships,
            projections=projections,
            status=str(data["status"]),
            revision=int(data["revision"]),
            reviewed_by=data.get("reviewed_by"),
            reviewed_at=data.get("reviewed_at"),
            review_source=data.get("review_source"),
            source_file=source_file,
        )

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "id": self.id,
            "term": self.term,
            "concept_class": self.concept_class,
            "definition": self.definition,
            "synonyms": list(self.synonyms),
            "status": self.status,
            "revision": self.revision,
        }
        rel_dict = self.relationships.to_dict()
        if rel_dict:
            d["relationships"] = rel_dict
        if self.projections:
            d["projections"] = self.projections
        if self.reviewed_by is not None:
            d["reviewed_by"] = self.reviewed_by
        if self.reviewed_at is not None:
            d["reviewed_at"] = self.reviewed_at
        if self.review_source is not None:
            d["review_source"] = self.review_source
        return d


def load_schema(schema_path: str | Path = DEFAULT_SCHEMA_PATH) -> dict[str, Any]:
    path = Path(schema_path)
    if not path.is_file():
        raise OntologyError(f"Ontology schema file not found at: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_ontology_entries(
    ontology_dir: str | Path = "data/kb/ontology",
    schema_path: str | Path = DEFAULT_SCHEMA_PATH,
) -> list[OntologyEntry]:
    """Load, validate and deterministically sort all ontology entries from a directory.

    Args:
        ontology_dir: Path to directory containing .yaml / .yml ontology files.
        schema_path: Path to ontology_entry.schema.json.

    Returns:
        List of OntologyEntry objects sorted strictly by their URN id.

    Raises:
        OntologySchemaError: If any entry violates the JSON Schema or has invalid syntax.
        OntologyDuplicateIdError: If two entries declare the same URN id.
    """
    path = Path(ontology_dir)
    if not path.is_dir():
        return []

    schema = load_schema(schema_path)
    validator = jsonschema.Draft7Validator(schema)

    # Collect and sort yaml files deterministically
    yaml_files = sorted(
        [p for p in path.glob("**/*") if p.is_file() and p.suffix.lower() in (".yaml", ".yml")]
    )

    id_to_file: dict[str, str] = {}
    entries: list[OntologyEntry] = []

    for file_path in yaml_files:
        norm_file = str(file_path).replace("\\", "/")
        try:
            content = file_path.read_text(encoding="utf-8")
            raw_docs = list(yaml.safe_load_all(content))
        except Exception as exc:
            raise OntologySchemaError(
                f"Failed to parse YAML file '{norm_file}': {exc}",
                file_path=norm_file,
            ) from exc

        for doc in raw_docs:
            if doc is None:
                continue
            # A file may contain a single entry (dict) or a list of entries
            raw_entries = doc if isinstance(doc, list) else [doc]
            for item in raw_entries:
                if not isinstance(item, dict):
                    raise OntologySchemaError(
                        f"Entry in '{norm_file}' must be a mapping, got {type(item).__name__}",
                        file_path=norm_file,
                    )

                errors = list(validator.iter_errors(item))
                if errors:
                    first_err = errors[0]
                    field_name = str(first_err.path[0]) if first_err.path else None
                    entry_id = str(item.get("id") or "unknown")
                    raise OntologySchemaError(
                        f"Validation error in '{norm_file}' for entry '{entry_id}': {first_err.message}",
                        file_path=norm_file,
                        entry_id=entry_id,
                        field=field_name,
                    )

                entry_id = str(item["id"])
                if entry_id in id_to_file:
                    raise OntologyDuplicateIdError(
                        urn=entry_id,
                        first_file=id_to_file[entry_id],
                        second_file=norm_file,
                    )
                id_to_file[entry_id] = norm_file
                entries.append(OntologyEntry.from_dict(item, source_file=norm_file))

    entries.sort(key=lambda e: e.id)
    return entries
