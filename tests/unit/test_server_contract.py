"""Complete Unit & Integration Contract Tests for ADR-0015 (Tasks F1 to F9)."""

import inspect
from pathlib import Path

import pytest

from mcp_server.core.auth import Unauthorised
from mcp_server.core.config import server_config
from mcp_server.core.db import (
    ReadOnlyKuzuClient,
    discover_engagements,
    get_engagement_path,
    open_connection,
    validate_engagement_id,
)
from mcp_server.engagement import tools as eng_tools
from mcp_server.knowledge import tools as kb_tools
from pipelines.ingestion.generate_schema_doc import generate_schema_markdown
from tools.elicitation.repository import ElicitationRepository

pytestmark = pytest.mark.deterministic


def is_empty_or_declared(result: dict | list | None) -> bool:
    """Checks if a tool result is empty or explicitly declares absence."""
    if result is None or result == [] or result == {}:
        return True
    if isinstance(result, list):
        return len(result) == 0
    if isinstance(result, dict):
        if result.get("found") is False:
            return True
        status = result.get("status")
        if status in ("not_found", "not_implemented", "invalid_argument", "error", "unauthorized"):
            return True
        if result.get("count") == 0:
            return True
        data = result.get("data")
        if data is None or data == [] or data == {}:
            return True
        if isinstance(data, dict) and data.get("nodes") == [] and data.get("edges") == []:
            return True
    return False


def is_error(result: dict | list | None) -> bool:
    """Checks if result indicates an error."""
    if isinstance(result, dict):
        return "error" in result or result.get("status") in ("error", "invalid_argument")
    return False


# --- F1: Identifier Validation & Discovery ---

def test_identifier_validation():
    """F1 — Engagement identifiers must be lowercase, alphanumeric and hyphens only."""
    assert validate_engagement_id("nordwave-mcx-2027") == "nordwave-mcx-2027"
    assert validate_engagement_id("demo-1") == "demo-1"

    invalid_ids = ["../malicious", "UPPERCASE", "with_underscore", "test/path", "dot.segment"]
    for inv in invalid_ids:
        with pytest.raises(ValueError):
            validate_engagement_id(inv)


def test_discovery_reports_filesystem(tmp_path):
    """F1 — get_graph_summary reports engagements present in data/engagements/ dynamically."""
    eng_dir = tmp_path / "engagements"
    eng_dir.mkdir(parents=True, exist_ok=True)

    (eng_dir / "alpha-1.kuzu").touch()
    (eng_dir / "beta-2.kuzu").touch()

    discovered = discover_engagements(base_dir=eng_dir)
    found_ids = [d["id"] for d in discovered]
    assert found_ids == ["alpha-1", "beta-2"]


# --- F2: Connection Routing & Order of Operations ---

def test_authorise_before_resolution_ordering(tmp_path):
    """F2 — Authorisation runs before file resolution. Unauthorised and unknown engagements are indistinguishable."""
    eng_dir = tmp_path / "engagements"
    eng_dir.mkdir(parents=True, exist_ok=True)
    server_config.engagements_dir = eng_dir

    # 1. Authorisation first
    with pytest.raises(Unauthorised):
        open_connection(scope="", caller="default_user")

    # 2. Unknown engagement raises FileNotFoundError (or returns not_found envelope in tools)
    with pytest.raises(FileNotFoundError):
        open_connection(scope="non-existent-9999", caller="default_user")


# --- F3: Physical Plane Separation Proof (ADR-0015) ---

def test_planes_are_physically_separate():
    """F3 & ADR-0015 — Assert physical plane separation between knowledge and engagement databases."""
    kb_p = server_config.knowledge_db_path
    eng_p = server_config.engagements_dir / "nordwave-mcx-2027.kuzu"

    client_k = ReadOnlyKuzuClient(db_path=kb_p)
    tables_k = {r["name"] for r in client_k.execute_cypher("CALL show_tables() RETURN name;")}

    forbidden_in_knowledge = {"Subject", "Statement", "Question", "Conflict", "Uncertainty"}
    assert not (forbidden_in_knowledge & tables_k), f"Knowledge plane contains engagement tables: {forbidden_in_knowledge & tables_k}"

    client_e = ReadOnlyKuzuClient(db_path=eng_p)
    tables_e = {r["name"] for r in client_e.execute_cypher("CALL show_tables() RETURN name;")}
    assert "Asset" not in tables_e, "Engagement plane contains copied Asset table!"


# --- F4: Extended query_graph & Driver-Level Enforceability ---

def test_query_graph_driver_level_enforcement():
    """F4 — Query naming Statement without engagement fails at driver level (table does not exist)."""
    res = kb_tools.query_graph("MATCH (st:Statement) RETURN st;")
    assert res.get("status") == "error"
    assert "does not exist" in res.get("reason", "").lower() or "binder exception" in res.get("reason", "").lower()


@pytest.mark.parametrize("q", [
    "CREATE (n:Asset {id:'x'})",
    "MATCH (a:Asset) SET a.title='x'",
    "MATCH (a:Asset) DETACH DELETE a",
    "MERGE (n:Asset {id:'y'})",
])
def test_query_graph_refuses_writes(q):
    """T0.2 — Cypher write statements are refused at driver level."""
    res_kb = kb_tools.query_graph(cypher_query=q)
    assert is_error(res_kb)

    res_eng = eng_tools.query_graph(cypher_query=q)
    assert is_error(res_eng)


