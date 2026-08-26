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
]


def test_fixtures_exist():
    """Verify all required fixture files exist."""
    for filename in REQUIRED_FIXTURES:
        filepath = FIXTURES_DIR / filename
        assert filepath.exists(), f"Fixture file {filename} is missing!"


def test_fixtures_valid_envelope():
    """Verify each fixture JSON matches the ResponseEnvelope structure."""
    required_keys = {"status", "count", "data"}
    allowed_statuses = {"ok", "not_found", "invalid_argument", "error", "unauthorized"}

    for filename in REQUIRED_FIXTURES:
        filepath = FIXTURES_DIR / filename
        data = json.loads(filepath.read_text(encoding="utf-8"))
        assert isinstance(data, dict), f"{filepath.name} is not a JSON object!"
        assert required_keys.issubset(data.keys()), f"{filepath.name} missing required envelope keys!"
        assert data["status"] in allowed_statuses, f"{filepath.name} invalid status: {data['status']}"
        assert isinstance(data["count"], int), f"{filepath.name} count is not an integer!"


def test_fixtures_freshness(tmp_path):
    """Verify committed fixtures match export_fixtures generator output."""
    export_fixtures(engagement="nordwave-mcx-2027", output_dir=tmp_path)

    for filename in REQUIRED_FIXTURES:
        committed_file = FIXTURES_DIR / filename
        generated_file = tmp_path / filename
        assert generated_file.exists(), f"Generator failed to produce {filename}"

        committed_json = json.loads(committed_file.read_text(encoding="utf-8"))
        generated_json = json.loads(generated_file.read_text(encoding="utf-8"))

        assert committed_json == generated_json, (
            f"Fixture {filename} is stale! Run 'poetry run python scripts/export_fixtures.py' to update."
        )
