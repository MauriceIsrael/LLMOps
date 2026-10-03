"""One confidence vocabulary (suite ADR-KH-01 D4): verified / designed / vendor-stated / stated-by-client / assumed."""

import json
import re
from pathlib import Path

import jsonschema
import pytest

from pipelines.kb_candidates.confidence import compute_confidence
from tools.elicitation.config import CONFIDENCE_LEVELS

ROOT = Path(__file__).parent.parent.parent
FIVE = {"verified", "designed", "vendor-stated", "stated-by-client", "assumed"}


def _frontmatter_enum() -> set[str]:
    schema = json.loads((ROOT / "data/kb/schema/frontmatter.schema.json").read_text(encoding="utf-8"))
    return set(schema["properties"]["confidence"]["enum"])


def test_every_place_that_names_the_vocabulary_agrees():
    snapshot = json.loads((ROOT / "schemas/sealed_snapshot.schema.json").read_text(encoding="utf-8"))
    snapshot_enum = set(snapshot["properties"]["assets"]["items"]["properties"]["confidence"]["enum"]) if "assets" in snapshot["properties"] else FIVE
    ts = (ROOT / "schemas/types.ts").read_text(encoding="utf-8")
    ts_union = set(re.search(r"export type ConfidenceLevel = ([^;]+);", ts).group(1).replace('"', "").replace(" ", "").split("|"))
    assert _frontmatter_enum() == set(CONFIDENCE_LEVELS) == snapshot_enum == ts_union == FIVE


@pytest.mark.parametrize("value", sorted(FIVE))
def test_an_asset_may_carry_any_of_the_five_values(value):
    schema = json.loads((ROOT / "data/kb/schema/frontmatter.schema.json").read_text(encoding="utf-8"))
    confidence_schema = {**schema["properties"]["confidence"], "$schema": "http://json-schema.org/draft-07/schema#"}
    jsonschema.validate(value, confidence_schema)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate("trusted", confidence_schema)


def test_promotion_never_manufactures_designed_or_client_stated_confidence():
    # Confidence is computed from evidence, never from the author: only these three can come out of a promotion.
    cases = [None, [], [{"kind": "engagement", "ref": "e1"}], [{"kind": "vendor-doc", "ref": "d"}], [{"kind": "measure", "ref": "m"}]]
    produced = {compute_confidence(evidence, "human-authored") for evidence in cases}
    assert produced == {"assumed", "vendor-stated", "verified"}
    assert not produced & {"designed", "stated-by-client"}
