"""K15 (ADR-KH-01 A10, A11): writing into a managed engagement through the REST API."""

import pytest
from starlette.testclient import TestClient

from mcp_server.core.config import server_config
from pipelines.engagement.access import get_access
from pipelines.governance.store import dispose_engines

ARCHINEX = "arx-token"
OPERATOR = {"Authorization": "Bearer demo-token"}
EMAILS = {"admin": "ada@example.org", "decider": "dan@example.org", "contributor": "carl@example.org", "reader": "rita@example.org"}
ENG = "eng-w"
BASE = f"/api/engagements/{ENG}"


def as_(role):
    return {"Authorization": f"Bearer {ARCHINEX}", "X-Actor-Email": EMAILS[role]}


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("SERVER_TOKEN", "demo-token")
    monkeypatch.setenv("ENGAGEMENT_TOKENS", f"{ARCHINEX}:*,eng:delegate")
    monkeypatch.setenv("GOVERNANCE_DATABASE_URL", f"sqlite:///{tmp_path}/gov.db")
    monkeypatch.setenv("LLMOPS_ENV", "development")
    monkeypatch.setattr(server_config, "engagements_dir", tmp_path)
    dispose_engines()
    from mcp_server.main import create_starlette_app

    c = TestClient(create_starlette_app(), raise_server_exceptions=False)
    assert c.post("/api/engagements", headers=OPERATOR, json={
        "engagement": ENG, "confidentiality": "confidential", "admin_email": EMAILS["admin"], "admin_handle": "@ada"}).status_code == 201
    get_access().replace_members(ENG, [
        {"email": EMAILS["admin"], "handle": "@ada", "role": "admin"},
        {"email": EMAILS["decider"], "handle": "@dan", "role": "decider"},
        {"email": EMAILS["contributor"], "handle": "@carl", "role": "contributor"},
        {"email": EMAILS["reader"], "handle": "@rita", "role": "reader"},
    ], "test")
    yield c
    dispose_engines()


STATEMENT = {"subject": "mcx-services", "predicate": "has_property", "value": "Gateway is active-active", "confidence": "designed"}


def propose(client, role="contributor", **over):
    res = client.post(f"{BASE}/statements", headers=as_(role), json={**STATEMENT, **over})
    assert res.status_code in (200, 201), res.text
    return res.json()["data"]["statement"]


# --- roles ---------------------------------------------------------------------------------------------------------


def test_a_reader_cannot_write(client):
    res = client.post(f"{BASE}/statements", headers=as_("reader"), json=STATEMENT)
    assert res.status_code == 403 and res.json()["reason"] == "role_insufficient"


def test_a_contributor_proposes_but_cannot_assert_arbitrate_or_advance(client):
    st = propose(client)
    for path, body in ((f"/statements/{st['id']}/assert", {}), ("/conflicts/C-0001/arbitrate", {}), ("/subjects/mcx-services/maturity", {"level": "L1_framed"})):
        res = client.post(BASE + path, headers=as_("contributor"), json=body)
        assert res.status_code == 403 and res.json()["reason"] == "role_insufficient", path


def test_a_non_member_and_an_unknown_engagement(client):
    other = {"Authorization": f"Bearer {ARCHINEX}", "X-Actor-Email": "mallory@example.org"}
    assert client.post(f"{BASE}/statements", headers=other, json=STATEMENT).json()["reason"] == "not_a_member"
    unmanaged = client.post("/api/engagements/legacy-eng/statements", headers=as_("contributor"), json=STATEMENT)
    assert unmanaged.status_code == 409 and unmanaged.json()["error"] == "engagement_not_managed"
    assert client.post("/api/engagements/Bad_Id/statements", headers=as_("contributor"), json=STATEMENT).status_code == 400


# --- statements ----------------------------------------------------------------------------------------------------


def test_the_author_is_the_member_never_the_body_and_nothing_starts_asserted(client):
    st = propose(client, author="@somebody-else", status="active", validated_by="@ada")
    assert st["author"] == "@carl" and st["status"] == "proposed" and st["validated_by"] in (None, "")
    assert st["origin"] == "human"


@pytest.mark.parametrize("over", [
    {"confidence": "certain"}, {"confidence": ""}, {"confidence": "verified"},  # verified needs evidence
    {"value": ""}, {"subject": ""}, {"predicate": "invents_things"}, {"origin": "oracle"}, {"based_on": "x"},
    {"value": "x" * 5000},
])
def test_invalid_statements_are_refused_with_the_field(client, over):
    res = client.post(f"{BASE}/statements", headers=as_("contributor"), json={**STATEMENT, **over})
    assert res.status_code == 400 and res.json()["status"] == "invalid_argument" and res.json()["argument"], over


def test_verified_is_accepted_with_evidence(client):
    st = propose(client, confidence="verified", based_on=[{"id": "ADR-0001"}])
    assert st["confidence"] == "verified"


def test_what_a_model_derived_is_proposed_like_the_rest(client):
    st = propose(client, origin="llm-derived", confidence="assumed")
    assert st["origin"] == "llm-derived" and st["status"] == "proposed"


