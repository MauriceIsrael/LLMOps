"""Contract 1.27: the decision on each requirement and the requirements a subject carries, up to the sealed snapshot."""

import copy
import json
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from mcp_server.core.config import server_config
from pipelines import canonical
from pipelines.engagement.access import get_access
from pipelines.engagement.snapshot import build_data, seal, verify
from pipelines.governance.store import dispose_engines
from scripts.export_engagement_example import scenario

ROOT = Path(__file__).resolve().parents[2]
ARCHINEX = "arx-token"
OPERATOR = {"Authorization": "Bearer demo-token"}
EMAILS = {"admin": "ada@example.org", "decider": "dan@example.org", "contributor": "carl@example.org", "reader": "rita@example.org"}
ENG = "eng-d"
BASE = f"/api/engagements/{ENG}"
QUESTION = "Which recovery time objective is tolerated after the loss of a site?"


def as_(role):
    return {"Authorization": f"Bearer {ARCHINEX}", "X-Actor-Email": EMAILS[role]}


@pytest.fixture
def client(monkeypatch, tmp_path):
    from mcp_server.knowledge import tools as knowledge_tools

    monkeypatch.setenv("SERVER_TOKEN", "demo-token")
    monkeypatch.setenv("ENGAGEMENT_TOKENS", f"{ARCHINEX}:*,eng:delegate;suite-token:*,eng:service")
    monkeypatch.setenv("GOVERNANCE_DATABASE_URL", f"sqlite:///{tmp_path}/gov.db")
    monkeypatch.setenv("LLMOPS_ENV", "development")
    monkeypatch.setattr(server_config, "engagements_dir", tmp_path)
    kb = tmp_path / "snapshots"
    kb.mkdir()
    (kb / "latest.json").write_text((ROOT / "data/snapshots/latest.json").read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(knowledge_tools, "SNAPSHOTS_DIR", kb)
    dispose_engines()
    from mcp_server.main import create_starlette_app

    c = TestClient(create_starlette_app(), raise_server_exceptions=False)
    assert c.post("/api/engagements", headers=OPERATOR, json={
        "engagement": ENG, "confidentiality": "confidential", "admin_email": EMAILS["admin"], "admin_handle": "@ada"}).status_code == 201
    get_access().replace_members(ENG, [
        {"email": EMAILS["admin"], "handle": "@ada", "role": "admin"},
        {"email": EMAILS["decider"], "handle": "@dan", "role": "decider"},
        {"email": EMAILS["contributor"], "handle": "@carl", "role": "contributor"},
        {"email": EMAILS["reader"], "handle": "@rita", "role": "reader"}], "test")
    assert c.post(f"{BASE}/requirements", headers=as_("contributor"), json={"requirements": [
        {"id": "SRC-1a2b3c4d:4.1", "text": "Incidents are notified within 24 hours.", "section": "4", "criticality": "bloquant"},
        {"id": "SRC-1a2b3c4d:4.2", "text": "Six workstations are provided.", "section": "4", "criticality": "info"},
        {"id": "SRC-1a2b3c4d:4.3", "text": "The platform recovers quickly after a site loss.", "section": "4", "criticality": "majeur"}]}).status_code == 200
    yield c
    dispose_engines()


R1, R2, R3 = "SRC-1a2b3c4d:4.1", "SRC-1a2b3c4d:4.2", "SRC-1a2b3c4d:4.3"


def url(rid, tail="disposition"):
    return f"{BASE}/requirements/{rid}/{tail}"


def propose(client, rid, disposition, reason="", role="contributor"):
    return client.post(url(rid), headers=as_(role), json={"disposition": disposition, "reason": reason})


def assert_it(client, rid, role="decider"):
    return client.post(url(rid, "disposition/assert"), headers=as_(role))


def snapshot(client):
    res = client.post(f"{BASE}/exports", headers=as_("admin"))
    return res, (res.json().get("data", {}) if res.status_code in (200, 201) else res.json())


# --- who may do what -----------------------------------------------------------------------------------------------


def test_a_contributor_proposes_a_decision_and_the_author_is_the_member(client):
    res = client.post(url(R2), headers=as_("contributor"), json={
        "disposition": "evacuated", "reason": "Facilities, no architecture impact", "author": "@somebody-else", "status": "active"})
    assert res.status_code == 201, res.text
    d = res.json()["data"]["requirement"]["disposition"]
    assert d["value"] == "evacuated" and d["status"] == "proposed" and d["author"] == "@carl" and d["validated_by"] == ""


def test_a_reader_cannot_propose_and_a_contributor_cannot_assert(client):
    assert propose(client, R2, "evacuated", "Facilities, no architecture impact", role="reader").status_code == 403
    propose(client, R2, "evacuated", "Facilities, no architecture impact")
    res = assert_it(client, R2, role="contributor")
    assert res.status_code == 403 and res.json()["reason"] == "role_insufficient"


def test_nobody_asserts_their_own_decision(client):
    propose(client, R2, "evacuated", "Facilities, no architecture impact", role="decider")
    res = assert_it(client, R2, role="decider")
    assert res.status_code == 409 and res.json()["error"] == "self_validation"


def test_a_decider_other_than_the_author_asserts_it(client):
    propose(client, R2, "evacuated", "Facilities, no architecture impact")
    res = assert_it(client, R2)
    assert res.status_code == 200, res.text
    d = res.json()["data"]["requirement"]["disposition"]
    assert d["status"] == "active" and d["validated_by"] == "@dan" and d["author"] == "@carl" and d["validated_at"]


# --- what is refused -----------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("disposition", "reason"),
    [("to_qualify", ""), ("maybe", ""), ("evacuated", ""), ("evacuated", "too short"), ("clarification_needed", "why?")],
)
def test_invalid_decisions_are_refused_with_the_field(client, disposition, reason):
    res = propose(client, R2, disposition, reason)
    assert res.status_code == 400
    assert res.json()["argument"] in ("disposition", "reason")


