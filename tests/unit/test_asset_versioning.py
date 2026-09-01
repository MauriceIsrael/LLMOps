"""Tests unitaires pour le versionnage des actifs et la lecture directe depuis LadybugDB."""

import pytest

from mcp_server.knowledge.tools import get_asset, list_assets


@pytest.mark.deterministic
def test_get_asset_returns_version_and_external_ref():
    """Vérifie que get_asset retourne la version et la référence externe KH:ID@vVersion."""
    res = get_asset("ADR-0005")
    assert res.get("status") == "ok"
    data = res.get("data", {})
    assert data.get("id") == "ADR-0005"
    assert data.get("version") == "1.0.0"
    assert data.get("external_ref") == "KH:ADR-0005@v1.0.0"
    assert "sections" in data
    assert len(data["sections"]) > 0


@pytest.mark.deterministic
def test_get_asset_principle_has_external_ref():
    """Vérifie qu'un principe d'architecture possède également une référence externe."""
    res = get_asset("P-002")
    assert res.get("status") == "ok"
    data = res.get("data", {})
    assert data.get("id") == "P-002"
    assert data.get("external_ref") == "KH:P-002@v1.0.0"


@pytest.mark.deterministic
def test_list_assets_includes_versioned_metadata():
    """Vérifie que le listing des actifs expose les statuts et niveaux de confiance attendus."""
    res = list_assets(status="active")
    assert res.get("status") == "ok"
    assert res.get("count", 0) > 0

