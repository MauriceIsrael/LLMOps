"""Engagement bundle (schemas/engagement_bundle.schema.json): the example verifies, every rule catches its violation."""

import copy
import json
from pathlib import Path

import jsonschema
import pytest

from pipelines.bundle.verify import load_schema, payload_sha256, seal, verify_bundle

ROOT = Path(__file__).parent.parent.parent
EXAMPLE = json.loads((ROOT / "schemas" / "examples" / "engagement_bundle.example.json").read_text(encoding="utf-8"))


def codes(bundle) -> set[str]:
    return {p.code for p in verify_bundle(bundle)}


def mutated(change) -> dict:
    """A deep copy of the example, changed by ``change(data)`` and re-sealed, so only the targeted rule can fail."""
    bundle = copy.deepcopy(EXAMPLE)
    change(bundle["data"])
    return seal(bundle)


def test_schema_is_a_valid_json_schema_and_the_example_verifies():
    jsonschema.Draft7Validator.check_schema(load_schema())
    assert [str(p) for p in verify_bundle(EXAMPLE)] == []


def test_the_seal_uses_the_suite_canonical_profile():
    # Same checksum for any key order, and the suite profile for numbers (1.0 is written 1, so 1.0 and 1 seal alike).
    assert payload_sha256({"a": 1.0, "b": 2}) == payload_sha256({"b": 2, "a": 1})
    assert EXAMPLE["checksum"] == payload_sha256(EXAMPLE["data"])


def test_a_value_the_profile_refuses_cannot_be_sealed():
    bundle = copy.deepcopy(EXAMPLE)
    bundle["data"]["statements"][0]["value"] = 12345678901234567890  # beyond 2**53 - 1: write it as a string
    assert codes(bundle) & {"CANONICAL", "SCHEMA"}


def test_a_changed_payload_breaks_the_seal():
    bundle = copy.deepcopy(EXAMPLE)
    bundle["data"]["decisions"][0]["decision"] += " (edited)"
    assert codes(bundle) == {"SEAL"}


def test_provisional_is_derived_not_declared():
    def lie(d):
        d["is_provisional"] = False  # one subject is still L1_framed

    def ripen(d):  # all subjects at L3_decided and no conflict: the bundle is no longer provisional
        d["subjects"][1]["maturity"] = "L3_decided"
        d["is_provisional"], d["provisional_reasons"]["unripe_subjects"] = False, []

    def open_conflict(d):
        ripen(d)
        d["conflicts"] = [{"id": "CON-1", "kind": "contradiction", "status": "open", "statement_ids": ["ST-001", "ST-002"]}]

    assert "PROVISIONAL" in codes(mutated(lie))
    assert codes(mutated(ripen)) == set()
    assert "PROVISIONAL" in codes(mutated(open_conflict))  # an open conflict makes it provisional again
    assert "DANGLING_REF" in codes(mutated(lambda d: (d.update(conflicts=[{"id": "CON-1", "kind": "stale_basis", "status": "arbitrated", "statement_ids": ["ST-404"]}]))))


def test_shape_errors_are_reported_first():
    bundle = copy.deepcopy(EXAMPLE)
    bundle["data"]["decisions"][0]["surprise"] = 1
    assert codes(bundle) == {"SCHEMA"}


def test_assertion_level_is_derived_from_the_epistemic_status():
    def lie(d):
        d["decisions"][1]["assertion_level"] = "asserted"  # an AI proposal presented as a fact

    assert {"LEVEL", "UNBACKED_CLAIM", "STATUS"} <= codes(mutated(lie))


def test_only_a_person_can_make_a_claim_asserted():
    def drop_validator(d):
        d["statements"][0]["provenance"]["by"] = []

    def machine_basis(d):
        d["compliance"][0]["provenance"]["basis"] = "ai_proposal"

    assert "UNBACKED_CLAIM" in codes(mutated(drop_validator))
    assert "UNBACKED_CLAIM" in codes(mutated(machine_basis))


