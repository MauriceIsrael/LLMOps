"""Tests for ontology integrity and quality checker, plus kb check --experimental-ontology (Issue #169)."""

import json
from pathlib import Path

import yaml
from typer.testing import CliRunner

from pipelines.kb_cli import app
from pipelines.ontology.checker import check_ontology

ROOT = Path(__file__).parent.parent.parent


def _make_base_entry(**kwargs):
    entry = {
        "id": "urn:llmops:ontology:ComputeSubstrate:base_1",
        "term": "Base 1",
        "concept_class": "ComputeSubstrate",
        "definition": "Base entry.",
        "synonyms": ["Base 1 syn"],
        "status": "draft",
        "revision": 1,
    }
    entry.update(kwargs)
    return entry


def test_referential_integrity_unknown_urn(tmp_path):
    d = tmp_path / "ont"
    d.mkdir()
    entry = _make_base_entry(
        relationships={
            "requires_capabilities": ["urn:llmops:ontology:ComputeSubstrate:missing_cap"]
        }
    )
    (d / "entry.yaml").write_text(yaml.safe_dump(entry), encoding="utf-8")

    report = check_ontology(d)
    assert report.status == "error"
    assert any("Referential integrity" in e and "missing_cap" in e for e in report.errors)


def test_poc_missing_relations_fails(tmp_path):
    """The PoC bare-metal entry references relations that must fail if missing."""
    d = tmp_path / "ont"
    d.mkdir()
    poc_entry = {
        "id": "urn:llmops:ontology:ComputeSubstrate:bare_metal_k8s",
        "term": "Bare Metal K8s",
        "concept_class": "ComputeSubstrate",
        "definition": "PoC bare metal substrate.",
        "synonyms": ["BM K8s"],
        "relationships": {
            "requires_capabilities": [
                "urn:llmops:ontology:ComputeSubstrate:oob_redfish",
                "urn:llmops:ontology:ComputeSubstrate:realtime_kernel",
            ],
            "forbids_substrate": [
                "urn:llmops:ontology:ComputeSubstrate:virtualized_vm"
            ],
        },
        "status": "draft",
        "revision": 1,
    }
    (d / "poc.yaml").write_text(yaml.safe_dump(poc_entry), encoding="utf-8")

    report = check_ontology(d)
    assert report.status == "error"
    assert len(report.errors) == 3
    assert any("oob_redfish" in e for e in report.errors)
    assert any("realtime_kernel" in e for e in report.errors)
    assert any("virtualized_vm" in e for e in report.errors)


def test_self_isolation_reflexivity_fails(tmp_path):
    d = tmp_path / "ont"
    d.mkdir()
    entry = _make_base_entry(
        id="urn:llmops:ontology:SecurityZone:zone_a",
        concept_class="SecurityZone",
        relationships={
            "isolated_from": ["urn:llmops:ontology:SecurityZone:zone_a"]
        }
    )
    (d / "zone.yaml").write_text(yaml.safe_dump(entry), encoding="utf-8")

    report = check_ontology(d)
    assert report.status == "error"
    assert any("Non-reflexivity" in e for e in report.errors)


def test_asymmetric_isolation_fails(tmp_path):
    d = tmp_path / "ont"
    d.mkdir()
    zone_a = _make_base_entry(
        id="urn:llmops:ontology:SecurityZone:zone_a",
        concept_class="SecurityZone",
        relationships={
            "isolated_from": ["urn:llmops:ontology:SecurityZone:zone_b"]
        }
    )
    zone_b = _make_base_entry(
        id="urn:llmops:ontology:SecurityZone:zone_b",
        concept_class="SecurityZone",
        synonyms=["Zone B syn"],
        relationships={
            "isolated_from": []  # missing zone_a!
        }
    )
    (d / "zones.yaml").write_text(yaml.safe_dump([zone_a, zone_b]), encoding="utf-8")

    report = check_ontology(d)
    assert report.status == "error"
    assert any("Asymmetric isolation" in e for e in report.errors)


def test_duplicate_synonym_across_entries_fails(tmp_path):
    d = tmp_path / "ont"
    d.mkdir()
    e1 = _make_base_entry(
        id="urn:llmops:ontology:ComputeSubstrate:sub_1",
        synonyms=["Shared Synonym", "Unique 1"]
    )
    e2 = _make_base_entry(
        id="urn:llmops:ontology:ComputeSubstrate:sub_2",
        synonyms=["shared synonym", "Unique 2"]
    )
    (d / "entries.yaml").write_text(yaml.safe_dump([e1, e2]), encoding="utf-8")

    report = check_ontology(d)
    assert report.status == "error"
    assert any("Duplicate synonym" in e and "shared synonym" in e.lower() for e in report.errors)


def test_validated_entry_missing_review_metadata_fails(tmp_path):
    d = tmp_path / "ont"
    d.mkdir()
    entry = _make_base_entry(
        status="validated",
        revision=2,
        # missing reviewed_by and reviewed_at
    )
    (d / "val.yaml").write_text(yaml.safe_dump(entry), encoding="utf-8")

    report = check_ontology(d)
    assert report.status == "error"
    assert any("Review requirement" in e for e in report.errors)


def test_invalid_projection_shape_fails(tmp_path):
    d = tmp_path / "ont"
    d.mkdir()
    entry = _make_base_entry(
        projections={"nautobot": "scalar_instead_of_mapping"}
    )
    (d / "entry.yaml").write_text(yaml.safe_dump(entry), encoding="utf-8")
    report = check_ontology(d)
    assert report.status == "error"


def test_kb_check_non_regression_without_flag(tmp_path):
    """When --experimental-ontology is absent, kb check output is byte-for-byte identical with or without ontology dir."""
    runner = CliRunner()
    kb_copy = tmp_path / "kb"
    import shutil
    shutil.copytree(ROOT / "data" / "kb", kb_copy)

    # 1. Output without ontology directory
    ont_dir = kb_copy / "ontology"
    if ont_dir.exists():
        shutil.rmtree(ont_dir)

    res1 = runner.invoke(app, ["check", "--kb-dir", str(kb_copy), "--json"])
    data1 = res1.output

    # 2. Add an ontology directory with broken files
    ont_dir.mkdir(exist_ok=True)
    (ont_dir / "broken.yaml").write_text("invalid_broken_yaml: [", encoding="utf-8")

    # 3. Output with ontology directory present, but flag absent
    res2 = runner.invoke(app, ["check", "--kb-dir", str(kb_copy), "--json"])
    data2 = res2.output

    # Must be byte-for-byte identical
    assert data1 == data2, "kb check output differed when --experimental-ontology was absent"
    assert "experimental_ontology" not in json.loads(data1)

    # 4. Now with --experimental-ontology, it must detect the broken file and exit code 1
    res3 = runner.invoke(app, ["check", "--kb-dir", str(kb_copy), "--experimental-ontology", "--json"])
    assert res3.exit_code != 0
    parsed3 = json.loads(res3.output)
    assert "experimental_ontology" in parsed3
    assert parsed3["experimental_ontology"]["status"] == "error"
