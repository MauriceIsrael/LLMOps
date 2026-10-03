"""K14 (ADR-KH-01 A11): roles, membership and audit of a managed engagement."""

import json

import pytest
from starlette.testclient import TestClient

from mcp_server.core import auth
from mcp_server.core.config import server_config
from pipelines.engagement.access import (
    ACTIONS,
    ROLE_ACTIONS,
    ROLES,
    AccessError,
    get_access,
    validate_members,
)
from pipelines.governance.store import dispose_engines

ADMIN = {"Authorization": "Bearer demo-token"}  # the operator: server_admin
ARCHINEX = "arx-token"
TOKENS = f"{ARCHINEX}:*,eng:delegate;suite-token:*,eng:service;plain-token:*;maker-token:*,eng:create;scoped-token:eng-other,eng:delegate"


def h(token, email=None):
    headers = {"Authorization": f"Bearer {token}"}
    if email:
        headers["X-Actor-Email"] = email
    return headers


@pytest.fixture
def env(monkeypatch, tmp_path):
    monkeypatch.setenv("SERVER_TOKEN", "demo-token")
    monkeypatch.setenv("ENGAGEMENT_TOKENS", TOKENS)
    monkeypatch.setenv("GOVERNANCE_DATABASE_URL", f"sqlite:///{tmp_path}/gov.db")
    monkeypatch.setenv("LLMOPS_ENV", "development")  # a managed engagement is closed even here
    monkeypatch.setattr(server_config, "engagements_dir", tmp_path)
    dispose_engines()
    yield tmp_path
    dispose_engines()


@pytest.fixture
def client(env):
    from mcp_server.main import create_starlette_app

    return TestClient(create_starlette_app(), raise_server_exceptions=False)


@pytest.fixture
def managed(client):
    """Engagement 'eng-m' with one member per role."""
    res = client.post("/api/engagements", headers=ADMIN, json={
        "engagement": "eng-m", "confidentiality": "confidential", "admin_email": "ada@example.org", "admin_handle": "@ada"})
    assert res.status_code == 201, res.text
    get_access().replace_members("eng-m", [
        {"email": "ada@example.org", "handle": "@ada", "role": "admin"},
        {"email": "dan@example.org", "handle": "@dan", "role": "decider"},
        {"email": "carl@example.org", "handle": "@carl", "role": "contributor"},
        {"email": "rita@example.org", "handle": "@rita", "role": "reader"},
    ], "test")
    return "eng-m"


EMAIL_OF = {"admin": "ada@example.org", "decider": "dan@example.org", "contributor": "carl@example.org", "reader": "rita@example.org"}


# --- roles ---------------------------------------------------------------------------------------------------------


def test_the_role_matrix_is_monotonic_and_only_admin_exports():
    for lower, higher in zip(ROLES, ROLES[1:], strict=False):
        assert ROLE_ACTIONS[lower] < ROLE_ACTIONS[higher]
    assert {r for r in ROLES if "export" in ROLE_ACTIONS[r]} == {"admin"}
    assert {r for r in ROLES if "decide" in ROLE_ACTIONS[r]} == {"decider", "admin"}
    assert set(ACTIONS) == set().union(*ROLE_ACTIONS.values())


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("action", ACTIONS)
def test_each_member_may_do_exactly_what_the_role_allows(managed, role, action):
    auth.set_current_caller(ARCHINEX)
    auth.set_current_actor_email(EMAIL_OF[role])
    if action in ROLE_ACTIONS[role]:
        auth.authorise_action(managed, action)
    else:
        with pytest.raises(auth.Forbidden) as err:
            auth.authorise_action(managed, action)
        assert err.value.reason == "role_insufficient" and err.value.action == action


# --- who is a person -----------------------------------------------------------------------------------------------


def test_a_non_member_is_refused(managed):
    auth.set_current_caller(ARCHINEX)
    auth.set_current_actor_email("mallory@example.org")
    with pytest.raises(auth.Forbidden) as err:
        auth.authorise_action(managed, "read")
    assert err.value.reason == "not_a_member"


def test_the_actor_header_counts_only_through_a_delegating_token(managed, client):
    res = client.get("/api/arbitration/board", headers=h("plain-token", EMAIL_OF["admin"]), params={"engagement": managed})
    assert res.status_code == 403 and res.json()["reason"] == "actor_required"  # the header of an admin means nothing


def test_a_delegating_token_without_a_person_is_refused(client, managed):
    res = client.get("/api/arbitration/board", headers=h(ARCHINEX), params={"engagement": managed})
    assert res.status_code == 403 and res.json()["reason"] == "actor_required"


