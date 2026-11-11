"""Ontology package for LLMOps Knowledge Hub (EDP experimental)."""

from pipelines.ontology.catalog import (
    PREDICATE_SATISFIES_CLAUSE,
    VALID_PREDICATES,
    build_clause_index,
    resolve_clauses_by_leaf,
    resolve_leaves_by_clause,
    validate_clause_leaf_integrity,
)
from pipelines.ontology.checker import OntologyCheckReport, check_ontology
from pipelines.ontology.export import (
    DEFAULT_EXPORT_PATH,
    build_ontology_payload,
    export_ontology_snapshot,
)
from pipelines.ontology.gateway import (
    is_ontology_experimental_enabled,
    project_ontology_to_vocabulary,
)
from pipelines.ontology.ledger import (
    DEFAULT_LEDGER_NAME,
    OntologyLedgerError,
    OntologyResolutionError,
    entry_content_sha256,
    load_ontology_ledger,
    resolve_ontology_entry,
    verify_or_record_ontology_ledger,
    write_ontology_ledger,
)
from pipelines.ontology.loader import (
    OntologyDuplicateIdError,
    OntologyEntry,
    OntologyError,
    OntologyRelationships,
    OntologySchemaError,
    load_ontology_entries,
    to_knowledge_key,
    to_urn,
)

__all__ = [
    "DEFAULT_EXPORT_PATH",
    "DEFAULT_LEDGER_NAME",
    "OntologyCheckReport",
    "OntologyDuplicateIdError",
    "OntologyEntry",
    "OntologyError",
    "OntologyLedgerError",
    "OntologyRelationships",
    "OntologyResolutionError",
    "OntologySchemaError",
    "PREDICATE_SATISFIES_CLAUSE",
    "VALID_PREDICATES",
    "build_clause_index",
    "build_ontology_payload",
    "check_ontology",
    "entry_content_sha256",
    "export_ontology_snapshot",
    "is_ontology_experimental_enabled",
    "load_ontology_entries",
    "load_ontology_ledger",
    "project_ontology_to_vocabulary",
    "resolve_clauses_by_leaf",
    "resolve_leaves_by_clause",
    "resolve_ontology_entry",
    "to_knowledge_key",
    "to_urn",
    "validate_clause_leaf_integrity",
    "verify_or_record_ontology_ledger",
    "write_ontology_ledger",
]