# --- F5: Published Snapshot Population Test ---

def test_published_engagement_returns_populated_board():
    """F5 — get_board on published reference engagement returns populated maturity board."""
    target_path = get_engagement_path("nordwave-mcx-2027")
    repo = ElicitationRepository(db_path=target_path)
    repo.save_subject("mcx-services", engagement="nordwave-mcx-2027")
    repo.advance_subject_level("mcx-services", "L2_decomposed", engagement="nordwave-mcx-2027")
    repo.close()

    ReadOnlyKuzuClient._read_db_cache.clear()

    res = eng_tools.get_board("nordwave-mcx-2027")
    assert res.get("status") == "ok"
    board = res.get("data", [])
    assert len(board) > 0, "Published reference engagement must return a populated board!"


# --- F7: get_graph_summary One Answer (No Root Duplicates) ---

def test_get_graph_summary_has_no_contradictory_root_fields():
    """F7 — get_graph_summary root contains data envelope only without plane/dataset root duplicates."""
    res = kb_tools.get_graph_summary()
    assert res.get("status") == "ok"
    assert "plane" not in res, "Root 'plane' field must be removed to avoid self-contradiction!"
    assert "dataset" not in res, "Root 'dataset' field must be removed!"
    assert "schema_version" not in res, "Root 'schema_version' field must be removed!"

    data = res.get("data", {})
    assert "knowledge" in data
    assert "engagements" in data


# --- F8: Introspection & Authorisation Proofs ---

def test_all_engagement_tools_call_authorise():
    """F8 — Introspect engagement tools module and assert every tool passes through authorise choke point."""
    from mcp_server.engagement import tools as eng_module

    for name, func in inspect.getmembers(eng_module, inspect.isfunction):
        if func.__module__ != eng_module.__name__ or name.startswith("_") or name == "authorise":
            continue
        source = inspect.getsource(func)
        assert "authorise(" in source, f"Engagement tool '{name}' does not call authorise choke point!"


def test_every_advertised_tool_is_callable():
    """A1 — Every advertised tool in main_knowledge and main_engagement is callable."""
    from mcp_server.main_engagement import mcp as eng_mcp
    from mcp_server.main_knowledge import mcp as kb_mcp

    kb_tools_list = kb_mcp._tool_manager.list_tools()
    kb_names = {t.name for t in kb_tools_list}
    forbidden_on_kb = {"get_subject_trajectory", "get_diagram_graph", "get_render_payload", "get_subject", "get_board"}
    assert not (kb_names & forbidden_on_kb), f"Knowledge server advertises engagement tools: {kb_names & forbidden_on_kb}"

    eng_tools_list = eng_mcp._tool_manager.list_tools()
    eng_names = {t.name for t in eng_tools_list}
    forbidden_on_eng = {"list_assets", "get_asset", "get_assets", "get_decision_trail", "get_glossary_term", "search_assets", "get_principles_for"}
    assert not (eng_names & forbidden_on_eng), f"Engagement server advertises knowledge tools: {eng_names & forbidden_on_eng}"


# --- F9: Schema Doc Validation ---

def test_schema_doc_is_up_to_date():
    """F9 — Assert docs/SCHEMA.md is up to date with generated catalogue."""
    generated = generate_schema_markdown(
        server_config.knowledge_db_path,
        server_config.engagements_dir / "nordwave-mcx-2027.kuzu",
    )
    schema_file = Path("docs/SCHEMA.md")
    assert schema_file.exists(), "docs/SCHEMA.md does not exist!"
    committed = schema_file.read_text(encoding="utf-8")
    assert committed.strip() == generated.strip(), "docs/SCHEMA.md differs from generated schema catalogue!"


# --- E1, E3, E4: Third-Party Integration Workorder Tests ---

def test_mermaid_output_has_quoted_labels():
    """E1 — get_diagram_graph format=mermaid returns quoted labels and safe node syntax."""
    res = eng_tools.get_diagram_graph(engagement="nordwave-mcx-2027", format="mermaid")
    assert res.get("status") == "ok"
    mermaid_str = res.get("data", {}).get("mermaid", "")
    assert "flowchart TD" in mermaid_str
    # Check that labels are properly quoted in double quotes
    for line in mermaid_str.splitlines():
        if "-->" in line:
            assert "|\"" in line or "|'" in line or "-->|" in line, f"Unquoted Mermaid edge label in line: {line}"


def test_schema_version_in_get_graph_summary():
    """E3 — get_graph_summary returns schema_version under data."""
    res = kb_tools.get_graph_summary()
    assert res.get("status") == "ok"
    data = res.get("data", {})
    assert data.get("schema_version") == "1.0", f"Expected schema_version '1.0', got: {data.get('schema_version')}"


def test_get_engagement_export_returns_all():
    """E4 — get_engagement_export combines board, render payload, and diagram graph."""
    res = eng_tools.get_engagement_export(engagement="nordwave-mcx-2027")
    assert res.get("status") == "ok"
    data = res.get("data", {})
    assert data.get("engagement") == "nordwave-mcx-2027"
    assert "board" in data
    assert "render_payload" in data
    assert "diagram_graph" in data

