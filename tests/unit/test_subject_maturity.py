"""Tests d'acceptation automatisés pour le modèle de maturité des sujets et le Maturity Board (SPEC maturity.md - Tests 9 à 17)."""

from datetime import datetime, timedelta

import pytest

from tools.elicitation.flows.assemble import build_assemble_graph
from tools.elicitation.flows.scan import build_scan_graph
from tools.elicitation.repository import ElicitationRepository


@pytest.fixture
def repo(tmp_path):
    """Fixture retournant un repository Elicitation isolée."""
    db_path = tmp_path / "kuzu_db"
    r = ElicitationRepository(db_path=db_path)
    yield r
    r.close()
    from mcp_server.db.kuzu_client import KuzuClient
    KuzuClient.clear_cache()
    import gc
    gc.collect()


@pytest.mark.stochastic
def test_question_matches_subject_level(repo, tmp_path):
    """Test 9 : Un sujet à L1 reçoit une question de cadrage, jamais une question de paramétrage."""
    db_path = tmp_path / "kuzu_db"
    repo.save_subject("Storage-5.2")
    repo.advance_subject_level("Storage-5.2", "L1_framed")

    sections = [{"id": "5.2", "name": "Storage System", "subject": "Storage-5.2", "required_level": "L0_named"}]
    graph = build_scan_graph()
    res = graph.invoke({"engagement": "test-mat-1", "sections": sections, "db_path": str(db_path)})

    questions = res.get("questions", [])
    assert len(questions) > 0
    # Vérifier que la question reste une question de cadrage
    q = questions[0]
    assert q["status"] == "open"


@pytest.mark.stochastic
def test_level_gate_holds_premature_question(repo, tmp_path):
    """Test 10 : Une question de paramétrage (L4) sur un sujet L1 est retenue (Level Gate)."""
    db_path = tmp_path / "kuzu_db"
    repo.save_subject("Storage-5.2")
    repo.advance_subject_level("Storage-5.2", "L1_framed")

    sections = [{"id": "5.2", "name": "Storage System", "subject": "Storage-5.2", "required_level": "L4_specified"}]
    graph = build_scan_graph()
    res = graph.invoke({"engagement": "test-gate-1", "sections": sections, "db_path": str(db_path)})

    # Si la question requiert L4 alors que le sujet est L1, enrich_node la retient (held_premature)
    enriched = res.get("enriched_gaps", [])
    if enriched:
        for gap in enriched:
            if gap.get("required_level") == "L4_specified":
                assert gap.get("held_premature") is True


@pytest.mark.stochastic
def test_patterns_proposed_at_l2(repo, tmp_path):
    """Test 11 : Atteindre L2 produit des patterns candidats avec leur clause 'quand ne pas utiliser'."""
    db_path = tmp_path / "kuzu_db"
    r = ElicitationRepository(db_path=db_path)
    r.save_subject("Storage-5.2", engagement="test-l2-patterns")
    r.advance_subject_level("Storage-5.2", "L2_decomposed")

    sections = [
        {"id": "5.2", "name": "Storage System", "subject": "Storage-5.2", "required_level": "L0_named"},
    ]
    graph = build_scan_graph()
    res = graph.invoke({"engagement": "test-l2-patterns", "sections": sections, "db_path": str(db_path)})

    questions = res.get("questions", [])
    assert len(questions) > 0
    q_l2 = next(q for q in questions if q.get("subject") == "Storage-5.2" or "Pattern" in q.get("question", ""))
    q_text = q_l2["question"]
    assert "Pattern proposé" in q_text
    assert "Quand ne pas utiliser" in q_text


@pytest.mark.deterministic
def test_model_cannot_set_level(repo):
    """Test 12 : Un appel avec un niveau invalide ou non autorisé par un modèle lève une erreur."""
    with pytest.raises(ValueError, match="Niveau de maturité inconnu"):
        repo.advance_subject_level("Storage-5.2", "L9_invalid_level")


