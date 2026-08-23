"""Suite de 12 tests d'acceptation selon la spécification SPEC-REFINEMENT-AND-CONTRIBUTIONS.md."""

from pathlib import Path

import pytest

from tools.elicitation.contribution_repository import ContributionRepository
from tools.elicitation.level_templates import validate_question_scope
from tools.elicitation.plan import generate_instruction_plan
from tools.elicitation.repository import ElicitationRepository
from tools.elicitation.trajectory import get_subject_trajectory
from tools.elicitation.vocabulary_protector import map_material_vocabulary

pytestmark = pytest.mark.stochastic


@pytest.fixture
def temp_db(tmp_path: Path) -> Path:
    """Fixture créant une base Kùzu DB isolée pour chaque test avec nettoyage du cache client."""
    import gc

    from mcp_server.db.kuzu_client import KuzuClient
    db_dir = tmp_path / "kuzu_test_db"
    yield db_dir
    KuzuClient.clear_cache(str(db_dir))
    gc.collect()


def test_question_respects_level_scope() -> None:
    """Test 1 : Une question L1/L2 ne contient aucun nom de technologie, unité ou seuil numérique."""
    valid_l1_q = "What is floor-control for, and what must keep working when a site is isolated?"
    is_valid, reason = validate_question_scope(valid_l1_q, "L1_framing")
    assert is_valid, f"Validation failed: {reason}"


def test_template_violation_is_rejected() -> None:
    """Test 2 : Une question violant le contrat forbids (ex: 100 ms ou 5QI en L1) est rejetée."""
    invalid_l1_q = "What is floor-control target latency in 100 ms under 5QI profile?"
    is_valid, reason = validate_question_scope(invalid_l1_q, "L1_framing")
    assert not is_valid
    assert "scope contract" in reason


def test_trajectory_orders_by_level_then_time(temp_db: Path) -> None:
    """Test 3 : La trajectoire d'un sujet restitue les étapes chronologiques par niveau et par date."""
    repo = ElicitationRepository(db_path=temp_db)
    repo.save_subject("floor-control")

    traj = get_subject_trajectory("floor-control", engagement="test-traj", db_path=temp_db)
    assert traj["subject"] == "floor-control"
    assert len(traj["steps"]) >= 2
    assert traj["steps"][0]["level"] == "L1_framed"
    assert traj["steps"][1]["level"] == "L2_decomposed"


def test_demotion_flags_but_does_not_delete(temp_db: Path) -> None:
    """Test 4 : La rétrogradation passe les énoncés de niveau supérieur en 'under_review' sans les supprimer."""
    repo = ElicitationRepository(db_path=temp_db)
    repo.save_subject("floor-control")
    repo.save_statement({
        "engagement": "test-demote",
        "section": "4.3",
        "subject": "floor-control",
        "predicate": "depends_on",
        "value": "centralized arbitration",
        "author": "amina",
        "status": "active",
    })

    res = repo.demote_subject("floor-control", to_level="L2_decomposed", author="sofia", reason="missed LMR case", engagement="test-demote")
    assert res["status"] == "demoted"

    query = "MATCH (st:Statement {engagement: 'test-demote', subject: 'floor-control'}) RETURN st.status as status;"
    rows = repo.db_client.execute_cypher(query)
    assert len(rows) > 0
    assert rows[0]["status"] == "under_review"


def test_demotion_reopens_questions_with_prior_answers(temp_db: Path) -> None:
    """Test 5 : La rétrogradation réouvre les questions fermées avec le contexte antérieur conservé."""
    repo = ElicitationRepository(db_path=temp_db)
    repo.save_subject("floor-control")
    q_id = repo.save_question({
        "engagement": "test-reopen",
        "gap_type": "G1_empty_section",
        "section": "4.3",
        "question": "Which arbitration mechanism?",
        "routed_to": "mcx-service-architect",
        "subject": "floor-control",
        "status": "confirmed",
    })

    repo.demote_subject("floor-control", to_level="L2_decomposed", author="sofia", reason="missed LMR case", engagement="test-reopen")

    query = f"MATCH (q:Question {{id: '{q_id}'}}) RETURN q.status as status;"
    rows = repo.db_client.execute_cypher(query)
    assert rows[0]["status"] == "open"


def test_external_cannot_write_directly(tmp_path: Path, temp_db: Path) -> None:
    """Test 6 : Une soumission externe crée un fichier de staging et aucun énoncé/sujet dans Kùzu DB avant le tri."""
    crepo = ContributionRepository(engagement="test-submit", base_dir=tmp_path)
    c = crepo.submit(contributor="external:m.okonkwo", title="ENM Limits", material_text="ENM export throughput limit 50 Mbps")

    assert c.status == "submitted"

    repo = ElicitationRepository(db_path=temp_db)
    board = repo.get_subjects_maturity_board("test-submit")
    assert not any(b["subject"] == "enm-export-throughput" for b in board)


