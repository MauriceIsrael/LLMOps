"""Doctrine context package: which doctrine applies to a subject (deterministic ranking).

Relevance is lexical (query concepts and glossary synonyms found in the asset) and, when the server holds its local
embedding model (issue #94), semantic as well: the similarity between the subject and the asset in the model's space,
which finds an English control for a French subject. The two are combined into one score that **orders** the package
and sets ``relevant``; it never decides anything about an option (ADR-KH-01 D9). Without the model the ranking is
exactly the lexical one (``relevance_method: "lexical"``).
"""

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

# Minimum calibrated semantic relevance (in [0, 1], see pipelines/similarity/models.py floor/ceil) for an asset to be
# relevant by meaning. Calibrated on tests/fixtures/similarity/fr-en-doctrine.yaml (docs/deployment.md §7).
MIN_SEMANTIC = 0.50

# Among the required controls of a declared framework, the one closest to the subject is relevant from this lower
# calibrated score: cosine levels vary with the wording of a subject, and the closest control of a framework the
# subject is declared under is the one an architect looks at first (same calibration run).
MIN_SEMANTIC_BEST = 0.40

# Combination of the two relevances: ``None`` takes the maximum (a French subject has no lexical evidence and must not
# be penalised for it); a number w in [0, 1] takes w * semantic + (1 - w) * lexical (``KB_HYBRID_WEIGHT``).
DEFAULT_HYBRID_WEIGHT: float | None = None

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
    relevance: float  # lexical
    required: bool
    semantic: float | None = None  # calibrated semantic relevance, None without a model
    score: float = 0.0  # combined score that orders the package (the lexical relevance without a model)
    relevant: bool = False

    @property
    def method(self) -> str:
        """``lexical`` (no model), ``semantic`` (found by meaning only) or ``hybrid`` (both kinds of evidence)."""
        if self.semantic is None:
            return "lexical"
        return "hybrid" if self.relevance > 0 else "semantic"

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


def combine(lexical: float, semantic: float | None, weight: float | None = DEFAULT_HYBRID_WEIGHT) -> float:
    """One score from the lexical and the semantic relevance (the lexical one alone without a model)."""
    if semantic is None:
        return lexical
    if weight is None:
        return round(max(lexical, semantic), 4)
    return round(weight * semantic + (1.0 - weight) * lexical, 4)


def rank(
    index: DoctrineIndex,
    subject: str,
    domains: list[str] | None = None,
    frameworks: list[str] | None = None,
    phase: str | None = None,
    semantic: dict[str, float] | None = None,
    weight: float | None = DEFAULT_HYBRID_WEIGHT,
    min_semantic: float = MIN_SEMANTIC,
) -> list[ScoredEntry]:
    """Active doctrine relevant to the subject, plus every active control of the required
    frameworks, ordered by type priority, then relevant first, then score, then identifier.

    ``semantic`` maps an asset id to its calibrated semantic relevance in [0, 1] (``None``: no model, lexical ranking).
    An asset is *relevant* when its lexical relevance reaches ``MIN_RELEVANCE`` or its semantic relevance reaches
    ``min_semantic``; only relevant assets enter the package, except the controls of the required frameworks, which are
    all included and flagged ``relevant`` or not (the closest control of each required framework is relevant from
    ``MIN_SEMANTIC_BEST``)."""
    domains = [d for d in (domains or []) if d]
    required_fw = {f.lower() for f in (frameworks or []) if f}
    concepts = query_concepts(subject, index.vocabulary)
    best: dict[str, float] = {}
    if semantic is not None:
        for entry in index.active():
            if entry.type == "control" and entry.framework.lower() in required_fw:
                fw = entry.framework.lower()
                best[fw] = max(best.get(fw, 0.0), semantic.get(entry.id, 0.0))
    scored: list[ScoredEntry] = []
    for entry in index.active():
        required = entry.type == "control" and entry.framework.lower() in required_fw
        if not required:
            if domains and not _domain_matches(entry.domain, domains):
                continue
            if phase and entry.phase and phase.upper() not in {p.upper() for p in entry.phase}:
                continue
        lexical = relevance(entry, concepts)
        sem = None if semantic is None else semantic.get(entry.id, 0.0)
        relevant = lexical >= MIN_RELEVANCE or (sem is not None and sem >= min_semantic)
        if required and sem is not None and sem >= MIN_SEMANTIC_BEST and sem >= best[entry.framework.lower()]:
            relevant = True
        if required or relevant:
            scored.append(ScoredEntry(entry=entry, relevance=lexical, required=required, semantic=sem,
                                      score=combine(lexical, sem, weight), relevant=relevant))
    scored.sort(key=lambda s: (s.priority, not s.relevant, -s.score, s.entry.id))
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
    semantic: dict[str, float] | None = None,
    weight: float | None = DEFAULT_HYBRID_WEIGHT,
    min_semantic: float = MIN_SEMANTIC,
    embedding: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Doctrine package for a subject: at most ``max_items`` items whose excerpts total at
    most ``max_chars`` characters. ``truncated`` tells whether anything was left out or cut.

    ``semantic`` (asset id -> calibrated semantic relevance) and ``embedding`` (the model that computed it) come from
    the server's local model; without them the package is the lexical one (``relevance_method: "lexical"``)."""
    concepts = query_concepts(subject, index.vocabulary)
    ranked = rank(index, subject, domains, frameworks, phase, semantic, weight, min_semantic)
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
    return {"items": items, "truncated": truncated, "snapshot_id": snapshot_id,
            "relevance_method": "lexical" if semantic is None else "hybrid",
            "embedding": embedding if semantic is not None else None}


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
        # Issue #94 (additive): what ordered the item. ``relevant`` separates the doctrine that is relevant for the
        # subject from the controls that are only required by the declared frameworks. D9: it orders, never decides.
        "relevant": scored.relevant,
        "semantic_relevance": scored.semantic,
        "combined_relevance": round(scored.score, 4),
        "relevance_method": scored.method,
    }
