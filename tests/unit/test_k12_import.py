"""K12 (ADR-KH-01 A10-f): importing an engagement from another system, rehearsable and without asserting in the batch's name."""

import copy

import pytest
from starlette.testclient import TestClient

from mcp_server.core.config import server_config
from pipelines.engagement.access import get_access
from pipelines.engagement.snapshot import verify
from pipelines.governance.store import dispose_engines

ARCHINEX = "arx-token"
OPERATOR = {"Authorization": "Bearer demo-token"}
EMAILS = {"admin": "ada@example.org", "decider": "dan@example.org", "contributor": "carl@example.org", "reader": "rita@example.org"}
ENG = "eng-i"
BASE = f"/api/engagements/{ENG}"

BATCH = {
    "batch_id": "archinex-2026-10-03",
    "subjects": [{"name": "mcx-services", "definition": "Mission-critical services", "maturity": "L3_decided"},
                 {"name": "core-network", "maturity": "L1_framed"}],
    "requirements": [{"id": "REQ-1", "text": "The gateway shall survive the loss of one site.", "section": "3.2"}],
    "statements": [
        {"key": "s-1", "subject": "mcx-services", "value": "Gateway is active-active", "confidence": "designed", "author": "@carl",
         "created_at": "2026-01-05T10:00:00", "validated_by": "@dan", "validated_at": "2026-01-06T09:00:00"},
        {"key": "s-2", "subject": "core-network", "value": "A second core site is under study", "confidence": "stated-by-client",
         "author": "@carl", "status": "active"},  # asserted in the source without a validator
    ],
    "decisions": [{"key": "d-1", "subject": "mcx-services", "decision": "Active-active gateway", "rationale": "Meets REQ-1.",
                   "reversibility": "costly", "rejected": [{"option": "Active-passive", "reason": "Failover too slow."}],
                   "author": "@carl", "created_at": "2026-01-05T11:00:00", "validated_by": "@ada", "validated_at": "2026-01-07T09:00:00"}],
    "questions": [{"key": "q-1", "question": "Which redundancy model for the core?", "subject": "core-network", "status": "open"}],
}


def as_(role):
    return {"Authorization": f"Bearer {ARCHINEX}", "X-Actor-Email": EMAILS[role]}


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("SERVER_TOKEN", "demo-token")
    monkeypatch.setenv("ENGAGEMENT_TOKENS", f"{ARCHINEX}:*,eng:delegate")
    monkeypatch.setenv("GOVERNANCE_DATABASE_URL", f"sqlite:///{tmp_path}/gov.db")
    monkeypatch.setattr(server_config, "engagements_dir", tmp_path)
    from mcp_server.knowledge import tools as knowledge_tools

    snaps = tmp_path / "snaps"
    snaps.mkdir()
    monkeypatch.setattr(knowledge_tools, "SNAPSHOTS_DIR", snaps)
    dispose_engines()
    from mcp_server.main import create_starlette_app

    c = TestClient(create_starlette_app(), raise_server_exceptions=False)
    assert c.post("/api/engagements", headers=OPERATOR, json={
        "engagement": ENG, "confidentiality": "internal", "admin_email": EMAILS["admin"], "admin_handle": "@ada"}).status_code == 201
    get_access().replace_members(ENG, [
        {"email": EMAILS["admin"], "handle": "@ada", "role": "admin"},
        {"email": EMAILS["decider"], "handle": "@dan", "role": "decider"},
        {"email": EMAILS["contributor"], "handle": "@carl", "role": "contributor"},
        {"email": EMAILS["reader"], "handle": "@rita", "role": "reader"}], "test")
    yield c
    dispose_engines()


def run(client, body=None, dry=False, role="admin"):
    return client.post(f"{BASE}/import" + ("?dry_run=true" if dry else ""), headers=as_(role), json=body if body is not None else BATCH)


def codes(res):
    return {r["code"] for r in res.json()["data"]["rejected"]}


def batch(**changes):
    b = copy.deepcopy(BATCH)
    b.update(changes)
    return b


def export(client):
    ref = client.post(f"{BASE}/exports", headers=as_("admin"))
    assert ref.status_code in (200, 201), ref.text
    return client.get(f"{BASE}/exports/{ref.json()['data']['snapshotRef']['snapshotId']}", headers=as_("reader")).json()


# --- who, and rehearsal --------------------------------------------------------------------------------------------


def test_only_an_admin_imports(client):
    for role in ("reader", "contributor", "decider"):
        assert run(client, role=role).status_code == 403, role
    assert client.post(f"{BASE}/import", headers=OPERATOR, json=BATCH).status_code == 403
    assert client.post("/api/engagements/legacy-eng/import", headers=as_("admin"), json=BATCH).status_code == 409