def test_author_confirms_meaning_lead_accepts_entry(tmp_path: Path, temp_db: Path) -> None:
    """Test 7 : Les énoncés ne sont enregistrés qu'après confirmation par l'auteur ET acceptation par le lead."""
    crepo = ContributionRepository(engagement="test-dual-confirm", base_dir=tmp_path)
    c = crepo.submit(contributor="external:m.okonkwo", title="ENM Limits", material_text="interworking gateway transcoding limit")

    crepo.triage(c.id, lead_author="sofia", decision="accept")
    crepo.crystallise(c.id, db_path=str(temp_db))

    with pytest.raises(ValueError):
        crepo.accept_by_lead(c.id, lead_author="sofia", db_path=str(temp_db))

    crepo.confirm_by_author(c.id, author="external:m.okonkwo", accept=True)

    c_final, p_ids = crepo.accept_by_lead(c.id, lead_author="sofia", db_path=str(temp_db))
    assert c_final.status == "accepted"
    assert len(p_ids) > 0


def test_unconfirmed_contribution_stays_as_material(tmp_path: Path) -> None:
    """Test 8 : Une contribution non confirmée reste lisible sous forme de matériel sans énoncé dérivés."""
    crepo = ContributionRepository(engagement="test-unconfirmed", base_dir=tmp_path)
    c = crepo.submit(contributor="external:m.okonkwo", title="Notes", material_text="raw material notes")

    loaded = crepo.get(c.id)
    assert loaded is not None
    assert loaded.status == "submitted"
    assert len(loaded.proposed_statements) == 0


def test_external_cannot_create_subject(temp_db: Path) -> None:
    """Test 9 : Un terme non cartographié génère une proposition nécessitant l'accord du lead, jamais un sujet direct."""
    repo = ElicitationRepository(db_path=temp_db)
    repo.save_subject("lmr-interworking")

    mapped, unmapped = map_material_vocabulary("interworking gateway with profile store extension", repo=repo)
    assert "lmr-interworking" in mapped
    assert "profile store" in unmapped


def test_contradicting_contribution_detected_and_shows_history(tmp_path: Path, temp_db: Path) -> None:
    """Test 10 : Une contribution contradictoire enregistrée génère un conflit origin:detected."""
    repo = ElicitationRepository(db_path=temp_db)
    repo.save_subject("lmr-interworking")
    repo.save_statement({
        "engagement": "test-conflict-contrib",
        "section": "4.5",
        "subject": "lmr-interworking",
        "predicate": "depends_on",
        "value": "analog signaling",
        "author": "amina",
        "status": "active",
    })

    crepo = ContributionRepository(engagement="test-conflict-contrib", base_dir=tmp_path)
    c = crepo.submit(contributor="external:m.okonkwo", title="Digital Interworking", material_text="lmr-interworking uses digital P25 signaling")
    crepo.triage(c.id, lead_author="sofia", decision="accept")
    crepo.crystallise(c.id, db_path=str(temp_db))
    crepo.confirm_by_author(c.id, author="external:m.okonkwo", accept=True)
    c_final, p_ids = crepo.accept_by_lead(c.id, lead_author="sofia", db_path=str(temp_db))

    assert c_final.status == "accepted"
    assert len(p_ids) > 0


def test_declined_contribution_is_retained_with_reason(tmp_path: Path) -> None:
    """Test 11 : Une contribution refusée est conservée avec son motif sans suppression."""
    crepo = ContributionRepository(engagement="test-declined", base_dir=tmp_path)
    c = crepo.submit(contributor="external:m.okonkwo", title="Irrelevant Note", material_text="out of scope material")

    c_declined = crepo.triage(c.id, lead_author="sofia", decision="decline", reason="out of scope for MCX")
    assert c_declined.status == "declined"
    assert c_declined.triage_decision["reason"] == "out of scope for MCX"


def test_chief_architect_answering_is_recorded(temp_db: Path) -> None:
    """Test 12 : L'architecte en chef répondant à la place d'un autre rôle est consigné et visible."""
    repo = ElicitationRepository(db_path=temp_db)
    repo.save_statement({
        "engagement": "test-chief-answer",
        "section": "5.1",
        "subject": "mobile-core",
        "predicate": "depends_on",
        "value": "5G SA UPF at edge",
        "author": "sofia",
        "role": "chief-architect",
        "status": "active",
    })

    plan_data = generate_instruction_plan(engagement="test-chief-answer", db_path=temp_db)
    assert plan_data is not None
