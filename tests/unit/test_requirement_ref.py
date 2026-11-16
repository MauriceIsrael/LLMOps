"""Unit tests for RequirementRef validation and engagement persistence (LLMOps #150)."""

from __future__ import annotations

import pytest

from pipelines.engagement.snapshot import build_data, collect
from pipelines.engagement.write import EngagementWriter, WriteError
from pipelines.requirement_ref import (
    RequirementRefError,
    hub_source_id,
    requirement_ref,
    try_requirement_ref,
    validate_requirement_ref,
)
from tools.elicitation.repository import ElicitationRepository


def test_hub_source_id_normalizes_scope():
    assert hub_source_id("NordWave_MCX 2027") == "knowledge-hub:nordwave-mcx-2027"
    with pytest.raises(RequirementRefError, match="valid sourceId"):
        hub_source_id("!!!")


def test_requirement_ref_enforces_three_fields_and_integer_version():
    ref = requirement_ref("tuleap:rrf", "RRF-FUN-1001", 3)
    assert ref == {"sourceId": "tuleap:rrf", "requirementKey": "RRF-FUN-1001", "version": 3}

    for bad_version in ("1", 0, -1, True, None, 1.5):
        with pytest.raises(RequirementRefError):
            requirement_ref("tuleap:rrf", "RRF-FUN-1001", bad_version)  # type: ignore[arg-type]

    with pytest.raises(RequirementRefError):
        requirement_ref("tuleap", "RRF-FUN-1001", 1)

    with pytest.raises(RequirementRefError):
        requirement_ref("tuleap:rrf", "   ", 1)


def test_validate_requirement_ref_rejects_partial_or_extra_fields():
    with pytest.raises(RequirementRefError, match="partial"):
        validate_requirement_ref({"sourceId": "tuleap:rrf", "requirementKey": "RRF-FUN-1001"})

    with pytest.raises(RequirementRefError, match="unexpected"):
        validate_requirement_ref({"sourceId": "tuleap:rrf", "requirementKey": "RRF-FUN-1001", "version": 1, "extra": True})


def test_try_requirement_ref_never_emits_partial():
    assert try_requirement_ref("tuleap:rrf", "RRF-1", None) is None
    assert try_requirement_ref("tuleap:rrf", "", 1) is None
    assert try_requirement_ref("tuleap:rrf", "RRF-1", "2") == {
        "sourceId": "tuleap:rrf",
        "requirementKey": "RRF-1",
        "version": 2,
    }


def test_engagement_write_and_snapshot_preserve_tuleap_ref_and_default_standalone(tmp_path):
    repo = ElicitationRepository(db_path=tmp_path / "eng.lbug")
    writer = EngagementWriter(repo, "rrf-eng", "@alice", "data/snapshots")

    res = writer.add_requirements({
        "origin": "human",
        "requirements": [
            {
                "id": "REQ-TULEAP-1",
                "text": "The gateway shall support dual-homing.",
                "ref": {"sourceId": "tuleap:rrf", "requirementKey": "RRF-NET-001", "version": 4},
            },
            {
                "id": "REQ-HUB-2",
                "text": "Logs shall be retained for 12 months.",
            },
        ],
    })
    assert res["created"] == ["REQ-TULEAP-1", "REQ-HUB-2"]

    with pytest.raises(WriteError, match="partial"):
        writer.add_requirements({
            "origin": "human",
            "requirements": [
                {
                    "id": "REQ-BAD",
                    "text": "Missing version.",
                    "ref": {"sourceId": "tuleap:rrf", "requirementKey": "RRF-BAD"},
                }
            ],
        })

    data = build_data(collect(repo, "rrf-eng"), "rrf-eng", "internal", None)
    by_id = {r["id"]: r for r in data["requirements"]}
    assert by_id["REQ-TULEAP-1"]["ref"] == {"sourceId": "tuleap:rrf", "requirementKey": "RRF-NET-001", "version": 4}
    assert by_id["REQ-HUB-2"]["ref"] == {"sourceId": "knowledge-hub:rrf-eng", "requirementKey": "REQ-HUB-2", "version": 1}