def test_a_match_found_by_a_machine_stays_proposed():
    # CMP-002 (legal-text match) is proposed in the example; promoting it without a person must fail.
    def promote(d):
        d["compliance"][1].update(epistemic_status="validated", assertion_level="asserted")

    assert "UNBACKED_CLAIM" in codes(mutated(promote))


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        (lambda d: d["decisions"][0].pop("derived_from"), "REUSE_UNBACKED"),
        (lambda d: d["decisions"][0]["derived_from"].update(reuse_log_id="RL-404"), "REUSE_UNBACKED"),
        (lambda d: d["reuse_log"][0].update(matched_ref="NIS2-ART21-2B"), "REUSE_UNBACKED"),
        (lambda d: d["reuse_log"][0].update(outcome="rejected_not_same"), "REUSE_UNBACKED"),
        (lambda d: d["reuse_log"][0].update(assumptions=[]), "REUSE_UNBACKED"),
        (lambda d: d["reuse_log"][0]["assumptions"][0].update(status="unknown"), "REUSE_UNBACKED"),
        (lambda d: d["reuse_log"][0].update(outcome="reused_with_exception", comment=" "), "REUSE_UNBACKED"),
    ],
)
def test_a_reused_decision_needs_a_confirmation_judged_assumption_by_assumption(change, expected):
    assert expected in codes(mutated(change))


def test_a_reuse_with_exception_is_accepted_when_motivated():
    def motivated(d):
        d["reuse_log"][0].update(outcome="reused_with_exception", comment="Volume above 10000: manual fallback agreed.")
        d["reuse_log"][0]["assumptions"][0]["status"] = "does_not_hold"

    assert codes(mutated(motivated)) == set()


def test_identifiers_are_unique_and_resolve():
    assert "DUPLICATE_ID" in codes(mutated(lambda d: d["statements"][0].update(id="DEC-001")))
    assert "DANGLING_REF" in codes(mutated(lambda d: d["decisions"][0].update(subject_id="SUBJ-404")))
    assert "DANGLING_REF" in codes(mutated(lambda d: d["architecture"]["relations"][0].update(to="EL-404")))
    assert "DANGLING_REF" in codes(mutated(lambda d: d["decisions"][0]["provenance"].update(references=["NOPE"])))


def test_cited_kb_assets_must_be_listed():
    assert "KB_REF_UNLISTED" in codes(mutated(lambda d: d["compliance"][0].update(control_ref="NIS2-ART99-9")))
    assert "KB_REF_UNLISTED" in codes(mutated(lambda d: d.update(kb_references=[k for k in d["kb_references"] if k["ref"] != "ADR-0001"])))


def test_a_decided_subject_needs_an_asserted_decision():
    def undecide(d):
        d["subjects"][1]["status"] = "decided"  # its only decision is an AI proposal

    assert "DECIDED_WITHOUT_DECISION" in codes(mutated(undecide))


def test_no_e_mail_address_in_a_bundle():
    assert "EMAIL" in codes(mutated(lambda d: d["statements"][0].update(text="Contact jane.doe@example.org for the volumes.")))
    assert "SCHEMA" in codes({**copy.deepcopy(EXAMPLE), "data": {**EXAMPLE["data"], "reuse_log": [{**EXAMPLE["data"]["reuse_log"][0], "by": "jane@example.org"}]}})


# ── Schema 1.1: audit of the RFP requirements, optional kb pins, Hub snapshot pin ──────────────────────────────────────
# The 1.1 examples were assembled and sealed by Archinex (TypeScript). Verifying them here also proves that its seal and
# the suite canonical-json profile agree byte for byte.

EXAMPLE_11 = json.loads((ROOT / "schemas" / "examples" / "engagement_bundle_1_1.example.json").read_text(encoding="utf-8"))
EXAMPLE_11_HUB = json.loads((ROOT / "schemas" / "examples" / "engagement_bundle_1_1.hub_process.example.json").read_text(encoding="utf-8"))
HUB_PIN = {"engagement_id": "eng-x", "snapshot_id": "eng-eng-x-0123456789ab", "checksum": "sha256:" + "ab" * 32}


def mutated11(change, base=None) -> dict:
    bundle = copy.deepcopy(base or EXAMPLE_11)
    change(bundle["data"])
    return seal(bundle)


def req(d, clause):
    return next(r for r in d["requirements"] if r["clause_ref"] == clause)


def test_the_1_1_examples_verify_and_carry_the_audit():
    for example in (EXAMPLE_11, EXAMPLE_11_HUB):
        assert example["schemaVersion"] == "1.1"
        assert [str(p) for p in verify_bundle(example)] == []
    assert {r["disposition"] for r in EXAMPLE_11["data"]["requirements"]} == {"deliberated", "evacuated", "clarification_needed", "to_qualify"}


