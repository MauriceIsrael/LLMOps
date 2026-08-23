import gc

import pytest

from mcp_server.db.kuzu_client import KuzuClient
from tools.elicitation.repository import ElicitationRepository, _esc


@pytest.fixture
def repo(tmp_path):
    db_path = tmp_path / "test_db"
    r = ElicitationRepository(db_path=db_path)
    yield r
    r.close()
    KuzuClient.clear_cache()
    gc.collect()


@pytest.mark.deterministic
def test_esc():
    assert _esc(None) == ""
    assert _esc("test") == "test"
    assert _esc("it's a test") == "it\\'s a test"
    assert _esc("line1\nline2") == "line1 line2"
    assert _esc("line1\rline2") == "line1 line2"


@pytest.mark.deterministic
def test_repository_context_manager(tmp_path):
    db_path = tmp_path / "test_db"
    with ElicitationRepository(db_path=db_path) as r:
        assert r.db_client is not None
    KuzuClient.clear_cache()
    gc.collect()


@pytest.mark.deterministic
def test_repository_close_safe(repo):
    repo.close()
    repo.close()  # Double close should be safe


@pytest.mark.deterministic
def test_save_subject_new(repo):
    repo.save_subject("SubjA", definition="Def A")
    res = repo.get_subject("SubjA")
    assert res["subject"] == "SubjA"


@pytest.mark.deterministic
def test_save_subject_existing_with_def(repo):
    repo.save_subject("SubjB")
    repo.save_subject("SubjB", definition="New Def")
    res = repo.get_subject("SubjB")
    assert res["subject"] == "SubjB"


@pytest.mark.deterministic
def test_save_subject_existing_without_def(repo):
    repo.save_subject("SubjC", definition="Def")
    repo.save_subject("SubjC")
    res = repo.get_subject("SubjC")
    assert res["subject"] == "SubjC"


@pytest.mark.deterministic
def test_subject_levels_empty(repo):
    levels = repo.subject_levels("nordwave-mcx-2027")
    assert levels == {}


@pytest.mark.deterministic
def test_subject_levels_with_data(repo):
    repo.save_subject("SubjA", engagement="eng1")
    levels = repo.subject_levels("eng1")
    assert "SubjA" in levels


@pytest.mark.deterministic
def test_sections_with_statements_empty(repo):
    assert repo.sections_with_statements("eng1") == set()


@pytest.mark.deterministic
def test_sections_with_statements_with_data(repo):
    repo.save_statement({"engagement": "eng1", "section": "sec1", "status": "active"})
    sections = repo.sections_with_statements("eng1")
    assert "sec1" in sections


class MockRoot:
    def __init__(self, name, instructed=True):
        self.name = name
        self.instructed = instructed
        self.definition = f"Def {name}"


class MockBlueprint:
    def __init__(self, roots=None):
        self.roots = roots

    def get_declared_subjects(self):
        return {"Fallback1", "Fallback2"}


@pytest.mark.deterministic
def test_bind_blueprint_roots(repo):
    bp = MockBlueprint(roots=[MockRoot("R1"), MockRoot("R2", instructed=False)])
    repo.bind_blueprint_to_engagement(bp, "eng1")
    levels = repo.subject_levels("eng1")
    assert "R1" in levels
    assert "R2" not in levels


@pytest.mark.deterministic
def test_bind_blueprint_fallback(repo):
    bp = MockBlueprint()
    repo.bind_blueprint_to_engagement(bp, "eng1")
    levels = repo.subject_levels("eng1")
    assert "Fallback1" in levels
    assert "Fallback2" in levels


@pytest.mark.deterministic
def test_question_lifecycle(repo):
    q_id1 = repo.save_question({
        "engagement": "eng1",
        "question": "What?",
    })
    assert q_id1.startswith("Q-")

    q_id2 = repo.save_question({
        "id": "Q-123",
        "engagement": "eng1",
        "subject": "SubjA",
        "question": "How?",
    })
    assert q_id2 == "Q-123"

    q = repo.get_question("Q-123")
    assert q["id"] == "Q-123"

    q_none = repo.get_question("Q-999")
    assert q_none is None

    repo.update_question_status("Q-123", "confirmed")
    q = repo.get_question("Q-123")
    assert q["status"] == "confirmed"


