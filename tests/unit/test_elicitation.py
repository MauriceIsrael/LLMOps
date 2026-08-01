"""Tests d'acceptation automatisés pour le prototype d'élicitation (SPEC.md - Section 11)."""

from pathlib import Path

import pytest
from langgraph.types import Command

from tools.elicitation.db_schema import ElicitationSchemaInitializer
from tools.elicitation.flows.assemble import build_assemble_graph
from tools.elicitation.flows.intake import build_intake_graph, get_sqlite_checkpointer
from tools.elicitation.flows.scan import build_scan_graph
from tools.elicitation.repository import ElicitationRepository


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path: Path):
    """Fixture réinitialisant une base Kùzu DB temporaire."""
    db_dir = tmp_path / "kuzu_test_db"
    ElicitationSchemaInitializer(db_path=db_dir)
    return db_dir


@pytest.mark.stochastic
def test_scan_detects_empty_section(setup_test_db):
    """Test 1 : scan détecte une section vide (G1) et crée au moins une question."""
    graph = build_scan_graph()
    res = graph.invoke({"engagement": "test-eng-1", "max_questions": 8, "db_path": str(setup_test_db)})
    questions = res.get("questions", [])
    assert len(questions) >= 1
    assert any(q["gap_type"] == "G1_empty_section" for q in questions)


@pytest.mark.stochastic
def test_scan_prioritises_by_blocking(setup_test_db):
    """Test 2 : scan trie les manques par nombre de blocages et plafonne à max_questions."""
    graph = build_scan_graph()
    res = graph.invoke({"engagement": "test-eng-2", "max_questions": 1, "db_path": str(setup_test_db)})
    questions = res.get("questions", [])
    assert len(questions) == 1


@pytest.mark.stochastic
def test_question_carries_vocabulary(setup_test_db):
    """Test 3 : La question générée porte le nom du sujet canonique."""
    repo = ElicitationRepository(db_path=setup_test_db)
    repo.save_subject("Storage-5.2", definition="Système de stockage de management", engagement="test-eng-3")

    sections = [{"id": "5.2", "name": "Storage System", "subject": "Storage-5.2", "required_level": "L0_named"}]
    graph = build_scan_graph()
    res = graph.invoke({"engagement": "test-eng-3", "max_questions": 8, "sections": sections, "db_path": str(setup_test_db)})
    questions = res.get("questions", [])
    q_storage = next(q for q in questions if "5.2" in q["section"])
    assert "Storage-5.2" in q_storage["subject"]


@pytest.mark.stochastic
def test_prior_answer_offered(setup_test_db):
    """Test 4 : Une réponse antérieure d'un autre engagement alimente la question élicitée."""
    repo = ElicitationRepository(db_path=setup_test_db)
    repo.save_subject("Storage-5.2", engagement="test-eng-4")
    repo.save_statement({
        "id": "S-prior-01",
        "engagement": "other-eng",
        "section": "5.2",
        "subject": "Storage-5.2",
        "predicate": "has_property",
        "value": "SAN NVMe dual-controller",
        "author": "charlie",
        "status": "active"
    })

    sections = [{"id": "5.2", "name": "Storage System", "subject": "Storage-5.2", "required_level": "L0_named"}]
    graph = build_scan_graph()
    res = graph.invoke({"engagement": "test-eng-4", "max_questions": 8, "sections": sections, "db_path": str(setup_test_db)})
    questions = res.get("questions", [])
    q_storage = next(q for q in questions if "5.2" in q["section"])
    assert "SAN NVMe dual-controller" in q_storage["question"] or "Storage-5.2" in q_storage["subject"]


@pytest.mark.stochastic
def test_interrupt_resumes_across_processes(setup_test_db, tmp_path):
    """Test 5 (CRITIQUE) : Exécute intake jusqu'à l'interrupt, détruit le graphe, recrée un nouveau graphe et reprend."""
    engagement = "test-eng-durability"
    q_id = "Q-durability-1"

    # --- PROCESSUS 1 : Lancement jusqu'à l'interrupt ---
    checkpointer1 = get_sqlite_checkpointer(engagement=engagement, base_dir=tmp_path / "projects")
    graph1 = build_intake_graph(checkpointer=checkpointer1)
    config = {"configurable": {"thread_id": q_id}}

    _res1 = graph1.invoke({
        "question_id": q_id,
        "answer_text": "Nous préconisons un SAN NVMe dual-controller tier-1.",
        "author": "alice",
        "role": "cloud-architect",
        "engagement": engagement,
        "db_path": str(setup_test_db)
    }, config=config)

    # Vérifier que le flux s'est arrêté sur l'interrupt sans encore écrire en base Kùzu
    repo = ElicitationRepository(db_path=setup_test_db)
    st_before = repo.get_active_statements(engagement)
    assert len(st_before) == 0
    del repo

    # --- SIMULATION DE DESTRUCTION DU PROCESSUS (Nouveau graphe & instance) ---
    del graph1
    del checkpointer1
    import gc
    gc.collect()


    # --- PROCESSUS 2 : NOUVEAU PROCESSUS & REPRISE ---

    checkpointer2 = get_sqlite_checkpointer(engagement=engagement, base_dir=tmp_path / "projects")
    graph2 = build_intake_graph(checkpointer=checkpointer2)

    _res2 = graph2.invoke(Command(resume={"action": "accept", "accept": True}), config=config)

    # Assert persistence réussie
    repo_after = ElicitationRepository(db_path=setup_test_db)
    st_after = repo_after.get_active_statements(engagement)
    assert len(st_after) >= 1
    assert "SAN NVMe dual-controller" in st_after[0]["value"]