def test_a_service_token_may_read_but_nothing_else(client, managed):
    ok = client.get("/api/arbitration/board", headers=h("suite-token"), params={"engagement": managed})
    assert ok.status_code != 403
    auth.set_current_caller("suite-token")
    auth.set_current_actor_email(None)
    for action in ("contribute", "decide", "export", "members"):
        with pytest.raises(auth.Forbidden):
            auth.authorise_action(managed, action)


def test_the_operator_manages_members_but_cannot_read_the_content(client, managed):
    assert client.get(f"/api/engagements/{managed}/members", headers=ADMIN).status_code == 200
    denied = client.get("/api/arbitration/board", headers=ADMIN, params={"engagement": managed})
    assert denied.status_code == 403 and denied.json()["reason"] == "actor_required"


def test_a_managed_engagement_is_closed_in_every_environment(client, managed, monkeypatch):
    for env_name in ("development", "demo", "production"):
        monkeypatch.setenv("LLMOPS_ENV", env_name)
        res = client.get("/api/arbitration/board", headers=h(ARCHINEX), params={"engagement": managed})
        assert res.status_code == 403, env_name


def test_a_token_scoped_elsewhere_is_refused_before_roles_are_looked_at(client, managed):
    res = client.get("/api/arbitration/board", headers=h("scoped-token", EMAIL_OF["admin"]), params={"engagement": managed})
    assert res.status_code == 403 and "reason" not in res.json()  # the token scope refused it (K9), not a role


def test_an_unmanaged_engagement_keeps_the_legacy_behaviour(client):
    res = client.get("/api/arbitration/board", headers=h(ARCHINEX), params={"engagement": "legacy-eng"})
    assert res.status_code != 403


def test_member_reads_through_the_routes(client, managed):
    for role in ROLES:
        res = client.get("/api/arbitration/board", headers=h(ARCHINEX, EMAIL_OF[role]), params={"engagement": managed})
        assert res.status_code != 403, role


# --- creation and membership ---------------------------------------------------------------------------------------


def test_creating_an_engagement_needs_the_operator_or_the_create_scope(client):
    body = {"engagement": "eng-n", "confidentiality": "internal", "admin_email": "a@example.org", "admin_handle": "@a"}
    assert client.post("/api/engagements", headers=h("plain-token"), json=body).status_code == 403
    assert client.post("/api/engagements", headers=h(ARCHINEX), json=body).status_code == 403
    created = client.post("/api/engagements", headers=h("maker-token"), json=body)
    assert created.status_code == 201
    assert "example.org" not in created.text  # e-mails never leave the registry in a response
    assert client.post("/api/engagements", headers=ADMIN, json=body).status_code == 409


@pytest.mark.parametrize("bad", [
    {"engagement": "Bad_Id", "confidentiality": "internal"},
    {"engagement": "../x", "confidentiality": "internal"},
    {"engagement": "eng-q", "confidentiality": "secret"},
    {"engagement": "eng-q", "confidentiality": "internal", "admin_email": "not-an-email"},
    {"engagement": "eng-q", "confidentiality": "internal", "admin_email": "a@example.org", "admin_handle": "nohandle"},
])
def test_creation_is_validated(client, bad):
    body = {"admin_email": "a@example.org", "admin_handle": "@a", **bad}
    assert client.post("/api/engagements", headers=ADMIN, json=body).status_code == 400


def test_members_are_validated():
    ok = [{"email": "A@Example.org", "handle": "@a", "role": "admin"}]
    assert validate_members(ok)[0]["email"] == "a@example.org"
    for bad, argument in (
        ([], "members"),
        ([{"email": "a@example.org", "handle": "@a", "role": "reader"}], "members"),  # no admin
        ([{"email": "a@example.org", "handle": "@a", "role": "boss"}], "role"),
        ([{"email": "a@example.org", "handle": "@a", "role": "admin"}, {"email": "A@example.org", "handle": "@b", "role": "reader"}], "email"),
        ([{"email": "a@example.org", "handle": "@a", "role": "admin"}, {"email": "b@example.org", "handle": "@a", "role": "reader"}], "handle"),
        ([{"email": "a@example.org", "handle": "a", "role": "admin"}], "handle"),
    ):
        with pytest.raises(AccessError) as err:
            validate_members(bad)
        assert err.value.argument == argument