def test_a_dry_run_writes_nothing_and_reports_everything(client):
    res = run(client, dry=True)
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["dry_run"] is True and data["applied"] is False and data["counts"]["rejected"] == 0
    assert data["counts"]["accepted"] == 7  # 2 subjects, 1 requirement, 2 statements, 1 decision, 1 question
    assert any(a["code"] == "no_validator" for a in data["adjusted"])
    empty = export(client)["data"]
    assert empty["statements"] == empty["decisions"] == empty["subjects"] == empty["requirements"] == []  # nothing was written


def test_batch_id_is_required(client):
    assert run(client, {**BATCH, "batch_id": ""}).status_code == 400
    assert run(client, {k: v for k, v in BATCH.items() if k != "batch_id"}).status_code == 400
    assert run(client, {"batch_id": "b", "statements": "no"}).status_code == 400


# --- what an import preserves, and what it refuses to assert -------------------------------------------------------


def test_the_import_keeps_the_provenance_and_marks_the_items(client):
    res = run(client)
    assert res.status_code == 200 and res.json()["data"]["applied"] is True
    env = export(client)
    assert verify(env) == []
    data = env["data"]
    s1 = next(s for s in data["statements"] if s["value"] == "Gateway is active-active")
    assert (s1["author"], s1["validated_by"], s1["validated_at"], s1["status"], s1["imported"]) == (
        "@carl", "@dan", "2026-01-06T09:00:00", "active", True)  # the source's author, validator and date: not "now"
    s2 = next(s for s in data["statements"] if s["value"].startswith("A second core"))
    assert s2["status"] == "proposed" and s2["validated_by"] == ""  # asserted in the source with nobody: proposed here
    d = data["decisions"][0]
    assert d["status"] == "active" and d["validated_by"] == "@ada" and d["imported"] is True and d["rejected"][0]["option"] == "Active-passive"
    assert {s["name"]: s["maturity"] for s in data["subjects"]} == {"mcx-services": "L3_decided", "core-network": "L1_framed"}
    assert data["requirements"][0]["id"] == "REQ-1" and data["gaps"]


def test_replaying_the_batch_changes_nothing(client):
    run(client)
    before = export(client)["checksum"]
    again = run(client)
    assert again.status_code == 200
    counts = again.json()["data"]["counts"]
    assert counts["accepted"] == 0 and counts["unchanged"] >= 6
    assert export(client)["checksum"] == before


# --- what it rejects -----------------------------------------------------------------------------------------------


def stmt(**over):
    return {"key": "x-1", "subject": "core-network", "value": "v", "confidence": "designed", "author": "@carl", **over}


@pytest.mark.parametrize(("name", "item", "code"), [
    ("self validation", stmt(validated_by="@carl", validated_at="2026-01-01T00:00:00"), "self_validation"),
    ("validator is only a contributor", stmt(author="@dan", validated_by="@carl", validated_at="2026-01-01T00:00:00"), "validator_not_a_decider"),
    ("validator is not a member", stmt(validated_by="@ghost", validated_at="2026-01-01T00:00:00"), "validator_not_a_decider"),
    ("no date for the assertion", stmt(validated_by="@dan"), "validated_at_required"),
    ("bad date", stmt(validated_by="@dan", validated_at="yesterday"), "invalid_argument"),
    ("proposed but with a validator", stmt(status="proposed", validated_by="@dan", validated_at="2026-01-01T00:00:00"), "status_conflict"),
    ("unknown author", stmt(author="@nobody"), "unknown_author"),
    ("author is an e-mail", stmt(author="carl@example.org"), "email"),
    ("e-mail in the text", stmt(value="ask carl@client.example"), "email"),
    ("unknown subject", stmt(subject="nowhere"), "unknown_subject"),
    ("confidence out of vocabulary", stmt(confidence="certain"), "invalid_argument"),
    ("verified without evidence", stmt(confidence="verified"), "invalid_argument"),
    ("no key", {k: v for k, v in stmt().items() if k != "key"}, "invalid_argument"),
    ("unknown status", stmt(status="deleted"), "invalid_argument"),
])
def test_what_is_rejected_comes_with_its_code(client, name, item, code):
    res = run(client, {"batch_id": "b", "subjects": [{"name": "core-network"}], "statements": [item]})
    assert res.status_code == 422 and res.json()["error"] == "import_refused", name
    assert code in codes(res), name
    assert res.json()["data"]["applied"] is False
    assert all(r["path"].startswith("statements[0]") for r in res.json()["data"]["rejected"] if r["kind"] == "statement")


