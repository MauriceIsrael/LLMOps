"""Unit tests for Automated Anti-Fabrication Validator.

Per Workorder v2 §2 & User Directives:
- Verifies AST anti-literal compliance (max 3 elements per literal return)
- Verifies SHA-256 spec checksum matching
- Verifies exact verbatim quote substring matching
- Verifies model run log directory traceability
- Verifies non-zero exit codes on length mismatch (even by 1 char) or missing extracted files
"""

import json
from pathlib import Path
from unittest.mock import patch

from scripts.eval.validate import (
    check_ast_literals,
    check_ground_truth,
    check_runs,
    check_sources,
)


def test_ast_literal_compliance(tmp_path: Path):
    """Asserts that Python functions returning > 3 hardcoded literal items are flagged."""
    script_valid = tmp_path / "valid_script.py"
    script_valid.write_text("def get_data(): return [1, 2, 3]", encoding="utf-8")

    script_invalid = tmp_path / "invalid_script.py"
    script_invalid.write_text("def get_data(): return [1, 2, 3, 4, 5]", encoding="utf-8")

    assert len(check_ast_literals(script_valid, max_allowed=3)) == 0

    errs = check_ast_literals(script_invalid, max_allowed=3)
    assert len(errs) > 0
    assert "hardcoded list literal with 5 elements" in errs[0]


def test_sources_sha256_verification(tmp_path: Path):
    """Asserts that source document SHA-256 hash mismatches are caught."""
    config = {
        "min_spec_text_length": 100,
        "min_verbatim_length": 10,
        "max_literal_elements": 3,
        "source_directories": ["data/eval/sources"],
    }
    (tmp_path / "eval_config.json").write_text(json.dumps(config), encoding="utf-8")

    sources_dir = tmp_path / "data" / "eval" / "sources"
    sources_dir.mkdir(parents=True)

    spec_file = sources_dir / "TS_22.179.txt"
    spec_file.write_text("Sample 3GPP specification text " * 10, encoding="utf-8")

    manifest_dir = tmp_path / "docs" / "eval"
    manifest_dir.mkdir(parents=True)

    bad_hash = "0000000000000000000000000000000000000000000000000000000000000000"
    manifest = manifest_dir / "SOURCES.md"
    manifest.write_text(
        f"| Document | Filename | SHA-256 | Size |\n|---|---|---|---|\n| TS 22.179 | TS_22.179.txt | {bad_hash} | 15 KB |\n",
        encoding="utf-8",
    )

    with patch("scripts.eval.validate.CONFIG_PATH", tmp_path / "eval_config.json"):
        errors = check_sources(tmp_path)
        assert len(errors) > 0
        assert "SHA-256 Mismatch" in errors[0]


def test_extracted_length_mismatch_rejection(tmp_path: Path):
    """Asserts that extracted text length mismatches against SOURCES.md are rejected."""
    config = {
        "min_spec_text_length": 100,
        "min_verbatim_length": 10,
        "max_literal_elements": 3,
        "source_directories": ["data/eval/sources"],
    }
    (tmp_path / "eval_config.json").write_text(json.dumps(config), encoding="utf-8")

    extracted_dir = tmp_path / "data" / "eval" / "extracted"
    extracted_dir.mkdir(parents=True)

    sample_text = "Sample extracted 3GPP text content. " * 500
    extracted_txt = extracted_dir / "TS_22.179.txt"
    extracted_txt.write_text(sample_text, encoding="utf-8")

    manifest_dir = tmp_path / "docs" / "eval"
    manifest_dir.mkdir(parents=True)

    manifest = manifest_dir / "SOURCES.md"
    manifest.write_text(
        "| Document | Filename | SHA-256 | Size | Extracted Length |\n|---|---|---|---|---|\n| TS 22.179 | 22179-d30.doc | `dummyhash` | 15 KB | 999,999 chars |\n",
        encoding="utf-8",
    )

    with patch("scripts.eval.validate.CONFIG_PATH", tmp_path / "eval_config.json"):
        errors = check_sources(tmp_path)
        assert len(errors) > 0
        assert "Length Mismatch" in errors[0]


