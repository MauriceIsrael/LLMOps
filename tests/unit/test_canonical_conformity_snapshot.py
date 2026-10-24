"""Tests unitaires pour le calcul canonique et la provenance du ConformitySnapshot."""

import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest

from pipelines.compliance_mapper import to_conformity_snapshot


def test_canonical_json_test_vector_hash_matches():
    """Valide que la sérialisation canonique et le checksum SHA-256 correspondent au vecteur de test partagé."""
    vector_path = Path("tests/fixtures/canonical_conformity_vector.json")
    with open(vector_path, encoding="utf-8") as f:
        vector = json.load(f)

    data = vector["data"]
    expected_canonical = vector["canonicalJson"]
    expected_checksum = vector["expectedChecksum"]

    # Profil strict canonical-json (v1): clés triées, séparateurs compacts sans espace, UTF-8
    canonical_str = json.dumps(data, separators=(",", ":"), sort_keys=True, ensure_ascii=False)
    assert canonical_str == expected_canonical

    computed_checksum = f"sha256:{hashlib.sha256(canonical_str.encode('utf-8')).hexdigest()}"
    assert computed_checksum == expected_checksum


def test_to_conformity_snapshot_defaults_to_knowledge_hub():
    """Vérifie que la provenance par défaut est 'knowledge-hub' avec identifiant 'kh-'."""
    snapshot = to_conformity_snapshot(engagement="nordwave-mcx-2027", framework="ISO27001")

    assert snapshot["sourceSystem"] == "knowledge-hub"
    assert snapshot["snapshotId"].startswith("kh-nordwave-mcx-2027-iso27001-")
    assert snapshot["schemaVersion"] == "2.0"
    assert snapshot["checksum"].startswith("sha256:")

    # Vérification que le checksum scelle fidèlement le bloc data
    canonical_str = json.dumps(snapshot["data"], separators=(",", ":"), sort_keys=True, ensure_ascii=False)
    expected_hash = f"sha256:{hashlib.sha256(canonical_str.encode('utf-8')).hexdigest()}"
    assert snapshot["checksum"] == expected_hash


def test_the_origin_is_not_declarative():
    """K6: no caller can make the Hub emit another origin (mutation: ``source_system="tuleap"``)."""
    with pytest.raises(ValueError, match="fixed"):
        to_conformity_snapshot(engagement="nordwave-mcx-2027", framework="ISO27001", source_system="tuleap")


def test_the_hub_never_emits_verified_nor_a_foreign_origin():
    snapshot = to_conformity_snapshot(engagement="nordwave-mcx-2027", framework="ALL")
    requirements = snapshot["data"]["requirements"]
    assert requirements
    # The consumer's vocabulary (eight statuses): the Hub says at most "allocated" (declared), never "verified". "proposed" and
    # "uncovered" belong to the engagement snapshot (K17), not to ConformityData.
    assert {r["status"] for r in requirements} <= {"identified", "allocated"}
    assert {e["source"] for r in requirements for e in r["evidence"]} <= {"knowledge-hub"}
    assert snapshot["sourceSystem"] == "knowledge-hub"


SUITE_CONTROLS = Path(__file__).parent.parent / "fixtures" / "suite" / "controls"
T1 = datetime(2026, 10, 1, 12, 0, 0, tzinfo=UTC)
T2 = datetime(2026, 10, 2, 8, 30, 0, tzinfo=UTC)


def _snapshot(controls_dir=SUITE_CONTROLS, now=T1):
    return to_conformity_snapshot(engagement="golden-engagement", framework="NIS2", controls_dir=controls_dir, now=now)


def test_the_identifier_derives_from_the_content_not_from_the_clock():
    """#149: the same state gives the same identifier and seal at any instant; only ``createdAt`` (outside the seal) moves."""
    first, second = _snapshot(now=T1), _snapshot(now=T2)
    assert first["data"] == second["data"]
    assert first["checksum"] == second["checksum"]
    assert first["snapshotId"] == second["snapshotId"]
    assert first["snapshotId"] == f"kh-golden-engagement-nis2-{first['checksum'][len('sha256:'):][:12]}"
    assert (first["createdAt"], second["createdAt"]) == ("2026-10-01T12:00:00Z", "2026-10-02T08:30:00Z")


def test_a_changed_content_changes_the_seal_and_the_identifier(tmp_path):
    """#149 (mutation): editing one control changes the checksum, hence the identifier."""
    controls = tmp_path / "controls"
    shutil.copytree(SUITE_CONTROLS, controls)
    target = controls / "NIS2" / "NIS2-ART20-1.md"
    target.write_text(target.read_text(encoding="utf-8").replace("Governance —", "Gouvernance —", 1), encoding="utf-8")
    before, after = _snapshot(), _snapshot(controls_dir=controls)
    assert before["checksum"] != after["checksum"]
    assert before["snapshotId"] != after["snapshotId"]


def test_a_control_no_asset_declares_is_not_allocated():
    """#148: ``allocated`` needs at least one declaring asset; without any, the control stays ``identified``."""
    by_id = {r["id"]: r for r in _snapshot()["data"]["requirements"]}
    declared, undeclared = by_id["NIS2-ART21-2A"], by_id["NIS2-ART20-1"]
    assert declared["status"] == "allocated" and declared["evidence"]
    assert undeclared["status"] == "identified" and undeclared["evidence"] == []


def test_no_requirement_is_allocated_without_evidence_on_the_real_base():
    """#148 (real base): the 40 controls of the demo base that no asset declares were all emitted ``allocated``."""
    requirements = to_conformity_snapshot(engagement="nordwave-mcx-2027", framework="ALL")["data"]["requirements"]
    assert requirements
    assert all(bool(r["evidence"]) == (r["status"] == "allocated") for r in requirements)
