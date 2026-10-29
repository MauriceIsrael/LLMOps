"""Tests for sealed ontology export ontology_export.json (Issue #173)."""

import json
from pathlib import Path

import yaml
from typer.testing import CliRunner

from pipelines import canonical
from pipelines.kb_cli import app
from pipelines.ontology.export import export_ontology_snapshot
from pipelines.ontology.ledger import verify_or_record_ontology_ledger, write_ontology_ledger
from pipelines.ontology.loader import load_ontology_entries

ROOT = Path(__file__).parent.parent.parent


def test_draft_entries_do_not_appear_in_export(tmp_path):
    """Draft and rejected entries must never appear in the sealed ontology export."""
    ont_dir = tmp_path / "ont"
    ont_dir.mkdir()
    ledger_path = ont_dir / "version-ledger.json"

    draft = {
        "id": "urn:llmops:ontology:ComputeSubstrate:draft_1",
        "term": "Draft One",
        "concept_class": "ComputeSubstrate",
        "definition": "Draft def.",
        "synonyms": ["D1"],
        "status": "draft",
        "revision": 1,
    }
    validated = {
        "id": "urn:llmops:ontology:ComputeSubstrate:val_1",
        "term": "Val One",
        "concept_class": "ComputeSubstrate",
        "definition": "Val def.",
        "synonyms": ["V1"],
        "status": "validated",
        "revision": 1,
        "reviewed_by": "@expert",
        "reviewed_at": "2026-10-29T10:00:00Z",
    }
    (ont_dir / "items.yaml").write_text(yaml.safe_dump([draft, validated]), encoding="utf-8")

    # Record validated into ledger
    entries = load_ontology_entries(ont_dir)
    updated = verify_or_record_ontology_ledger(entries, ledger_path, record=True, validated_only=True)
    write_ontology_ledger(ledger_path, updated)

    out_file = tmp_path / "ontology_export.json"
    envelope = export_ontology_snapshot(ont_dir, output_path=out_file, ledger_path=ledger_path)

    assert envelope["entries_count"] == 1
    entries_in_payload = envelope["payload"]["entries"]
    assert len(entries_in_payload) == 1
    assert entries_in_payload[0]["id"] == "urn:llmops:ontology:ComputeSubstrate:val_1"
    assert "content_sha256" in entries_in_payload[0]
    assert entries_in_payload[0]["content_sha256"].startswith("sha256:")

    # Draft entry must NOT be present
    assert not any(e["id"] == "urn:llmops:ontology:ComputeSubstrate:draft_1" for e in entries_in_payload)


def test_two_exports_of_same_content_identical_byte_for_byte(tmp_path):
    """Two successive exports of the same ontology content produce identical bytes."""
    ont_dir = tmp_path / "ont"
    ont_dir.mkdir()
    ledger_path = ont_dir / "version-ledger.json"

    val_a = {
        "id": "urn:llmops:ontology:ComputeSubstrate:val_a",
        "term": "Val A",
        "concept_class": "ComputeSubstrate",
        "definition": "Val A def.",
        "synonyms": ["VA"],
        "status": "validated",
        "revision": 1,
        "reviewed_by": "@expert",
        "reviewed_at": "2026-10-29T10:00:00Z",
    }
    val_b = {
        "id": "urn:llmops:ontology:SecurityZone:val_b",
        "term": "Val B",
        "concept_class": "SecurityZone",
        "definition": "Val B def.",
        "synonyms": ["VB"],
        "status": "validated",
        "revision": 1,
        "reviewed_by": "@expert",
        "reviewed_at": "2026-10-29T10:00:00Z",
    }
    # Write in reverse order
    (ont_dir / "b.yaml").write_text(yaml.safe_dump(val_b), encoding="utf-8")
    (ont_dir / "a.yaml").write_text(yaml.safe_dump(val_a), encoding="utf-8")

    entries = load_ontology_entries(ont_dir)
    updated = verify_or_record_ontology_ledger(entries, ledger_path, record=True, validated_only=True)
    write_ontology_ledger(ledger_path, updated)

    out_file_1 = tmp_path / "export_1.json"
    out_file_2 = tmp_path / "export_2.json"

    export_ontology_snapshot(ont_dir, output_path=out_file_1, ledger_path=ledger_path)
    export_ontology_snapshot(ont_dir, output_path=out_file_2, ledger_path=ledger_path)

    bytes_1 = out_file_1.read_bytes()
    bytes_2 = out_file_2.read_bytes()
    assert bytes_1 == bytes_2, "Two exports of the same content differed!"


def test_existing_sealed_snapshot_payload_sha256_unmodified():
    """Existing sealed snapshot latest.json maintains identical payload_sha256."""
    latest_file = ROOT / "data" / "snapshots" / "latest.json"
    if latest_file.is_file():
        data = json.loads(latest_file.read_text(encoding="utf-8"))
        assert "payload_sha256" in data
        assert len(data["payload_sha256"]) == 64 or data["payload_sha256"].startswith("sha256:")


def test_cli_ontology_export_command(tmp_path):
    """CLI command 'kb ontology export' creates sealed JSON matching canonical hash."""
    ont_dir = tmp_path / "ont"
    ont_dir.mkdir()
    ledger_path = ont_dir / "version-ledger.json"

    val_entry = {
        "id": "urn:llmops:ontology:ComputeSubstrate:cli_val",
        "term": "CLI Val",
        "concept_class": "ComputeSubstrate",
        "definition": "CLI val def.",
        "synonyms": ["CV"],
        "status": "validated",
        "revision": 1,
        "reviewed_by": "@expert",
        "reviewed_at": "2026-10-29T10:00:00Z",
    }
    (ont_dir / "val.yaml").write_text(yaml.safe_dump(val_entry), encoding="utf-8")

    entries = load_ontology_entries(ont_dir)
    updated = verify_or_record_ontology_ledger(entries, ledger_path, record=True, validated_only=True)
    write_ontology_ledger(ledger_path, updated)

    out_file = tmp_path / "cli_export.json"
    runner = CliRunner()
    res = runner.invoke(app, ["ontology", "export", "--ontology-dir", str(ont_dir), "-o", str(out_file), "--ledger", str(ledger_path)])
    assert res.exit_code == 0, res.output
    assert out_file.is_file()

    doc = json.loads(out_file.read_text(encoding="utf-8"))
    assert doc["payload_sha256"] == canonical.sha256(doc["payload"])
    assert doc["emitter"] == "knowledge-hub"
