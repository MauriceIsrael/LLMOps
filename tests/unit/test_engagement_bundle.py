"""Engagement bundle (schemas/engagement_bundle.schema.json): the example verifies, every rule catches its violation."""

import copy
import json
from pathlib import Path

import jsonschema
import pytest

from pipelines.bundle.verify import canonical_json, load_schema, payload_sha256, seal, verify_bundle

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


def test_canonical_json_v1_oracle():
    # Same profile as the conformity snapshot: sorted keys, compact separators, UTF-8 kept.
    assert canonical_json({"b": [1, "é"], "a": {"z": None, "y": True}}) == '{"a":{"y":true,"z":null},"b":[1,"é"]}'
    assert payload_sha256({"b": [1, "é"], "a": {"z": None, "y": True}}).startswith("sha256:")
    assert payload_sha256({"a": 1, "b": 2}) == payload_sha256({"b": 2, "a": 1})  # key order never changes the seal


def test_a_changed_payload_breaks_the_seal():
    bundle = copy.deepcopy(EXAMPLE)
    bundle["data"]["decisions"][0]["decision"] += " (edited)"
    assert codes(bundle) == {"SEAL"}


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
