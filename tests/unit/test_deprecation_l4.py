"""K10 (contract 1.14): the 1.13 deprecation of the engagement part is cancelled; legacy stays legacy; conflict detection mode flag."""

import gc
import logging

import pytest
from starlette.testclient import TestClient

from mcp_server.core import deprecation
from mcp_server.db.kuzu_client import KuzuClient
from tools.elicitation.repository import ElicitationRepository

DEPRECATED_ROUTES = [
    ("POST", "/api/elicitation/trigger"),
    ("GET", "/api/elicitation/questions"),
    ("GET", "/api/arbitration/board"),
    ("GET", "/api/arbitration/conflicts"),
    ("GET", "/api/arbitration/statements"),
]


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("SERVER_TOKEN", "demo-token")
    monkeypatch.delenv("ENGAGEMENT_TOKENS", raising=False)
    monkeypatch.setenv("ENGAGEMENTS_DIR", str(tmp_path))
    from mcp_server.main import create_starlette_app

    return TestClient(create_starlette_app())


@pytest.mark.parametrize(("method", "path"), DEPRECATED_ROUTES)
def test_engagement_routes_are_in_service_without_deprecation_signal(client, caplog, method, path):
    with caplog.at_level(logging.WARNING, logger="mcp_server.deprecation"):
        res = client.request(method, path, headers={"Authorization": "Bearer demo-token"}, params={"engagement": "dep-eng"})
    assert "Deprecation" not in res.headers and "Link" not in res.headers
    assert "deprecation" not in res.json()
    assert not [r for r in caplog.records if "deprecated interface called" in r.message]


def test_nothing_is_deprecated_in_1_14():
    assert deprecation.DEPRECATED == {}


def test_legacy_routes_carry_no_deprecation_signal(client):
    res = client.get("/api/knowledge/health", headers={"Authorization": "Bearer demo-token"})
    assert "Deprecation" not in res.headers and "deprecation" not in res.json()
    assert set(deprecation.LEGACY) >= {"shred_rfp", "generate_zero_draft_hld", "trigger_rfp_elicitation"}  # K4 still applies


def test_engagement_tools_return_their_result_without_deprecation_field(monkeypatch, tmp_path):
    monkeypatch.setenv("ENGAGEMENTS_DIR", str(tmp_path))
    from mcp_server.engagement import tools

    marked = [n for n in ("get_board", "get_statements", "get_conflicts", "get_open_questions") if hasattr(tools, n)]
    for name in marked:
        res = getattr(tools, name)(engagement="dep-eng")
        assert res["status"] == "ok" and "deprecation" not in res
        assert not hasattr(getattr(tools, name), "__wrapped__")  # the decorator is gone, the function is the tool


@pytest.fixture
def repo(tmp_path):
    r = ElicitationRepository(db_path=tmp_path / "db")
    yield r
    r.close()
    from tools.adapters.ladybug_store import LadybugGraphStore

    LadybugGraphStore.clear_cache()
    KuzuClient.clear_cache()
    gc.collect()


def _two_authors_same_value(repo):
    for author in ("A1", "A2"):
        repo.save_statement({"engagement": "e", "subject": "S", "predicate": "has_color", "value": "same", "author": author})


@pytest.mark.deterministic
def test_conflict_detection_legacy_is_the_default(repo, monkeypatch):
    monkeypatch.delenv("CONFLICT_DETECTION_MODE", raising=False)
    _two_authors_same_value(repo)
    assert len(repo.run_checks("e")) == 1  # current behaviour kept: same value by two authors is flagged


@pytest.mark.deterministic
def test_conflict_detection_strict_only_flags_different_values(repo, monkeypatch):
    monkeypatch.setenv("CONFLICT_DETECTION_MODE", "strict")
    _two_authors_same_value(repo)
    assert repo.run_checks("e") == []
    repo.save_statement({"engagement": "e", "subject": "S", "predicate": "has_color", "value": "other", "author": "A3"})
    assert len(repo.run_checks("e")) >= 1
