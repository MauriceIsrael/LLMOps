"""K16 (ADR-KH-01 A10): decisions in the engagement base: proposed, asserted by another decider, superseded, sealed."""

import json

import pytest
from starlette.testclient import TestClient

from mcp_server.core.config import server_config
from pipelines.engagement.access import get_access
from pipelines.engagement.snapshot import seal, verify
from pipelines.governance.store import dispose_engines

ARCHINEX = "arx-token"
OPERATOR = {"Authorization": "Bearer demo-token"}
EMAILS = {"admin": "ada@example.org", "decider": "dan@example.org", "contributor": "carl@example.org", "reader": "rita@example.org"}
ENG = "eng-d"
BASE = f"/api/engagements/{ENG}"
DECISION = {
    "subject": "mcx-services", "decision": "Active-active gateway", "rationale": "Meets REQ-001 within the latency budget.",
    "reversibility": "costly", "consequences": ["Two sites to operate"],
    "rejected": [{"option": "Active-passive gateway", "reason": "Failover time above the budget."}],
    "accepted_violations": [{"typed_id": "principle:P-009", "justification": "Pilot only."}],
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
    monkeypatch.setattr(knowledge_tools, "SNAPSHOTS_DIR", snaps)  # no KB snapshot: decisions here cite nothing
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
    assert c.post(f"{BASE}/subjects", headers=as_("contributor"), json={"name": "mcx-services"}).status_code == 201
    yield c
    dispose_engines()


def propose(client, role="contributor", **over):
    res = client.post(f"{BASE}/decisions", headers=as_(role), json={**DECISION, **over})
    assert res.status_code in (200, 201), res.text
    return res.json()["data"]["decision"]


def assert_(client, did, role="admin"):
    return client.post(f"{BASE}/decisions/{did}/assert", headers=as_(role))


# --- roles and attribution -----------------------------------------------------------------------------------------


def test_roles(client):
    assert client.post(f"{BASE}/decisions", headers=as_("reader"), json=DECISION).status_code == 403
    d = propose(client)
    assert assert_(client, d["id"], "contributor").status_code == 403
    assert assert_(client, d["id"], "decider").status_code == 200


def test_a_decision_is_proposed_with_the_member_as_author_and_nothing_sent_in_the_body_counts(client):
    d = propose(client, author="@somebody", status="active", validated_by="@ada")
    assert d["status"] == "proposed" and d["author"] == "@carl" and not d["validated_by"] and d["origin"] == "human"
    assert d["rejected"] == DECISION["rejected"] and d["accepted_violations"] == DECISION["accepted_violations"]


def test_nobody_asserts_their_own_decision(client):
    d = propose(client, role="decider")
    own = assert_(client, d["id"], "decider")
    assert own.status_code == 409 and own.json()["error"] == "self_validation"
    ok = assert_(client, d["id"], "admin")
    assert ok.status_code == 200
    data = ok.json()["data"]["decision"]
    assert data["status"] == "active" and data["validated_by"] == "@ada" and data["validated_at"]
    assert assert_(client, d["id"], "admin").json()["error"] == "not_proposed"


def test_what_a_model_derived_is_proposed_like_the_rest(client):
    assert propose(client, origin="llm-derived")["origin"] == "llm-derived"


# --- validation ----------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("over", [
    {"rationale": ""}, {"decision": ""}, {"reversibility": "maybe"}, {"reversibility": ""},
    {"subject": "unknown-subject"}, {"rejected": [{"option": "x"}]}, {"rejected": "none"},
    {"rejected": [{"option": "Active-active gateway", "reason": "same as retained"}]},
    {"accepted_violations": [{"typed_id": "principle:P-1"}]}, {"consequences": [1]}, {"origin": "oracle"},
])
def test_invalid_decisions_are_refused_with_the_field(client, over):
    res = client.post(f"{BASE}/decisions", headers=as_("contributor"), json={**DECISION, **over})
    assert res.status_code == 400 and res.json()["argument"], over


# --- one asserted decision per subject, supersession ---------------------------------------------------------------


def test_a_pending_decision_blocks_a_second_proposal(client):
    propose(client)
    again = client.post(f"{BASE}/decisions", headers=as_("contributor"), json={**DECISION, "decision": "Another"})
    assert again.status_code == 409 and again.json()["error"] == "decision_pending"


def test_an_asserted_decision_is_replaced_only_by_naming_it(client):
    d1 = propose(client)
    assert_(client, d1["id"])
    blocked = client.post(f"{BASE}/decisions", headers=as_("contributor"), json={**DECISION, "decision": "Another"})
    assert blocked.status_code == 409 and blocked.json()["error"] == "decision_exists"
    wrong = client.post(f"{BASE}/decisions", headers=as_("contributor"), json={**DECISION, "decision": "Another", "supersedes": "D-nope"})
    assert wrong.status_code == 400
    d2 = propose(client, decision="Active-active with a third witness site", supersedes=d1["id"])
    assert d2["supersedes"] == d1["id"] and d2["status"] == "proposed"
    out = assert_(client, d2["id"]).json()["data"]
    assert out["superseded"] == [d1["id"]]
    env = export(client)
    status = {d["id"]: d["status"] for d in env["data"]["decisions"]}
    assert status == {d1["id"]: "superseded", d2["id"]: "active"}


