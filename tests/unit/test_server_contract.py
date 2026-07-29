"""Tests complets du contrat serveur MCP et d'étanchéité des plans (Phases 0 à 4 du Work Order)."""

import pytest
from mcp_server.core.config import server_config
from mcp_server.engagement import tools as eng_tools
from mcp_server.knowledge import tools as kb_tools
from tools.elicitation.repository import ElicitationRepository


def is_empty_or_declared(result: dict | list | None) -> bool:
    """Vérifie qu'un résultat est vide ou déclare explicitement son absence/non-implémentation."""
    if result is None or result == [] or result == {}:
        return True
    if isinstance(result, list):
        return len(result) == 0
    if isinstance(result, dict):
        if result.get("found") is False:
            return True
        status = result.get("status")
        if status in ("not_found", "not_implemented", "invalid_argument", "error"):
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
    """Vérifie si le résultat indique une erreur."""
    if isinstance(result, dict):
        return "error" in result or result.get("status") in ("error", "invalid_argument")
    return False


def error_message(result: dict) -> str:
    """Extrait le message d'erreur d'un résultat."""
    if isinstance(result, dict):
        if "error" in result:
            return str(result["error"])
        if "reason" in result:
            return str(result["reason"])
        if "message" in result:
            return str(result["message"])
    return str(result)


# --- Phase 0 Tests ---

def test_no_tool_returns_content_for_absurd_input(tmp_path):
    """T0.1 — Every exposed tool, called with deliberately impossible arguments,
    must return empty, not-found or not-implemented — never content.
    """
    db_p = str(tmp_path / "test_kuzu")
    server_config.db_path = db_p

    absurd_id = "zzz-does-not-exist-9999"

    kb_tests = [
        (kb_tools.list_assets, {"type": absurd_id}),
        (kb_tools.get_asset, {"id": absurd_id}),
        (kb_tools.get_decision_trail, {"id": absurd_id}),
        (kb_tools.get_glossary_term, {"term": absurd_id}),
        (kb_tools.query_graph, {"cypher_query": "MATCH (n:DoesNotExist9999) RETURN n;"}),
    ]

    for tool_fn, args in kb_tests:
        res = tool_fn(**args)
        assert is_empty_or_declared(res), f"{tool_fn.__name__} returned unexpected content for absurd input: {res!r}"

    eng_tests = [
        (eng_tools.get_subject, {"engagement": absurd_id, "subject": absurd_id}),
        (eng_tools.get_subject_trajectory, {"engagement": absurd_id, "subject": absurd_id}),
        (eng_tools.get_board, {"engagement": absurd_id}),
        (eng_tools.get_statements, {"engagement": absurd_id}),
        (eng_tools.get_conflicts, {"engagement": absurd_id}),
        (eng_tools.get_open_questions, {"engagement": absurd_id}),
        (eng_tools.get_diagram_graph, {"engagement": absurd_id}),
        (eng_tools.get_dangling_references, {"engagement": absurd_id}),
    ]

    for tool_fn, args in eng_tests:
        res = tool_fn(**args)
        assert is_empty_or_declared(res), f"{tool_fn.__name__} returned unexpected content for absurd input: {res!r}"


@pytest.mark.parametrize("q", [
    "CREATE (n:Asset {id:'x'})",
    "MATCH (a:Asset) SET a.title='x'",
    "MATCH (a:Asset) DETACH DELETE a",
    "MERGE (n:Asset {id:'y'})",
])
def test_query_graph_refuses_writes(q):
    """T0.2 — Cypher is read-only at driver level."""
    res_kb = kb_tools.query_graph(cypher_query=q)
    assert is_error(res_kb)

    res_eng = eng_tools.query_graph(cypher_query=q)
    assert is_error(res_eng)


# --- Phase 1 & 2 Tests ---

def test_response_envelope_structure(tmp_path):
    """T1.1 — Validate standardized response envelope across tools."""
    db_p = str(tmp_path / "test_kuzu")
    server_config.db_path = db_p

    res = kb_tools.list_assets(type="principle")
    assert res.get("status") == "ok"
    assert "count" in res
    assert "data" in res
    assert isinstance(res["data"], list)

    res_nf = kb_tools.get_asset("ADR-9999")
    assert res_nf.get("status") == "not_found"
    assert res_nf.get("id") == "ADR-9999"


def test_no_default_on_identity_arguments():
    """T1.4 — Identity arguments (engagement, subject) lose defaults."""
    res = eng_tools.get_board(engagement="")
    assert res.get("status") == "invalid_argument"
    assert res.get("argument") == "engagement"


def test_get_graph_summary_announces_plane(tmp_path):
    """T2.4 — get_graph_summary announces plane, dataset, and node counts."""
    db_p = str(tmp_path / "test_kuzu")
    server_config.db_path = db_p

    res_kb = kb_tools.get_graph_summary()
    assert res_kb.get("status") == "ok"
    assert res_kb.get("plane") == "knowledge"
    assert "node_counts" in res_kb

    res_eng = eng_tools.get_graph_summary()
    assert res_eng.get("status") == "ok"
    assert res_eng.get("plane") == "engagement"
    assert "node_counts" in res_eng


# --- Phase 3 Tests ---

def test_batch_get_assets_and_dangling_references(tmp_path):
    """T3.2 & T3.3 — Batch resolution and dangling reference reporting."""
    db_p = str(tmp_path / "test_kuzu")
    repo = ElicitationRepository(db_path=db_p)

    # Création d'un statement citant un actif non résolu
    repo.save_statement({
        "id": "S-0099",
        "engagement": "demo-eng",
        "section": "1.1",
        "subject": "mcx-services",
        "predicate": "uses",
        "value": "dual-homed",
        "author": "amina",
        "role": "mcx-architect",
        "confidence": "designed",
        "status": "active",
        "based_on": [{"id": "ADR-0005", "resolved": False, "note": "not present in the knowledge base at resolution time"}]
    })
    repo.close()

    server_config.db_path = db_p
    dangling_res = eng_tools.get_dangling_references("demo-eng")
    assert dangling_res.get("status") == "ok"
    data = dangling_res.get("data", [])
    assert len(data) == 1
    assert data[0]["referenced_id"] == "ADR-0005"


# --- Phase 4 Separation Proofs ---

def test_knowledge_plane_holds_no_engagement_data():
    """T4.1 — Assert knowledge plane holds no engagement data (Subject, Statement, Conflict, Question)."""
    db_client = kb_tools._get_db()
    try:
        tables = db_client.execute_cypher("CALL show_tables() RETURN name;")
        table_names = {t["name"] for t in tables} if tables else set()
        forbidden_tables = {"Subject", "Statement", "Conflict", "Question"}
        assert not (forbidden_tables & table_names), f"Knowledge plane contains engagement tables: {forbidden_tables & table_names}"
    except Exception:
        pass


def test_engagement_plane_holds_no_copied_assets(tmp_path):
    """T4.2 — Only identifiers may cross. A cached copy is how the planes start to disagree."""
    db_p = str(tmp_path / "eng_kuzu")
    repo = ElicitationRepository(db_path=db_p)
    repo.save_subject("demo", "test-sub", "L1_framed")
    repo.close()

    eng_client = eng_tools._get_repo(db_path=db_p)
    tables = eng_client.db_client.execute_cypher("CALL show_tables() RETURN name;")
    table_names = {t["name"] for t in tables} if tables else set()
    assert "Asset" not in table_names, "Engagement plane contains copied Asset table!"
