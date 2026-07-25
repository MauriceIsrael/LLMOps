"""Tests d'intégration des outils exposés par le serveur FastMCP."""

from mcp_server.tools.asset_tools import list_assets, get_glossary_term, get_decision_trail


def test_list_assets_tool() -> None:
    res = list_assets(status="active")
    assert isinstance(res, list)


def test_get_glossary_term_fallback() -> None:
    res = get_glossary_term("TermeInexistant")
    assert res["term"] == "TermeInexistant"
    assert "non trouvé" in res["definition"]


def test_get_decision_trail_structure() -> None:
    res = get_decision_trail("TPL-mcp-spec")
    assert "asset" in res
    assert "supersedes" in res
    assert "superseded_by" in res