def test_withdrawal(client):
    d = propose(client)
    assert client.post(f"{BASE}/decisions/{d['id']}/withdraw", headers=as_("contributor")).status_code == 200
    d2 = propose(client)
    get_access().replace_members(ENG, get_access().members(ENG) + [{"email": "cleo@example.org", "handle": "@cleo", "role": "contributor"}], "test")
    cleo = {"Authorization": f"Bearer {ARCHINEX}", "X-Actor-Email": "cleo@example.org"}
    refused = client.post(f"{BASE}/decisions/{d2['id']}/withdraw", headers=cleo)
    assert refused.status_code == 403 and refused.json()["error"] == "not_author"
    assert client.post(f"{BASE}/decisions/{d2['id']}/withdraw", headers=as_("decider")).status_code == 200
    assert client.post(f"{BASE}/decisions/D-nope/withdraw", headers=as_("decider")).status_code == 404


def test_a_decision_a_subject_stands_on_cannot_be_withdrawn(client):
    d = propose(client)
    assert_(client, d["id"])
    assert client.post(f"{BASE}/subjects/mcx-services/maturity", headers=as_("decider"), json={"level": "L3_decided"}).status_code == 200
    res = client.post(f"{BASE}/decisions/{d['id']}/withdraw", headers=as_("admin"))
    assert res.status_code == 409 and res.json()["error"] == "subject_decided"


def test_idempotency_replays_without_resetting_the_assertion(client):
    h = {**as_("contributor"), "Idempotency-Key": "adr-import-7"}
    first = client.post(f"{BASE}/decisions", headers=h, json=DECISION)
    assert first.status_code == 201
    did = first.json()["data"]["decision"]["id"]
    assert_(client, did)
    replay = client.post(f"{BASE}/decisions", headers=h, json=DECISION)
    assert replay.status_code == 200 and replay.json()["data"]["created"] is False
    assert replay.json()["data"]["decision"]["status"] == "active"


# --- maturity ------------------------------------------------------------------------------------------------------


def test_a_subject_is_decided_only_on_an_asserted_decision(client):
    adv = f"{BASE}/subjects/mcx-services/maturity"
    none = client.post(adv, headers=as_("decider"), json={"level": "L3_decided"})
    assert none.status_code == 409 and none.json()["error"] == "no_asserted_decision"
    d = propose(client)
    assert client.post(adv, headers=as_("decider"), json={"level": "L3_decided"}).status_code == 409  # proposed is not enough
    assert_(client, d["id"])
    assert client.post(adv, headers=as_("decider"), json={"level": "L3_decided"}).status_code == 200


# --- the sealed snapshot -------------------------------------------------------------------------------------------


def export(client):
    ref = client.post(f"{BASE}/exports", headers=as_("admin"))
    assert ref.status_code in (200, 201), ref.text
    sid = ref.json()["data"]["snapshotRef"]["snapshotId"]
    return client.get(f"{BASE}/exports/{sid}", headers=as_("reader")).json()


def test_the_snapshot_carries_decisions_with_their_assertion_level(client):
    d = propose(client)
    env = export(client)
    assert env["schemaVersion"] == "1.2" and verify(env) == []  # 1.1 added decisions, 1.2 the imported flag
    only = env["data"]["decisions"][0]
    assert only["assertion_level"] == "proposed" and only["author"] == "@carl" and only["validated_by"] == ""
    assert_(client, d["id"])
    only = export(client)["data"]["decisions"][0]
    assert only["assertion_level"] == "asserted" and only["validated_by"] == "@ada"
    assert only["rejected"] == DECISION["rejected"] and only["reversibility"] == "costly"


def test_lowering_a_decision_changes_the_checksum(client):
    d = propose(client)
    before = export(client)["checksum"]
    assert_(client, d["id"])
    assert export(client)["checksum"] != before


def test_a_subject_decided_without_a_decision_stops_the_export(client):
    """A subject moved to L3 by an older path (statements only) cannot be sealed as decided."""
    from tools.elicitation.repository import ElicitationRepository

    repo = ElicitationRepository(db_path=server_config.engagements_dir / f"{ENG}.lbug")
    repo.advance_subject_level(name="mcx-services", level="L3_decided", engagement=ENG)
    repo.close()
    res = client.post(f"{BASE}/exports", headers=as_("admin"))
    assert res.status_code == 422 and "DECIDED_WITHOUT_DECISION" in {p["code"] for p in res.json()["problems"]}


def sealed_with(env, fn):
    data = json.loads(json.dumps(env["data"]))
    fn(data)
    return seal(data, ENG, env["createdAt"], env["sourceRevision"])


@pytest.mark.parametrize(("name", "fn", "code"), [
    ("self validation", lambda d: d["decisions"][0].update(validated_by="@carl"), "SELF_VALIDATION"),
    ("asserted by nobody", lambda d: d["decisions"][0].update(validated_by="", validated_at=""), "ASSERTED_WITHOUT_PERSON"),
    ("retained among rejected", lambda d: d["decisions"][0]["rejected"].append({"option": "Active-active gateway", "reason": "x"}), "INCONSISTENT_ALTERNATIVES"),
    ("unknown subject", lambda d: d["decisions"][0].update(subject="nowhere"), "DANGLING"),
    ("dangling supersession", lambda d: d["decisions"][0].update(supersedes="D-ghost"), "DANGLING"),
    ("two asserted", lambda d: d["decisions"].append({**d["decisions"][0], "id": "D-twin"}), "MULTIPLE_ACTIVE_DECISIONS"),
    ("decider is a name", lambda d: d["decisions"][0].update(author="Carl Dupont"), "AUTHOR_NOT_A_HANDLE"),
])
def test_the_verification_refuses_decision_defects(client, name, fn, code):
    d = propose(client)
    assert_(client, d["id"])
    env = export(client)
    assert code in {p.code for p in verify(sealed_with(env, fn))}, name
