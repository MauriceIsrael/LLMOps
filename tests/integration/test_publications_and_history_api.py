"""Integration tests for publications list and asset history APIs (Archinex #95, LLMOps #108)."""

from pathlib import Path

import pytest
from starlette.testclient import TestClient

from mcp_server.knowledge.tools import list_frameworks
from mcp_server.main import create_starlette_app

ROOT = Path(__file__).parent.parent.parent
CLIENT = {"Authorization": "Bearer archinex-token"}


@pytest.fixture
def app_client(monkeypatch):
    monkeypatch.setenv("SERVER_TOKEN", "archinex-token")
    return TestClient(create_starlette_app())


def test_publications_list_api(app_client):
    """GET /api/knowledge/publications returns published snapshots with entry paths and filters."""
    res = app_client.get("/api/knowledge/publications", headers=CLIENT)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["count"] >= 3
    pubs = data["publications"]
    
    # Check that snapshots exist and have entry_path
    snapshot_ids = [p["snapshot_id"] for p in pubs]
    assert "snapshot-2026-09-29-75fa05f" in snapshot_ids
    assert "snapshot-2026-10-09-373f720" in snapshot_ids

    # Find a framework ingestion publication
    fw_pubs = [p for p in pubs if p["entry_path"].get("type") == "framework_ingestion"]
    assert len(fw_pubs) >= 1
    cra_pub = fw_pubs[0]
    assert cra_pub["entry_path"]["type"] == "framework_ingestion"
    assert cra_pub["entry_path"]["framework"] == "CRA"
    assert cra_pub["entry_path"]["source_sha256"]
    assert "@maintainers" in cra_pub["reviewers"]

    # Test filtering by entry_type
    fw_res = app_client.get("/api/knowledge/publications?entry_type=framework_ingestion", headers=CLIENT)
    assert fw_res.status_code == 200
    fw_data = fw_res.json()
    assert all(p["entry_path"]["type"] == "framework_ingestion" for p in fw_data["publications"])

    # Test filtering by framework
    cra_res = app_client.get("/api/knowledge/publications?framework=CRA", headers=CLIENT)
    assert cra_res.status_code == 200
    cra_data = cra_res.json()
    assert len(cra_data["publications"]) >= 1
    assert all(p["entry_path"].get("framework") == "CRA" for p in cra_data["publications"])


def test_asset_history_api(app_client):
    """GET /api/knowledge/assets/{id}/history returns complete revision history and entry path."""
    # 1. CRA ingested asset
    res = app_client.get("/api/knowledge/assets/CRA-ART14-1/history", headers=CLIENT)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["asset_id"] == "CRA-ART14-1"
    assert data["entry_path"]["type"] == "framework_ingestion"
    assert data["entry_path"]["framework"] == "CRA"
    assert data["entry_path"]["source_sha256"]
    assert len(data["revisions"]) >= 1
    rev = data["revisions"][0]
    assert rev["snapshot_id"].startswith("snapshot-2026-10-12")
    assert "@maintainers" in data["validators"]

    # 2. Baseline asset (P-002)
    res_p002 = app_client.get("/api/knowledge/assets/P-002/history", headers=CLIENT)
    assert res_p002.status_code == 200
    p002_data = res_p002.json()
    assert p002_data["status"] == "ok"
    assert p002_data["asset_id"] == "P-002"
    assert p002_data["entry_path"]["type"] == "initial_baseline"
    assert p002_data["revisions"][0]["snapshot_id"] == "snapshot-2026-09-29-75fa05f"
    assert p002_data["initial_date"] == "2026-07-25"

    # 3. Unknown asset returns 404
    res_unknown = app_client.get("/api/knowledge/assets/NON-EXISTENT-XYZ/history", headers=CLIENT)
    assert res_unknown.status_code == 404
    assert res_unknown.json()["status"] == "not_found"


def test_frameworks_enrichment():
    """list_frameworks() enriches frameworks with ingested_source, SHA-256 and publications."""
    fw_resp = list_frameworks()
    assert fw_resp["status"] == "ok"
    frameworks = {fw["framework"]: fw for fw in fw_resp["data"]}
    
    assert "CRA" in frameworks
    cra = frameworks["CRA"]
    assert cra.get("ingested_source")["file"] == "CELEX_32024R2847_EN.html"
    assert cra.get("source_sha256")
    assert any("snapshot-2026-10-12" in s for s in cra.get("associated_publications", []))


