"""Migration additive du catalogue depuis la fixture d'un consommateur (issue #192)."""

import json
from pathlib import Path

import pytest

from pipelines.ontology.catalog import validate_clause_leaf_integrity
from pipelines.ontology.catalog_checks import SEVERITY_ERROR, SEVERITY_WARNING, check_catalog
from pipelines.ontology.catalog_file import load_catalog_document
from scripts.migrate_ontology_from_fixture import (
    PROJECT_MARK,
    URN_TWINS,
    Report,
    _extends,
    migrate,
    retire_urn_twins,
)

ROOT = Path(__file__).parent.parent.parent
CLAUSE = "urn:archinex:kb:clause:test:one"


def _leaf(urn, **kw):
    return {"urn": urn, "revision": 1, "kind": "leaf", "title": urn.split(":")[-1], **kw}


def _cat(entities, triplets=()):
    return {"catalog_version": "1.0", "generated_at": "2026-01-01T00:00:00Z", "entities": entities, "triplets": list(triplets)}


U1, U2, U3 = (f"urn:archinex:ontology:test:{n}" for n in ("a", "b", "c"))


def test_adds_missing_entities_and_keeps_hub_values_on_conflict():
    hub = _cat({U1: _leaf(U1, title="Titre du Hub", domain="d1")})
    src = _cat({U1: _leaf(U1, title="Titre de la source", domain="d2"), U2: _leaf(U2)})
    out, rep = migrate(hub, src)
    assert U2 in out["entities"] and rep.added_entities == [U2]
    assert out["entities"][U1]["title"] == "Titre du Hub"
    assert out["entities"][U1]["domain"] == "d1"  # conflit : conservé côté Hub
    assert any(c["field"] == "domain" for c in rep.conflicts)


def test_missing_field_is_filled_and_revision_is_bumped_but_unchanged_entity_is_not():
    hub = _cat({U1: _leaf(U1), U2: _leaf(U2, keywords=["x"])})
    src = _cat({U1: _leaf(U1, keywords=["k1", "k2"]), U2: _leaf(U2, keywords=["x"])})
    out, rep = migrate(hub, src)
    assert out["entities"][U1]["keywords"] == ["k1", "k2"] and out["entities"][U1]["revision"] == 2
    assert out["entities"][U2]["revision"] == 1 and U2 not in rep.enriched


def test_a_source_that_only_adds_to_the_hub_is_an_enrichment_not_a_conflict():
    hub = _cat({U1: _leaf(U1, oracle_rules=["r"], projections={"a": 1})})
    src = _cat({U1: _leaf(U1, oracle_rules=["r"], projections={"a": 1, "b": 2})})
    out, rep = migrate(hub, src)
    assert out["entities"][U1]["projections"] == {"a": 1, "b": 2}
    assert rep.conflicts == []
    assert _extends({"a": 1, "b": 2}, {"a": 1}) and not _extends({"a": 2}, {"a": 1})


def test_rules_and_projections_are_a_bundle_never_mixed():
    hub = _cat({U1: _leaf(U1, oracle_rules=["hub_rule"], projections={"p": 1})})
    src = _cat({U1: _leaf(U1, oracle_rules=["src_rule"], projections={"q": 2})})
    out, rep = migrate(hub, src)
    assert out["entities"][U1]["oracle_rules"] == ["hub_rule"]
    assert out["entities"][U1]["projections"] == {"p": 1}
    assert [c["field"] for c in rep.conflicts] == ["oracle_rules+projections"]


def test_project_data_does_not_migrate():
    src = _cat({U1: _leaf(
        U1,
        governed_by_clauses=[CLAUSE, "REQ-Lot1-1343"],
        keywords=["ipsec", "lot3", "tunnel"],
        projections={"cipher": "AES-256-GCM", "required_hops": ["secgw-lot1-01"]},
        oracle_rules=["r"],
        hydration_template={"crypto_profile": "x", "partner_tenant_id": "org-lot3-mno"},
    )})
    out, rep = migrate(_cat({}), src)
    e = out["entities"][U1]
    assert e["governed_by_clauses"] == [CLAUSE]
    assert e["keywords"] == ["ipsec", "tunnel"]
    assert e["projections"] == {"cipher": "AES-256-GCM"}
    assert e["hydration_template"] == {"crypto_profile": "x"}
    assert not PROJECT_MARK.search(json.dumps(e))
    assert len(rep.stripped) == 4


def test_rules_without_their_parameters_are_not_migrated():
    src = _cat({U1: _leaf(U1, oracle_rules=["r"], projections={"only_instance": "secgw-lot1-01"})})
    out, _ = migrate(_cat({}), src)
    assert "oracle_rules" not in out["entities"][U1] and "projections" not in out["entities"][U1]


def test_satisfies_clause_triplets_are_generated_with_their_provenance_and_integrity_holds():
    src = _cat({U1: _leaf(U1, governed_by_clauses=[CLAUSE])})
    out, rep = migrate(_cat({}), src)
    sc = [t for t in out["triplets"] if t["predicate"] == "satisfies_clause"]
    assert [(t["subject"], t["object"]) for t in sc] == [(U1, CLAUSE)]
    assert "fixture" in sc[0]["rationale"] and sc[0]["rationale"].strip()
    assert validate_clause_leaf_integrity(out) == []
    assert out["clause_index"]["by_clause"][CLAUSE] == [U1]


