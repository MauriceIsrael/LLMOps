"""Frozen interface contract (v1) — backward compatibility guard.

Every public MCP tool and REST route has its response shape frozen in
``tests/contract/frozen/``. A key that disappears or changes type fails the test;
added keys pass. The frozen shapes are never regenerated to make this test pass
(see ``scripts/freeze_interfaces.py`` and ``docs/VERSIONING.md``).
"""

import json
from typing import Any

import pytest

from scripts.freeze_interfaces import (
    FROZEN_DIR,
    STATUS_CODES_FILE,
    build_catalogue,
    compare_shapes,
    current_shapes,
    file_name,
    run_catalogue,
    shape_of,
    status_codes,
)

# Contract v1 (docs/VERSIONING.md, schema_version "1.0"). Removing an entry from this
# list is a breaking change.
V1_MCP_TOOLS = [
    # Knowledge plane
    "list_assets", "get_asset", "get_assets", "get_decision_trail", "get_glossary_term",
    "get_principles_for", "search_assets", "query_graph", "get_graph_summary",
    "get_knowledge_analytics", "get_domain_prominence_report", "list_frameworks",
    "list_controls", "get_compliance_trail", "get_compliance_matrix",
    "suggest_knowledge_improvement", "list_skills", "get_skills_matrix", "shred_rfp",
    "generate_zero_draft_hld", "get_rfp_compliance_matrix", "trigger_rfp_elicitation",
    # Engagement plane
    "get_subject", "get_subject_trajectory", "get_board", "get_statements", "get_conflicts",
    "get_open_questions", "get_diagram_graph", "get_dangling_references",
    "get_render_payload", "get_engagement_export",
]

V1_REST_ROUTES = [
    "GET /health", "GET /healthz", "GET /ready", "GET /readyz", "GET /sse", "POST /messages",
    "GET /visualize", "GET /snapshot/latest", "GET /snapshot/{snapshot_id}",
    "GET /api/knowledge/search", "GET /api/knowledge/engagements",
    "POST /api/knowledge/suggestions", "GET /api/compliance/conformity-snapshot",
    "GET /api/compliance/frameworks", "GET /api/compliance/frameworks/applicable",
    "PUT /api/compliance/frameworks/applicable", "POST /api/compliance/frameworks/applicable",
    "POST /api/rfp/shred-to-candidates", "POST /api/documents/zero-draft-blueprint",
    "POST /api/prose/suggest-batch", "POST /api/elicitation/trigger",
    "GET /api/elicitation/questions", "GET /api/arbitration/board",
    "GET /api/arbitration/conflicts", "GET /api/arbitration/statements", "GET /api/skills",
    "GET /api/skills/matrix",
]

V1_INTERFACES = [f"mcp.{t}" for t in V1_MCP_TOOLS] + [f"rest.{r}" for r in V1_REST_ROUTES]


def _catalogue_names() -> list[str]:
    return [i.name for i in build_catalogue()]


# ---------------------------------------------------------------------------
# Coverage of the frozen contract
# ---------------------------------------------------------------------------

def test_v1_contract_is_fully_frozen():
    """Every §1 interface is in the catalogue and has a committed frozen shape."""
    catalogue = set(_catalogue_names())
    missing_catalogue = [n for n in V1_INTERFACES if n not in catalogue]
    missing_frozen = [n for n in V1_INTERFACES if not (FROZEN_DIR / file_name(n)).exists()]
    assert not missing_catalogue, f"Interfaces missing from the catalogue: {missing_catalogue}"
    assert not missing_frozen, f"Interfaces without a frozen shape: {missing_frozen}"


def test_every_frozen_shape_is_still_served():
    """A frozen shape whose interface left the catalogue means the interface was removed."""
    catalogue = {file_name(n) for n in _catalogue_names()}
    orphans = sorted(p.name for p in FROZEN_DIR.glob("*.shape.json") if p.name not in catalogue)
    assert not orphans, f"Frozen interfaces no longer in the catalogue (removed?): {orphans}"


