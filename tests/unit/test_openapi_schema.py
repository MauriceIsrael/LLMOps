"""Unit tests — OpenAPI 3.1 schema generation from frozen REST interfaces (Issues #36 & #37)."""

import json
from pathlib import Path

from scripts.generate_openapi import OUTPUT_PATH, build_openapi

ROOT = Path(__file__).resolve().parents[2]


def test_openapi_schema_is_up_to_date_and_covers_frozen_routes():
    assert OUTPUT_PATH.is_file(), "schemas/openapi.json is missing; run scripts/generate_openapi.py"
    committed = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    expected = build_openapi()
    assert committed == expected, "schemas/openapi.json is out of date; regenerate with scripts/generate_openapi.py"
    assert committed["openapi"] == "3.1.0"
    assert len(committed["paths"]) >= 110
    assert committed["paths"]["/api/documents/zero-draft-blueprint"]["post"]["deprecated"] is True
    assert committed["paths"]["/api/rfp/shred-to-candidates"]["post"]["deprecated"] is True
    assert committed["paths"]["/health"]["get"]["security"] == []
