"""Tests for ontology revision ledger and citable references (Issue #172)."""

import pytest
import yaml
from typer.testing import CliRunner

from pipelines.kb_cli import app
from pipelines.ontology.ledger import (
    OntologyLedgerError,
    OntologyResolutionError,
    load_ontology_ledger,
    resolve_ontology_entry,
    verify_or_record_ontology_ledger,
    write_ontology_ledger,
)
from pipelines.ontology.loader import load_ontology_entries


def _make_validated_entry(**kwargs):
    entry = {
        "id": "urn:llmops:ontology:ComputeSubstrate:bare_metal_k8s",
        "term": "Bare Metal K8s",
        "concept_class": "ComputeSubstrate",
        "definition": "Nœud bare-metal pour Kubernetes.",
        "synonyms": ["BM K8s", "Serveur physique K8s"],
        "relationships": {},
        "projections": {
            "nautobot": {"role": "telco-worker"}
        },
        "status": "validated",
        "revision": 1,
        "reviewed_by": "@lead",
        "reviewed_at": "2026-10-29T10:00:00Z",
    }
    entry.update(kwargs)
    return entry


def test_modified_projection_without_incrementing_revision_raises(tmp_path):
    """Modifying a projection under a published revision without bumping revision is refused."""
    ont_dir = tmp_path / "ont"
    ont_dir.mkdir()
    ledger_file = ont_dir / "version-ledger.json"

    entry_v1 = _make_validated_entry(
        projections={"nautobot": {"role": "telco-worker"}}
    )
    (ont_dir / "entry.yaml").write_text(yaml.safe_dump(entry_v1), encoding="utf-8")

    # Record v1 into ledger
    entries = load_ontology_entries(ont_dir)
    initial_ledger = verify_or_record_ontology_ledger(entries, ledger_file, record=True)
    write_ontology_ledger(ledger_file, initial_ledger)

    # Now modify projection without changing revision (still revision 1)
    entry_v1_tampered = _make_validated_entry(
        projections={"nautobot": {"role": "telco-worker-modified"}}
    )
    (ont_dir / "entry.yaml").write_text(yaml.safe_dump(entry_v1_tampered), encoding="utf-8")

    tampered_entries = load_ontology_entries(ont_dir)
    with pytest.raises(OntologyLedgerError, match="changed without incrementing 'revision'"):
        verify_or_record_ontology_ledger(tampered_entries, ledger_file, record=False)


def test_incremented_revision_unregistered_raises(tmp_path):
    """Incrementing revision without registering it into the ledger is refused."""
    ont_dir = tmp_path / "ont"
    ont_dir.mkdir()
    ledger_file = ont_dir / "version-ledger.json"

    entry_v1 = _make_validated_entry(revision=1)
    (ont_dir / "entry.yaml").write_text(yaml.safe_dump(entry_v1), encoding="utf-8")

    entries_v1 = load_ontology_entries(ont_dir)
    initial_ledger = verify_or_record_ontology_ledger(entries_v1, ledger_file, record=True)
    write_ontology_ledger(ledger_file, initial_ledger)

    # Bump revision to 2 without recording it
    entry_v2 = _make_validated_entry(
        revision=2,
        projections={"nautobot": {"role": "telco-worker-v2"}}
    )
    (ont_dir / "entry.yaml").write_text(yaml.safe_dump(entry_v2), encoding="utf-8")

    entries_v2 = load_ontology_entries(ont_dir)
    with pytest.raises(OntologyLedgerError, match="is not registered in version-ledger.json"):
        verify_or_record_ontology_ledger(entries_v2, ledger_file, record=False)


def test_resolve_ontology_entry_revision_guarantees(tmp_path):
    """Resolving an absent revision returns an explicit error, never falling back to current content."""
    ont_dir = tmp_path / "ont"
    ont_dir.mkdir()

    entry = _make_validated_entry(revision=2)
    (ont_dir / "entry.yaml").write_text(yaml.safe_dump(entry), encoding="utf-8")

    entries = load_ontology_entries(ont_dir)

    # Resolving existing revision succeeds
    resolved = resolve_ontology_entry(entries, "urn:llmops:ontology:ComputeSubstrate:bare_metal_k8s", revision=2)
    assert resolved.id == "urn:llmops:ontology:ComputeSubstrate:bare_metal_k8s"
    assert resolved.revision == 2

    # Resolving absent revision 1 must raise explicit error, never return revision 2
    with pytest.raises(OntologyResolutionError) as exc:
        resolve_ontology_entry(entries, "urn:llmops:ontology:ComputeSubstrate:bare_metal_k8s", revision=1)
    assert exc.value.reason == "revision_not_found"

    # Resolving unknown URN raises unknown_urn
    with pytest.raises(OntologyResolutionError) as exc2:
        resolve_ontology_entry(entries, "urn:llmops:ontology:ComputeSubstrate:does_not_exist")
    assert exc2.value.reason == "unknown_urn"


def test_cli_ontology_record_command(tmp_path):
    """The kb ontology record CLI command registers newly validated revisions."""
    ont_dir = tmp_path / "ont"
    ont_dir.mkdir()
    ledger_file = ont_dir / "version-ledger.json"

    entry = _make_validated_entry(revision=1)
    (ont_dir / "entry.yaml").write_text(yaml.safe_dump(entry), encoding="utf-8")

    runner = CliRunner()
    res = runner.invoke(app, ["ontology", "record", "--ontology-dir", str(ont_dir), "--ledger", str(ledger_file)])
    assert res.exit_code == 0, res.output
    assert ledger_file.is_file()

    data = load_ontology_ledger(ledger_file)
    assert "urn:llmops:ontology:ComputeSubstrate:bare_metal_k8s" in data
    assert "1" in data["urn:llmops:ontology:ComputeSubstrate:bare_metal_k8s"]
    assert data["urn:llmops:ontology:ComputeSubstrate:bare_metal_k8s"]["1"].startswith("sha256:")
