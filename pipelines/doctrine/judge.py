"""Option judge: does an option respect the doctrine? (``deterministic-checks-v1``)

The judge never interprets natural language. It evaluates the structured ``checks``
clauses of the active doctrine against the option's text (title, description,
statements) and reports, for each relevant asset:

* ``supports`` / ``violates`` when a clause applies;
* ``unassessed`` when the asset is relevant but no clause applies (or it has none) —
  the client-side reviewer decides, e.g. with a language model.

Every active control of a required framework is always reported, at least as
``unassessed``, so that nothing required is silently forgotten.
"""

from __future__ import annotations

from typing import Any

from pipelines.doctrine.checks import ClauseResult, evaluate_clause
from pipelines.doctrine.context import (
    TYPE_PRIORITY,
    ScoredEntry,
    best_section,
    rank,
    truncate,
)
from pipelines.doctrine.index import DoctrineEntry, DoctrineIndex
from pipelines.doctrine.text import normalize, query_concepts

METHOD = "deterministic-checks-v1"
VERDICT_ORDER = {"violates": 0, "supports": 1, "unassessed": 2}
EXCERPT_CHARS = 400
MAX_RELEVANT_UNASSESSED = 20


def option_text(option: dict[str, Any]) -> str:
    """The text the clauses are matched against: title, description and statements."""
    parts = [str(option.get("title") or ""), str(option.get("description") or "")]
    for st in option.get("statements") or []:
        if isinstance(st, dict):
            parts.extend(str(st.get(k) or "") for k in ("subject", "predicate", "value"))
        elif isinstance(st, str):
            parts.append(st)
    return "\n".join(p for p in parts if p)


def _priority(entry: DoctrineEntry, required: bool) -> int:
    if entry.type == "control":
        return TYPE_PRIORITY["required-control" if required else "control"]
    return TYPE_PRIORITY.get(entry.type, 9)


def _verdict(
    entry: DoctrineEntry,
    verdict: str,
    excerpt: str,
    result: ClauseResult | None = None,
) -> dict[str, Any]:
    return {
        "typed_id": entry.typed_id,
        "check_id": result.clause.id if result else None,
        "verdict": verdict,
        "message": (result.clause.message or None) if result else None,
        "matched_terms": list(result.matched_terms) if result else [],
        "excerpt": excerpt,
        "source_ref": entry.source_ref,
        "check_status": result.clause.status if result else None,
    }


def check_option(
    index: DoctrineIndex,
    option: dict[str, Any],
    subject: str | None = None,
    domains: list[str] | None = None,
    frameworks: list[str] | None = None,
    snapshot_id: str | None = None,
) -> dict[str, Any]:
    text = option_text(option)
    normalized = normalize(text)
    required_fw = {f.lower() for f in (frameworks or []) if f}
    query = " ".join(p for p in (subject or "", str(option.get("title") or "")) if p)
    concepts = query_concepts(query, index.vocabulary)

    rows: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    judged: set[str] = set()

    # 1. Every applicable clause of the active doctrine, relevant to the subject or not:
    #    a clause that fires is doctrine that applies to this option.
    for entry in index.active():
        required = entry.type == "control" and entry.framework.lower() in required_fw
        for clause in entry.checks:
            result = evaluate_clause(clause, normalized, index.vocabulary)
            if result is None:
                continue
            judged.add(entry.id)
            excerpt, _ = truncate(best_section(entry, concepts), EXCERPT_CHARS)
            key = (VERDICT_ORDER[result.verdict], _priority(entry, required), entry.id, clause.id)
            rows.append((key, _verdict(entry, result.verdict, excerpt, result)))

    # 2. Relevant doctrine without an applicable clause, and every required control.
    ranked: list[ScoredEntry] = rank(index, query, domains, frameworks)
    optional_count = 0
    for scored in ranked:
        entry = scored.entry
        if entry.id in judged:
            continue
        if not scored.required:
            if optional_count >= MAX_RELEVANT_UNASSESSED:
                continue
            optional_count += 1
        excerpt, _ = truncate(best_section(entry, concepts), EXCERPT_CHARS)
        key = (VERDICT_ORDER["unassessed"], scored.priority, entry.id, "")
        rows.append((key, _verdict(entry, "unassessed", excerpt)))

    rows.sort(key=lambda r: r[0])
    verdicts = [r[1] for r in rows]
    summary = {v: sum(1 for r in verdicts if r["verdict"] == v) for v in ("supports", "violates", "unassessed")}
    return {"verdicts": verdicts, "summary": summary, "method": METHOD, "snapshot_id": snapshot_id}
