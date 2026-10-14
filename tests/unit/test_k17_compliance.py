"""K17 — requirement → control coverage in the engagement snapshot (contract 1.31): declared by decisions, never verified."""

import copy

from pipelines.engagement.snapshot import build_data, seal, verify
from scripts.export_engagement_example import CREATED_AT, scenario


def data_of(mutate=None):
    raw, kb = scenario()
    raw = copy.deepcopy(raw)
    if mutate:
        mutate(raw)
    return build_data(raw, "example-eng", "confidential", kb)


def rows(data):
    return {(i["requirement_id"], i["control_id"]): i["status"] for i in data["compliance"]["items"]}


def test_coverage_is_what_asserted_decisions_declare():
    section = data_of()["compliance"]
    assert section["origin"] == "knowledge-hub"
    assert rows(data_of()) == {("REQ-001", "NIS2-ART21-2C"): "allocated", ("REQ-002", "NIS2-ART21-2H"): "uncovered"}
    covered = next(i for i in section["items"] if i["status"] == "allocated")
    assert covered["decisions"] == ["D-0001"] and covered["assets"] == ["ADR-0001"]
    assert section["unresolved"] == [{"requirement_id": "REQ-002", "control_id": "GHOST-1"}]  # never invented


def downgrade(raw):
    d = raw["decisions"][0]
    d.update(status="proposed", validated_by="", validated_at="")


def test_lowering_a_decision_to_proposed_changes_the_coverage_and_the_checksum():
    before, after = data_of(), data_of(downgrade)
    assert rows(after)[("REQ-001", "NIS2-ART21-2C")] == "proposed"
    assert seal(before, "example-eng", CREATED_AT, "x")["checksum"] != seal(after, "example-eng", CREATED_AT, "x")["checksum"]


def test_a_withdrawn_decision_covers_nothing():
    after = data_of(lambda raw: raw["decisions"][0].update(status="withdrawn"))
    assert rows(after)[("REQ-001", "NIS2-ART21-2C")] == "uncovered"


def test_an_evacuated_requirement_brings_no_row():
    def evacuate(raw):
        raw["requirements"][0].update(disposition="evacuated", disposition_reason="Out of the scope of the call", disposition_status="active")

    assert ("REQ-001", "NIS2-ART21-2C") not in rows(data_of(evacuate))


def test_without_a_pinned_snapshot_nothing_is_claimed():
    from pipelines.engagement.compliance import coverage

    raw, _ = scenario()
    section = coverage([{"id": r["id"], "matched_controls": r["matched_controls"]} for r in raw["requirements"]], raw["decisions"], None)
    assert section["items"] == [] and section["kb_snapshot"] is None


def envelope(mutate):
    env = seal(data_of(), "example-eng", CREATED_AT, "x")
    mutate(env["data"]["compliance"])
    return env


def codes(env):
    return {p.code for p in verify(env)}


def test_the_sealed_example_is_valid_and_has_no_verified_nor_foreign_origin():
    env = seal(data_of(), "example-eng", CREATED_AT, "x")
    assert verify(env) == []
    assert env["schemaVersion"] == "1.7"


def test_mutations_are_refused():
    def verified(c):
        c["items"][0]["status"] = "verified"

    def foreign(c):
        c["origin"] = "tuleap"

    def lying(c):  # allocated while only a proposed decision backs it
        c["items"][1]["status"] = "allocated"

    def dangling(c):
        c["items"][0]["decisions"] = ["D-9999"]

    assert "SCHEMA" in codes(envelope(verified))
    assert "SCHEMA" in codes(envelope(foreign))
    assert "COVERAGE_STATUS" in {p.code for p in verify(_rechecksummed(lying))}
    assert "DANGLING" in {p.code for p in verify(_rechecksummed(dangling))}


def _rechecksummed(mutate):
    data = data_of()
    mutate(data["compliance"])
    return seal(data, "example-eng", CREATED_AT, "x")  # a valid seal: only the content rules can stop it