@pytest.mark.deterministic
def test_statement_lifecycle(repo):
    s_id1 = repo.save_statement({
        "engagement": "eng1",
        "value": "Val1"
    })
    assert s_id1.startswith("S-")

    repo.save_statement({
        "id": "S-123",
        "engagement": "eng1",
        "based_on": "Some string",
        "value": "Val2"
    })
    
    repo.save_statement({
        "id": "S-124",
        "engagement": "eng1",
        "based_on_asset": "Asset1",
        "value": "Val3"
    })

    repo.save_statement({
        "id": "S-125",
        "engagement": "eng1",
        "based_on": [{"id": "Asset2"}],
        "value": "Val4"
    })

    s2 = repo.get_statement("S-123")
    assert s2["id"] == "S-123"

    s_none = repo.get_statement("S-999")
    assert s_none is None

    active = repo.get_active_statements("eng1")
    assert len(active) >= 4

    empty = repo.get_active_statements("eng_empty")
    assert len(empty) == 0


@pytest.mark.deterministic
def test_conflict_lifecycle(repo):
    s1 = repo.save_statement({"engagement": "eng1", "value": "A"})
    s2 = repo.save_statement({"engagement": "eng1", "value": "B"})
    
    c_id = repo.save_conflict(
        {"kind": "contradiction", "detail": "Test conflict"},
        [s1, s2]
    )
    
    c = repo.get_conflict(c_id)
    assert c["id"] == c_id
    assert s1 in c["statement_ids"]

    c_none = repo.get_conflict("C-999")
    assert c_none is None
    
    conflicts = repo.get_conflicts("eng1", "open")
    assert len(conflicts) > 0

    repo.arbitrate_conflict(
        conflict_id=c_id,
        keep_statement_id=s1,
        reason="Because",
        arbitrated_by="Me"
    )
    
    c_arb = repo.get_conflict(c_id)
    assert c_arb["status"] == "arbitrated"


@pytest.mark.deterministic
def test_arbitrate_with_amendment(repo):
    s1 = repo.save_statement({"engagement": "eng1", "value": "A"})
    s2 = repo.save_statement({"engagement": "eng1", "value": "B"})
    s3 = repo.save_statement({"engagement": "eng1", "value": "C"})
    c_id = repo.save_conflict({}, [s1, s2, s3])

    repo.arbitrate_conflict(
        conflict_id=c_id,
        keep_statement_id=s1,
        reason="Because",
        arbitrated_by="Me",
        amend_statement_id=s2,
        amend_to="B_Amended"
    )

    s2_obj = repo.get_statement(s2)
    assert s2_obj["value"] == "B_Amended"


@pytest.mark.deterministic
def test_uncertainty_lifecycle(repo):
    repo.save_uncertainty({"engagement": "eng1", "text": "Uncertain about X", "subject": "SubjX"})
    repo.save_uncertainty({"engagement": "eng1", "text": "Uncertain about Y", "subject": "SubjY"})
    
    u_all = repo.get_uncertainties("eng1")
    assert len(u_all) == 2

    u_sub = repo.get_uncertainties("eng1", "SubjX")
    assert len(u_sub) == 1
    assert u_sub[0]["subject"] == "SubjX"

    u_empty = repo.get_uncertainties("eng2")
    assert len(u_empty) == 0


@pytest.mark.deterministic
def test_run_checks_contradiction(repo):
    s1 = repo.save_statement({
        "engagement": "eng1",
        "subject": "SubjA",
        "predicate": "has_color",
        "value": "red",
        "author": "A1"
    })
    s2 = repo.save_statement({
        "engagement": "eng1",
        "subject": "SubjA",
        "predicate": "has_color",
        "value": "blue",
        "author": "A1"
    })
    
    conflicts = repo.run_checks("eng1")
    assert len(conflicts) > 0
    in_conf = conflicts[0]["statement_ids"]
    assert s1 in in_conf or s2 in in_conf


@pytest.mark.deterministic
def test_run_checks_no_contradiction(repo):
    repo.save_statement({
        "engagement": "eng_safe",
        "subject": "SubjA",
        "predicate": "has_color",
        "value": "red",
        "author": "A1"
    })
    conflicts = repo.run_checks("eng_safe")
    assert len(conflicts) == 0
    