def test_the_1_0_example_is_still_valid_as_1_0():
    assert EXAMPLE["schemaVersion"] == "1.0"
    assert [str(p) for p in verify_bundle(EXAMPLE)] == []


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d["requirements"][0].update(title="Added by 1.1"),
        lambda d: d["requirements"][0].update(criticality="majeur"),
        lambda d: d["gaps"].append({"id": "GAP-9", "kind": "requirement_unqualified", "description": "x", "blocking": False}),
        lambda d: d["pins"].update(hub_snapshot=HUB_PIN),
        lambda d: d["pins"].pop("kb"),
        lambda d: d["pins"].pop("llmops_contract_version"),
    ],
)
def test_what_1_1_adds_is_rejected_in_a_1_0_document(change):
    bundle = copy.deepcopy(EXAMPLE)
    change(bundle["data"])
    assert codes(seal(bundle)) == {"SCHEMA"}


def test_a_1_1_document_may_omit_the_kb_pins():
    # An engagement can use no knowledge base: pins.kb and pins.llmops_contract_version are optional from 1.1.
    assert EXAMPLE_11["data"]["pins"] == {}
    assert codes(EXAMPLE_11) == set()


def test_the_hub_snapshot_pin_is_well_formed_and_changes_the_seal():
    pinned = mutated11(lambda d: d["pins"].update(hub_snapshot=HUB_PIN))
    assert codes(pinned) == set()
    assert pinned["checksum"] != EXAMPLE_11["checksum"]
    assert "SCHEMA" in codes(mutated11(lambda d: d["pins"].update(hub_snapshot={**HUB_PIN, "checksum": "sha256:short"})))
    assert "SCHEMA" in codes(mutated11(lambda d: d["pins"].update(hub_snapshot={"engagement_id": "eng-x"})))


def test_the_hub_process_bundle_declares_no_fact_and_no_decided_subject():
    d = EXAMPLE_11_HUB["data"]
    assert d["pins"]["hub_snapshot"]["checksum"].startswith("sha256:")
    assert d["decisions"] == [] and d["statements"] == []
    assert all(s["status"] != "decided" for s in d["subjects"])


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        (lambda d: req(d, "4.3").pop("disposition_reason"), "REQ_UNJUSTIFIED"),
        (lambda d: req(d, "4.4").pop("clarification_question"), "REQ_UNJUSTIFIED"),
        (lambda d: req(d, "4.3").update(criticality="bloquant"), "REQ_BLOCKING_EVACUATED"),
        (lambda d: d["subjects"][1].update(requirement_ids=[]), "REQ_UNCOVERED"),
        (lambda d: d["subjects"][1]["requirement_ids"].append(req(d, "4.3")["id"]), "REQ_NOT_DELIBERATED"),
        (lambda d: d.update(gaps=[g for g in d["gaps"] if g.get("requirement_id") != req(d, "4.5")["id"]]), "REQ_NO_GAP"),
        (lambda d: d.update(gaps=[g for g in d["gaps"] if g.get("requirement_id") != req(d, "4.4")["id"]]), "REQ_NO_GAP"),
        (lambda d: req(d, "4.1")["provenance"].update(by=[]), "UNBACKED_CLAIM"),
        (lambda d: req(d, "4.1")["provenance"].update(basis="ai_proposal"), "UNBACKED_CLAIM"),
    ],
)
def test_each_rule_of_the_requirement_audit_catches_its_violation(change, expected):
    assert expected in codes(mutated11(change))


def test_a_blocking_clause_evacuated_by_a_person_is_accepted():
    def decided(d):
        r = req(d, "4.3")
        r.update(criticality="bloquant", assertion_level="asserted", provenance={"basis": "human_validation", "by": ["@lead-architect"], "at": "2026-10-02T12:00:00Z"})

    assert codes(mutated11(decided)) == set()


def test_the_shape_of_a_requirement_audit_is_checked_by_the_schema():
    assert codes(mutated11(lambda d: req(d, "4.1").update(disposition="maybe"))) == {"SCHEMA"}
    assert codes(mutated11(lambda d: req(d, "4.1").pop("assertion_level"))) == {"SCHEMA"}  # a disposition needs its level and provenance
    assert codes(mutated11(lambda d: req(d, "4.1").pop("provenance"))) == {"SCHEMA"}
    assert codes(mutated11(lambda d: req(d, "4.1").update(criticality="urgent"))) == {"SCHEMA"}


def test_the_requirement_audit_is_not_required_to_exist():
    # A 1.1 document without any audit (no disposition anywhere) is valid: the audit is optional per requirement.
    def strip(d):
        for r in d["requirements"]:
            for key in ("disposition", "disposition_reason", "clarification_question", "assertion_level", "provenance", "title", "criticality", "category"):
                r.pop(key, None)
        d["gaps"] = [g for g in d["gaps"] if not g.get("requirement_id")]

    assert codes(mutated11(strip)) == set()
