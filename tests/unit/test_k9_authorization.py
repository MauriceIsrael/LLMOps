"""K9 (ADR-KH-01 A4 lines 5-6, A10-d-1): per-caller authorisation answers 403, enumeration is scoped, Cypher is parameterised."""

import logging

import pytest
from starlette.testclient import TestClient

from mcp_server.core import auth

ADMIN = {"Authorization": "Bearer demo-token"}
SCOPED = {"Authorization": "Bearer svc-a"}

# Entry points that build a path from the engagement identifier (found by the K9 audit, beyond the five
# arbitration/elicitation routes of the issue): each must refuse a foreign engagement.
PATH_ROUTES = [
    ("GET", "/api/compliance/frameworks/applicable", None),
    ("PUT", "/api/compliance/frameworks/applicable", {"frameworks": ["NIS2"]}),
    ("GET", "/api/compliance/conformity-snapshot", None),
    ("POST", "/api/documents/zero-draft-blueprint", {"engagement": "eng-b"}),
]

ENGAGEMENT_ROUTES = [
    ("GET", "/api/arbitration/board"),
    ("GET", "/api/arbitration/conflicts"),
    ("GET", "/api/arbitration/statements"),
    ("GET", "/api/elicitation/questions"),
    ("POST", "/api/elicitation/trigger"),
]


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("SERVER_TOKEN", "demo-token")
    monkeypatch.setenv("ENGAGEMENT_TOKENS", "svc-a:eng-a")
    from mcp_server.core.config import server_config

    monkeypatch.setattr(server_config, "engagements_dir", tmp_path)
    for name in ("eng-a", "eng-b", "eng-c"):
        (tmp_path / f"{name}.lbug").touch()
    from mcp_server.main import create_starlette_app

    return TestClient(create_starlette_app(), raise_server_exceptions=False)


@pytest.mark.parametrize(("method", "path"), ENGAGEMENT_ROUTES)
def test_foreign_engagement_is_403_not_500(client, method, path):
    res = client.request(method, path, headers=SCOPED, params={"engagement": "eng-b"})
    assert res.status_code == 403, res.text
    body = res.json()
    assert body["status"] == "error" and body["error"] == "forbidden" and body["engagement"] == "eng-b"
    assert "Traceback" not in res.text


@pytest.mark.parametrize(("method", "path"), ENGAGEMENT_ROUTES)
def test_own_engagement_and_admin_are_not_refused(client, method, path):
    assert client.request(method, path, headers=SCOPED, params={"engagement": "eng-a"}).status_code != 403
    assert client.request(method, path, headers=ADMIN, params={"engagement": "eng-b"}).status_code != 403


def test_enumeration_is_limited_to_the_token_scopes(client):
    ids = {e["id"] for e in client.get("/api/knowledge/engagements", headers=SCOPED).json()["engagements"]}
    assert ids == {"default", "eng-a"}
    assert "eng-b" not in ids and "eng-c" not in ids


def test_admin_enumeration_is_complete(client):
    body = client.get("/api/knowledge/engagements", headers=ADMIN).json()
    assert {e["id"] for e in body["engagements"]} == {"default", "eng-a", "eng-b", "eng-c"}
    assert body["count"] == 4


def test_wildcard_token_enumerates_everything(client, monkeypatch):
    monkeypatch.setenv("ENGAGEMENT_TOKENS", "svc-a:eng-a;svc-all:*")
    body = client.get("/api/knowledge/engagements", headers={"Authorization": "Bearer svc-all"}).json()
    assert body["count"] == 4


def test_intake_conflict_query_binds_the_engagement(monkeypatch):
    from tools.elicitation.flows import intake

    seen = {}

    class FakeStore:
        def close(self):
            pass

        def execute_cypher(self, query, params=None):
            seen["query"], seen["params"] = query, params
            return []

    monkeypatch.setattr(intake, "make_graph_store", lambda **_: FakeStore())
    intake.check_node({"engagement": "eng-a", "db_path": "unused"})
    assert "eng-a" not in seen["query"] and "$engagement" in seen["query"]  # bound as a parameter, never spliced into the query
    assert seen["params"] == {"engagement": "eng-a"}
    # and a hostile identifier no longer gets that far: the engagement is validated before any query (issue #81)
    with pytest.raises(ValueError, match="Invalid engagement identifier"):
        intake.check_node({"engagement": "o'brien'}) RETURN 1 //", "db_path": "unused"})


def test_open_access_is_announced(monkeypatch, caplog):
    monkeypatch.delenv("ENGAGEMENT_TOKENS", raising=False)
    monkeypatch.setenv("LLMOPS_ENV", "development")
    with caplog.at_level(logging.WARNING, logger="mcp_server.auth"):
        assert auth.open_access_warning() is not None
    monkeypatch.setenv("ENGAGEMENT_TOKENS", "svc-a:eng-a")
    assert auth.open_access_warning() is None
    monkeypatch.delenv("ENGAGEMENT_TOKENS")
    monkeypatch.setenv("LLMOPS_ENV", "production")
    assert auth.open_access_warning() is None  # closed, nothing to announce


@pytest.mark.parametrize(("method", "path", "body"), PATH_ROUTES)
def test_path_building_routes_refuse_a_foreign_engagement(client, method, path, body):
    res = client.request(method, path, headers=SCOPED, params={"engagement": "eng-b"}, json=body)
    assert res.status_code == 403, res.text
    assert res.json()["error"] == "forbidden"


@pytest.mark.parametrize(("method", "path", "body"), PATH_ROUTES)
def test_path_building_routes_refuse_an_identifier_that_escapes_the_directory(client, method, path, body):
    hostile = {"engagement": "../../etc/x"}
    res = client.request(method, path, headers=ADMIN, params=hostile, json={**(body or {}), **hostile})
    assert res.status_code == 400, res.text
    assert res.json()["status"] == "invalid_argument"


def test_applicable_frameworks_put_writes_nothing_outside_the_data_dir(client, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # the meta file path is relative to the working directory
    client.put(
        "/api/compliance/frameworks/applicable",
        headers=ADMIN,
        params={"engagement": "../../escaped"},
        json={"frameworks": ["NIS2"]},
    )
    assert not list(tmp_path.parent.glob("**/escaped*"))


TOOLS = ["shred_rfp", "generate_zero_draft_hld", "get_rfp_compliance_matrix", "trigger_rfp_elicitation"]


def _kwargs(name):
    return {"rfp_text": "The system shall encrypt data.", "persist": True} if name == "shred_rfp" else {}


@pytest.mark.parametrize("name", TOOLS)
def test_mcp_tools_authorise_before_touching_the_engagement(monkeypatch, name):
    monkeypatch.setenv("ENGAGEMENT_TOKENS", "svc-a:eng-a")
    from mcp_server.core import auth
    from mcp_server.knowledge import tools

    auth.set_current_caller("svc-a")
    with pytest.raises(auth.Unauthorised):
        getattr(tools, name)(engagement="eng-b", **_kwargs(name))


@pytest.mark.parametrize("name", TOOLS)
def test_mcp_tools_refuse_an_identifier_that_escapes_the_directory(monkeypatch, name):
    monkeypatch.delenv("ENGAGEMENT_TOKENS", raising=False)
    from mcp_server.core import auth
    from mcp_server.core.exceptions import InvalidEngagementIdError
    from mcp_server.knowledge import tools

    auth.set_current_caller("server_admin")
    with pytest.raises(InvalidEngagementIdError):
        getattr(tools, name)(engagement="../x", **_kwargs(name))