def test_validator_fails_when_manifest_length_modified_by_one_char(tmp_path: Path):
    """Asserts that modifying declared length in SOURCES.md by even 1 character causes validation failure."""
    config = {
        "min_spec_text_length": 10,
        "min_verbatim_length": 10,
        "max_literal_elements": 3,
        "source_directories": ["data/eval/sources"],
    }
    (tmp_path / "eval_config.json").write_text(json.dumps(config), encoding="utf-8")

    extracted_dir = tmp_path / "data" / "eval" / "extracted"
    extracted_dir.mkdir(parents=True)

    sample_text = "Exact text content on disk."  # length = 27
    extracted_txt = extracted_dir / "TS_22.179.txt"
    extracted_txt.write_text(sample_text, encoding="utf-8")

    manifest_dir = tmp_path / "docs" / "eval"
    manifest_dir.mkdir(parents=True)

    # Intentionally off by 1 character (28 chars instead of 27)
    manifest = manifest_dir / "SOURCES.md"
    manifest.write_text(
        "| Document | Filename | SHA-256 | Size | Extracted Length |\n|---|---|---|---|---|\n| TS 22.179 | 22179-d30.doc | `dummy` | 1 KB | 28 chars |\n",
        encoding="utf-8",
    )

    with patch("scripts.eval.validate.CONFIG_PATH", tmp_path / "eval_config.json"):
        errs = check_sources(tmp_path)
        assert len(errs) == 1
        assert "Length Mismatch for 'TS 22.179'" in errs[0]
        assert "28" in errs[0] and "27" in errs[0]


def test_validator_fails_when_extracted_text_file_deleted(tmp_path: Path):
    """Asserts that validator fails when an extracted text file is missing from data/eval/extracted/."""
    config = {
        "min_spec_text_length": 10,
        "min_verbatim_length": 10,
        "max_literal_elements": 3,
        "source_directories": ["data/eval/sources"],
    }
    (tmp_path / "eval_config.json").write_text(json.dumps(config), encoding="utf-8")

    extracted_dir = tmp_path / "data" / "eval" / "extracted"
    extracted_dir.mkdir(parents=True)
    # Do NOT create TS_22.179.txt (missing file)

    manifest_dir = tmp_path / "docs" / "eval"
    manifest_dir.mkdir(parents=True)

    manifest = manifest_dir / "SOURCES.md"
    manifest.write_text(
        "| Document | Filename | SHA-256 | Size | Extracted Length |\n|---|---|---|---|---|\n| TS 22.179 | 22179-d30.doc | `dummy` | 1 KB | 233,237 chars |\n",
        encoding="utf-8",
    )

    with patch("scripts.eval.validate.CONFIG_PATH", tmp_path / "eval_config.json"):
        errs = check_sources(tmp_path)
        assert len(errs) == 1
        assert "Extracted text file for 'TS 22.179' missing on disk" in errs[0]


def test_verbatim_quote_not_found_rejection(tmp_path: Path):
    """Asserts that a decision point with a verbatim quote not in the spec text is rejected."""
    config = {
        "min_spec_text_length": 10,
        "min_verbatim_length": 10,
        "max_literal_elements": 3,
        "source_directories": ["data/eval/sources"],
    }
    (tmp_path / "eval_config.json").write_text(json.dumps(config), encoding="utf-8")

    extracted_dir = tmp_path / "data" / "eval" / "extracted"
    extracted_dir.mkdir(parents=True)

    spec_text = "This is actual 3GPP TS 23.179 spec text containing floor control procedures."
    spec_file = extracted_dir / "TS_23.179.txt"
    spec_file.write_text(spec_text, encoding="utf-8")

    fixtures_dir = tmp_path / "fixtures" / "eval"
    fixtures_dir.mkdir(parents=True)

    dp_file = fixtures_dir / "decision_points.json"
    fake_dp = [
        {
            "dp_id": "DP-001",
            "doc_id": "TS 23.179",
            "verbatim": "This is a fabricated verbatim quote that does not exist in the spec.",
        }
    ]
    dp_file.write_text(json.dumps(fake_dp), encoding="utf-8")

    with patch("scripts.eval.validate.CONFIG_PATH", tmp_path / "eval_config.json"):
        errors = check_ground_truth(tmp_path)
        assert len(errors) > 0
        assert "Ground Truth Violation" in errors[0]


def test_run_logs_traceability_verification(tmp_path: Path):
    """Asserts that model generation outputs without matching run log directories are rejected."""
    fixtures_dir = tmp_path / "fixtures" / "eval"
    fixtures_dir.mkdir(parents=True)

    arm_a = fixtures_dir / "arm_a_output.json"
    arm_a.write_text(json.dumps({"run_dir": "2026-08-27_fake_run", "questions": []}), encoding="utf-8")

    errors = check_runs(tmp_path)
    assert len(errors) > 0
    assert "referenced run directory '2026-08-27_fake_run' does not exist" in errors[0]
