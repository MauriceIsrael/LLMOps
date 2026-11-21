"""Une seule forme d'export d'ontologie est servie : le catalogue « entities » (issue #189)."""

import json
from pathlib import Path

import pytest

from pipelines.ontology.catalog_file import (
    DEFAULT_CATALOG_PATH,
    OntologyCatalogUnavailableError,
    load_catalog_document,
)
from pipelines.ontology.export import DEFAULT_EXPORT_PATH, export_ontology_snapshot

ROOT = Path(__file__).parent.parent.parent


def test_committed_catalog_is_served_in_catalog_shape():
    data = load_catalog_document(ROOT / DEFAULT_CATALOG_PATH)
    assert isinstance(data["entities"], dict) and data["entities"]
    assert "triplets" in data
    assert data["clause_index"], "clause_index must be present (built when absent)"
    assert "entries" not in data


def test_two_producers_never_share_a_path():
    assert DEFAULT_EXPORT_PATH != DEFAULT_CATALOG_PATH


def test_missing_catalog_is_an_explicit_error_not_a_regeneration(tmp_path):
    with pytest.raises(OntologyCatalogUnavailableError) as exc:
        load_catalog_document(tmp_path / "absent.json")
    assert exc.value.code == "ontology_export_not_found"
    assert not (tmp_path / "absent.json").exists(), "loading must never regenerate the file"


def test_entries_shape_is_refused_not_served(tmp_path):
    ont_dir = ROOT / "data" / "kb" / "ontology"
    out = tmp_path / "entries.json"
    export_ontology_snapshot(ont_dir, output_path=out)
    produced = json.loads(out.read_text(encoding="utf-8"))
    assert "entries" in produced["payload"]  # confirme la forme du producteur « entries »

    with pytest.raises(OntologyCatalogUnavailableError) as exc:
        load_catalog_document(out)
    assert exc.value.code == "ontology_export_wrong_shape"


def test_sealed_envelope_with_entities_is_unwrapped(tmp_path):
    envelope = {
        "schema_version": "1.0",
        "generated_at": "2026-11-21T00:00:00Z",
        "payload": {"entities": {"urn:archinex:ontology:x:y": {"urn": "urn:archinex:ontology:x:y", "kind": "leaf"}}, "triplets": []},
    }
    f = tmp_path / "env.json"
    f.write_text(json.dumps(envelope), encoding="utf-8")
    data = load_catalog_document(f)
    assert list(data["entities"]) == ["urn:archinex:ontology:x:y"]
    assert data["catalog_version"] == "1.0"
    assert "clause_index" in data
