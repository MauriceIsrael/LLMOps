"""Tests for the deterministic ontology loader (Issue #168)."""

from pathlib import Path

import pytest
import yaml

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

ROOT = Path(__file__).parent.parent.parent


def test_urn_and_knowledge_key_bidirectional():
    urn = "urn:llmops:ontology:ComputeSubstrate:bare_metal_k8s"
    key = "ontology:ComputeSubstrate:bare_metal_k8s"
    assert to_knowledge_key(urn) == key
    assert to_urn(key) == urn
    # Idempotent fallback
    assert to_knowledge_key(key) == key
    assert to_urn(urn) == urn


def test_empty_or_non_existent_directory(tmp_path):
    empty_dir = tmp_path / "empty_ontology"
    empty_dir.mkdir()
    assert load_ontology_entries(empty_dir) == []
    assert load_ontology_entries(tmp_path / "does_not_exist") == []


def test_missing_schema_raises_ontology_error(tmp_path):
    d = tmp_path / "ont"
    d.mkdir()
    (d / "item.yaml").write_text("id: 1", encoding="utf-8")
    with pytest.raises(OntologyError, match="not found"):
        load_ontology_entries(d, schema_path=tmp_path / "missing_schema.json")


def test_valid_loading_and_sorting(tmp_path):
    d = tmp_path / "ont"
    d.mkdir()

    entry_z = {
        "id": "urn:llmops:ontology:SecurityZone:zone_z",
        "term": "Zone Z",
        "concept_class": "SecurityZone",
        "definition": "Zone de fin de liste.",
        "synonyms": ["ZZ"],
        "status": "draft",
        "revision": 1,
    }
    entry_a = {
        "id": "urn:llmops:ontology:ComputeSubstrate:substrate_a",
        "term": "Substrate A",
        "concept_class": "ComputeSubstrate",
        "definition": "Premier substrat par ordre alphabetique.",
        "synonyms": ["SA"],
        "relationships": {
            "requires_capabilities": ["urn:llmops:ontology:ComputeSubstrate:cap_1"]
        },
        "projections": {
            "nautobot": {"role": "worker"}
        },
        "status": "validated",
        "revision": 2,
        "reviewed_by": "@expert",
        "reviewed_at": "2026-10-29T10:00:00Z",
    }

    # Write in reverse order in two separate files
    (d / "file_2.yaml").write_text(yaml.safe_dump(entry_z), encoding="utf-8")
    (d / "file_1.yaml").write_text(yaml.safe_dump(entry_a), encoding="utf-8")

    entries = load_ontology_entries(d)
    assert len(entries) == 2
    # Result must be sorted by ID deterministically
    assert entries[0].id == "urn:llmops:ontology:ComputeSubstrate:substrate_a"
    assert entries[1].id == "urn:llmops:ontology:SecurityZone:zone_z"

    # Properties
    first = entries[0]
    assert isinstance(first, OntologyEntry)
    assert first.knowledge_key == "ontology:ComputeSubstrate:substrate_a"
    assert isinstance(first.relationships, OntologyRelationships)
    assert first.relationships.requires_capabilities == ["urn:llmops:ontology:ComputeSubstrate:cap_1"]
    assert first.projections == {"nautobot": {"role": "worker"}}
    assert first.reviewed_by == "@expert"
    assert first.to_dict()["term"] == "Substrate A"

    # Repeated calls give equal objects
    entries_second = load_ontology_entries(d)
    assert entries == entries_second


def test_duplicate_id_in_separate_files_raises(tmp_path):
    d = tmp_path / "ont"
    d.mkdir()

    entry = {
        "id": "urn:llmops:ontology:ComputeSubstrate:same_id",
        "term": "Same ID",
        "concept_class": "ComputeSubstrate",
        "definition": "Def.",
        "synonyms": ["Same"],
        "status": "draft",
        "revision": 1,
    }

    (d / "a.yaml").write_text(yaml.safe_dump(entry), encoding="utf-8")
    (d / "b.yaml").write_text(yaml.safe_dump(entry), encoding="utf-8")

    with pytest.raises(OntologyDuplicateIdError) as exc:
        load_ontology_entries(d)

    assert exc.value.urn == "urn:llmops:ontology:ComputeSubstrate:same_id"
    assert "a.yaml" in exc.value.first_file
    assert "b.yaml" in exc.value.second_file


def test_duplicate_id_in_same_file_raises(tmp_path):
    d = tmp_path / "ont"
    d.mkdir()

    entry = {
        "id": "urn:llmops:ontology:ComputeSubstrate:same_id",
        "term": "Same ID",
        "concept_class": "ComputeSubstrate",
        "definition": "Def.",
        "synonyms": ["Same"],
        "status": "draft",
        "revision": 1,
    }

    content = yaml.safe_dump(entry) + "\n---\n" + yaml.safe_dump(entry)
    (d / "multi.yaml").write_text(content, encoding="utf-8")

    with pytest.raises(OntologyDuplicateIdError) as exc:
        load_ontology_entries(d)

    assert exc.value.urn == "urn:llmops:ontology:ComputeSubstrate:same_id"
    assert "multi.yaml" in exc.value.first_file
    assert "multi.yaml" in exc.value.second_file


def test_schema_violation_raises(tmp_path):
    d = tmp_path / "ont"
    d.mkdir()

    invalid_entry = {
        "id": "urn:llmops:ontology:ComputeSubstrate:bad_entry",
        "concept_class": "ComputeSubstrate",
        # missing term
        "definition": "Missing term",
        "synonyms": ["Bad"],
        "status": "draft",
        "revision": 1,
    }
    (d / "bad.yaml").write_text(yaml.safe_dump(invalid_entry), encoding="utf-8")

    with pytest.raises(OntologySchemaError) as exc:
        load_ontology_entries(d)

    assert "bad.yaml" in exc.value.file_path
    assert exc.value.entry_id == "urn:llmops:ontology:ComputeSubstrate:bad_entry"
    assert exc.value.field == "term" or "term" in str(exc.value)


def test_invalid_yaml_syntax_raises(tmp_path):
    d = tmp_path / "ont"
    d.mkdir()
    (d / "corrupt.yaml").write_text("{ unclosed yaml : [", encoding="utf-8")

    with pytest.raises(OntologySchemaError) as exc:
        load_ontology_entries(d)

    assert "corrupt.yaml" in exc.value.file_path


def test_non_mapping_entry_raises(tmp_path):
    d = tmp_path / "ont"
    d.mkdir()
    (d / "scalar.yaml").write_text("- just a scalar string", encoding="utf-8")

    with pytest.raises(OntologySchemaError) as exc:
        load_ontology_entries(d)

    assert "must be a mapping" in str(exc.value)