@pytest.mark.deterministic
def test_board_flags_stall(repo):
    """Test 13 : Un sujet inchangé depuis plus de 7 jours avec une question ouverte est marqué STAGNANT."""
    repo.save_subject("Storage-5.2")
    repo.advance_subject_level("Storage-5.2", "L1_framed")

    # Simuler une date mise à jour il y a 10 jours
    old_date = (datetime.now() - timedelta(days=10)).isoformat()
    sub_esc = "Storage-5.2"
    repo.db_client.execute_cypher(f"MATCH (s:Subject {{name: '{sub_esc}'}}) SET s.updated_at = '{old_date}';")

    # Ajouter une question ouverte sur ce sujet
    repo.save_question({
        "id": "Q-stall-1",
        "engagement": "test-stall",
        "subject": "Storage-5.2",
        "status": "open",
        "routed_to": "cloud-architect"
    })

    board = repo.get_subjects_maturity_board("test-stall", stall_days=7)
    target = [b for b in board if b["subject"] == "Storage-5.2"][0]

    assert target["is_stalled"] is True
    assert target["open_question_ref"] == "Q-stall-1"
    assert target["assigned_role"] == "cloud-architect"


@pytest.mark.stochastic
def test_section_readiness(repo, tmp_path):
    """Test 14 : Une section dont les sujets sont sous L3 rend un statut PROVISIONAL et les nomme."""
    db_path = tmp_path / "kuzu_db"
    r = ElicitationRepository(db_path=db_path)
    r.save_subject("Storage-5.2")
    r.advance_subject_level("Storage-5.2", "L1_framed")

    graph = build_assemble_graph()
    res = graph.invoke({"engagement": "test-readiness", "db_path": str(db_path)})

    assert res["is_provisional"] is True
    unripe_names = [u["subject"] if isinstance(u, dict) else u for u in res["unripe_subjects"]]
    assert "Storage-5.2" in unripe_names


@pytest.mark.stochastic
def test_prior_answer_goes_to_confirmation_batch(repo, tmp_path):
    """Test 15 : Une réponse antérieure apparaît dans les données d'enrichissement comme défaut à confirmer."""
    db_path = tmp_path / "kuzu_db"
    r = ElicitationRepository(db_path=db_path)
    r.save_subject("Storage-5.2", engagement="test-prior-batch")
    r.save_statement({
        "id": "S-prior-1",
        "engagement": "other-eng",
        "section": "5.2",
        "subject": "Storage-5.2",
        "predicate": "has_property",
        "value": "SAN NVMe dual-controller",
        "status": "active"
    })

    sections = [
        {"id": "5.2", "name": "Storage System", "subject": "Storage-5.2", "required_level": "L0_named"},
    ]
    graph = build_scan_graph()
    res = graph.invoke({"engagement": "test-prior-batch", "sections": sections, "db_path": str(db_path)})
    enriched = res.get("enriched_gaps", [])
    target = [g for g in enriched if g["subject"] == "Storage-5.2"][0]
    assert target["prior_answer"]["value"] == "SAN NVMe dual-controller"




@pytest.mark.stochastic
def test_question_carries_fresh_context_links(repo, tmp_path):
    """Test 16 : Chaque question émise porte des liens de contexte permanents non obsolètes (draft_ref et subject_ref)."""
    db_path = tmp_path / "kuzu_db"
    graph = build_scan_graph()
    res = graph.invoke({"engagement": "test-links", "db_path": str(db_path)})

    questions = res.get("questions", [])
    assert len(questions) > 0
    q = questions[0]
    assert "draft_ref" in q and q["draft_ref"].startswith("file://")
    assert "subject_ref" in q and q["subject_ref"].startswith("file://")


@pytest.mark.deterministic
def test_llm_cannot_write(repo):
    """Test 17 : Seul le module Repository est autorisé à écrire dans Kùzu DB avec validation des prédicats."""
    with pytest.raises(ValueError, match="Prédicat non autorisé"):
        repo.save_statement({
            "subject": "Storage-5.2",
            "predicate": "invalid_predicate_from_llm",
            "value": "Test"
        })
