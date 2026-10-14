"""Élicitation alignée sur l'engagement géré et sur le moteur de cascade (issues #78, #79, #80)."""

import gc

import pytest
from typer.testing import CliRunner

from mcp_server.db.kuzu_client import KuzuClient
from pipelines.governance.store import dispose_engines
from tools.elicitation.cli import app
from tools.elicitation.flows import intake
from tools.elicitation.flows.scan import build_scan_graph
from tools.elicitation.repository import ElicitationRepository

ENG = "eng-align"
STATEMENT = {"engagement": ENG, "section": "4.4", "subject": "media", "predicate": "has_property", "confidence": "designed",
             "role": "architect"}


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "graph"
    yield str(path)
    KuzuClient.clear_cache(str(path))
    gc.collect()


@pytest.fixture
def managed(monkeypatch, tmp_path):
    from pipelines.engagement.access import get_access

    monkeypatch.setenv("GOVERNANCE_DATABASE_URL", f"sqlite:///{tmp_path}/gov.db")
    dispose_engines()
    get_access().create(ENG, "internal", "ada@example.org", "@ada", "test")
    yield
    dispose_engines()


@pytest.fixture
def unmanaged(monkeypatch):
    monkeypatch.delenv("GOVERNANCE_DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)


def candidate(**over):
    return {**STATEMENT, "value": "multicast", "author": "Amina", **over}


# --- #78 : intake on a managed engagement ---------------------------------------------------------------------------

def test_managed_intake_proposes_and_does_not_advance(managed, db):
    repo = ElicitationRepository(db_path=db)
    repo.save_subject("media", engagement=ENG)
    out = intake.persist_node({"engagement": ENG, "db_path": db, "candidate_statements": [candidate()], "advance_level_to": "L3_decided"})
    assert out["managed"] is True
    rows = repo.db_client.execute_cypher("MATCH (s:Statement {engagement: $e}) RETURN s.status as status, s.author as author", {"e": ENG})
    assert [(r["status"], r["author"]) for r in rows] == [("proposed", "Amina")]
    assert repo.subject_levels(engagement=ENG).get("media", "L0_named") == "L0_named"
    assert intake.check_node({"engagement": ENG, "db_path": db, "managed": True, "persisted_statement_ids": out["persisted_statement_ids"]}) == {}


def test_unmanaged_intake_keeps_its_behaviour(unmanaged, db):
    repo = ElicitationRepository(db_path=db)
    repo.save_subject("media", engagement=ENG)
    out = intake.persist_node({"engagement": ENG, "db_path": db, "candidate_statements": [candidate()], "advance_level_to": "L3_decided"})
    assert out["managed"] is False
    rows = repo.db_client.execute_cypher("MATCH (s:Statement {engagement: $e}) RETURN s.status as status", {"e": ENG})
    assert [r["status"] for r in rows] == ["active"]
    assert repo.subject_levels(engagement=ENG)["media"] == "L3_decided"


@pytest.mark.parametrize("args", [
    ["arbitrate", "C-0001", "--keep", "S-0001", "--reason", "x"],
    ["demote", "media", "--reason", "x"],
    ["contest", "S-0001", "--text", "x"],
    ["import", "payload.json"],
])
def test_asserting_commands_refuse_a_managed_engagement(managed, tmp_path, monkeypatch, args):
    monkeypatch.chdir(tmp_path)
    if args[0] == "import":
        (tmp_path / "payload.json").write_text(f'{{"engagement": "{ENG}", "subjects": [], "statements": []}}')
    result = CliRunner().invoke(app, [*args, "--engagement", ENG])
    assert result.exit_code == 2, result.output
    assert "géré" in result.output
    assert not (tmp_path / "artifacts").exists()  # nothing was opened, so nothing was written


# --- #79 : one definition of a contradiction -------------------------------------------------------------------------

def test_intake_and_api_detect_the_same_conflicts(unmanaged, db):
    repo = ElicitationRepository(db_path=db)
    repo.save_subject("media", engagement=ENG)
    a = repo.save_statement(candidate(value="multicast", status="active"))
    b = repo.save_statement(candidate(value="unicast", author="Rui", status="active"))
    c = repo.save_statement(candidate(predicate="uses", value="site-a", author="Zed", status="active"))  # another predicate
    found = intake.check_node({"engagement": ENG, "db_path": db, "persisted_statement_ids": [b]})
    assert [sorted(x["statement_ids"]) for x in found["detected_conflicts"]] == [sorted([a, b])]
    assert len(found["created_conflict_ids"]) == 1
    assert c not in found["detected_conflicts"][0]["statement_ids"]  # different predicates and authors are no contradiction


def test_no_conflict_query_outside_run_checks():
    import inspect

    assert "predicate <>" not in inspect.getsource(intake)
    assert "Conflict" not in inspect.getsource(intake.check_node).replace("nœuds Conflict", "")


# --- #80 : the scan knows derived subjects ----------------------------------------------------------------------------

SECTIONS = [{"id": "4.1", "name": "Base", "subject": "base", "required_level": "L1_framed", "routes_to": "architect"}]


def derive(repo, name, mandatory=False, role="resilience-architect"):
    repo.save_derived_subject(ENG, name, "q", "L0_named", f"TRG-{name}", {
        "mandatory": mandatory, "suggested_role": role, "question": {"en": f"What about {name}?", "fr": f"Et {name} ?"}})


def scan(db):
    return build_scan_graph().invoke({"engagement": ENG, "sections": SECTIONS, "db_path": db})


def questions(repo):
    return repo.db_client.execute_cypher("MATCH (q:Question {engagement: $e}) RETURN q.section as subject, q.routed_to as role", {"e": ENG})


def test_scan_asks_about_a_derived_subject_once(unmanaged, db, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    repo = ElicitationRepository(db_path=db)
    derive(repo, "dr-site")
    scan(db)
    scan(db)
    asked = [q for q in questions(repo) if q["subject"] == "derived:dr-site"]
    assert [q["role"] for q in asked] == ["resilience-architect"]


def test_a_contested_foundation_is_not_dispatched_until_restored(unmanaged, db, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    repo = ElicitationRepository(db_path=db)
    derive(repo, "dr-site")
    repo.set_foundation(ENG, "dr-site", "contested", {"cause": "x"})
    scan(db)
    assert not [q for q in questions(repo) if q["subject"] == "derived:dr-site"]
    repo.set_foundation(ENG, "dr-site", "sound", {})
    scan(db)
    assert [q for q in questions(repo) if q["subject"] == "derived:dr-site"]


def test_a_mandatory_question_is_not_duplicated(unmanaged, db, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    repo = ElicitationRepository(db_path=db)
    derive(repo, "rto", mandatory=True)
    scan(db)
    assert not [q for q in questions(repo) if q["subject"] == "derived:rto"]


def test_a_subject_the_blueprint_names_is_not_doubled(unmanaged, db, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    repo = ElicitationRepository(db_path=db)
    derive(repo, "base")
    scan(db)
    assert len([q for q in questions(repo) if q["subject"] == "4.1"]) == 1
