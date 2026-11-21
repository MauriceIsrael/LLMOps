"""Contract and integration tests for the ontology API and MCP tools (Issue #175)."""

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


def test_ontology_routes_are_always_served_without_any_feature_flag():
    """There is no feature flag: the ontology routes are served, and no response says the feature is disabled."""
    client = TestClient(create_starlette_app())
    listing = client.get("/api/knowledge/ontology", headers=AUTH)
    assert listing.status_code == 200
    assert "experimental" not in listing.json()
    export = client.get("/api/knowledge/ontology/export", headers=AUTH)
    assert export.status_code == 200
    assert "disabled" not in export.text.lower()


def test_mcp_tools_and_http_endpoints_respond():
    """REST endpoints and MCP tools respond, with no `experimental` marker."""

    app = create_starlette_app()
    client = TestClient(app)

    # 1. GET /api/knowledge/ontology
    res = client.get("/api/knowledge/ontology", headers=AUTH)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "ok"
    assert "experimental" not in body
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
    assert "experimental" not in urn_body
    assert urn_body["data"]["id"] == urn
    assert urn_body["data"]["term"] == "Bare Metal Kubernetes"
    assert "projections" in urn_body["data"]
    assert "suse_sylva_capi" in urn_body["data"]["projections"]

    # 3. Direct MCP tool calls
    tool_list_res = list_ontology_terms(concept_class="ComputeSubstrate")
    assert tool_list_res["status"] == "ok"
    assert "experimental" not in tool_list_res
    assert len(tool_list_res["data"]) >= 4

    tool_get_res = get_ontology_term(urn)
    assert tool_get_res["status"] == "ok"
    assert "experimental" not in tool_get_res
    assert tool_get_res["data"]["id"] == urn


def test_unknown_revision_returns_explicit_machine_readable_error(monkeypatch):
    """Requesting an absent revision returns 404 with reason='revision_not_found' without fallback."""

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
    assert "experimental" not in body

    # Request unknown URN
    res_unknown = client.get("/api/knowledge/ontology/urn:llmops:ontology:ComputeSubstrate:unknown_id", headers=AUTH)
    assert res_unknown.status_code == 404
    unknown_body = res_unknown.json()
    assert unknown_body["status"] == "not_found"
    assert unknown_body["reason"] == "unknown_urn"


def test_ontology_export_contract_and_tool(monkeypatch):
    """GET /api/knowledge/ontology/export serves the validated SI & Telco catalog (Issue #180, #182)."""

    app = create_starlette_app()
    client = TestClient(app)

    # 1. Unauthorized when missing or invalid auth
    res_unauth = client.get("/api/knowledge/ontology/export")
    assert res_unauth.status_code in (401, 403)

    # 2. Authorized export returns 200 with JSON catalog
    res = client.get("/api/knowledge/ontology/export", headers=AUTH)
    assert res.status_code == 200
    assert "application/json" in res.headers["content-type"]
    catalog = res.json()

    assert "catalog_version" in catalog
    assert "generated_at" in catalog
    assert "entities" in catalog
    assert "triplets" in catalog

    entities = catalog["entities"]
    triplets = catalog["triplets"]

    assert len(entities) >= 46
    assert len(triplets) >= 43

    # Check HLD concepts present
    hld_concepts = [
        "urn:archinex:ontology:concept:telco_cloud_platform",
        "urn:archinex:ontology:concept:interconnection_gateway",
        "urn:archinex:ontology:concept:storage_data_persistence",
        "urn:archinex:ontology:concept:iam_security_zerotrust",
        "urn:archinex:ontology:concept:observability_noc_soc",
        "urn:archinex:ontology:concept:resilience_drp_continuity",
    ]
    for c_urn in hld_concepts:
        assert c_urn in entities, f"Missing HLD concept: {c_urn}"
        assert entities[c_urn]["kind"] == "concept"

    # Check triplets structure and relational consistency
    for t in triplets:
        assert "id" in t
        # Prédicats du contrat : ceux d'origine, plus requires_prerequisite_axis et instantiates_component (issue #192).
        assert t["predicate"] in (
            "requires_aspect",
            "implemented_by",
            "depends_on",
            "constrains",
            "conflicts_with",
            "satisfies_clause",
            "requires_prerequisite_axis",
            "instantiates_component",
        )
        assert t["subject"] in entities, f"Dangling subject: {t['subject']}"
        if t["predicate"] == "satisfies_clause":
            assert t["object"].startswith("urn:archinex:kb:clause:") or t["object"].startswith("urn:llmops:kb:clause:")
        elif t["predicate"] == "instantiates_component":
            # L'objet est un composant logique, pas une entité d'ontologie (issue #192).
            assert t["object"].startswith("urn:archinex:component:"), t["object"]
        else:
            assert t["object"] in entities, f"Dangling object: {t['object']}"

    # 3. Direct MCP tool call
    from mcp_server.knowledge.tools import export_ontology_catalog

    tool_res = export_ontology_catalog()
    assert tool_res["status"] == "ok"
    assert "experimental" not in tool_res
    assert "entities" in tool_res
    assert len(tool_res["entities"]) >= 46
    assert "triplets" in tool_res
    assert len(tool_res["triplets"]) >= 43


