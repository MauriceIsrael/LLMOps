"""Doctrine context package: which doctrine applies to a subject (deterministic ranking)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pipelines.doctrine.index import DoctrineEntry, DoctrineIndex
from pipelines.doctrine.text import contains_phrase, normalize, query_concepts

# Field weights: where a query concept is found in an asset.
TITLE_WEIGHT = 1.0
TERMS_WEIGHT = 1.0
DOMAIN_WEIGHT = 0.8
APPLICABILITY_WEIGHT = 0.8
BODY_WEIGHT = 0.5

# Minimum relevance for an asset to be part of the package (required controls excepted).
MIN_RELEVANCE = 0.2

# Priority order of the package: principle > required control > pattern > decision > other control.
TYPE_PRIORITY = {"principle": 0, "required-control": 1, "pattern": 2, "decision": 3, "control": 4}

# Preferred excerpt sections per type, used to break ties between equally relevant sections.
PREFERRED_SECTIONS = {
    "principle": ("Statement", "Why", "Implications"),
    "pattern": ("Solution", "Problem", "Context", "Introduction"),
    "decision": ("Decision", "Context", "Consequences"),
    "control": ("Architecture Acceptance Criteria", "Legal Requirement", "Regulatory Reference"),
}

MIN_EXCERPT_CHARS = 120


@dataclass
class ScoredEntry:
    entry: DoctrineEntry
    relevance: float
    required: bool

    @property
    def priority(self) -> int:
        if self.entry.type == "control":
            return TYPE_PRIORITY["required-control" if self.required else "control"]
        return TYPE_PRIORITY.get(self.entry.type, 9)


def _domain_matches(entry_domains: list[str], wanted: list[str]) -> bool:
    for a in entry_domains:
        for d in wanted:
            if a == d or a.startswith(d.rstrip("/") + "/"):
                return True
    return False


def relevance(entry: DoctrineEntry, concepts: list[frozenset[str]]) -> float:
    """Share of query concepts found in the asset, weighted by the field where found."""
    if not concepts:
        return 0.0
    fields = (
        (normalize(entry.title) + normalize(entry.id), TITLE_WEIGHT),
        (normalize(" ; ".join(entry.terms)), TERMS_WEIGHT),
        (normalize(" ; ".join(entry.domain)), DOMAIN_WEIGHT),
        (normalize(entry.applicability), APPLICABILITY_WEIGHT),
        (normalize(entry.body), BODY_WEIGHT),
    )
    total = 0.0
    for concept in concepts:
        best = 0.0
        for text, weight in fields:
            if weight > best and any(contains_phrase(text, v) for v in concept):
                best = weight
        total += best
    return round(total / len(concepts), 4)


def rank(
    index: DoctrineIndex,
    subject: str,
    domains: list[str] | None = None,
    frameworks: list[str] | None = None,
    phase: str | None = None,
) -> list[ScoredEntry]:
    """Active doctrine relevant to the subject, plus every active control of the required
    frameworks, ordered by type priority, then relevance, then identifier."""
    domains = [d for d in (domains or []) if d]
    required_fw = {f.lower() for f in (frameworks or []) if f}
    concepts = query_concepts(subject, index.vocabulary)
    scored: list[ScoredEntry] = []
    for entry in index.active():
        required = entry.type == "control" and entry.framework.lower() in required_fw
        if not required:
            if domains and not _domain_matches(entry.domain, domains):
                continue
            if phase and entry.phase and phase.upper() not in {p.upper() for p in entry.phase}:
                continue
        score = relevance(entry, concepts)
        if required or score >= MIN_RELEVANCE:
            scored.append(ScoredEntry(entry=entry, relevance=score, required=required))
    scored.sort(key=lambda s: (s.priority, -s.relevance, s.entry.id))
    return scored


def best_section(entry: DoctrineEntry, concepts: list[frozenset[str]]) -> str:
    """The section of the asset that matches most query concepts (ties: preferred sections)."""
    sections = entry.sections()
    if not sections:
        return entry.body.strip()
    preferred = PREFERRED_SECTIONS.get(entry.type, ())

    def key(item: tuple[int, tuple[str, str]]) -> tuple[int, int, int]:
        pos, (heading, text) = item
        norm = normalize(text)
        hits = sum(1 for c in concepts if any(contains_phrase(norm, v) for v in c))
        pref = preferred.index(heading) if heading in preferred else len(preferred)
        return (-hits, pref, pos)

    _, (_, text) = min(enumerate(sections), key=key)
    return text.strip()


def truncate(text: str, limit: int) -> tuple[str, bool]:
    """Cut ``text`` to ``limit`` characters on a sentence or word boundary."""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text, False
    if limit <= 1:
        return "", True
    window = text[: limit - 1]
    cut = max(window.rfind(". "), window.rfind("; "))
    if cut >= limit // 2:
        return window[: cut + 1], True
    space = window.rfind(" ")
    if space > 0:
        window = window[:space]
    return window.rstrip(" ,;:") + "…", True


def build_doctrine_context(
    index: DoctrineIndex,
    subject: str,
    domains: list[str] | None = None,
    frameworks: list[str] | None = None,
    phase: str | None = None,
    max_items: int = 20,
    max_chars: int = 8000,
    snapshot_id: str | None = None,
) -> dict[str, Any]:
    """Doctrine package for a subject: at most ``max_items`` items whose excerpts total at
    most ``max_chars`` characters. ``truncated`` tells whether anything was left out or cut."""
    concepts = query_concepts(subject, index.vocabulary)
    ranked = rank(index, subject, domains, frameworks, phase)
    selected = ranked[: max(0, max_items)]
    truncated = len(selected) < len(ranked)

    items: list[dict[str, Any]] = []
    used = 0
    per_item = max(MIN_EXCERPT_CHARS, max_chars // max(1, len(selected))) if selected else 0
    for scored in selected:
        remaining = max_chars - used
        if remaining < min(MIN_EXCERPT_CHARS // 3, per_item):
            truncated = True
            break
        limit = min(per_item, remaining)
        excerpt, cut = truncate(best_section(scored.entry, concepts), limit)
        truncated = truncated or cut
        used += len(excerpt)
        items.append(context_item(scored, excerpt))
    return {"items": items, "truncated": truncated, "snapshot_id": snapshot_id}


def context_item(scored: ScoredEntry, excerpt: str) -> dict[str, Any]:
    e = scored.entry
    return {
        "typed_id": e.typed_id,
        "id": e.id,
        "type": e.type,
        "title": e.title,
        "status": e.status,
        "confidence": e.confidence,
        "domain": list(e.domain),
        "excerpt": excerpt,
        "source_ref": e.source_ref,
        "relevance": round(scored.relevance, 2),
        "has_checks": bool(e.checks),
        "framework": e.framework or None,
        "required": scored.required,
    }
