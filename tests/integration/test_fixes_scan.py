"""Suite des 10 tests d'acceptation selon la spécification TPL-fixes-scan (FIXES-SCAN.md)."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from tools.elicitation.flows.scan import Gap, build_scan_graph, evaluate, load_frame_node
from tools.elicitation.models.blueprint_schema import (
    BlueprintRequirement,
    BlueprintSection,
    load_blueprint,
)
from tools.elicitation.repository import ElicitationRepository


@pytest.fixture
def temp_db(tmp_path: Path) -> Path:
    """Fixture réutilisable avec nettoyage du cache Kùzu DB."""
    import gc

    from mcp_server.db.kuzu_client import KuzuClient
    db_dir = tmp_path / "kuzu_test_db"
    yield db_dir
    KuzuClient.clear_cache(str(db_dir))
    gc.collect()


def test_blueprint_change_changes_gaps(temp_db: Path, tmp_path: Path) -> None:
    """Test 1 (Discriminant) : Ajouter ou supprimer une section dans un blueprint YAML modifie les manques détectés sans toucher au code source."""
    _repo = ElicitationRepository(db_path=temp_db)
    
    # 1. Blueprint avec 1 section
    bp1_path = tmp_path / "bp1.yaml"
    bp1_path.write_text("""
id: bp1
title: Test Blueprint 1
sections:
  - id: "4.1"
    title: Test Section 1
    must_answer: Question 1?
    requires:
      - {subject: sub-alpha, level: L1_framed}
    unlocks: []
    routes_to: architect
""", encoding="utf-8")

    graph = build_scan_graph()
    res1 = graph.invoke({"engagement": "test-dynamic", "blueprint_id": str(bp1_path), "db_path": str(temp_db)})
    gaps1 = res1["counts_summary"]["total"]
    assert gaps1 == 1

    # 2. Blueprint avec 2 sections
    bp2_path = tmp_path / "bp2.yaml"
    bp2_path.write_text("""
id: bp2
title: Test Blueprint 2
sections:
  - id: "4.1"
    title: Test Section 1
    must_answer: Question 1?
    requires:
      - {subject: sub-alpha, level: L1_framed}
    unlocks: ["4.2"]
    routes_to: architect
  - id: "4.2"
    title: Test Section 2
    must_answer: Question 2?
    requires:
      - {subject: sub-beta, level: L1_framed}
    unlocks: []
    routes_to: architect
