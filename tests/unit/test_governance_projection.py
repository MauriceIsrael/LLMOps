"""#153: décision du Hub → ``governanceStatements`` du Document Engine (ADR-DE-44)."""

import copy
import json
import os
from pathlib import Path

import pytest

from pipelines.engagement import governance_projection
from pipelines.engagement.governance_projection import ProjectionRefusedError, project_decisions
from pipelines.engagement.snapshot import build_data, seal
from scripts.export_engagement_example import CREATED_AT, build_example, scenario

ROOT = Path(__file__).resolve().parents[2]
GOLDEN = ROOT / "tests" / "fixtures" / "suite" / "governance-statements.golden.json"


def _rebuilt(mutate):
    """The example scenario with its raw rows mutated, then built and sealed again: a snapshot the Hub would really emit."""
    raw, kb = scenario()
    mutate(raw)
    return seal(build_data(raw, "example-eng", "confidential", kb), "example-eng", CREATED_AT, "example")


def _row(raw, decision_id):
    return next(d for d in raw["decisions"] if d["id"] == decision_id)


def test_the_golden_is_what_the_projection_rebuilds():
    statements, _ = project_decisions(build_example())
    rebuilt = json.dumps(statements, indent=2, ensure_ascii=False) + "\n"
    if os.environ.get("GOVERNANCE_WRITE_GOLDEN") == "1":
        GOLDEN.write_text(rebuilt, encoding="utf-8", newline="\n")
    assert GOLDEN.read_text(encoding="utf-8").replace("\r\n", "\n") == rebuilt, (
        "témoin périmé : GOVERNANCE_WRITE_GOLDEN=1 poetry run pytest tests/unit/test_governance_projection.py"
    )


def test_an_asserted_decision_is_published_with_what_a_reader_needs():
    statements, report = project_decisions(build_example())
    assert [s["id"] for s in statements] == ["example-eng:D-0001"]
    s = statements[0]
    assert (s["governanceKind"], s["name"], s["description"]) == ("decision", "Active-active gateway across two sites", "Meets REQ-001 within the latency budget.")
    a = s["attributes"]
    assert a["decision-status"] == "accepted" and a["reversibility"] == "costly" and a["validated-by"] == "@ada"
    assert a["rejected-options"] == "Active-passive gateway — Failover time above the budget."
    assert a["based-on"] == "ADR-0001" and a["facts"] == "topology.dc_count=2; topology.mode=active-active"
    assert a["source"] == "knowledge-hub" and a["source-snapshot"] == build_example()["snapshotId"]
    assert report["published"] == 1 and report["excluded"] == {"proposed": 1, "superseded": 0, "withdrawn": 0}


def test_every_attribute_value_is_a_string_and_no_person_but_a_handle_crosses():
    statements, _ = project_decisions(build_example(), include_proposed=True)
    for s in statements:
        assert all(isinstance(v, str) for v in s["attributes"].values())
        assert "@" not in json.dumps(s).replace("@ada", "").replace("@carl", "").replace("@dan", "")


def test_a_proposed_decision_never_comes_out_as_a_fact():
    default, _ = project_decisions(build_example())
    assert "example-eng:D-0002" not in {s["id"] for s in default}
    included, _ = project_decisions(build_example(), include_proposed=True)
    proposed = next(s for s in included if s["id"] == "example-eng:D-0002")
    assert proposed["attributes"]["decision-status"] == "proposed" and "validated-by" not in proposed["attributes"]
    assert proposed["attributes"]["accepted-violations"] == "principle:P-009 — Pilot only."


def test_mutation_editing_an_asserted_decision_changes_the_output():
    before, _ = project_decisions(build_example())
    after, _ = project_decisions(_rebuilt(lambda raw: _row(raw, "D-0001").update(rationale="Another reason.")))
    assert before != after and after[0]["description"] == "Another reason."


def test_mutation_demoting_an_asserted_decision_removes_it():
    def demote(raw):
        _row(raw, "D-0001").update(status="proposed", validated_by="", validated_at="")
        next(s for s in raw["subjects"] if s["name"] == "gateway-services")["level"] = "L2_decomposed"

    statements, report = project_decisions(_rebuilt(demote))
    assert statements == [] and report["excluded"]["proposed"] == 2


def test_a_withdrawn_decision_is_never_published():
    statements, report = project_decisions(_rebuilt(lambda raw: _row(raw, "D-0002").update(status="withdrawn")), include_proposed=True)
    assert "example-eng:D-0002" not in {s["id"] for s in statements} and report["excluded"]["withdrawn"] == 1


def test_a_superseded_decision_is_never_published(monkeypatch):
    envelope = copy.deepcopy(build_example())
    next(d for d in envelope["data"]["decisions"] if d["id"] == "D-0002")["status"] = "superseded"
    monkeypatch.setattr(governance_projection, "verify", lambda _envelope: [])  # the supersession chain is the verifier's business
    statements, report = project_decisions(envelope, include_proposed=True)
    assert "example-eng:D-0002" not in {s["id"] for s in statements} and report["excluded"]["superseded"] == 1


def test_an_unverified_snapshot_is_refused():
    envelope = copy.deepcopy(build_example())
    envelope["data"]["decisions"][0]["decision"] = "edited by hand"
    with pytest.raises(ProjectionRefusedError, match="non vérifié"):
        project_decisions(envelope)


def test_an_unknown_status_raises_instead_of_being_guessed(monkeypatch):
    envelope = copy.deepcopy(build_example())
    envelope["data"]["decisions"][1]["status"] = "frozen"
    monkeypatch.setattr(governance_projection, "verify", lambda _envelope: [])
    with pytest.raises(ProjectionRefusedError, match="statut de décision inconnu"):
        project_decisions(envelope)


def test_the_report_says_what_the_hub_does_not_publish_and_that_the_snapshot_is_provisional():
    _, report = project_decisions(build_example())
    assert report["not_published_by_the_hub"] == ["assumption", "risk"]
    assert report["is_provisional"] is True and report["provisional_reasons"] == {"unripe_subjects": 1, "open_conflicts": 0}
