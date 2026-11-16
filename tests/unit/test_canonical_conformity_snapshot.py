"""Tests unitaires pour le calcul canonique, la majeure 4.0 et la provenance du ConformitySnapshot (#148, #149, #150)."""

import copy
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from pipelines.compliance_mapper import to_conformity_snapshot

T1 = datetime(2026, 10, 1, 12, 0, 0, tzinfo=UTC)
T2 = datetime(2026, 10, 2, 8, 30, 0, tzinfo=UTC)

SAMPLE_ENGAGEMENT_DATA = {
    "requirements": [
        {
            "id": "REQ-001",
            "text": "Network traffic between zones shall be segmented.",
            "category": "network",
            "ref": {"sourceId": "tuleap:rrf", "requirementKey": "RRF-NET-001", "version": 3},
        },
        {
            "id": "REQ-002",
            "text": "Incident response procedures shall be documented.",
            "category": "security",
        },
    ],
    "compliance": {
        "items": [
            {
                "requirement_id": "REQ-001",
                "control_id": "NIS2-ART21-2A",
                "framework": "NIS2",
                "status": "allocated",
                "decisions": ["D-0001"],
                "assets": ["PAT-006"],
            },
            {
                "requirement_id": "REQ-002",
                "control_id": "ISO27001-A5-24",
                "framework": "ISO27001",
                "status": "proposed",
                "decisions": ["D-0002"],
                "assets": ["ADR-0002"],
            },
        ],
    },
}


def test_canonical_json_test_vector_hash_matches():
    """Valide que la sérialisation canonique et le checksum SHA-256 correspondent au vecteur de test partagé."""
    vector_path = Path("tests/fixtures/canonical_conformity_vector.json")
    with open(vector_path, encoding="utf-8") as f:
        vector = json.load(f)

    data = vector["data"]
    expected_canonical = vector["canonicalJson"]
    expected_checksum = vector["expectedChecksum"]

    canonical_str = json.dumps(data, separators=(",", ":"), sort_keys=True, ensure_ascii=False)
    assert canonical_str == expected_canonical

    computed_checksum = f"sha256:{hashlib.sha256(canonical_str.encode('utf-8')).hexdigest()}"
    assert computed_checksum == expected_checksum


def test_to_conformity_snapshot_emits_major_4_and_knowledge_hub_origin():
    """Vérifie la majeure 4.0, la provenance 'knowledge-hub' et le sceau canonique."""
    snapshot = to_conformity_snapshot(
        engagement="nordwave-mcx-2027",
        framework="ALL",
        engagement_data=SAMPLE_ENGAGEMENT_DATA,
    )

    assert snapshot["sourceSystem"] == "knowledge-hub"
    assert snapshot["snapshotId"].startswith("kh-nordwave-mcx-2027-all-")
    assert snapshot["schemaVersion"] == "4.0"
    assert snapshot["checksum"].startswith("sha256:")

    canonical_str = json.dumps(snapshot["data"], separators=(",", ":"), sort_keys=True, ensure_ascii=False)
    expected_hash = f"sha256:{hashlib.sha256(canonical_str.encode('utf-8')).hexdigest()}"
    assert snapshot["checksum"] == expected_hash

    by_id = {r["id"]: r for r in snapshot["data"]["requirements"]}
    assert by_id["REQ-001"]["ref"] == {"sourceId": "tuleap:rrf", "requirementKey": "RRF-NET-001", "version": 3}
    assert by_id["REQ-002"]["ref"] == {"sourceId": "knowledge-hub:nordwave-mcx-2027", "requirementKey": "REQ-002", "version": 1}


def test_the_origin_is_not_declarative():
    """K6: no caller can make the Hub emit another origin (mutation: ``source_system="tuleap"``)."""
    with pytest.raises(ValueError, match="fixed"):
        to_conformity_snapshot(engagement="nordwave-mcx-2027", framework="ISO27001", source_system="tuleap")


def test_the_hub_never_emits_verified_nor_a_foreign_origin():
    snapshot = to_conformity_snapshot(
        engagement="nordwave-mcx-2027",
        framework="ALL",
        engagement_data=SAMPLE_ENGAGEMENT_DATA,
    )
    requirements = snapshot["data"]["requirements"]
    assert requirements
    assert {r["status"] for r in requirements} <= {"identified", "allocated"}
    assert {e["source"] for r in requirements for e in r["evidence"]} <= {"knowledge-hub"}
    assert snapshot["sourceSystem"] == "knowledge-hub"


def _snapshot(data=SAMPLE_ENGAGEMENT_DATA, now=T1):
    return to_conformity_snapshot(
        engagement="golden-engagement",
        framework="ALL",
        now=now,
        engagement_data=data,
    )


def test_the_identifier_derives_from_the_content_not_from_the_clock():
    """#149: the same state gives the same identifier and seal at any instant; only ``createdAt`` (outside the seal) moves."""
    first, second = _snapshot(now=T1), _snapshot(now=T2)
    assert first["data"] == second["data"]
    assert first["checksum"] == second["checksum"]
    assert first["snapshotId"] == second["snapshotId"]
    assert first["snapshotId"] == f"kh-golden-engagement-all-{first['checksum'][len('sha256:'):][:12]}"
    assert (first["createdAt"], second["createdAt"]) == ("2026-10-01T12:00:00Z", "2026-10-02T08:30:00Z")


def test_lowering_a_decision_from_asserted_to_proposed_changes_status_and_checksum():
    """#148 (mutation): lowering a decision from asserted ('allocated') to 'proposed' flips status to 'identified' and changes checksum."""
    before = _snapshot(data=SAMPLE_ENGAGEMENT_DATA)
    mutated = copy.deepcopy(SAMPLE_ENGAGEMENT_DATA)
    mutated["compliance"]["items"][0]["status"] = "proposed"
    after = _snapshot(data=mutated)

    req_before = {r["id"]: r for r in before["data"]["requirements"]}["REQ-001"]
    req_after = {r["id"]: r for r in after["data"]["requirements"]}["REQ-001"]
    assert req_before["status"] == "allocated" and req_before["evidence"]
    assert req_after["status"] == "identified" and req_after["evidence"] == []
    assert before["checksum"] != after["checksum"]
    assert before["snapshotId"] != after["snapshotId"]


def test_evacuated_requirement_is_excluded_and_partial_ref_is_rejected():
    data = copy.deepcopy(SAMPLE_ENGAGEMENT_DATA)
    data["requirements"][1]["disposition"] = {"status": "active", "value": "evacuated"}
    snap = _snapshot(data=data)
    assert [r["id"] for r in snap["data"]["requirements"]] == ["REQ-001"]

    bad = copy.deepcopy(SAMPLE_ENGAGEMENT_DATA)
    bad["requirements"][0]["ref"] = {"sourceId": "tuleap:rrf", "requirementKey": "RRF-NET-001"}
    with pytest.raises(ValueError, match="partial or invalid RequirementRef"):
        _snapshot(data=bad)