def test_a_deliberated_decision_needs_no_reason(client):
    assert propose(client, R1, "deliberated").status_code == 201


def test_an_unknown_requirement_is_404(client):
    assert propose(client, "SRC-1a2b3c4d:9.9", "deliberated").status_code == 404


def test_one_proposal_at_a_time_and_an_asserted_decision_is_withdrawn_before_another(client):
    propose(client, R1, "deliberated")
    pending = propose(client, R1, "clarification_needed", QUESTION)
    assert pending.status_code == 409 and pending.json()["error"] == "disposition_pending"
    assert assert_it(client, R1).status_code == 200
    exists = propose(client, R1, "clarification_needed", QUESTION)
    assert exists.status_code == 409 and exists.json()["error"] == "disposition_exists"


def test_replaying_the_same_decision_changes_nothing(client):
    first = propose(client, R2, "evacuated", "Facilities, no architecture impact")
    again = propose(client, R2, "evacuated", "Facilities, no architecture impact")
    assert (first.status_code, again.status_code) == (201, 200)
    assert again.json()["data"]["created"] is False
    assert_it(client, R2)
    replay = propose(client, R2, "evacuated", "Facilities, no architecture impact")
    assert replay.status_code == 200 and replay.json()["data"]["requirement"]["disposition"]["status"] == "active"  # not reset to proposed


def test_withdrawal_belongs_to_the_author_or_a_decider_and_frees_the_requirement(client):
    propose(client, R2, "evacuated", "Facilities, no architecture impact")
    other = client.post(url(R2, "disposition/withdraw"), headers=as_("reader"))
    assert other.status_code == 403
    assert client.post(url(R2, "disposition/withdraw"), headers=as_("contributor")).status_code == 200
    assert client.post(url(R2, "disposition/withdraw"), headers=as_("contributor")).status_code == 409  # nothing left to withdraw
    assert propose(client, R2, "deliberated").status_code == 201  # free again


# --- the requirements a subject carries ---------------------------------------------------------------------------


def test_a_subject_carries_requirements_and_unknown_ones_are_refused(client):
    ok = client.post(f"{BASE}/subjects", headers=as_("contributor"), json={"name": "notification", "requirement_ids": [R1]})
    assert ok.status_code == 201 and ok.json()["data"]["requirement_ids"] == [R1]
    bad = client.post(f"{BASE}/subjects", headers=as_("contributor"), json={"name": "other", "requirement_ids": ["SRC-1a2b3c4d:9.9"]})
    assert bad.status_code == 400 and bad.json()["code"] == "unknown_requirement"
    more = client.post(f"{BASE}/subjects/notification/requirements", headers=as_("contributor"), json={"add": [R3, R1]})
    assert more.json()["data"]["requirement_ids"] == sorted([R1, R3])
    less = client.post(f"{BASE}/subjects/notification/requirements", headers=as_("contributor"), json={"remove": [R3]})
    assert less.json()["data"]["requirement_ids"] == [R1]
    assert client.post(f"{BASE}/subjects/nope/requirements", headers=as_("contributor"), json={"add": [R1]}).status_code == 404
    assert client.post(f"{BASE}/subjects/notification/requirements", headers=as_("contributor"), json={}).status_code == 400


def test_a_requirement_decided_evacuated_cannot_be_carried_and_one_already_carried_must_be_released_first(client):
    client.post(f"{BASE}/subjects", headers=as_("contributor"), json={"name": "notification", "requirement_ids": [R2]})
    propose(client, R2, "evacuated", "Facilities, no architecture impact")
    blocked = assert_it(client, R2)
    assert blocked.status_code == 409 and blocked.json()["error"] == "carried_by_subject" and blocked.json()["subjects"] == ["notification"]
    client.post(f"{BASE}/subjects/notification/requirements", headers=as_("contributor"), json={"remove": [R2]})
    assert assert_it(client, R2).status_code == 200
    refused = client.post(f"{BASE}/subjects/notification/requirements", headers=as_("contributor"), json={"add": [R2]})
    assert refused.status_code == 409 and refused.json()["error"] == "requirement_not_deliberated"


