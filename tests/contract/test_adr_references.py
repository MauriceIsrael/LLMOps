"""Contract test asserting no dangling ADR references exist in codebase or documentation (P1-4 remediation)."""

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.deterministic


def test_no_dangling_adr_references():
    """Verify that all ADR-XXXX identifiers cited across docs, schemas, and code exist in data/kb/decisions/."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    decisions_dir = repo_root / "data" / "kb" / "decisions"

    existing_adrs = {f.stem for f in decisions_dir.glob("ADR-*.md")}
    assert len(existing_adrs) >= 15, f"Expected at least 15 ADRs, found {len(existing_adrs)}"

    adr_pattern = re.compile(r"\b(ADR-\d{4})\b")
    scanned_extensions = {".py", ".md", ".json", ".yaml", ".yml", ".toml"}
    ignored_dirs = {".git", ".venv", "node_modules", "Audit", ".svelte-kit", "build"}

    referenced_adrs: set[str] = set()

    for path in repo_root.rglob("*"):
        if any(part in ignored_dirs for part in path.parts):
            continue
        if path.is_file() and path.suffix in scanned_extensions:
            # Skip snapshot json outputs which contain generated nodes
            if "snapshots" in path.parts or path.name == "sealed_snapshot.json":
                continue
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
                matches = adr_pattern.findall(content)
                referenced_adrs.update(matches)
            except Exception:
                pass

    missing_adrs = referenced_adrs - existing_adrs
    assert not missing_adrs, f"Dangling ADR references found: {missing_adrs}. All cited ADRs must have a corresponding file in data/kb/decisions/!"