def test_ontology_clause_governance_and_bidirectional_resolution(monkeypatch):
    """Test satisfies_clause triplets, leaf governed_by_clauses, and bidirectional resolution (Issue #184)."""
    import json

    import jsonschema

    from mcp_server.knowledge.tools import export_ontology_catalog
    from pipelines.ontology.catalog import validate_clause_leaf_integrity


    app = create_starlette_app()
    client = TestClient(app)

    # 1. Full export validation and mathematical integrity
    res = client.get("/api/knowledge/ontology/export", headers=AUTH)
    assert res.status_code == 200
    catalog = res.json()

    assert "clause_index" in catalog
    assert "by_clause" in catalog["clause_index"]
    assert "by_leaf" in catalog["clause_index"]

    # Verify no dangling links or mismatch between governed_by_clauses and satisfies_clause
    integrity_errors = validate_clause_leaf_integrity(catalog)
    assert not integrity_errors, f"Clause-leaf integrity failed: {integrity_errors}"

    # 2. JSON Schema validation against ontology_catalog.schema.json
    schema_path = ROOT / "schemas" / "ontology_catalog.schema.json"
    assert schema_path.is_file(), f"Missing schema file: {schema_path}"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.validate(instance=catalog, schema=schema)

    # 3. Verify specific leaf with governed_by_clauses (Issue #184 specification)
    leaf_urn = "urn:archinex:ontology:security:crypto:ipsec_ikev2_aes256"
    assert leaf_urn in catalog["entities"]
    leaf_entity = catalog["entities"][leaf_urn]
    assert leaf_entity["kind"] == "leaf"
    assert "governed_by_clauses" in leaf_entity
    assert "urn:archinex:kb:clause:nis2:art21_crypto" in leaf_entity["governed_by_clauses"]
    assert "urn:archinex:kb:clause:3gpp:ts33_501_sec_s6a" in leaf_entity["governed_by_clauses"]

    # 4. Bidirectional REST resolution: by clause
    clause_urn = "urn:archinex:kb:clause:nis2:art21_crypto"
    res_clause = client.get("/api/knowledge/ontology/export", headers=AUTH, params={"clause": clause_urn})
    assert res_clause.status_code == 200
    by_clause_data = res_clause.json()
    assert by_clause_data["status"] == "ok"
    assert by_clause_data["clause"] == clause_urn
    assert leaf_urn in by_clause_data["satisfying_leaves"]
    assert leaf_urn in by_clause_data["entities"]
    assert any(
        t["subject"] == leaf_urn and t["predicate"] == "satisfies_clause" and t["object"] == clause_urn
        for t in by_clause_data["triplets"]
    )

    # 5. Bidirectional REST resolution: by leaf
    res_leaf = client.get("/api/knowledge/ontology/export", headers=AUTH, params={"leaf": leaf_urn})
    assert res_leaf.status_code == 200
    by_leaf_data = res_leaf.json()
    assert by_leaf_data["status"] == "ok"
    assert by_leaf_data["leaf"] == leaf_urn
    assert clause_urn in by_leaf_data["governing_clauses"]
    assert by_leaf_data["entity"]["urn"] == leaf_urn
    assert any(
        t["subject"] == leaf_urn and t["predicate"] == "satisfies_clause" and t["object"] == clause_urn
        for t in by_leaf_data["triplets"]
    )

    # 6. MCP tool bidirectional calls
    tool_clause = export_ontology_catalog(clause=clause_urn)
    assert tool_clause["status"] == "ok"
    assert leaf_urn in tool_clause["satisfying_leaves"]

    tool_leaf = export_ontology_catalog(leaf=leaf_urn)
    assert tool_leaf["status"] == "ok"
    assert clause_urn in tool_leaf["governing_clauses"]




def test_export_serves_catalog_shape_and_never_regenerates_another_shape(monkeypatch, tmp_path):
    """Issue #189 : l'export servi est le catalogue « entities » ; fichier absent ou mauvaise forme = erreur explicite."""
    from pipelines.ontology import catalog_file

    client = TestClient(create_starlette_app())

    # Fichier versionné : forme catalogue.
    monkeypatch.setattr(catalog_file, "DEFAULT_CATALOG_PATH", ROOT / "data" / "snapshots" / "ontology_export.json")
    ok = client.get("/api/knowledge/ontology/export", headers=AUTH)
    assert ok.status_code == 200
    body = ok.json()
    assert isinstance(body["entities"], dict) and body["entities"]
    assert "entries" not in body

    # Fichier absent : 404 explicite, et RIEN n'est régénéré.
    absent = tmp_path / "ontology_export.json"
    monkeypatch.setattr(catalog_file, "DEFAULT_CATALOG_PATH", absent)
    missing = client.get("/api/knowledge/ontology/export", headers=AUTH)
    assert missing.status_code == 404
    assert missing.json()["code"] == "ontology_export_not_found"
    assert not absent.exists()

    # Mauvaise forme (« payload.entries ») : 503 explicite, jamais servie.
    wrong = tmp_path / "wrong.json"
    wrong.write_text('{"payload": {"entries": []}}', encoding="utf-8")
    monkeypatch.setattr(catalog_file, "DEFAULT_CATALOG_PATH", wrong)
    bad = client.get("/api/knowledge/ontology/export", headers=AUTH)
    assert bad.status_code == 503
    assert bad.json()["code"] == "ontology_export_wrong_shape"
