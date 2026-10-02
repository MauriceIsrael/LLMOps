"""Suite canonical-json v1: the shared vectors (accepted and refused) pass; json.dumps is shown NOT to be the profile."""

import hashlib
import json
from pathlib import Path

import pytest

from pipelines import canonical

VECTORS_FILE = Path(__file__).parent.parent / "fixtures" / "canonical-json.vectors.json"
VECTORS = json.loads(VECTORS_FILE.read_text(encoding="utf-8"))


def test_vectors_file_is_the_one_of_the_suite():
    # Pinned: the suite requires this file to be identical byte for byte in every repository that holds it.
    assert hashlib.sha256(VECTORS_FILE.read_bytes()).hexdigest()[:16] == "3f629da8a4b9bd8a"
    assert VECTORS["profile"] == "architecture-suite/canonical-json" and VECTORS["version"] == 1


@pytest.mark.parametrize("case", VECTORS["accept"], ids=lambda c: c["name"])
def test_accepted_vectors_give_the_same_text_and_checksum(case):
    value = canonical.loads(case["json"])
    assert canonical.dumps(value) == case["canonical"]
    assert canonical.sha256(value) == case["sha256"]


@pytest.mark.parametrize("case", VECTORS["reject"], ids=lambda c: c["name"])
def test_refused_vectors_are_refused_with_the_profile_code(case):
    with pytest.raises(canonical.CanonicalError) as err:
        canonical.dumps(canonical.loads(case["json"]))
    assert err.value.code == case["code"]


def test_python_json_dumps_is_not_the_profile():
    # Why this module exists: the common idiom diverges on 7 accepted vectors and accepts every refused one.
    def idiom(text):
        return json.dumps(json.loads(text), separators=(",", ":"), sort_keys=True, ensure_ascii=False)

    assert sum(idiom(c["json"]) != c["canonical"] for c in VECTORS["accept"]) >= 7


def test_other_python_values_are_refused_not_guessed():
    from datetime import datetime
    from decimal import Decimal

    for value in (datetime(2026, 10, 2), Decimal("1.5"), {1, 2}, (1, 2), b"x", {1: "a"}, float("nan"), float("inf"), "\ud800"):
        with pytest.raises(canonical.CanonicalError):
            canonical.dumps(value)
