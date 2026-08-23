"""Tests d'intégration des outils exposés par le serveur FastMCP (avec Enveloppe)."""

import pytest

from mcp_server.knowledge.tools import get_decision_trail, get_glossary_term, list_assets

pytestmark = pytest.mark.stochastic


def test_list_assets_tool() -> None:
    res = list_assets(status="active")
    assert res.get("status") == "ok"
    assert isinstance(res.get("data"), list)


def test_get_glossary_term_fallback() -> None:
    res = get_glossary_term("TermeInexistant")
    assert res.get("status") == "not_found"
    assert res.get("id") == "TermeInexistant"


def test_get_decision_trail_structure() -> None:
    res = get_decision_trail("TPL-mcp-spec")
    assert res.get("status") in ("ok", "not_found")
    if res.get("status") == "ok":
        data = res.get("data", {})
        assert "asset" in data
        assert "supersedes" in data
        assert "superseded_by" in data
