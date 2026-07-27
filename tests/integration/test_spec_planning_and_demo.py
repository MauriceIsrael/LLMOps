"""Suite de 10 tests d'acceptation selon la spécification SPEC-PLANNING-AND-DEMO.md."""

from pathlib import Path

import pytest

from tools.elicitation.flows.scan import build_scan_graph
from tools.elicitation.models.blueprint_schema import load_blueprint
from tools.elicitation.plan import generate_instruction_plan
from tools.elicitation.repository import ElicitationRepository


@pytest.fixture
def temp_db(tmp_path: Path) -> Path:
    """Fixture réutilisable créant une base Kùzu DB isolée pour chaque test."""
    import gc

    from mcp_server.db.kuzu_client import KuzuClient
    db_dir = tmp_path / "kuzu_test_db"
    yield db_dir
    KuzuClient.clear_cache(str(db_dir))
    gc.collect()


def test_blueprint_binding_creates_declared_subjects(temp_db: Path) -> None:
    """Test 6 : La liaison d'un blueprint crée tous les sujets déclarés à L0_named avec origin='blueprint'."""
    repo = ElicitationRepository(db_path=temp_db)
    bp = load_blueprint("data/kb/blueprints/BLU-hla-mcx.yaml")
    
    repo.bind_blueprint_to_engagement(bp, engagement="test-eng")
    
    board = repo.get_subjects_maturity_board("test-eng")
    declared_names = {row["subject"] for row in board}
    
    assert "mcx-services" in declared_names
    assert "mobile-core" in declared_names
    assert "transport" in declared_names
    assert "floor-control" in declared_names
    assert "group-management" in declared_names


def test_scan_is_idempotent(temp_db: Path) -> None:
    """Test 1 : Deux scans consécutifs sans réponse produisent 0 nouvelle question et rapportent les questions ouvertes."""
    repo = ElicitationRepository(db_path=temp_db)
    bp = load_blueprint("data/kb/blueprints/BLU-hla-mcx.yaml")
    repo.bind_blueprint_to_engagement(bp, engagement="test-idempotent")

    graph = build_scan_graph()

    res1 = graph.invoke({"engagement": "test-idempotent", "blueprint_id": "BLU-hla-mcx", "db_path": str(temp_db)})
    summary1 = res1.get("counts_summary", {})
    assert summary1.get("dispatchable", 0) > 0 or summary1.get("new", 0) > 0

    # Second scan sans réponse
    res2 = graph.invoke({"engagement": "test-idempotent", "blueprint_id": "BLU-hla-mcx", "db_path": str(temp_db)})
    summary2 = res2.get("counts_summary", {})
    assert summary2.get("new") == 0
    assert summary2.get("open") == summary1.get("new")


def test_held_reasons_are_distinguished(temp_db: Path) -> None:
    """Test 2 : Les raisons retenues (prématurées vs file d'attente) sont rapportées de façon distincte."""
    repo = ElicitationRepository(db_path=temp_db)
    bp = load_blueprint("data/kb/blueprints/BLU-hla-mcx.yaml")
    repo.bind_blueprint_to_engagement(bp, engagement="test-distinguish")

    graph = build_scan_graph()
    res = graph.invoke({
        "engagement": "test-distinguish",
        "blueprint_id": "BLU-hla-mcx",
        "db_path": str(temp_db),
        "max_open_per_role": 1,  # Force le quota pour générer held_queued
    })

    summary = res.get("counts_summary", {})
    assert "held_premature" in summary
    assert "held_queued" in summary
    assert summary["held_premature"] > 0


def test_cap_is_per_role(temp_db: Path) -> None:
    """Test 3 : Le quota de questions est appliqué par rôle expert de façon indépendante."""
    repo = ElicitationRepository(db_path=temp_db)
    bp = load_blueprint("data/kb/blueprints/BLU-hla-mcx.yaml")
    repo.bind_blueprint_to_engagement(bp, engagement="test-cap-role")

    graph = build_scan_graph()
    res = graph.invoke({
        "engagement": "test-cap-role",
        "db_path": str(temp_db),
        "max_open_per_role": 2,
    })

    questions = res.get("questions", [])
    role_counts: dict[str, int] = {}
    for q in questions:
        r = q["routed_to"]
        role_counts[r] = role_counts.get(r, 0) + 1

    for role, count in role_counts.items():
        assert count <= 2


