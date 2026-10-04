"""K19 (ADR-KH-01 A10): question triggers attached to the elements of the knowledge base, validated against the facts vocabulary."""

import copy
import json
import shutil
from pathlib import Path

import pytest
import yaml

from pipelines import canonical, triggers
from pipelines.engagement import facts as fact_module
from pipelines.knowledge_ref import PAYLOAD_KEYS

ROOT = Path(__file__).resolve().parents[2]
KB = ROOT / "data/kb"
VOC = fact_module.load(KB / "vocabulary/facts.yaml")
CARRIERS = triggers.carriers(KB)
GOOD = yaml.safe_load((KB / "triggers/TRG-multisite-replication.yaml").read_text(encoding="utf-8"))


def problems(**over):
    doc = {**copy.deepcopy(GOOD), **over}
    return {(p["path"], p["code"]) for p in triggers.validate_rule(doc, GOOD["trigger_id"], VOC, CARRIERS)}


# --- the initial rules ---------------------------------------------------------------------------------------------


def test_the_initial_rules_are_valid_and_cover_the_scenario():
    rules = {r["trigger_id"]: r for r in triggers.load_all(KB)}
    assert {"TRG-multisite-replication", "TRG-active-active-split-brain", "TRG-active-active-traffic-failover",
            "TRG-multisite-distribution", "TRG-sovereign-hosting-jurisdiction", "TRG-nis2-business-continuity"} <= set(rules)
    assert all(r["mandatory"] for r in rules.values() if CARRIERS[r["asset"]].get("type") == "control")


def test_a_valid_rule_has_no_problem():
    assert problems() == set()


# --- refusals, each with its path ----------------------------------------------------------------------------------


@pytest.mark.parametrize("when,expected", [
    ([{"key": "topology.sites", "op": "gte", "value": 2}], ("when[0].key", "UNKNOWN_FACT_KEY")),
    ([{"key": "topology.dc_count", "op": "gte", "value": "2"}], ("when[0].value", "VALUE_TYPE")),
    ([{"key": "topology.dc_count", "op": "gte", "value": 0}], ("when[0].value", "VALUE_TYPE")),
    ([{"key": "topology.mode", "op": "eq", "value": "triple"}], ("when[0].value", "VALUE_TYPE")),
    ([{"key": "topology.mode", "op": "gte", "value": "active-active"}], ("when[0].op", "OP_TYPE")),
    ([{"key": "continuity.nis2_in_scope", "op": "lte", "value": True}], ("when[0].op", "OP_TYPE")),
    ([{"key": "topology.dc_count", "op": "approx", "value": 2}], ("when[0].op", "UNKNOWN_OP")),
    ([{"key": "topology.mode", "op": "in", "value": []}], ("when[0].value", "VALUE_TYPE")),
    ([{"key": "topology.mode", "op": "in", "value": ["active-active", "bogus"]}], ("when[0].value", "VALUE_TYPE")),
    ([{"key": "topology.dc_count", "op": "gte"}], ("when[0]", "CONDITION_SHAPE")),
    ([], ("when", "WHEN")),
])
def test_a_bad_condition_is_refused_with_its_path(when, expected):
    assert expected in problems(when=when)


@pytest.mark.parametrize("field,value,expected", [
    ("asset", "P-999", ("asset", "UNKNOWN_ASSET")),
    ("version", 0, ("version", "VERSION")),
    ("initial_level", "L3_decided", ("initial_level", "LEVEL")),
    ("suggested_role", "", ("suggested_role", "ROLE")),
    ("mandatory", "yes", ("mandatory", "MANDATORY")),
    ("question", {"fr": "seulement"}, ("question", "TEXT")),
    ("rationale", {"fr": "a", "en": ""}, ("rationale", "TEXT")),
    ("trigger_id", "TRG-other", ("trigger_id", "ID")),
    ("extra", 1, ("extra", "UNKNOWN_FIELD")),
])
def test_other_fields_are_checked(field, value, expected):
    assert expected in problems(**{field: value})


def test_a_rule_on_a_mandatory_control_must_be_mandatory():
    assert ("mandatory", "MANDATORY_REQUIRED") in problems(asset="NIS2-ART21-2C", mandatory=False)
    assert ("mandatory", "MANDATORY_REQUIRED") not in problems(asset="NIS2-ART21-2C", mandatory=True)


def test_an_invalid_rule_is_not_published_and_the_report_names_each_error(tmp_path):
    kb = tmp_path / "kb"
    shutil.copytree(KB, kb)
    bad = copy.deepcopy(GOOD)
    bad["when"] = [{"key": "no.such_key", "op": "eq", "value": 1}]
    (kb / "triggers/TRG-multisite-replication.yaml").write_text(yaml.safe_dump(bad), encoding="utf-8")
    (kb / "triggers/TRG-broken.yaml").write_text("trigger_id: [", encoding="utf-8")
    with pytest.raises(triggers.TriggerError) as err:
        triggers.load_all(kb)
    got = {(p["trigger"], p["path"], p["code"]) for p in err.value.problems}
    assert ("TRG-multisite-replication", "when[0].key", "UNKNOWN_FACT_KEY") in got and ("TRG-broken", "$", "YAML") in got