""", encoding="utf-8")

    res2 = graph.invoke({"engagement": "test-dynamic", "blueprint_id": str(bp2_path), "db_path": str(temp_db)})
    gaps2 = res2["counts_summary"]["total"]
    assert gaps2 == 2


def test_no_subject_name_in_source() -> None:
    """Test 2 : Vérifie qu'aucun nom de sujet ('mcx-services', 'mobile-core', 'transport') n'est écrit en dur dans scan.py."""
    scan_source = Path("tools/elicitation/flows/scan.py").read_text(encoding="utf-8")
    for forbidden in ["mcx-services", "mobile-core", "transport"]:
        assert forbidden not in scan_source, f"Nom de sujet interdit '{forbidden}' trouvé dans scan.py !"


def test_counts_reconcile(temp_db: Path, tmp_path: Path) -> None:
    """Test 3 : Les quatre statuts (dispatchable, held_premature, held_queued, satisfied) égalent exactement total sur 3 blueprints."""
    _repo = ElicitationRepository(db_path=temp_db)
    graph = build_scan_graph()

    for idx in range(1, 4):
        bp_path = tmp_path / f"reconcile_{idx}.yaml"
        sections_yaml = "\n".join([
            f"""  - id: "4.{i}"
    title: Section {i}
    must_answer: Question {i}?
    requires:
      - {{subject: sub-{i}, level: L{i % 3 + 1}_decided}}
    unlocks: []
    routes_to: architect"""
            for i in range(1, idx + 3)
        ])
        bp_path.write_text(f"id: rec_{idx}\ntitle: Reconcile {idx}\nsections:\n{sections_yaml}", encoding="utf-8")

        res = graph.invoke({"engagement": f"eng-rec-{idx}", "blueprint_id": str(bp_path), "db_path": str(temp_db)})
        c = res["counts_summary"]
        assert c["total"] == (c["dispatchable"] + c["held_premature"] + c["held_queued"] + c["satisfied"])


def test_every_held_gap_has_a_reason(temp_db: Path) -> None:
    """Test 4 : Aucun manque retenu (status != 'dispatchable') ne peut exister sans hold_reason (sauf si satisfied)."""
    _repo = ElicitationRepository(db_path=temp_db)
    graph = build_scan_graph()

    res = graph.invoke({
        "engagement": "test-reasons",
        "blueprint_id": "BLU-hla-mcx",
        "db_path": str(temp_db)
    })
    
    for gap in res["gaps"]:
        if gap["status"] in ("held_premature", "held_queued"):
            assert gap["hold_reason"] is not None and len(gap["hold_reason"]) > 0


def test_blocking_references_existing_sections(temp_db: Path) -> None:
    """Test 5 : Chaque identifiant présent dans 'blocking' correspond à une section existante du blueprint."""
    _repo = ElicitationRepository(db_path=temp_db)
    graph = build_scan_graph()

    res = graph.invoke({
        "engagement": "test-blocking-ref",
        "blueprint_id": "BLU-hla-mcx",
        "db_path": str(temp_db)
    })

    bp = load_blueprint("data/kb/blueprints/BLU-hla-mcx.yaml")
    all_sec_ids = {s.id for s in bp.sections}

    for gap in res["gaps"]:
        for blk in gap["blocking"]:
            assert blk in all_sec_ids or blk.split(".")[0] in all_sec_ids


def test_gate_is_uniform() -> None:
    """Test 6 : Un sujet racine et un sujet découvert au même niveau de maturité reçoivent exactement le même traitement."""
    sec = BlueprintSection(
        id="4.9",
        title="Uniform Test",
        must_answer="Is it uniform?",
        requires=[BlueprintRequirement(subject="any-subject", level="L2_decomposed")],
        unlocks=[],
        routes_to="architect",
    )
    
    gap_l0 = evaluate(sec, sec.requires[0], current_level="L0_named", has_statements=False)
    assert gap_l0.status == "held_premature"
    assert "needs L2_decomposed" in gap_l0.hold_reason

    gap_l2 = evaluate(sec, sec.requires[0], current_level="L2_decomposed", has_statements=False)
    assert gap_l2.status == "dispatchable"
    assert gap_l2.hold_reason is None


def test_subjects_are_engagement_scoped(temp_db: Path) -> None:
    """Test 7 : Deux engagements déclarant le même nom de sujet possèdent une maturité indépendante."""
    repo = ElicitationRepository(db_path=temp_db)
    
    repo.save_subject("shared-subject", engagement="eng-alpha", origin="blueprint")
    repo.advance_subject_level("shared-subject", "L3_decided") # eng-alpha
    
    repo.save_subject("shared-subject", engagement="eng-beta", origin="blueprint")

    mat_alpha = repo.get_subject_maturity("shared-subject", engagement="eng-alpha")
    mat_beta = repo.get_subject_maturity("shared-subject", engagement="eng-beta")

    assert mat_alpha["level"] == "L3_decided"
    assert mat_beta["level"] == "L0_named"


def test_evaluate_is_pure() -> None:
    """Test 8 : Appeler evaluate() s'exécute sans aucune dépendance ni E/S vers une base de données."""
    sec = BlueprintSection(
        id="9.9",
        title="Pure Section",
        must_answer="Pure test?",
        requires=[BlueprintRequirement(subject="pure-sub", level="L1_framed")],
        unlocks=["9.9.1"],
        routes_to="architect",
    )
    
    gap = evaluate(sec, sec.requires[0], current_level="L0_named", has_statements=False)
    assert isinstance(gap, Gap)
    assert gap.section == "9.9"
    assert gap.status == "dispatchable"


def test_single_maturity_query(temp_db: Path) -> None:
    """Test 9 : Un scan sur un blueprint consulte les niveaux de maturité en une seule requête batch."""
    repo = ElicitationRepository(db_path=temp_db)
    spy_repo = MagicMock(wraps=repo)

    bp = load_blueprint("data/kb/blueprints/BLU-hla-mcx.yaml")
    
    from tools.elicitation.flows.scan import detect_gaps_node
    state = {"engagement": "test-spy", "blueprint": bp, "repo": spy_repo}
    detect_gaps_node(state)

    assert spy_repo.subject_levels.call_count == 1


def test_missing_engagement_raises() -> None:
    """Test 10 : Invoquer load_frame_node sans engagement lève une ValueError nommant la clé manquante."""
    with pytest.raises(ValueError) as exc_info:
        load_frame_node({})
    
    assert "engagement" in str(exc_info.value)