@pytest.mark.deterministic
def test_run_checks_with_statement_ids(repo):
    s1 = repo.save_statement({
        "engagement": "eng2",
        "subject": "SubjB",
        "predicate": "has_color",
        "value": "red",
    })
    repo.save_statement({
        "engagement": "eng2",
        "subject": "SubjB",
        "predicate": "has_color",
        "value": "blue",
    })
    conflicts = repo.run_checks("eng2", statement_ids=[s1])
    assert len(conflicts) > 0
    
    conflicts2 = repo.run_checks("eng2", statement_ids=["S-999"])
    assert len(conflicts2) == 0


@pytest.mark.deterministic
def test_advance_subject_level(repo):
    repo.save_subject("SubjA")
    repo.advance_subject_level(subject_name="SubjA", new_level="L1_framed")
    sub = repo.get_subject("SubjA")
    assert sub["level"] == "L1_framed"


@pytest.mark.deterministic
def test_advance_subject_level_kwargs(repo):
    repo.advance_subject_level(name="SubjB", level="L2_decomposed", engagement="eng1")
    sub = repo.get_subject_maturity("SubjB", "eng1")
    assert sub["level"] == "L2_decomposed"


@pytest.mark.deterministic
def test_get_subject_trajectory(repo):
    repo.save_subject("SubjA", engagement="eng1")
    repo.advance_subject_level("SubjA", "L2_decomposed", engagement="eng1")
    
    repo.save_statement({
        "engagement": "eng1",
        "subject": "SubjA",
        "section": "4.1",
        "value": "Val 4.1"
    })
    repo.save_statement({
        "engagement": "eng1",
        "subject": "SubjA",
        "section": "4.2",
        "value": "Val 4.2"
    })
    
    traj = repo.get_subject_trajectory("eng1", "SubjA")
    assert len(traj) > 0
    levels = [t["level"] for t in traj]
    assert "L1_framed" in levels
    assert "L2_decomposed" in levels


@pytest.mark.deterministic
def test_get_subject_maturity(repo):
    sub = repo.get_subject_maturity("SubjX", engagement="eng1")
    assert sub["level"] == "L0_named"

    repo.save_subject("SubjX", engagement="eng1")
    sub2 = repo.get_subject_maturity(name="SubjX", engagement="eng1")
    assert sub2["level"] == "L0_named"


@pytest.mark.deterministic
def test_get_subjects_maturity_board(repo):
    repo.save_subject("SubjFast", engagement="engMB")
    repo.save_question({
        "engagement": "engMB",
        "subject": "SubjFast",
        "status": "open"
    })
    
    board = repo.get_subjects_maturity_board("engMB", stall_days=0)
    assert len(board) > 0
    stalled = [b for b in board if b["subject"] == "SubjFast"]
    assert len(stalled) == 1
    assert stalled[0]["is_stalled"] is True
    
    board_no_stall = repo.get_subjects_maturity_board("engMB", stall_days=999)
    stalled2 = [b for b in board_no_stall if b["subject"] == "SubjFast"]
    assert stalled2[0]["is_stalled"] is False


@pytest.mark.deterministic
def test_contest_statement(repo):
    s_id = repo.save_statement({"engagement": "eng1", "value": "A"})
    s_new, c_id = repo.contest_statement(s_id, "Me", "Arch", "No it's B", "eng1")
    assert s_new.startswith("S-")
    assert c_id.startswith("C-")
    
    c = repo.get_conflict(c_id)
    assert s_id in c["statement_ids"]
    assert s_new in c["statement_ids"]


@pytest.mark.deterministic
def test_demote_subject(repo):
    repo.save_subject("SubjA", engagement="eng1")
    s_id = repo.save_statement({"engagement": "eng1", "subject": "SubjA", "status": "active"})
    q_id = repo.save_question({"engagement": "eng1", "subject": "SubjA", "status": "confirmed"})
    
    res = repo.demote_subject(name="SubjA", to_level="L0_named", engagement="eng1")
    assert res["status"] == "demoted"
    
    sub = repo.get_subject("SubjA")
    assert sub["level"] == "L0_named"
    
    s = repo.get_statement(s_id)
    assert s["status"] == "under_review"
    
    q = repo.get_question(q_id)
    assert q["status"] == "open"