def test_every_served_interface_is_catalogued():
    """New MCP tools and REST routes must be added to the catalogue (and frozen)."""
    import mcp_server.main as main
    import mcp_server.main_engagement as main_engagement
    import mcp_server.main_knowledge as main_knowledge

    catalogue = set(_catalogue_names())
    tools: set[str] = set()
    for server in (main.mcp, main_knowledge.mcp, main_engagement.mcp):
        tools.update(server._tool_manager._tools.keys())
    uncatalogued_tools = sorted(t for t in tools if f"mcp.{t}" not in catalogue)

    routes: set[str] = set()
    for route in main.create_starlette_app().routes:
        for method in sorted(getattr(route, "methods", None) or {"GET"}):
            if method == "HEAD":
                continue
            routes.add(f"rest.{method} {route.path}")
    uncatalogued_routes = sorted(r for r in routes if r not in catalogue)

    assert not uncatalogued_tools, f"MCP tools missing from the catalogue: {uncatalogued_tools}"
    assert not uncatalogued_routes, f"REST routes missing from the catalogue: {uncatalogued_routes}"
    # Engagement tools served by the knowledge server entry point (query_graph,
    # get_graph_summary) share their name with knowledge tools and are covered there.


# ---------------------------------------------------------------------------
# Shape comparison
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def results() -> dict[str, Any]:
    return run_catalogue()


@pytest.fixture(scope="module")
def shapes(results: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return current_shapes(results)


@pytest.mark.parametrize("name", sorted(p.name for p in FROZEN_DIR.glob("*.shape.json")))
def test_frozen_shape_is_preserved(name: str, shapes: dict[str, dict[str, Any]]):
    frozen = json.loads((FROZEN_DIR / name).read_text(encoding="utf-8"))
    interface = frozen["interface"]
    assert interface in shapes, f"Interface {interface} was not exercised"
    errors = compare_shapes(frozen["shape"], shapes[interface])
    assert not errors, f"Breaking change on {interface}:\n  " + "\n  ".join(errors)


def test_rest_status_codes_are_preserved(results: dict[str, Any]):
    """The HTTP status code of each REST call is part of the contract."""
    frozen = json.loads(STATUS_CODES_FILE.read_text(encoding="utf-8"))
    current = status_codes(results)
    changed = {n: (code, current.get(n)) for n, code in frozen.items() if current.get(n) != code}
    assert not changed, f"HTTP status changed (frozen, current): {changed}"


# ---------------------------------------------------------------------------
# The comparator itself
# ---------------------------------------------------------------------------

def test_comparator_detects_removed_key():
    frozen = shape_of({"status": "ok", "data": {"id": "P-1", "title": "x"}})
    current = shape_of({"status": "ok", "data": {"id": "P-1"}})
    assert compare_shapes(frozen, current) == ["$.data.title: key removed"]


def test_comparator_detects_type_change():
    frozen = shape_of({"count": 3})
    current = shape_of({"count": "3"})
    assert compare_shapes(frozen, current)


def test_comparator_detects_removed_key_in_list_items():
    frozen = shape_of({"data": [{"id": "a", "title": "t"}]})
    current = shape_of({"data": [{"id": "a"}]})
    assert compare_shapes(frozen, current) == ["$.data[].title: key removed"]


def test_comparator_accepts_added_keys_and_nulls():
    frozen = shape_of({"data": [{"id": "a", "owner": "x"}]})
    current = shape_of({"data": [{"id": "a", "owner": None, "deprecation": {"since": "1.2"}}], "extra": 1})
    assert compare_shapes(frozen, current) == []


def test_comparator_accepts_empty_lists():
    frozen = shape_of({"data": [{"id": "a"}]})
    assert compare_shapes(frozen, shape_of({"data": []})) == []
