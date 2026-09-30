"""Read access to the knowledge base files (``data/kb``) for the candidate cycle."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
SKIPPED_FILES = {"README.md", "CONTRIBUTING.md", "GOVERNANCE.md", "GETTING-STARTED.md", "CHANGELOG.md", "deltas.md"}

# Where each asset type lives in the KB (controls: controls/<framework>/).
TYPE_DIRS = {
    "principle": "principles",
    "pattern": "patterns",
    "decision": "decisions",
    "control": "controls",
    "glossary": "glossary",
}


@dataclass
class KbAsset:
    id: str
    type: str
    title: str
    body: str
    path: Path
    frontmatter: dict[str, Any]


def split_frontmatter(content: str) -> tuple[dict[str, Any] | None, str]:
    """Return (front matter or None when absent/invalid, body)."""
    match = FRONTMATTER.match(content or "")
    if not match:
        return None, content or ""
    try:
        fm = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return None, content[match.end():]
    if not isinstance(fm, dict):
        return None, content[match.end():]
    for k, v in list(fm.items()):
        if isinstance(v, date):
            fm[k] = v.isoformat()
    return fm, content[match.end():]


def join_frontmatter(fm: dict[str, Any], body: str) -> str:
    # Flow style for scalar lists ([BUILD, RUN]), as in the existing assets.
    dumped = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True, width=1000, default_flow_style=None).strip()
    return f"---\n{dumped}\n---\n\n{body.lstrip()}"


def load_assets(kb_dir: str | Path) -> list[KbAsset]:
    """Every asset of the KB with an ``id`` in its front matter (Markdown and YAML)."""
    kb = Path(kb_dir)
    assets: list[KbAsset] = []
    for path in sorted(list(kb.rglob("*.md")) + list(kb.rglob("*.yaml")) + list(kb.rglob("*.yml"))):
        if path.name.startswith("_") or path.name in SKIPPED_FILES:
            continue
        text = path.read_text(encoding="utf-8")
        if path.suffix == ".md":
            fm, body = split_frontmatter(text)
        else:
            try:
                fm = yaml.safe_load(text)
            except yaml.YAMLError:
                fm = None
            body = ""
        if not isinstance(fm, dict) or not fm.get("id"):
            continue
        assets.append(
            KbAsset(
                id=str(fm["id"]),
                type=str(fm.get("type") or ""),
                title=str(fm.get("title") or fm["id"]),
                body=body,
                path=path,
                frontmatter=fm,
            )
        )
    return assets


def glossary_terms(kb_dir: str | Path) -> list[str]:
    glossary = Path(kb_dir) / "glossary" / "glossary.md"
    if not glossary.is_file():
        return []
    return [m.strip() for m in re.findall(r"^\*\*(.*?)\*\*\s*[—\-]", glossary.read_text(encoding="utf-8"), re.MULTILINE)]


def asset_path(kb_dir: str | Path, asset_type: str, asset_id: str, framework: str | None = None) -> Path:
    kb = Path(kb_dir)
    if asset_type == "control":
        return kb / "controls" / (framework or "UNKNOWN") / f"{asset_id}.md"
    return kb / TYPE_DIRS.get(asset_type, f"{asset_type}s") / f"{asset_id}.md"