def test_nobody_asserts_their_own_statement(client):
    st = propose(client, role="decider")  # dan writes
    own = client.post(f"{BASE}/statements/{st['id']}/assert", headers=as_("decider"))
    assert own.status_code == 409 and own.json()["error"] == "self_validation"
    ok = client.post(f"{BASE}/statements/{st['id']}/assert", headers=as_("admin"))  # ada asserts
    assert ok.status_code == 200
    data = ok.json()["data"]["statement"]
    assert data["status"] == "active" and data["validated_by"] == "@ada" and data["validated_at"]
    again = client.post(f"{BASE}/statements/{st['id']}/assert", headers=as_("admin"))
    assert again.status_code == 409 and again.json()["error"] == "not_proposed"


def test_unknown_statement_is_404(client):
    assert client.post(f"{BASE}/statements/S-nope/assert", headers=as_("decider")).status_code == 404


def test_idempotency_replays_without_duplicating_or_resetting(client):
    h = {**as_("contributor"), "Idempotency-Key": "import-42"}
    first = client.post(f"{BASE}/statements", headers=h, json=STATEMENT)
    again = client.post(f"{BASE}/statements", headers=h, json=STATEMENT)
    assert first.status_code == 201 and again.status_code == 200
    assert first.json()["data"]["statement"]["id"] == again.json()["data"]["statement"]["id"]
    assert again.json()["data"]["created"] is False
    sid = first.json()["data"]["statement"]["id"]
    client.post(f"{BASE}/statements/{sid}/assert", headers=as_("decider"))
    replay = client.post(f"{BASE}/statements", headers=h, json=STATEMENT)
    assert replay.json()["data"]["statement"]["status"] == "active"  # the replay did not reset the assertion
    assert client.post(f"{BASE}/statements", headers={**as_("contributor"), "Idempotency-Key": "bad key!"}, json=STATEMENT).status_code == 400


def test_withdrawal_belongs_to_the_author_or_a_decider(client):
    st = propose(client)
    other = {"Authorization": f"Bearer {ARCHINEX}", "X-Actor-Email": "carl@example.org"}
    assert client.post(f"{BASE}/statements/{st['id']}/withdraw", headers=other).status_code == 200
    st2 = propose(client, value="Another claim")
    # a second contributor is not the author
    get_access().replace_members(ENG, get_access().members(ENG) + [{"email": "cleo@example.org", "handle": "@cleo", "role": "contributor"}], "test")
    cleo = {"Authorization": f"Bearer {ARCHINEX}", "X-Actor-Email": "cleo@example.org"}
    refused = client.post(f"{BASE}/statements/{st2['id']}/withdraw", headers=cleo)
    assert refused.status_code == 403 and refused.json()["error"] == "not_author"
    assert client.post(f"{BASE}/statements/{st2['id']}/withdraw", headers=as_("decider")).status_code == 200


def test_proposed_statements_are_visible_with_their_author_to_a_reader(client):
    propose(client)
    res = client.get("/api/arbitration/statements", headers=as_("reader"), params={"engagement": ENG, "status": "proposed"})
    rows = res.json()["data"]
    assert [r["author"] for r in rows] == ["@carl"]


# --- conflicts and maturity ----------------------------------------------------------------------------------------


def two_conflicting_asserted(client):
    a = propose(client, value="active-active")  # carl
    b = propose(client, role="decider", value="active-passive")  # dan
    client.post(f"{BASE}/statements/{a['id']}/assert", headers=as_("admin"))
    out = client.post(f"{BASE}/statements/{b['id']}/assert", headers=as_("admin")).json()["data"]
    return a, b, out["conflicts_opened"]


def test_asserting_a_contradiction_opens_a_conflict_that_only_a_third_person_arbitrates(client):
    a, b, opened = two_conflicting_asserted(client)
    assert len(opened) == 1
    cid = opened[0]
    for role in ("contributor", "decider"):  # carl and dan wrote the two statements
        res = client.post(f"{BASE}/conflicts/{cid}/arbitrate", headers=as_(role), json={"keep_statement_id": a["id"], "reason": "r"})
        assert res.status_code in (403, 409), role
    assert client.post(f"{BASE}/conflicts/{cid}/arbitrate", headers=as_("admin"), json={"keep_statement_id": "S-zzz", "reason": "r"}).status_code == 400
    assert client.post(f"{BASE}/conflicts/{cid}/arbitrate", headers=as_("admin"), json={"keep_statement_id": a["id"]}).status_code == 400  # reason
    ok = client.post(f"{BASE}/conflicts/{cid}/arbitrate", headers=as_("admin"), json={"keep_statement_id": a["id"], "reason": "latency budget"})
    assert ok.status_code == 200 and ok.json()["data"]["conflict"]["status"] == "arbitrated"
    assert ok.json()["data"]["conflict"]["arbitrated_by"] == "@ada"
    assert client.post(f"{BASE}/conflicts/{cid}/arbitrate", headers=as_("admin"), json={"keep_statement_id": a["id"], "reason": "x"}).status_code == 409


