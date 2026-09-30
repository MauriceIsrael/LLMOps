"""In-memory doctrine index built from the knowledge graph.

The index holds the servable doctrine (principles, patterns, decisions, controls) with
the fields needed by the doctrine context and the option judge. It is read from the
knowledge graph; ``terms``, ``checks`` and ``checks_status`` come from the graph
columns written by the ingestion pipeline and, for a graph ingested before these
columns existed, from the asset's front matter on disk.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from pipelines.doctrine.checks import CheckClause, parse_checks
from pipelines.doctrine.text import Vocabulary

DOCTRINE_TYPES = ("principle", "pattern", "decision", "control")

ExecuteCypher = Callable[[str, dict[str, Any] | None], list[dict[str, Any]]]

_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


@dataclass
class DoctrineEntry:
    id: str
    type: str
    title: str
    status: str
    confidence: str
    domain: list[str]
    phase: list[str]
    source_ref: str
    body: str
    framework: str = ""
    applicability: str = ""
    terms: list[str] = field(default_factory=list)
    checks: list[CheckClause] = field(default_factory=list)

    @property
    def typed_id(self) -> str:
        return f"{self.type}:{self.id}"

    def sections(self) -> list[tuple[str, str]]:
        """H2 sections of the body as (heading, text), in document order."""
        result: list[tuple[str, str]] = []
        heading = "Introduction"
        lines: list[str] = []
        for line in self.body.splitlines():
            if line.startswith("## "):
                if "\n".join(lines).strip():
                    result.append((heading, "\n".join(lines).strip()))
                heading, lines = line[3:].strip(), []
            elif not line.startswith("# "):
                lines.append(line)
        if "\n".join(lines).strip():
            result.append((heading, "\n".join(lines).strip()))
        return result


@dataclass
class DoctrineIndex:
    entries: list[DoctrineEntry]
    vocabulary: Vocabulary

    def active(self) -> list[DoctrineEntry]:
        return [e for e in self.entries if e.status == "active"]

    def get(self, entry_id: str) -> DoctrineEntry | None:
        for e in self.entries:
            if e.id == entry_id:
                return e
        return None


def _split(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [v.strip() for v in str(value or "").split(",") if v.strip()]


def _json_list(value: Any) -> list[Any] | None:
    if value in (None, ""):
        return None
    if isinstance(value, list):
        return value
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError):
        return None
    return parsed if isinstance(parsed, list) else None


def read_frontmatter(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        return {}
    match = _FRONTMATTER.match(p.read_text(encoding="utf-8"))
    if not match:
        return {}
    try:
        fm = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return {}
    return fm if isinstance(fm, dict) else {}


def _query(execute: ExecuteCypher, full: str, fallback: str) -> tuple[list[dict[str, Any]], bool]:
    """Run ``full`` (with the newer columns); fall back to ``fallback`` on an older graph."""
    try:
        return execute(full, None), True
    except Exception:
        return execute(fallback, None), False


def load_vocabulary(execute: ExecuteCypher, kb_dir: str | Path) -> Vocabulary:
    """Glossary synonyms: ``A / B`` glossary terms and ``glossary/synonyms.yaml`` groups."""
    vocab = Vocabulary()
    try:
        rows = execute("MATCH (g:GlossaryTerm) RETURN g.term as term ORDER BY g.term;", None)
    except Exception:
        rows = []
    for row in rows:
        term = str(row.get("term") or "")
        parts = [p for p in re.split(r"\s+/\s+", term) if p.strip()]
        vocab.add_group(parts if len(parts) > 1 else [term])
    synonyms_file = Path(kb_dir) / "glossary" / "synonyms.yaml"
    if synonyms_file.is_file():
        data = yaml.safe_load(synonyms_file.read_text(encoding="utf-8")) or {}
        for group in data.get("groups", []) if isinstance(data, dict) else []:
            if isinstance(group, list):
                vocab.add_group(str(t) for t in group)
    return vocab


def load_index(execute: ExecuteCypher, kb_dir: str | Path = "data/kb") -> DoctrineIndex:
    """Build the doctrine index from the knowledge graph (read-only queries)."""
    kb_dir = Path(kb_dir)
    entries: list[DoctrineEntry] = []

    asset_rows, has_cols = _query(
        execute,
        "MATCH (a:Asset) RETURN a.id as id, a.type as type, a.title as title, a.status as status, "
        "a.confidence as confidence, a.domain as domain, a.phase as phase, a.source_path as source_path, "
        "a.markdown_content as body, a.terms as terms, a.checks as checks, a.checks_status as checks_status "
        "ORDER BY a.id;",
        "MATCH (a:Asset) RETURN a.id as id, a.type as type, a.title as title, a.status as status, "
        "a.confidence as confidence, a.domain as domain, a.phase as phase, a.source_path as source_path, "
        "a.markdown_content as body ORDER BY a.id;",
    )
    for row in asset_rows:
        atype = str(row.get("type") or "")
        if atype == "adr":
            atype = "decision"
        if atype not in DOCTRINE_TYPES or atype == "control":
            continue
        source = str(row.get("source_path") or "")
        entries.append(_entry(row, atype, source, has_cols))

    control_rows, has_cols = _query(
        execute,
        "MATCH (c:Control) RETURN c.id as id, c.title as title, c.status as status, c.framework as framework, "
        "c.domain as domain, c.markdown_content as body, c.source_path as source_path, "
        "c.confidence as confidence, c.phase as phase, c.terms as terms, c.checks as checks, "
        "c.checks_status as checks_status ORDER BY c.id;",
        "MATCH (c:Control) RETURN c.id as id, c.title as title, c.status as status, c.framework as framework, "
        "c.domain as domain, c.markdown_content as body ORDER BY c.id;",
    )
    for row in control_rows:
        framework = str(row.get("framework") or "")
        source = str(row.get("source_path") or "") or str(kb_dir / "controls" / framework / f"{row.get('id')}.md")
        entries.append(_entry(row, "control", source, has_cols, framework=framework))

    entries.sort(key=lambda e: (e.type, e.id))
    return DoctrineIndex(entries=entries, vocabulary=load_vocabulary(execute, kb_dir))


def _entry(row: dict[str, Any], atype: str, source: str, has_cols: bool, framework: str = "") -> DoctrineEntry:
    terms = _json_list(row.get("terms")) if has_cols else None
    checks = _json_list(row.get("checks")) if has_cols else None
    checks_status = row.get("checks_status") if has_cols else None
    confidence = str(row.get("confidence") or "")
    phase = _split(row.get("phase"))
    # ``applicability`` is not a graph column: it is read from the front matter on disk.
    fm = read_frontmatter(source)
    applicability = str(fm.get("applicability") or "")
    if not has_cols or not confidence:
        terms = terms if terms is not None else _split(fm.get("terms"))
        checks = checks if checks is not None else fm.get("checks")
        checks_status = checks_status or fm.get("checks_status")
        confidence = confidence or str(fm.get("confidence") or "")
        phase = phase or _split(fm.get("phase"))
    return DoctrineEntry(
        id=str(row.get("id") or ""),
        type=atype,
        title=str(row.get("title") or row.get("id") or ""),
        status=str(row.get("status") or ""),
        confidence=confidence or "assumed",
        domain=_split(row.get("domain")),
        phase=phase,
        source_ref=source,
        body=str(row.get("body") or ""),
        framework=framework,
        applicability=applicability,
        terms=[str(t) for t in (terms or [])],
        checks=parse_checks(checks, checks_status),
    )
