"""Contract and integration tests for experimental ontology API and MCP tools (Issue #175)."""

import json
from pathlib import Path
import pytest
from starlette.testclient import TestClient

from mcp_server.core.config import server_config
from mcp_server.knowledge.tools import get_ontology_term, list_ontology_terms
from mcp_server.main import create_starlette_app

ROOT = Path(__file__).parent.parent.parent
AUTH = {"Authorization": "Bearer demo-token"}


@pytest.fixture(autouse=True)
def base_server_env(monkeypatch):
    monkeypatch.setenv("SERVER_TOKEN", "demo-token")
    monkeypatch.setattr(server_config, "kb_dir", ROOT / "data" / "kb")


def test_flag_absent_mcp_tools_and_http_endpoints_unexposed(monkeypatch):
    """When LLMOPS_EXPERIMENTAL_ONTOLOGY is absent, endpoints return 404 and MCP tools are not registered."""
    monkeypatch.delenv("LLMOPS_EXPERIMENTAL_ONTOLOGY", raising=False)

    app = create_starlette_app()
    client = TestClient(app)

    # REST endpoints must 404
    res_list = client.get("/api/knowledge/ontology", headers=AUTH)
    assert res_list.status_code == 404

    res_get = client.get("/api/knowledge/ontology/urn:llmops:ontology:ComputeSubstrate:bare_metal_k8s", headers=AUTH)
    assert res_get.status_code == 404

    # Direct tool functions return disabled error
    assert list_ontology_terms()["status"] == "not_found"
    assert get_ontology_term("urn:llmops:ontology:ComputeSubstrate:bare_metal_k8s")["status"] == "not_found"


def test_flag_active_mcp_tools_and_http_endpoints_respond(monkeypatch):
    """When LLMOPS_EXPERIMENTAL_ONTOLOGY=1, REST endpoints and MCP tools respond with experimental: True."""
    monkeypatch.setenv("LLMOPS_EXPERIMENTAL_ONTOLOGY", "1")

    app = create_starlette_app()
    client = TestClient(app)

    # 1. GET /api/knowledge/ontology
    res = client.get("/api/knowledge/ontology", headers=AUTH)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "ok"
    assert body.get("experimental") is True
    assert isinstance(body["data"], list)
    assert len(body["data"]) >= 8

    # Filter by concept_class
    res_filtered = client.get("/api/knowledge/ontology", headers=AUTH, params={"concept_class": "SecurityZone"})
    assert res_filtered.status_code == 200
    filtered_body = res_filtered.json()
    assert all(item["concept_class"] == "SecurityZone" for item in filtered_body["data"])
    assert len(filtered_body["data"]) >= 3

    # 2. GET /api/knowledge/ontology/{urn}
    urn = "urn:llmops:ontology:ComputeSubstrate:bare_metal_k8s"
    res_urn = client.get(f"/api/knowledge/ontology/{urn}", headers=AUTH)
    assert res_urn.status_code == 200, res_urn.text
    urn_body = res_urn.json()
    assert urn_body["status"] == "ok"
    assert urn_body.get("experimental") is True
    assert urn_body["data"]["id"] == urn
    assert urn_body["data"]["term"] == "Bare Metal Kubernetes"
    assert "projections" in urn_body["data"]
    assert "suse_sylva_capi" in urn_body["data"]["projections"]

    # 3. Direct MCP tool calls
    tool_list_res = list_ontology_terms(concept_class="ComputeSubstrate")
    assert tool_list_res["status"] == "ok"
    assert tool_list_res.get("experimental") is True
    assert len(tool_list_res["data"]) >= 4

    tool_get_res = get_ontology_term(urn)
    assert tool_get_res["status"] == "ok"
    assert tool_get_res.get("experimental") is True
    assert tool_get_res["data"]["id"] == urn


def test_unknown_revision_returns_explicit_machine_readable_error(monkeypatch):
    """Requesting an absent revision returns 404 with reason='revision_not_found' without fallback."""
    monkeypatch.setenv("LLMOPS_EXPERIMENTAL_ONTOLOGY", "1")

    app = create_starlette_app()
    client = TestClient(app)

    urn = "urn:llmops:ontology:ComputeSubstrate:bare_metal_k8s"
    # Available revision is 1; request revision 99
    res = client.get(f"/api/knowledge/ontology/{urn}", headers=AUTH, params={"revision": 99})
    assert res.status_code == 404
    body = res.json()
    assert body["status"] == "not_found"
    assert body["reason"] == "revision_not_found"
    assert body.get("requested_revision") == 99
    assert body.get("experimental") is True

    # Request unknown URN
    res_unknown = client.get("/api/knowledge/ontology/urn:llmops:ontology:ComputeSubstrate:unknown_id", headers=AUTH)
    assert res_unknown.status_code == 404
    unknown_body = res_unknown.json()
    assert unknown_body["status"] == "not_found"
    assert unknown_body["reason"] == "unknown_urn"