def test_an_admin_member_replaces_the_members_but_a_decider_cannot(client, managed):
    new = {"members": [{"email": "ada@example.org", "handle": "@ada", "role": "admin"},
                       {"email": "zoe@example.org", "handle": "@zoe", "role": "reader"}]}
    assert client.put(f"/api/engagements/{managed}/members", headers=h(ARCHINEX, EMAIL_OF["decider"]), json=new).status_code == 403
    ok = client.put(f"/api/engagements/{managed}/members", headers=h(ARCHINEX, EMAIL_OF["admin"]), json=new)
    assert ok.status_code == 200 and {m["handle"] for m in ok.json()["data"]["members"]} == {"@ada", "@zoe"}
    # the engagement can never be left without an admin
    locked = client.put(f"/api/engagements/{managed}/members", headers=h(ARCHINEX, "ada@example.org"),
                        json={"members": [{"email": "zoe@example.org", "handle": "@zoe", "role": "reader"}]})
    assert locked.status_code == 400


def test_me_reports_the_role_and_the_actions(client, managed):
    me = client.get(f"/api/engagements/{managed}/me", headers=h(ARCHINEX, EMAIL_OF["contributor"])).json()["data"]
    assert me["managed"] is True and me["role"] == "contributor" and me["actions"] == ["contribute", "read"]
    assert me["handle"] == "@carl" and me["confidentiality"] == "confidential"
    legacy = client.get("/api/engagements/legacy-eng/me", headers=h(ARCHINEX)).json()["data"]
    assert legacy["managed"] is False and legacy["role"] is None


def test_management_needs_a_governance_database(monkeypatch, tmp_path):
    monkeypatch.setenv("SERVER_TOKEN", "demo-token")
    monkeypatch.delenv("GOVERNANCE_DATABASE_URL", raising=False)
    monkeypatch.setenv("CANDIDATES_BACKEND", "file")
    from mcp_server.main import create_starlette_app

    c = TestClient(create_starlette_app(), raise_server_exceptions=False)
    res = c.post("/api/engagements", headers=ADMIN, json={"engagement": "eng-z", "confidentiality": "internal",
                                                          "admin_email": "a@example.org", "admin_handle": "@a"})
    assert res.status_code == 503 and res.json()["error"] == "governance_database_required"


# --- listing and audit ---------------------------------------------------------------------------------------------


def test_enumeration_shows_a_managed_engagement_only_to_its_members(client, managed, env):
    (env / f"{managed}.lbug").touch()
    member = client.get("/api/knowledge/engagements", headers=h(ARCHINEX, EMAIL_OF["reader"])).json()["engagements"]
    outsider = client.get("/api/knowledge/engagements", headers=h(ARCHINEX, "mallory@example.org")).json()["engagements"]
    assert managed in {e["id"] for e in member} and managed not in {e["id"] for e in outsider}


def test_the_audit_records_refusals_and_changes_never_reads_and_never_a_secret(client, managed):
    client.get("/api/arbitration/board", headers=h(ARCHINEX, EMAIL_OF["reader"]), params={"engagement": managed})  # read: not logged
    client.get("/api/arbitration/board", headers=h(ARCHINEX, "mallory@example.org"), params={"engagement": managed})  # refused
    client.get("/api/arbitration/board", headers=h("plain-token"), params={"engagement": managed})  # refused
    auth.set_current_caller(ARCHINEX)
    auth.set_current_actor_email(EMAIL_OF["contributor"])
    auth.authorise_action(managed, "contribute")  # allowed non-read: logged
    events = client.get(f"/api/engagements/{managed}/audit", headers=h(ARCHINEX, EMAIL_OF["admin"])).json()["data"]["events"]
    outcomes = [(e["action"], e["outcome"]) for e in events]
    assert ("read", "denied") in outcomes and ("contribute", "allowed") in outcomes and ("read", "allowed") not in outcomes
    dump = json.dumps(events)
    for secret in (ARCHINEX, "plain-token", "suite-token", "demo-token", "@example.org"):
        assert secret not in dump, secret
    assert any(e["actor"].startswith("token:") for e in events)  # tokens appear as a fingerprint
    assert client.get(f"/api/engagements/{managed}/audit", headers=h(ARCHINEX, EMAIL_OF["decider"])).status_code == 403


# --- separation of duties ------------------------------------------------------------------------------------------


def test_nobody_validates_what_they_wrote():
    auth.require_distinct_validator("@dan", "@carl")
    auth.require_distinct_validator("@dan", None)
    with pytest.raises(PermissionError, match="self_validation"):
        auth.require_distinct_validator("@dan", "@dan")


def test_acting_member_is_resolved_through_the_delegating_token(managed):
    auth.set_current_caller(ARCHINEX)
    auth.set_current_actor_email(EMAIL_OF["decider"])
    assert auth.acting_member(managed)["handle"] == "@dan"
    auth.set_current_caller("plain-token")
    assert auth.acting_member(managed) is None
