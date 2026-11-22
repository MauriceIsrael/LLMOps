"""Fiches de règles d'oracle et énumérations du catalogue (proposition aux experts, OOB/OAM)."""

import json
from pathlib import Path

import jsonschema
import pytest

from pipelines.ontology.catalog_checks import (
    SEVERITY_ERROR,
    SEVERITY_WARNING,
    check_catalog,
    check_enumerations,
    check_rule_cards,
)
from pipelines.ontology.catalog_file import load_catalog_document

ROOT = Path(__file__).parent.parent.parent
CATALOG = ROOT / "data" / "snapshots" / "ontology_export.json"
SCHEMA = ROOT / "schemas" / "ontology_catalog.schema.json"
U = "urn:archinex:ontology:test:leaf"
CLAUSE = "urn:archinex:kb:clause:test:one"
RULE = "data.archinex.edp.multiaxis.deny_x"


def _leaf(**kw):
    return {"urn": U, "revision": 1, "kind": "leaf", "title": "t", **kw}


def _cat(entity, cards=None, enums=None):
    return {"entities": {U: entity}, "triplets": [], "rule_cards": cards or {}, "enumerations": enums or {}}


def _card(**kw):
    return {"object": "o", "violation": "v", "parameters": [], "evidence_plan": "p", "evidence_drift": None, "clauses": [], **kw}


def _isolation():
    values = [{"value": v, "definition": v} for v in ("shared", "segmented", "strict")]
    return {"isolation_level": {"ordered": True, "values": values}}


def test_a_named_rule_without_a_card_is_a_warning_not_an_error():
    f = check_rule_cards(_cat(_leaf(oracle_rules=[RULE], projections={"p": 1})))
    assert [(x.code, x.severity) for x in f] == [("rule_without_card", SEVERITY_WARNING)]


def test_a_card_reading_a_parameter_the_leaf_does_not_carry_is_an_error():
    cat = _cat(_leaf(oracle_rules=[RULE], projections={"p": 1}), {RULE: _card(parameters=["p", "missing"])})
    f = check_rule_cards(cat)
    assert [(x.code, x.severity) for x in f] == [("rule_card_unknown_parameter", SEVERITY_ERROR)]
    assert "missing" in f[0].message


def test_a_complete_card_is_clean_and_an_orphan_card_is_a_warning():
    cat = _cat(_leaf(oracle_rules=[RULE], projections={"p": 1}, governed_by_clauses=[CLAUSE]), {RULE: _card(parameters=["p"], clauses=[CLAUSE])})
    assert check_rule_cards(cat) == []
    cat["rule_cards"]["data.other.deny_y"] = _card()
    assert [(x.code, x.severity) for x in check_rule_cards(cat)] == [("rule_card_orphan", SEVERITY_WARNING)]


def test_a_card_citing_a_clause_the_leaf_does_not_list_is_a_warning():
    cat = _cat(_leaf(oracle_rules=[RULE], projections={"p": 1}, governed_by_clauses=[CLAUSE]), {RULE: _card(clauses=["urn:archinex:kb:clause:test:two"])})
    assert [(x.code, x.severity) for x in check_rule_cards(cat)] == [("rule_card_clause_not_on_leaf", SEVERITY_WARNING)]


def test_a_value_outside_the_enumeration_is_an_error_and_a_value_inside_is_not():
    ok = _cat(_leaf(projections={"isolation_level": "strict"}), enums=_isolation())
    assert check_enumerations(ok) == []
    bad = _cat(_leaf(projections={"isolation_level": "high_throughput"}), enums=_isolation())
    f = check_enumerations(bad)
    assert [(x.code, x.severity) for x in f] == [("value_outside_enumeration", SEVERITY_ERROR)]
    assert "shared, segmented, strict" in f[0].message


def test_the_enumeration_is_also_checked_inside_the_hydration_template():
    bad = _cat(_leaf(hydration_template={"security_zone": {"isolation_level": "lax"}}), enums=_isolation())
    assert [x.path for x in check_enumerations(bad)] == ["hydration_template.security_zone.isolation_level"]


def test_a_duplicated_enumeration_value_is_an_error():
    dup = {"isolation_level": {"ordered": True, "values": [{"value": "a", "definition": "x"}, {"value": "a", "definition": "y"}]}}
    assert [x.code for x in check_enumerations(_cat(_leaf(), enums=dup))] == ["enumeration_duplicate_value"]


def test_check_catalog_runs_the_new_families():
    codes = {x.code for x in check_catalog(_cat(_leaf(oracle_rules=[RULE], projections={"isolation_level": "x"}), enums=_isolation()))}
    assert {"rule_without_card", "value_outside_enumeration"} <= codes


# --- le catalogue livré ---------------------------------------------------------------------------------------------

def test_committed_catalog_validates_against_the_schema_with_its_new_sections():
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    jsonschema.validate(data, json.loads(SCHEMA.read_text(encoding="utf-8")))
    assert "isolation_level" in data["enumerations"] and data["rule_cards"]


def test_isolation_scale_is_ordered_weakest_first_with_five_levels():
    enum = load_catalog_document(CATALOG)["enumerations"]["isolation_level"]
    assert enum["ordered"] is True
    assert [v["value"] for v in enum["values"]] == ["shared", "segmented", "strict", "air-gap-logical", "air-gap-physical"]


@pytest.mark.parametrize(
    "leaf,expected_rules",
    [
        ("telecom:network:oob", {"deny_shared_oob_network", "deny_invalid_device_status", "deny_insufficient_interfaces",
                                 "deny_missing_oob_ip", "deny_bmc_oob_drift"}),
        ("security:zone:oam", {"deny_missing_oam_zone", "deny_weak_oam_isolation", "deny_unproxied_oam_access"}),
    ],
)
def test_oob_and_oam_carry_exactly_the_executable_rules_and_each_has_a_card(leaf, expected_rules):
    cat = load_catalog_document(CATALOG)
    e = cat["entities"][f"urn:archinex:ontology:{leaf}"]
    assert {r.rsplit(".", 1)[1] for r in e["oracle_rules"]} == expected_rules
    assert all(r in cat["rule_cards"] for r in e["oracle_rules"])


def test_oam_no_longer_names_the_umbrella_rule_and_oob_no_longer_declares_a_latency():
    cat = load_catalog_document(CATALOG)
    assert "deny_insecure_security_zone" not in json.dumps(cat)
    assert "max_latency_ms" not in cat["entities"]["urn:archinex:ontology:telecom:network:oob"]["projections"]


def test_user_plane_declares_a_real_isolation_level_and_a_separate_forwarding_profile():
    p = load_catalog_document(CATALOG)["entities"]["urn:archinex:ontology:security:zone:user_plane"]["projections"]
    assert p == {"forwarding_profile": "high_throughput", "isolation_level": "strict"}


def test_committed_catalog_has_no_error_from_any_family():
    findings = check_catalog(load_catalog_document(CATALOG))
    assert [f.to_dict() for f in findings if f.severity == SEVERITY_ERROR] == []
