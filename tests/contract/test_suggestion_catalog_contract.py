"""Contract tests for Architecture Studio SuggestionCatalogPort integration."""

import json
from pathlib import Path

import jsonschema
import pytest

from tools.adapters.suggestion_adapter import SuggestionCatalogAdapter


@pytest.mark.deterministic
def test_suggestion_catalog_spof_contract():
    """Verify SuggestionCatalogAdapter satisfies SuggestionCatalogPort contract schema for SPOF."""
    adapter = SuggestionCatalogAdapter()
    res = adapter.get_suggestions(
        issue_kind="SPOF",
        domain="MCX",
        context_tags=["resilience", "active-active"],
        limit=3,
    )

    assert res.get("status") == "ok"
    assert res.get("count", 0) > 0
    data = res.get("data", {})
    assert "context" in data
    assert "suggestions" in data
    assert len(data["suggestions"]) > 0

    # Validate against JSON schema
    schema_path = Path("schemas/suggestion_catalog.schema.json")
    assert schema_path.exists()
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.validate(instance=res, schema=schema)

    # Check suggestion fields
    for sugg in data["suggestions"]:
        assert "pattern_id" in sugg
        assert "typed_id" in sugg
        assert "title" in sugg
        assert "confidence" in sugg
        assert "external_ref" in sugg
        assert sugg["external_ref"].startswith("KH:")
        assert "@v" in sugg["external_ref"]


@pytest.mark.deterministic
def test_suggestion_catalog_graceful_fallback():
    """Verify SuggestionCatalogAdapter degrades gracefully when queried with unusual context."""
    adapter = SuggestionCatalogAdapter(snapshot_path="/non/existent/path.json")
    res = adapter.get_suggestions(issue_kind="UNKNOWN_ISSUE", domain="NON_EXISTENT", limit=2)

    assert res.get("status") == "ok"
    assert "data" in res
    assert isinstance(res["data"]["suggestions"], list)

