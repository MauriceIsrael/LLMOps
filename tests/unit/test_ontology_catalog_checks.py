"""Cohérence interne des feuilles, pureté d'intention et contrat d'export du catalogue (issues #190, #191)."""

import json
from pathlib import Path

import jsonschema
from typer.testing import CliRunner

from pipelines.kb_cli import app
from pipelines.ontology.catalog_checks import (
    SEVERITY_ERROR,
    SEVERITY_WARNING,
    check_catalog,
    check_intention_purity,
    check_leaf_coherence,
    has_errors,
)
from pipelines.ontology.catalog_file import load_catalog_document

ROOT = Path(__file__).parent.parent.parent
CATALOG = ROOT / "data" / "snapshots" / "ontology_export.json"
SCHEMA = ROOT / "schemas" / "ontology_catalog.schema.json"
U = "urn:archinex:ontology:test:leaf"


def _leaf(**kw):
    return {"urn": U, "revision": 1, "kind": "leaf", "title": "t", **kw}


def test_rules_without_projections_is_an_error():
    f = check_leaf_coherence({U: _leaf(oracle_rules=["data.x.deny_y"])})
    assert [(x.code, x.severity) for x in f] == [("oracle_rules_without_projections", SEVERITY_ERROR)]


def test_projections_without_clauses_is_a_warning_and_complete_leaf_is_clean():
    f = check_leaf_coherence({U: _leaf(projections={"cipher": "AES-256-GCM"})})
    assert [(x.code, x.severity) for x in f] == [("projections_without_clauses", SEVERITY_WARNING)]
    clean = _leaf(oracle_rules=["r"], projections={"cipher": "AES-256-GCM"}, governed_by_clauses=["urn:archinex:kb:clause:a:b"])
    assert check_leaf_coherence({U: clean}) == []


def test_instantiation_values_are_refused_in_projections_and_graph_model():
    ents = {
        U: _leaf(
            projections={"peer": "10.1.2.3", "net": "192.168.99.0/24", "hw": "aa:bb:cc:dd:ee:ff", "v6": "2001:db8::1:2"},
            hydration_template={"reconciliation_graph": {"ip_underlay_links": [{"subnet": "198.51.100.0/30"}]}},
        )
    }
    kinds = sorted(f.message.split()[0] for f in check_intention_purity(ents))
    assert kinds == ["ipv4", "ipv4", "ipv4", "ipv6", "mac"]
    assert all(f.severity == SEVERITY_ERROR for f in check_intention_purity(ents))


def test_generic_values_versions_and_ordinary_templates_are_not_flagged():
    ents = {
        U: _leaf(
            projections={"k8s": "1.28.11", "default_route": "0.0.0.0/0", "protocol": "IPsec-ESP-IKEv2"},
            # Un gabarit d'hydratation génère par nature des valeurs par défaut : non contrôlé hors reconciliation_graph.
            hydration_template={"network_segment": {"subnet": "192.168.99.0/24"}},
        )
    }
    assert check_intention_purity(ents) == []


def test_committed_catalog_has_no_error():
    findings = check_catalog(load_catalog_document(CATALOG))
    assert not has_errors(findings), [f.to_dict() for f in findings if f.severity == SEVERITY_ERROR]


def test_committed_catalog_satisfies_its_schema_and_the_export_contract():
    """Contrat d'export : champs garantis aux consommateurs (Archinex lit `entities`, `triplets`, `clause_index`)."""
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    jsonschema.validate(data, json.loads(SCHEMA.read_text(encoding="utf-8")))
    for guaranteed in ("catalog_version", "generated_at", "entities", "triplets", "clause_index"):
        assert guaranteed in data, f"guaranteed export field lost: {guaranteed}"
    for urn, e in data["entities"].items():
        for field in ("urn", "revision", "kind", "title"):
            assert field in e, f"{urn}: guaranteed entity field lost: {field}"
        assert e["urn"] == urn


def test_cli_exit_codes(tmp_path):
    runner = CliRunner()
    ok = runner.invoke(app, ["ontology", "catalog-check", "--catalog", str(CATALOG)])
    assert ok.exit_code == 0, ok.output

    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"entities": {U: _leaf(oracle_rules=["r"])}}), encoding="utf-8")
    res = runner.invoke(app, ["ontology", "catalog-check", "--catalog", str(bad)])
    assert res.exit_code == 1
    assert "oracle_rules_without_projections" in res.output

    # --strict : un avertissement suffit à échouer.
    warn = tmp_path / "warn.json"
    warn.write_text(json.dumps({"entities": {U: _leaf(projections={"a": "b"})}}), encoding="utf-8")
    assert runner.invoke(app, ["ontology", "catalog-check", "--catalog", str(warn)]).exit_code == 0
    assert runner.invoke(app, ["ontology", "catalog-check", "--catalog", str(warn), "--strict"]).exit_code == 1
