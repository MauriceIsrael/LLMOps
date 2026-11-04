"""Tests for the ontology entry JSON Schema (Issue #167).

Verifies valid and invalid fixtures against schemas/ontology_entry.schema.json.
Every invalid fixture must fail validation, naming the specific causing field.
"""

import json
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).parent.parent.parent
SCHEMA_PATH = ROOT / "schemas" / "ontology_entry.schema.json"
VALID_DIR = ROOT / "fixtures" / "ontology" / "valid"
INVALID_DIR = ROOT / "fixtures" / "ontology" / "invalid"


@pytest.fixture(scope="module")
def ontology_schema():
    assert SCHEMA_PATH.is_file(), f"Schema file missing: {SCHEMA_PATH}"
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def test_schema_itself_is_valid(ontology_schema):
    """The ontology entry schema itself conforms to Draft-07 metaschema."""
    jsonschema.Draft7Validator.check_schema(ontology_schema)


@pytest.mark.parametrize("fixture_file", list(VALID_DIR.glob("*.json")), ids=lambda p: p.stem)
def test_valid_ontology_fixtures(fixture_file, ontology_schema):
    data = json.loads(fixture_file.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(ontology_schema)
    errors = list(validator.iter_errors(data))
    assert not errors, f"Expected {fixture_file.name} to be valid, but got: {[e.message for e in errors]}"


INVALID_EXPECTED_FIELDS = {
    "missing_required_term": "term",
    "unknown_concept_class": "concept_class",
    "malformed_urn": "id",
    "disallowed_relationship": "relationships",
    "invalid_projection_shape": "nautobot",
    "duplicate_synonym": "synonyms",
    "unknown_status": "status",
    "non_integer_revision": "revision",
}


@pytest.mark.parametrize("fixture_file", list(INVALID_DIR.glob("*.json")), ids=lambda p: p.stem)
def test_invalid_ontology_fixtures(fixture_file, ontology_schema):
    data = json.loads(fixture_file.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(ontology_schema)
    errors = list(validator.iter_errors(data))
    assert len(errors) > 0, f"Expected {fixture_file.name} to fail schema validation, but it passed."

    expected_field = INVALID_EXPECTED_FIELDS.get(fixture_file.stem)
    if expected_field:
        # Check that the expected field appears in error message or error path
        matches = [
            e for e in errors
            if expected_field in e.message or any(expected_field in str(p) for p in e.path)
        ]
        assert matches, (
            f"Expected failure for {fixture_file.name} to name field '{expected_field}', "
            f"but got errors: {[e.message for e in errors]} with paths: {[list(e.path) for e in errors]}"
        )
