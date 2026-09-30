"""Fail when a denylisted project term appears in the generic code (plan L3 §6.4).

Scans mcp_server/, tools/, pipelines/ and schemas/ (text files) for the terms of
``.project-names-denylist`` (case-insensitive). Project-specific content belongs to
``data/kb/`` (knowledge), ``examples/<project>/`` or ``tests/``.

Usage: poetry run python scripts/check_no_project_names.py [--denylist PATH] [paths...]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_PATHS = ("mcp_server", "tools", "pipelines", "schemas")
TEXT_SUFFIXES = {".py", ".json", ".ts", ".yaml", ".yml", ".md", ".txt", ".toml", ".cfg", ".ini", ".sql", ".html", ".j2"}


def load_denylist(path: Path) -> list[str]:
    terms = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            terms.append(line.lower())
    return terms


def scan(paths: list[Path], terms: list[str]) -> list[str]:
    pattern = re.compile("|".join(re.escape(t) for t in terms), re.IGNORECASE)
    findings = []
    for base in paths:
        files = [base] if base.is_file() else sorted(p for p in base.rglob("*") if p.is_file())
        for file in files:
            if "__pycache__" in file.parts or file.suffix.lower() not in TEXT_SUFFIXES:
                continue
            for n, line in enumerate(file.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                for match in pattern.finditer(line):
                    rel = file.relative_to(ROOT_DIR) if file.is_relative_to(ROOT_DIR) else file
                    findings.append(f"{rel}:{n}: '{match.group(0)}' — {line.strip()[:120]}")
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--denylist", type=Path, default=ROOT_DIR / ".project-names-denylist")
    parser.add_argument("paths", nargs="*", type=Path)
    args = parser.parse_args()
    terms = load_denylist(args.denylist)
    paths = [p if p.is_absolute() else ROOT_DIR / p for p in (args.paths or [Path(d) for d in DEFAULT_PATHS])]
    findings = scan(paths, terms)
    if findings:
        print(f"Project names found in generic code ({len(findings)}):")
        print("\n".join(findings))
        print("Move project-specific content to data/kb/, examples/<project>/ or tests/.")
        return 1
    print(f"No project name in {', '.join(str(p.relative_to(ROOT_DIR)) for p in paths)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