def test_the_decider_who_wrote_a_conflicting_statement_cannot_arbitrate_it(client):
    a, b, opened = two_conflicting_asserted(client)
    res = client.post(f"{BASE}/conflicts/{opened[0]}/arbitrate", headers=as_("decider"), json={"keep_statement_id": a["id"], "reason": "mine"})
    assert res.status_code == 409 and res.json()["error"] == "self_validation"


def test_maturity_l3_needs_an_asserted_statement_and_no_open_conflict(client):
    assert client.post(f"{BASE}/subjects", headers=as_("contributor"), json={"name": "mcx-services", "definition": "d"}).status_code == 201
    assert client.post(f"{BASE}/subjects", headers=as_("contributor"), json={"name": "mcx-services"}).status_code == 200  # replay
    adv = f"{BASE}/subjects/mcx-services/maturity"
    assert client.post(adv, headers=as_("decider"), json={"level": "L1_framed"}).status_code == 200
    assert client.post(adv, headers=as_("decider"), json={"level": "nonsense"}).status_code == 400
    no_fact = client.post(adv, headers=as_("decider"), json={"level": "L3_decided"})
    assert no_fact.status_code == 409 and no_fact.json()["error"] == "no_asserted_statement"
    a, b, opened = two_conflicting_asserted(client)
    blocked = client.post(adv, headers=as_("decider"), json={"level": "L3_decided"})
    assert blocked.status_code == 409 and blocked.json()["error"] == "open_conflict"
    client.post(f"{BASE}/conflicts/{opened[0]}/arbitrate", headers=as_("admin"), json={"keep_statement_id": a["id"], "reason": "r"})
    assert client.post(adv, headers=as_("decider"), json={"level": "L3_decided"}).status_code == 200


# --- requirements, questions, answers ------------------------------------------------------------------------------


def test_requirements_are_added_once_and_never_rewritten(client):
    body = {"requirements": [{"id": "REQ-1", "text": "Encrypt data at rest", "criticality": "mandatory"}, {"id": "REQ-2", "text": "99.99% availability"}]}
    first = client.post(f"{BASE}/requirements", headers=as_("contributor"), json=body).json()["data"]
    again = client.post(f"{BASE}/requirements", headers=as_("contributor"), json=body).json()["data"]
    assert first["created"] == ["REQ-1", "REQ-2"] and again["created"] == [] and again["unchanged"] == ["REQ-1", "REQ-2"]
    changed = {"requirements": [{"id": "REQ-1", "text": "Encrypt nothing"}]}
    res = client.post(f"{BASE}/requirements", headers=as_("contributor"), json=changed)
    assert res.status_code == 409 and res.json()["error"] == "requirement_changed"
    assert client.post(f"{BASE}/requirements", headers=as_("reader"), json=body).status_code == 403
    for bad in ({"requirements": []}, {"requirements": [{"text": "no id"}]}, {"requirements": [{"id": "../x", "text": "t"}]}):
        assert client.post(f"{BASE}/requirements", headers=as_("contributor"), json=bad).status_code == 400


def test_a_question_is_answered_by_a_proposed_statement_that_closes_it(client):
    q = client.post(f"{BASE}/questions", headers={**as_("decider"), "Idempotency-Key": "q1"},
                    json={"question": "Which redundancy model?", "subject": "mcx-services", "section": "resilience"})
    assert q.status_code == 201
    qid = q.json()["data"]["question"]["id"]
    assert client.post(f"{BASE}/questions", headers={**as_("decider"), "Idempotency-Key": "q1"}, json={"question": "x"}).json()["data"]["created"] is False
    ans = client.post(f"{BASE}/questions/{qid}/answers", headers=as_("contributor"),
                      json={"value": "Active-active across two sites", "confidence": "stated-by-client"})
    assert ans.status_code == 201
    st = ans.json()["data"]["statement"]
    assert st["status"] == "proposed" and st["author"] == "@carl" and st["subject"] == "mcx-services"
    open_q = client.get("/api/elicitation/questions", headers=as_("reader"), params={"engagement": ENG}).json()["data"]
    assert qid not in [x["id"] for x in open_q]
    assert client.post(f"{BASE}/questions/Q-nope/answers", headers=as_("contributor"), json={"value": "v", "confidence": "assumed"}).status_code == 404


# --- audit ---------------------------------------------------------------------------------------------------------


def test_every_change_is_attributed_in_the_audit_by_handle(client):
    st = propose(client)
    client.post(f"{BASE}/statements/{st['id']}/assert", headers=as_("admin"))
    events = client.get(f"{BASE}/audit", headers=as_("admin")).json()["data"]["events"]
    acts = {(e["actor"], e["action"], e["outcome"]) for e in events}
    assert ("@carl", "contribute", "allowed") in acts and ("@ada", "decide", "allowed") in acts
    assert "example.org" not in str(events)
