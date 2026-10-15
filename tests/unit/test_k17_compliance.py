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
    assert rows(data_of()) == {
        ("REQ-001", "NIS2-ART21-2C"): "allocated",
        ("REQ-001", "NIS2-ART21-2D"): "allocated",  # declared by the chain, not matched (contract 1.33)
        ("REQ-002", "NIS2-ART21-2H"): "uncovered",
    }
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
    assert env["schemaVersion"] == "1.8"


def test_mutations_are_refused():
    def verified(c):
        c["items"][0]["status"] = "verified"

    def foreign(c):
        c["origin"] = "tuleap"

    def lying(c):  # allocated while no decision backs it
        next(i for i in c["items"] if i["status"] == "uncovered")["status"] = "allocated"

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


# --- contract 1.33: the chain requirement <- subject <- decision -> asset -> control, without any matching of text -------------------


def unmatched(raw):
    """REQ-001 loses its matched control (as a requirement created by the write API never had one)."""
    raw["requirements"][0]["matched_controls"] = "[]"


def declared(data):
    return {(i["requirement_id"], i["control_id"]): i for i in data["compliance"]["items"] if i.get("basis")}


def test_a_requirement_without_any_matched_control_still_reaches_the_controls_its_decisions_declare():
    data = data_of(unmatched)
    rows_ = declared(data)
    assert set(rows_) == {("REQ-001", "NIS2-ART21-2C"), ("REQ-001", "NIS2-ART21-2D")}
    row = rows_[("REQ-001", "NIS2-ART21-2C")]
    assert row == {"requirement_id": "REQ-001", "control_id": "NIS2-ART21-2C", "framework": "NIS2", "severity": "mandatory",
                   "status": "allocated", "decisions": ["D-0001"], "assets": ["ADR-0001"], "basis": "declared_by_decision"}
    assert verify(seal(data, "example-eng", CREATED_AT, "x")) == []


def test_matched_rows_are_unchanged_and_a_matched_pair_is_not_repeated():
    matched = next(i for i in data_of()["compliance"]["items"] if i["control_id"] == "NIS2-ART21-2C")
    assert "basis" not in matched  # a row produced by matching keeps exactly its former shape
    assert sum(1 for i in data_of()["compliance"]["items"] if i["control_id"] == "NIS2-ART21-2C") == 1
    assert set(declared(data_of())) == {("REQ-001", "NIS2-ART21-2D")}  # only the pair no matching produced


def test_lowering_the_decision_lowers_the_declared_rows_and_changes_the_checksum():
    before, after = data_of(unmatched), data_of(lambda raw: (unmatched(raw), downgrade(raw)))
    assert {r["status"] for r in declared(after).values()} == {"proposed"}
    assert seal(before, "example-eng", CREATED_AT, "x")["checksum"] != seal(after, "example-eng", CREATED_AT, "x")["checksum"]


def test_a_withdrawn_decision_declares_nothing():
    assert declared(data_of(lambda raw: (unmatched(raw), raw["decisions"][0].update(status="withdrawn")))) == {}


def test_a_decision_on_a_subject_that_does_not_carry_the_requirement_declares_nothing():
    def elsewhere(raw):
        unmatched(raw)
        raw["decisions"][0]["subject"] = "core-network"  # core-network carries no requirement

    assert declared(data_of(elsewhere)) == {}


def test_an_evacuated_requirement_declares_nothing():
    def evacuate(raw):
        raw["requirements"][0].update(disposition="evacuated", disposition_reason="Out of the scope of the call", disposition_status="active")
        raw["subject_requirements"] = {}  # an evacuated requirement is carried by no subject

    assert declared(data_of(evacuate)) == {}


def test_a_typed_key_in_based_on_designates_the_asset_it_names():
    def typed(raw):
        raw["decisions"][0]["based_on"] = [{"id": "decision:ADR-0001", "resolved": None}]

    assert set(declared(data_of(lambda raw: (unmatched(raw), typed(raw))))) == {("REQ-001", "NIS2-ART21-2C"), ("REQ-001", "NIS2-ART21-2D")}
    assert rows(data_of(typed))[("REQ-001", "NIS2-ART21-2C")] == "allocated"  # the matched row too (it ignored typed keys before)


def test_a_decision_citing_the_control_itself_declares_it():
    def cites_control(raw):
        unmatched(raw)
        raw["decisions"][0]["based_on"] = [{"id": "NIS2-ART21-2C", "resolved": None}]

    row = declared(data_of(cites_control))[("REQ-001", "NIS2-ART21-2C")]
    assert row["assets"] == [] and row["decisions"] == ["D-0001"]


def test_the_declared_rows_do_not_depend_on_the_order_of_the_decisions():
    first = seal(data_of(unmatched), "example-eng", CREATED_AT, "x")["checksum"]
    second = seal(data_of(lambda raw: (unmatched(raw), raw["decisions"].reverse())), "example-eng", CREATED_AT, "x")["checksum"]
    assert first == second


def test_the_verification_refuses_an_inconsistent_declared_row():
    def mutate(edit):
        data = data_of(unmatched)
        edit(data["compliance"]["items"])
        return {p.code for p in verify(seal(data, "example-eng", CREATED_AT, "x"))}

    assert "COVERAGE_WITHOUT_DECISION" in mutate(lambda items: items[0].update(decisions=[], status="uncovered"))
    assert "COVERAGE_NOT_CARRIED" in mutate(lambda items: items[0].update(decisions=["D-0002"], status="proposed"))
    assert "COVERAGE_DUPLICATE" in mutate(lambda items: items.append(dict(items[0])))
    assert "SCHEMA" in mutate(lambda items: items[0].update(basis="text_match"))
