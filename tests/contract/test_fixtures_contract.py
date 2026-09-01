"""Contract test verifying offline fixtures against schemas and export generator."""

import json
from pathlib import Path

from scripts.export_fixtures import export_fixtures

ROOT_DIR = Path(__file__).parent.parent.parent
FIXTURES_DIR = ROOT_DIR / "fixtures"
SCHEMAS_DIR = ROOT_DIR / "schemas"


REQUIRED_FIXTURES = [
    "knowledge_snapshot.json",
    "engagement_snapshot.json",
    "get_render_payload.json",
    "get_board.json",
    "get_diagram_graph.json",
    "sealed_snapshot.json",
]


def test_fixtures_exist():
    """Verify all required fixture files exist."""
    for filename in REQUIRED_FIXTURES:
        filepath = FIXTURES_DIR / filename
        assert filepath.exists(), f"Fixture file {filename} is missing!"


def test_fixtures_valid_envelope():
    """Verify standard MCP fixtures match ResponseEnvelope structure."""
    mcp_fixtures = [
        "knowledge_snapshot.json",
        "engagement_snapshot.json",
        "get_render_payload.json",
        "get_board.json",
        "get_diagram_graph.json",
    ]
    required_keys = {"status", "count", "data"}
    allowed_statuses = {"ok", "not_found", "invalid_argument", "error", "unauthorized"}

    for filename in mcp_fixtures:
        filepath = FIXTURES_DIR / filename
        data = json.loads(filepath.read_text(encoding="utf-8"))
        assert isinstance(data, dict), f"{filepath.name} is not a JSON object!"
        assert required_keys.issubset(data.keys()), f"{filepath.name} missing required envelope keys!"
        assert data["status"] in allowed_statuses, f"{filepath.name} invalid status: {data['status']}"
        assert isinstance(data["count"], int), f"{filepath.name} count is not an integer!"


def test_sealed_snapshot_structure():
    """Verify sealed_snapshot.json matches SealedSnapshotEnvelope requirements."""
    filepath = FIXTURES_DIR / "sealed_snapshot.json"
    data = json.loads(filepath.read_text(encoding="utf-8"))

    required_sealed_keys = {
        "snapshot_id",
        "created_at",
        "source_revision",
        "payload_sha256",
        "schema_version",
        "applicability_index",
        "assets",
        "glossary",
    }
    assert required_sealed_keys.issubset(data.keys()), "Sealed snapshot missing required envelope keys!"
    assert data["payload_sha256"].startswith("sha256:"), "Missing or invalid sha256 prefix in payload_sha256!"
    assert data["schema_version"] == "1.0"
    assert isinstance(data["assets"], list) and len(data["assets"]) > 0
    assert isinstance(data["applicability_index"], dict)

    for asset in data["assets"]:
        assert "id" in asset and "typed_id" in asset and "confidence" in asset
        assert asset["typed_id"].startswith(("decision:", "principle:", "pattern:", "template:", "risk:", "questionnaire:", "framework:", "asset:"))
        assert "provenance" in asset and "text_sha256" in asset["provenance"]


def test_fixtures_freshness(tmp_path):
    """Verify committed fixtures match export_fixtures generator output."""
    export_fixtures(engagement="nordwave-mcx-2027", output_dir=tmp_path)

    for filename in REQUIRED_FIXTURES:
        committed_file = FIXTURES_DIR / filename
        generated_file = tmp_path / filename
        assert generated_file.exists(), f"Generator failed to produce {filename}"

        committed_json = json.loads(committed_file.read_text(encoding="utf-8"))
        generated_json = json.loads(generated_file.read_text(encoding="utf-8"))

        def strip_transient(obj):
            if isinstance(obj, dict):
                return {k: strip_transient(v) for k, v in obj.items() if k not in ("updated_at", "created_at", "dataset")}
            if isinstance(obj, list):
                return [strip_transient(item) for item in obj]
            return obj

        if filename == "sealed_snapshot.json":
            # Compare deterministic payload fields (excluding non-deterministic timestamp)
            assert committed_json["assets"] == generated_json["assets"]
            assert committed_json["glossary"] == generated_json["glossary"]
            assert committed_json["applicability_index"] == generated_json["applicability_index"]
            assert committed_json["schema_version"] == generated_json["schema_version"]
        else:
            assert strip_transient(committed_json) == strip_transient(generated_json), (
                f"Fixture {filename} is stale! Run 'poetry run python scripts/export_fixtures.py' to update."
            )
