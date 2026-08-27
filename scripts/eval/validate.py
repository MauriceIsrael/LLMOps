"""Automated Anti-Fabrication Validator for 3GPP Evaluation Benchmark.

Per Workorder v2 §2: Enforces source document checksums, verbatim substring verification,
AST anti-literal limits, and model run log traceability.
"""

import ast
import hashlib
import json
import re
import sys
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "eval_config.json"


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Configuration file missing: {CONFIG_PATH}")
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def compute_sha256(file_path: Path) -> str:
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def check_ast_literals(script_path: Path, max_allowed: int = 3) -> list[str]:
    """Inspects AST of Python script to detect functions returning hardcoded list/dict literals > 3 items."""
    errors = []
    source = script_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(script_path))

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for stmt in ast.walk(node):
                if isinstance(stmt, ast.Return) and stmt.value:
                    val = stmt.value
                    if isinstance(val, ast.List) and len(val.elts) > max_allowed:
                        errors.append(
                            f"AST Violation in {script_path.name}:{stmt.lineno}: function '{node.name}' returns hardcoded list literal with {len(val.elts)} elements (max allowed: {max_allowed})."
                        )
                    elif isinstance(val, ast.Dict) and len(val.keys) > max_allowed:
                        errors.append(
                            f"AST Violation in {script_path.name}:{stmt.lineno}: function '{node.name}' returns hardcoded dict literal with {len(val.keys)} elements (max allowed: {max_allowed})."
                        )
    return errors


def check_scripts(scripts_dir: Path) -> list[str]:
    config = load_config()
    max_allowed = config.get("max_literal_elements", 3)
    errors = []

    for script in scripts_dir.glob("*.py"):
        if script.name in ("validate.py", "eval_config.py"):
            continue
        errs = check_ast_literals(script, max_allowed=max_allowed)
        errors.extend(errs)

    return errors


def check_sources(project_root: Path) -> list[str]:
    config = load_config()
    min_len = config.get("min_spec_text_length", 10000)
    manifest_path = project_root / "docs" / "eval" / "SOURCES.md"
    errors = []

    if not manifest_path.exists():
        return [f"Source manifest missing: {manifest_path}"]

    lines = manifest_path.read_text(encoding="utf-8").splitlines()
    spec_entries = []

    for line in lines:
        if line.startswith("|") and not line.startswith("| Document") and not line.startswith("|---"):
            parts = [p.strip() for p in line.split("|")[1:-1]]
            if len(parts) >= 4:
                spec_entries.append({"doc_id": parts[0], "filename": parts[1], "sha256": parts[2], "size": parts[3]})

    if not spec_entries:
        return ["No spec entries found in docs/eval/SOURCES.md"]

    for entry in spec_entries:
        filename = entry["filename"]
        declared_hash = entry["sha256"].strip("` ").strip()

        file_path = None
        for dir_rel in config.get("source_directories", []):
            candidate = project_root / dir_rel / filename
            if candidate.exists():
                file_path = candidate
                break

        if not file_path:
            errors.append(f"Source file '{filename}' for {entry['doc_id']} not found on disk.")
            continue

        actual_hash = compute_sha256(file_path)
        if actual_hash.lower() != declared_hash.lower():
            errors.append(f"SHA-256 Mismatch for '{filename}': declared {declared_hash}, calculated {actual_hash}.")

        if file_path.suffix.lower() in (".txt", ".json"):
            content = file_path.read_text(encoding="utf-8")
            if len(content) < min_len:
                errors.append(f"Extracted text for '{filename}' is too short: {len(content)} chars (min: {min_len}).")

    return errors