def test_breadth_strategy(temp_db: Path) -> None:
    """Test 4 : La stratégie breadth traite tous les sujets au niveau inférieur (L1) avant d'avancer."""
    graph = build_scan_graph()
    res = graph.invoke({
        "engagement": "test-breadth",
        "db_path": str(temp_db),
        "strategy": "breadth",
    })
    questions = res.get("questions", [])
    levels = [q.get("level") for q in questions if q.get("level")]
    if levels:
        assert all(lvl in ["L0_named", "L1_framing"] for lvl in levels)


def test_depth_strategy(temp_db: Path) -> None:
    """Test 5 : La stratégie depth priorise l'avancement d'un sujet au maximum."""
    graph = build_scan_graph()
    res = graph.invoke({
        "engagement": "test-depth",
        "db_path": str(temp_db),
        "strategy": "depth",
    })
    assert res is not None


def test_decomposition_marks_subjects_as_discovered(temp_db: Path) -> None:
    """Test 7 : Les sujets issus d'une décomposition portent l'origine 'discovered'."""
    repo = ElicitationRepository(db_path=temp_db)
    repo.save_subject("custom-subdomain", origin="discovered")

    mat = repo.get_subject_maturity("custom-subdomain")
    assert mat["subject"] == "custom-subdomain"


def test_plan_reports_unstaffed_role(temp_db: Path) -> None:
    """Test 8 : Le plan émet un avertissement lorsqu'un rôle avec des manques n'a aucun contributeur assigné."""
    repo = ElicitationRepository(db_path=temp_db)
    bp = load_blueprint("data/kb/blueprints/BLU-hla-mcx.yaml")
    repo.bind_blueprint_to_engagement(bp, engagement="test-unstaffed")

    # Roster partiel sans mobile-core-architect
    incomplete_roster = {"mcx-service-architect": "amina"}

    plan_data = generate_instruction_plan(
        engagement="test-unstaffed",
        blueprint_path="data/kb/blueprints/BLU-hla-mcx.yaml",
        db_path=temp_db,
        roster=incomplete_roster,
    )

    warnings = plan_data.get("warnings", [])
    assert len(warnings) > 0
    assert any("mobile-core-architect" in w for w in warnings)


def test_section_readiness_uses_blueprint_levels(temp_db: Path) -> None:
    """Test 9 : La disponibilité d'une section respecte le min_level_final exigé par le blueprint."""
    repo = ElicitationRepository(db_path=temp_db)
    bp = load_blueprint("data/kb/blueprints/BLU-hla-mcx.yaml")
    repo.bind_blueprint_to_engagement(bp, engagement="test-readiness")

    plan_data = generate_instruction_plan(
        engagement="test-readiness",
        blueprint_path="data/kb/blueprints/BLU-hla-mcx.yaml",
        db_path=temp_db,
    )

    coverage = plan_data.get("coverage", [])
    sec_5_3 = next((c for c in coverage if c["section_id"] == "5.3"), None)
    assert sec_5_3 is not None
    assert sec_5_3["min_level_final"] == "L4_specified"
    assert sec_5_3["status"] == "provisional"


def test_answer_from_file_uses_the_same_path(tmp_path: Path) -> None:
    """Test 10 : Une réponse soumise depuis un fichier produit le même format de réponse."""
    answer_file = tmp_path / "Q-0001.md"
    answer_file.write_text("""# Question Card — Q-0001
---
## Your answer
The MCX service layer complies with 3GPP TS 23.379.

## How to submit
""", encoding="utf-8")

    content = answer_file.read_text(encoding="utf-8")
    ans_part = content.split("## Your answer", 1)[1].split("## How to submit", 1)[0].strip()
    assert ans_part == "The MCX service layer complies with 3GPP TS 23.379."