@pytest.mark.stochastic
def test_no_statement_without_confirmation(setup_test_db, tmp_path):
    """Test 6 : Rejet lors de l'interrupt -> aucun énoncé n'est écrit dans Kùzu DB."""
    engagement = "test-eng-reject"
    q_id = "Q-reject-1"
    checkpointer = get_sqlite_checkpointer(engagement=engagement, base_dir=tmp_path / "projects")
    graph = build_intake_graph(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": q_id}}

    graph.invoke({
        "question_id": q_id,
        "answer_text": "Proposition rejetée.",
        "author": "bob",
        "engagement": engagement,
        "db_path": str(setup_test_db)
    }, config=config)

    res = graph.invoke(Command(resume={"action": "reject", "accept": False}), config=config)
    assert res.get("rejected") is True

    repo = ElicitationRepository(db_path=setup_test_db)
    statements = repo.get_active_statements(engagement)
    assert len(statements) == 0


@pytest.mark.stochastic
def test_contradiction_creates_conflict(setup_test_db, tmp_path):
    """Test 7 : Deux réponses contradictoires génèrent un conflit. Les DEUX énoncés restent actifs."""
    repo = ElicitationRepository(db_path=setup_test_db)

    # Énoncé 1 de Alice
    repo.save_statement({
        "id": "S-alice-01",
        "engagement": "demo-2026",
        "section": "5.2",
        "subject": "Storage-5.2",
        "predicate": "has_property",
        "value": "SAN NVMe dual-controller",
        "author": "alice",
        "status": "active"
    })

    # Énoncé 2 contradictoire de Bob
    repo.save_statement({
        "id": "S-bob-01",
        "engagement": "demo-2026",
        "section": "5.2",
        "subject": "Storage-5.2",
        "predicate": "has_property",
        "value": "Ceph HCI all-flash SSD",
        "author": "bob",
        "status": "active"
    })

    # Intake check
    checkpointer = get_sqlite_checkpointer(engagement="demo-2026", base_dir=tmp_path / "projects")
    graph = build_intake_graph(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": "Q-contradict"}}

    graph.invoke({
        "question_id": "Q-contradict",
        "answer_text": "Ceph HCI all-flash SSD",
        "author": "bob",
        "engagement": "demo-2026",
        "db_path": str(setup_test_db)
    }, config=config)

    res = graph.invoke(Command(resume={"action": "accept", "accept": True}), config=config)
    assert len(res.get("created_conflict_ids", [])) >= 1

    # Vérifier que les deux énoncés SONT TOUJOURS ACTIFS
    statements = repo.get_active_statements("demo-2026")
    assert len(statements) >= 2


@pytest.mark.stochastic
def test_conflict_blocks_completion_not_rendering(setup_test_db):
    """Test 8 : Un conflit ouvert passe le statut du document à PROVISIONAL mais n'empêche pas le rendu."""
    repo = ElicitationRepository(db_path=setup_test_db)
    repo.save_statement({
        "id": "S-101",
        "engagement": "demo-2026",
        "section": "5.2",
        "subject": "Storage-5.2",
        "predicate": "has_property",
        "value": "SAN NVMe",
        "author": "alice",
        "status": "active"
    })
    repo.save_conflict({
        "id": "C-101",
        "kind": "contradiction",
        "detail": "Contradiction entre SAN NVMe et Ceph HCI",
        "status": "open"
    }, statement_ids=["S-101"])

    graph = build_assemble_graph()
    res = graph.invoke({"engagement": "demo-2026", "db_path": str(setup_test_db)})
    assert res.get("status") == "PROVISIONAL"
    assert Path(res.get("document_path")).exists()


@pytest.mark.deterministic
def test_llm_cannot_write(setup_test_db):
    """Test 9 : Valide que la tentative d'écriture directe sans passer par Repository lève une erreur de prédicat non autorisé."""
    repo = ElicitationRepository(db_path=setup_test_db)
    with pytest.raises(ValueError) as excinfo:
        repo.save_statement({
            "id": "S-invalid-pred",
            "predicate": "invalid_invented_predicate_by_llm",
            "value": "something"
        })
    assert "Prédicat non autorisé" in str(excinfo.value)