def check_ground_truth(project_root: Path) -> list[str]:
    config = load_config()
    min_verbatim_len = config.get("min_verbatim_length", 40)
    dp_path = project_root / "fixtures" / "eval" / "decision_points.json"
    errors = []

    if not dp_path.exists():
        return [f"Ground truth file missing: {dp_path}"]

    dps = json.loads(dp_path.read_text(encoding="utf-8"))
    extracted_dir = project_root / "data" / "eval" / "extracted"

    for dp in dps:
        dp_id = dp.get("id", "UNKNOWN")
        verbatim = dp.get("verbatim", "")
        declared_hash = dp.get("source_sha256", "")
        source_doc = dp.get("source_doc", "")

        if len(verbatim) < min_verbatim_len:
            errors.append(f"Decision point {dp_id}: verbatim length ({len(verbatim)}) is shorter than min {min_verbatim_len} chars.")
            continue

        norm_verbatim = normalize_spaces(verbatim)
        spec_text_path = extracted_dir / f"{source_doc.replace(' ', '_')}.txt"

        if not spec_text_path.exists():
            errors.append(f"Decision point {dp_id}: source text file {spec_text_path.name} not found.")
            continue

        actual_hash = compute_sha256(spec_text_path)
        if declared_hash and actual_hash.lower() != declared_hash.lower():
            errors.append(f"Decision point {dp_id}: SHA-256 mismatch for source text {spec_text_path.name}.")
            continue

        spec_text = normalize_spaces(spec_text_path.read_text(encoding="utf-8"))
        if norm_verbatim not in spec_text:
            errors.append(f"Decision point {dp_id}: verbatim quote NOT FOUND in source specification text ({source_doc}).")

    return errors


def check_runs(project_root: Path) -> list[str]:
    errors = []
    fixtures_dir = project_root / "fixtures" / "eval"

    for arm_file_name in ("arm_a_output.json", "arm_b_output.json"):
        arm_path = fixtures_dir / arm_file_name
        if not arm_path.exists():
            continue

        data = json.loads(arm_path.read_text(encoding="utf-8"))

        if isinstance(data, dict):
            run_dir_name = data.get("run_dir")
            items = data.get("questions", [])
        else:
            run_dir_name = None
            items = data

        if not run_dir_name:
            errors.append(f"{arm_file_name}: missing mandatory 'run_dir' reference to runs/<timestamp>/ log directory.")
        else:
            run_dir = project_root / "runs" / run_dir_name
            if not run_dir.exists() or not any(run_dir.iterdir()):
                errors.append(f"{arm_file_name}: referenced run directory '{run_dir_name}' does not exist or is empty.")

        for item in items:
            if isinstance(item, dict) and ("matched_dp" in item or "match" in item):
                errors.append(f"{arm_file_name}: contains forbidden matching field ('matched_dp'/'match'). Generation outputs must NOT contain matching data.")

    return errors


def main() -> None:
    project_root = Path(__file__).parent.parent.parent
    scripts_dir = Path(__file__).parent

    mode = sys.argv[1] if len(sys.argv) > 1 else "--all"

    all_errors = []

    if mode in ("--check-scripts", "--all"):
        print("🔍 Checking Python AST anti-literal compliance...")
        errs = check_scripts(scripts_dir)
        all_errors.extend(errs)

    if mode in ("--check-sources", "--all"):
        print("🔍 Checking source documents SHA-256 and text lengths...")
        errs = check_sources(project_root)
        all_errors.extend(errs)

    if mode in ("--check-ground-truth", "--all"):
        print("🔍 Checking ground truth verbatim quote exact substring matches...")
        errs = check_ground_truth(project_root)
        all_errors.extend(errs)

    if mode in ("--check-runs", "--all"):
        print("🔍 Checking model run log directories and output separation...")
        errs = check_runs(project_root)
        all_errors.extend(errs)

    if all_errors:
        print("\n❌ VALIDATION FAILED:")
        for err in all_errors:
            print(f"  - {err}")
        sys.exit(1)
    else:
        print("✅ VALIDATION PASSED: All anti-fabrication rules satisfied.")
        sys.exit(0)


if __name__ == "__main__":
    main()