def test_a_rule_whose_key_left_the_vocabulary_stops_the_publication(tmp_path):
    kb = tmp_path / "kb"
    shutil.copytree(KB, kb)
    voc = yaml.safe_load((kb / "vocabulary/facts.yaml").read_text(encoding="utf-8"))
    voc["keys"] = [k for k in voc["keys"] if k["key"] != "topology.dc_count"]
    (kb / "vocabulary/facts.yaml").write_text(yaml.safe_dump(voc), encoding="utf-8")
    with pytest.raises(triggers.TriggerError, match="UNKNOWN|not in the facts vocabulary"):
        triggers.load_all(kb)


# --- reference evaluation (the semantics every evaluator must give) ---------------------------------------------------


def rule(*conditions):
    return {"when": [{"key": k, "op": op, "value": v} for k, op, v in conditions]}


def test_semantics_of_the_operators():
    f = {"topology.dc_count": 2, "topology.mode": "active-active", "continuity.nis2_in_scope": True}
    assert triggers.matches(rule(("topology.dc_count", "gte", 2)), f)
    assert not triggers.matches(rule(("topology.dc_count", "gte", 3)), f)
    assert triggers.matches(rule(("topology.dc_count", "lte", 2)), f)
    assert triggers.matches(rule(("topology.mode", "eq", "active-active"), ("topology.dc_count", "eq", 2)), f)  # a conjunction
    assert not triggers.matches(rule(("topology.mode", "eq", "active-active"), ("topology.dc_count", "eq", 3)), f)
    assert triggers.matches(rule(("topology.mode", "in", ["single-site", "active-active"])), f)
    assert triggers.matches(rule(("topology.mode", "neq", "single-site")), f)
    assert not triggers.matches(rule(("continuity.nis2_in_scope", "eq", 1)), f)  # a boolean is not an integer


def test_a_condition_without_a_fact_is_false_even_for_neq():
    assert not triggers.matches(rule(("topology.mode", "neq", "single-site")), {})
    assert not triggers.matches(rule(("topology.dc_count", "gte", 1)), {"topology.mode": "single-site"})


# --- the sealed knowledge snapshot ---------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def sealed():
    return json.loads((ROOT / "data/snapshots/latest.json").read_text(encoding="utf-8"))


def test_the_rules_are_in_the_snapshot_resolved_to_their_carrier(sealed):
    section = sealed["question_triggers"]
    items = {i["trigger_id"]: i for i in section["items"]}
    assert len(items) >= 4
    for needed in ("multisite-replication", "active-active-split-brain", "sovereign-hosting-jurisdiction", "nis2-business-continuity"):
        assert f"TRG-{needed}" in items
    assert items["TRG-multisite-replication"]["carrier"]["kind"] == "asset"
    assert items["TRG-multisite-replication"]["carrier"]["knowledge_ref"] == next(
        a for a in sealed["assets"] if a["id"] == "P-010")["knowledge_ref"]
    assert items["TRG-nis2-business-continuity"]["carrier"] == {"kind": "control", "id": "NIS2-ART21-2C", "framework": "NIS2"}
    assert items["TRG-multisite-replication"]["knowledge_ref"] == {
        "sourceId": "knowledge-hub", "knowledgeKey": "trigger:TRG-multisite-replication", "version": "1"}
    assert section["content_sha256"] == canonical.sha256(section["items"])
    # every key of every rule resolves in the vocabulary of the same snapshot
    keys = {k["key"] for k in sealed["fact_vocabulary"]["keys"]}
    assert all(c["key"] in keys for i in section["items"] for c in i["when"])


def test_the_section_does_not_change_the_payload_seal(sealed):
    assert sealed["payload_sha256"] == canonical.sha256({k: sealed[k] for k in PAYLOAD_KEYS})


def test_changing_a_rule_changes_its_version_and_the_section_seal(sealed):
    items = copy.deepcopy(sealed["question_triggers"]["items"])
    items[0]["version"] += 1
    assert canonical.sha256(items) != sealed["question_triggers"]["content_sha256"]
    ledger = json.loads((KB / "version-ledger.json").read_text(encoding="utf-8"))["revisions"]
    for item in sealed["question_triggers"]["items"]:
        assert f"trigger:{item['trigger_id']}" in ledger


def test_the_export_refuses_a_rule_edited_without_a_new_version(tmp_path):
    """K3 applies to rules: the same {knowledgeKey, version} must always resolve to the same bytes."""
    from pipelines.knowledge_ref import (
        LEDGER_NAME,
        VersionLedgerError,
        check_revisions,
        load_ledger,
    )

    ledger = load_ledger(KB / LEDGER_NAME)
    rules = triggers.load_all(KB)
    published = {triggers.trigger_key(r["trigger_id"]): (r["version"], r["content_sha256"]) for r in rules}
    check_revisions(ledger, published, record=False)  # the committed rules match the ledger
    first = next(iter(published))
    published[first] = (published[first][0], "sha256:" + "0" * 64)
    with pytest.raises(VersionLedgerError, match="content changed without a new revision"):
        check_revisions(ledger, published, record=False)