def test_triplets_are_merged_without_loss_and_colliding_ids_are_renumbered():
    t_hub = {"id": "tr-001", "subject": U1, "predicate": "depends_on", "object": U2, "rationale": "r"}
    t_src_same_id = {"id": "tr-001", "subject": U2, "predicate": "depends_on", "object": U1, "rationale": "r2"}
    t_src_dup = {"id": "tr-099", "subject": U1, "predicate": "depends_on", "object": U2, "rationale": "r"}
    hub = _cat({U1: _leaf(U1), U2: _leaf(U2)}, [t_hub])
    src = _cat({U1: _leaf(U1), U2: _leaf(U2)}, [t_src_same_id, t_src_dup])
    out, rep = migrate(hub, src)
    assert t_hub in out["triplets"]
    assert any(t["subject"] == U2 and t["object"] == U1 and t["id"].startswith("tr-mig-") for t in out["triplets"])
    assert [i for i, _ in rep.triplets_skipped] == ["tr-099"]  # même triplet déjà présent
    assert len({t["id"] for t in out["triplets"]}) == len(out["triplets"])


def test_triplet_pointing_to_a_project_requirement_is_skipped():
    src = _cat({U1: _leaf(U1)}, [{"id": "t", "subject": U1, "predicate": "satisfies_clause", "object": "REQ-Lot1-9", "rationale": "x"}])
    out, rep = migrate(_cat({}), src)
    assert out["triplets"] == []
    assert rep.triplets_skipped[0][0] == "t"


def test_the_migration_never_loses_a_hub_value():
    hub = _cat({U1: _leaf(U1, keywords=["a"], projections={"p": 1}, oracle_rules=["r"])})
    src = _cat({U1: _leaf(U1, keywords=["b"], projections={"p": 2}, oracle_rules=["r"])})
    out, _ = migrate(hub, src)
    e = out["entities"][U1]
    assert e["projections"] == {"p": 1} and e["oracle_rules"] == ["r"]
    assert "a" in e["keywords"]


# --- Le catalogue versionné après migration ---------------------------------------------------------------------

CATALOG = ROOT / "data" / "snapshots" / "ontology_export.json"


def test_committed_catalog_has_no_project_data():
    text = CATALOG.read_text(encoding="utf-8")
    assert not PROJECT_MARK.search(text), "une marque de projet (lot, nom de projet, REQ-) est revenue dans le catalogue"


def test_committed_catalog_keeps_clause_leaf_integrity_and_has_no_error():
    cat = load_catalog_document(CATALOG)
    assert validate_clause_leaf_integrity(cat) == []
    findings = check_catalog(cat)
    assert not [f for f in findings if f.severity == SEVERITY_ERROR]


def test_every_leaf_with_rules_has_its_parameters():
    cat = load_catalog_document(CATALOG)
    for urn, e in cat["entities"].items():
        if e.get("kind") == "leaf" and e.get("oracle_rules"):
            assert e.get("projections"), urn


def test_known_duplicate_triplet_ids_are_reported_as_warnings():
    """Le Hub portait déjà trois identifiants dupliqués (tr-014 à tr-016) : signalés, pas renumérotés ici."""
    dups = [f for f in check_catalog(load_catalog_document(CATALOG)) if f.code == "duplicate_triplet_id"]
    assert {f.urn for f in dups} == {"tr-014", "tr-015", "tr-016"}
    assert all(f.severity == SEVERITY_WARNING for f in dups)


def test_guard_fails_when_project_data_would_survive(monkeypatch):
    import scripts.migrate_ontology_from_fixture as m

    monkeypatch.setattr(m, "sanitize_entity", lambda urn, e, rep: e)  # simule un nettoyage défaillant
    src = _cat({U3: _leaf(U3, title="Passerelle Lot 3")})
    with pytest.raises(SystemExit, match="Marque de projet résiduelle"):
        m.migrate(_cat({}), src)


def _t(i, s, p, o):
    return {"id": i, "subject": s, "predicate": p, "object": o, "rationale": "r"}


def test_a_twin_is_retired_and_its_relations_move_to_the_kept_urn_without_loss():
    axis, twin_axis, leaf, plat = (f"urn:archinex:ontology:axis:{n}" for n in ("kept", "twin", "leaf", "plat"))
    entities = {axis: {"urn": axis, "kind": "axis"}, twin_axis: {"urn": twin_axis, "kind": "axis"}, leaf: _leaf(leaf), plat: {"urn": plat, "kind": "concept"}}
    triplets = [
        _t("t1", plat, "requires_aspect", axis),
        _t("t2", plat, "requires_aspect", twin_axis),   # déjà porté par t1 sur l'URN conservée : écarté
        _t("t3", twin_axis, "implemented_by", leaf),    # absent de l'URN conservée : reporté
    ]
    rep = Report()
    out_e, out_t = retire_urn_twins(entities, triplets, {twin_axis: axis}, rep)
    assert twin_axis not in out_e and axis in out_e
    assert {(t["subject"], t["predicate"], t["object"]) for t in out_t} == {(plat, "requires_aspect", axis), (axis, "implemented_by", leaf)}
    assert rep.twin_triplets_dropped == ["t2"] and rep.twin_triplets_repointed == ["t3"]
    assert rep.twins_retired == [(twin_axis, axis)]


def test_a_twin_whose_equivalent_is_missing_is_never_retired():
    twin, other = "urn:archinex:ontology:axis:twin", "urn:archinex:ontology:axis:absent"
    entities = {twin: {"urn": twin, "kind": "axis"}}
    out_e, out_t = retire_urn_twins(entities, [], {twin: other}, Report())
    assert twin in out_e and out_t == []


def test_committed_catalog_has_none_of_the_known_urn_twins_and_no_dangling_relation():
    cat = load_catalog_document(CATALOG)
    assert not set(URN_TWINS) & set(cat["entities"])
    for t in cat["triplets"]:
        for end in (t["subject"], t["object"]):
            assert end not in URN_TWINS, t["id"]
    assert all(kept in cat["entities"] for kept in URN_TWINS.values())
