"""Unit tests for the anti-fabrication validator (scripts/eval/validate.py).

Per Workorder v2 §2.5: Verifies that the validator rejects all artificial bad cases
(AST literal violation, SHA-256 mismatch, unquoted verbatim, missing runs/ directory, pre-matched fields).
"""

import json
from pathlib import Path

from scripts.eval.validate import (
    check_ast_literals,
    check_ground_truth,
    check_runs,
    check_sources,
    compute_sha256,
)


def test_ast_literal_rejection(tmp_path: Path):
    """Asserts that a python script with a function returning a literal list > 3 items is rejected."""
    bad_script = tmp_path / "bad_script.py"
    bad_script.write_text(
        "def fake_fetch():\n    return ['item1', 'item2', 'item3', 'item4']\n",
        encoding="utf-8",
    )

    errors = check_ast_literals(bad_script, max_allowed=3)
    assert len(errors) > 0
    assert "returns hardcoded list literal" in errors[0]


def test_sha256_mismatch_rejection(tmp_path: Path):
    """Asserts that a source file with mismatched SHA-256 is rejected."""
    sources_dir = tmp_path / "data" / "eval" / "sources"
    sources_dir.mkdir(parents=True)

    spec_file = sources_dir / "TS_22.179.txt"
    spec_file.write_text("Sample 3GPP specification text " * 500, encoding="utf-8")

    manifest_dir = tmp_path / "docs" / "eval"
    manifest_dir.mkdir(parents=True)

    # Intentionally bad SHA-256 hash
    bad_hash = "0000000000000000000000000000000000000000000000000000000000000000"
    manifest = manifest_dir / "SOURCES.md"
    manifest.write_text(
        f"| Document | Filename | SHA-256 | Size |\n|---|---|---|---|\n| TS 22.179 | TS_22.179.txt | {bad_hash} | 15 KB |\n",
        encoding="utf-8",
    )

    errors = check_sources(tmp_path)
    assert len(errors) > 0
    assert "SHA-256 Mismatch" in errors[0]


def test_verbatim_quote_not_found_rejection(tmp_path: Path):
    """Asserts that a decision point with a verbatim quote not in the spec text is rejected."""
    extracted_dir = tmp_path / "data" / "eval" / "extracted"
    extracted_dir.mkdir(parents=True)

    spec_text = "This is actual 3GPP TS 23.179 spec text containing floor control procedures."
    spec_file = extracted_dir / "TS_23.179.txt"
    spec_file.write_text(spec_text, encoding="utf-8")

    real_hash = compute_sha256(spec_file)

    fixtures_dir = tmp_path / "fixtures" / "eval"
    fixtures_dir.mkdir(parents=True)

    # Invented verbatim quote not present in spec_text
    dp_file = fixtures_dir / "decision_points.json"
    fake_dp = [
        {
            "id": "DP-001",
            "source_doc": "TS 23.179",
            "source_sha256": real_hash,
            "verbatim": "This is a fake invented quote that does not exist in the source document at all.",
        }
    ]
    dp_file.write_text(json.dumps(fake_dp), encoding="utf-8")

    errors = check_ground_truth(tmp_path)
    assert len(errors) > 0
    assert "verbatim quote NOT FOUND" in errors[0]


def test_missing_runs_dir_rejection(tmp_path: Path):
    """Asserts that an arm output file lacking a valid runs/ log reference is rejected."""
    fixtures_dir = tmp_path / "fixtures" / "eval"
    fixtures_dir.mkdir(parents=True)

    arm_file = fixtures_dir / "arm_a_output.json"
    arm_file.write_text(json.dumps({"questions": ["Q1", "Q2"]}), encoding="utf-8")

    errors = check_runs(tmp_path)
    assert len(errors) > 0
    assert "missing mandatory 'run_dir'" in errors[0]


def test_prematched_field_rejection(tmp_path: Path):
    """Asserts that an arm output file containing pre-matched fields ('matched_dp') is rejected."""
    fixtures_dir = tmp_path / "fixtures" / "eval"
    fixtures_dir.mkdir(parents=True)

    runs_dir = tmp_path / "runs" / "20260827_120000"
    runs_dir.mkdir(parents=True)
    (runs_dir / "prompt_response.json").write_text("{}", encoding="utf-8")

    arm_file = fixtures_dir / "arm_a_output.json"
    arm_file.write_text(
        json.dumps(
            {
                "run_dir": "20260827_120000",
                "questions": [{"question": "Q1", "matched_dp": "DP-001"}],
            }
        ),
        encoding="utf-8",
    )

    errors = check_runs(tmp_path)
    assert len(errors) > 0
    assert "contains forbidden matching field" in errors[0]