def test_one_rejection_blocks_the_whole_batch_unless_partial_is_asked(client):
    bad = batch()
    bad["statements"].append(stmt(key="bad", validated_by="@carl", validated_at="2026-01-01T00:00:00"))
    blocked = run(client, bad)
    assert blocked.status_code == 422 and blocked.json()["data"]["counts"]["rejected"] == 1
    assert export(client)["data"]["statements"] == []  # nothing was written
    partial = run(client, {**bad, "allow_partial": True})
    assert partial.status_code == 200 and partial.json()["data"]["applied"] is True
    assert len(export(client)["data"]["statements"]) == 2  # the two good ones; the self-validated one is not there


def test_a_batch_cannot_assert_in_its_own_name(client):
    """An item with no validator is proposed, whatever the batch says; only a named decider asserts."""
    b = {"batch_id": "b", "subjects": [{"name": "core-network"}], "statements": [stmt(key=f"k{i}", status="active") for i in range(3)]}
    res = run(client, b)
    assert res.status_code == 200 and {a["code"] for a in res.json()["data"]["adjusted"]} == {"no_validator"}
    assert {s["status"] for s in export(client)["data"]["statements"]} == {"proposed"}


def test_requirements_are_never_rewritten(client):
    run(client)
    res = run(client, {"batch_id": "b2", "requirements": [{"id": "REQ-1", "text": "Another text"}]})
    assert res.status_code == 422 and "requirement_changed" in codes(res)


# --- decisions, maturity, conflicts --------------------------------------------------------------------------------


def decision(**over):
    return {"key": "d-x", "subject": "core-network", "decision": "Keep one core", "rationale": "Budget.", "reversibility": "reversible",
            "author": "@carl", **over}


def test_a_second_asserted_decision_for_a_subject_is_rejected(client):
    validated = {"validated_by": "@ada", "validated_at": "2026-02-01T00:00:00"}
    res = run(client, {"batch_id": "b", "subjects": [{"name": "core-network"}],
                       "decisions": [decision(key="a", **validated), decision(key="b", decision="Two cores", **validated)]})
    assert res.status_code == 422 and "decision_exists" in codes(res)
    pending = run(client, {"batch_id": "b", "subjects": [{"name": "core-network"}],
                           "decisions": [decision(key="a"), decision(key="b", decision="Two cores")]})
    assert "decision_pending" in codes(pending)


def test_a_replaced_decision_is_imported_with_its_supersession(client):
    validated = {"validated_by": "@ada", "validated_at": "2026-02-01T00:00:00"}
    old = decision(key="old", status="superseded", **validated)
    new = decision(key="new", decision="Two cores", supersedes_key="old", **validated)
    res = run(client, {"batch_id": "b", "subjects": [{"name": "core-network"}], "decisions": [old, new]})
    assert res.status_code == 200, res.text
    status = {d["decision"]: d["status"] for d in export(client)["data"]["decisions"]}
    assert status == {"Keep one core": "superseded", "Two cores": "active"}
    inconsistent = run(client, {"batch_id": "c", "subjects": [{"name": "edge"}],
                                "decisions": [decision(key="o2", subject="edge", **validated),
                                              decision(key="n2", subject="edge", decision="Two", supersedes_key="o2", **validated)]})
    assert inconsistent.status_code == 422 and codes(inconsistent) & {"supersession_inconsistent", "decision_exists"}


def test_a_subject_whose_decisions_do_not_support_its_maturity_is_capped_and_reported(client):
    res = run(client, {"batch_id": "b", "subjects": [{"name": "mcx-services", "maturity": "L3_decided"}]})
    assert res.status_code == 200
    assert [a["code"] for a in res.json()["data"]["adjusted"]] == ["maturity_capped"]
    assert {s["name"]: s["maturity"] for s in export(client)["data"]["subjects"]} == {"mcx-services": "L2_decomposed"}


def test_asserted_contradictions_open_conflicts_and_cap_the_subject(client):
    validated = {"validated_by": "@dan", "validated_at": "2026-02-01T00:00:00"}
    b = {"batch_id": "b", "subjects": [{"name": "mcx-services", "maturity": "L3_decided"}],
         "statements": [
             {"key": "a", "subject": "mcx-services", "value": "active-active", "confidence": "designed", "author": "@carl", **validated},
             {"key": "b", "subject": "mcx-services", "value": "active-passive", "confidence": "designed", "author": "@carl", **validated}],
         "decisions": [{"key": "d", "subject": "mcx-services", "decision": "Active-active", "rationale": "r", "reversibility": "costly",
                        "author": "@carl", "validated_by": "@ada", "validated_at": "2026-02-02T00:00:00"}]}
    res = run(client, b)
    assert res.status_code == 200 and len(res.json()["data"]["conflicts_opened"]) == 1
    assert any(a["code"] == "maturity_capped" for a in res.json()["data"]["adjusted"])
    assert export(client)["data"]["is_provisional"] is True


def test_the_batch_size_is_bounded(client):
    big = {"batch_id": "b", "statements": [stmt(key=f"k{i}") for i in range(2001)]}
    assert run(client, big).status_code == 400