# --- the sealed snapshot -------------------------------------------------------------------------------------------


def test_the_snapshot_states_the_decisions_and_the_carried_requirements_and_verifies(client):
    client.post(f"{BASE}/subjects", headers=as_("contributor"), json={"name": "notification", "requirement_ids": [R1]})
    propose(client, R1, "deliberated")
    assert_it(client, R1)
    propose(client, R2, "evacuated", "Facilities, no architecture impact")  # proposed only
    propose(client, R3, "clarification_needed", QUESTION)
    res, data = snapshot(client)
    assert res.status_code == 201, res.text
    env = client.get(f"{BASE}/exports/{data['snapshotRef']['snapshotId']}", headers={"Authorization": "Bearer suite-token"}).json()
    assert env["schemaVersion"] == "1.6" and verify(env) == []
    by_id = {r["id"]: r for r in env["data"]["requirements"]}
    assert by_id[R1]["disposition"] == {"value": "deliberated", "reason": "", "status": "active", "assertion_level": "asserted",
                                        "author": "@carl", "validated_by": "@dan", "validated_at": by_id[R1]["disposition"]["validated_at"]}
    assert by_id[R2]["disposition"]["assertion_level"] == "proposed" and by_id[R2]["disposition"]["validated_by"] == ""
    assert by_id[R3]["disposition"]["reason"] == QUESTION
    assert next(s for s in env["data"]["subjects"] if s["name"] == "notification")["requirement_ids"] == [R1]
    assert "example.org" not in json.dumps(env)


def test_a_withdrawn_decision_disappears_from_the_snapshot(client):
    propose(client, R2, "evacuated", "Facilities, no architecture impact")
    client.post(url(R2, "disposition/withdraw"), headers=as_("contributor"))
    _, data = snapshot(client)
    env = client.get(f"{BASE}/exports/{data['snapshotRef']['snapshotId']}", headers={"Authorization": "Bearer suite-token"}).json()
    assert all("disposition" not in r for r in env["data"]["requirements"])


def test_nothing_is_issued_when_a_requirement_to_deliberate_has_no_subject(client):
    propose(client, R1, "deliberated")
    assert_it(client, R1)
    res, body = snapshot(client)
    assert res.status_code >= 400 and body["error"] == "verification_failed"
    assert "REQ_UNCOVERED" in json.dumps(body)


def test_an_engagement_without_decisions_is_sealed_exactly_as_before(client):
    _, data = snapshot(client)
    env = client.get(f"{BASE}/exports/{data['snapshotRef']['snapshotId']}", headers={"Authorization": "Bearer suite-token"}).json()
    assert all("disposition" not in r for r in env["data"]["requirements"])
    assert all("requirement_ids" not in s for s in env["data"]["subjects"])


# --- the rules of the verification (pure) --------------------------------------------------------------------------


def example():
    raw, kb = scenario()
    return raw, kb


def sealed(raw, kb):
    return seal(build_data(raw, "example-eng", "confidential", kb), "example-eng", "2026-10-03T12:00:00Z", "test")


def codes(env):
    return {p.code for p in verify(env)}


def test_the_example_scenario_verifies_and_states_a_decision_and_a_carried_requirement():
    raw, kb = example()
    env = sealed(raw, kb)
    assert verify(env) == []
    req1 = next(r for r in env["data"]["requirements"] if r["id"] == "REQ-001")
    assert req1["disposition"]["assertion_level"] == "asserted"
    assert next(s for s in env["data"]["subjects"] if s["name"] == "gateway-services")["requirement_ids"] == ["REQ-001"]
    assert canonical.sha256(env["data"]) == env["checksum"]


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        (lambda raw: raw["requirements"][0].update(disposition_by="@carl"), "SELF_VALIDATION"),
        (lambda raw: raw["requirements"][0].update(disposition_by=""), "ASSERTED_WITHOUT_PERSON"),
        (lambda raw: raw["requirements"][1].update(disposition_by="@ada"), "VALIDATOR_ON_PROPOSED"),
        (lambda raw: raw["requirements"][1].update(disposition_reason="why?"), "DISPOSITION_UNJUSTIFIED"),
        (lambda raw: raw["requirements"][0].update(disposition_author="carl@example.org"), "SCHEMA"),
        (lambda raw: raw.update(subject_requirements={"gateway-services": []}), "REQ_UNCOVERED"),
        (lambda raw: raw.update(subject_requirements={"gateway-services": ["REQ-001", "REQ-404"]}), "DANGLING"),
        (lambda raw: raw["requirements"][0].update(disposition="evacuated", disposition_reason="Not an architecture matter"), "REQ_NOT_DELIBERATED"),
    ],
)
def test_each_rule_of_the_decision_on_a_requirement_catches_its_violation(change, expected):
    raw, kb = example()
    raw = copy.deepcopy(raw)
    change(raw)
    assert expected in codes(sealed(raw, kb))
