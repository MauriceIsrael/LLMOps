"""Evaluation of the doctrine ranking on the FR→EN set (issue #94, lot E5).

For every case (a subject, optional declared frameworks, the expected asset ids) the candidate pool is ranked by the
same scores as the doctrine context: lexical relevance, calibrated semantic relevance, and their combination.

* ``recall_at_5``: share of the expected ids ranked in the first 5 of the pool (the required controls of the declared
  frameworks, or the whole active doctrine when none is declared). It does not depend on any threshold.
* the threshold sweep: for each ``min_semantic``, how many expected ids are flagged ``relevant`` and how many other
  assets are flagged with them (noise), to choose ``MIN_SEMANTIC``.

Deterministic for a given index, model and set; used by ``tests/eval/test_semantic_fr_en.py`` and
``scripts/eval/eval_semantic_search.py``.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

from pipelines.doctrine.context import MIN_RELEVANCE, combine, rank, relevance
from pipelines.doctrine.index import DoctrineEntry, DoctrineIndex
from pipelines.doctrine.text import query_concepts

TOP_K = 5
SWEEP = [round(0.30 + 0.05 * i, 2) for i in range(14)]  # 0.30 .. 0.95

SemanticFn = Callable[[str], dict[str, float]]


def load_cases(path: str | Path) -> list[dict[str, Any]]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return list(data.get("cases") or [])


def pool(index: DoctrineIndex, frameworks: list[str] | None) -> list[DoctrineEntry]:
    wanted = {f.lower() for f in (frameworks or [])}
    active = index.active()
    if wanted:
        return [e for e in active if e.type == "control" and e.framework.lower() in wanted]
    return active


def ranked(index: DoctrineIndex, case: dict[str, Any], semantic: dict[str, float] | None,
           weight: float | None) -> list[dict[str, Any]]:
    concepts = query_concepts(case["subject"], index.vocabulary)
    rows: list[dict[str, Any]] = []
    for e in pool(index, case.get("frameworks")):
        lex = relevance(e, concepts)
        sem = None if semantic is None else semantic.get(e.id, 0.0)
        rows.append({"id": e.id, "lexical": lex, "semantic": sem, "score": combine(lex, sem, weight)})
    rows.sort(key=lambda r: (-r["score"], r["id"]))
    return rows


def evaluate(index: DoctrineIndex, cases: list[dict[str, Any]], semantic_fn: SemanticFn | None,
             weight: float | None = None, min_semantic: float = 0.8) -> dict[str, Any]:
    """Recall at 5 and the ``relevant`` threshold sweep; ``semantic_fn=None`` is the lexical baseline."""
    per_case = []
    found = expected_total = flagged_expected = flagged_other = 0
    by_language: dict[str, list[int]] = {}
    sweep = {t: {"expected_relevant": 0, "other_relevant": 0} for t in SWEEP}
    for case in cases:
        semantic = semantic_fn(case["subject"]) if semantic_fn else None
        rows = ranked(index, case, semantic, weight)
        top = [r["id"] for r in rows[:TOP_K]]
        expected = list(case["expected"])
        hits = [x for x in expected if x in top]
        found += len(hits)
        expected_total += len(expected)
        lang = case.get("language", "fr")
        by_language.setdefault(lang, [0, 0])
        by_language[lang][0] += len(hits)
        by_language[lang][1] += len(expected)
        for t in SWEEP:
            flagged = {r["id"] for r in rows if r["lexical"] >= MIN_RELEVANCE
                       or (r["semantic"] is not None and r["semantic"] >= t)}
            sweep[t]["expected_relevant"] += len(flagged & set(expected))
            sweep[t]["other_relevant"] += len(flagged - set(expected))
        # The ``relevant`` flag exactly as the doctrine context sets it (rank), restricted to the pool.
        in_pool = {r["id"] for r in rows}
        relevant = sorted(s.entry.id for s in rank(index, case["subject"], frameworks=case.get("frameworks"),
                                                   semantic=semantic, weight=weight, min_semantic=min_semantic)
                          if s.relevant and s.entry.id in in_pool)
        flagged_expected += len(set(relevant) & set(expected))
        flagged_other += len(set(relevant) - set(expected))
        per_case.append({
            "id": case["id"], "subject": case["subject"], "frameworks": case.get("frameworks") or [],
            "expected": expected, "hits": hits, "top": [{k: r[k] for k in ("id", "score", "lexical", "semantic")}
                                                         for r in rows[:TOP_K]],
            "expected_rank": {x: next((i + 1 for i, r in enumerate(rows) if r["id"] == x), None) for x in expected},
            "relevant": relevant,
        })
    n = len(cases) or 1
    return {
        "cases": len(cases),
        "method": "lexical" if semantic_fn is None else "hybrid",
        "weight": weight,
        "recall_at_5": round(found / expected_total, 4) if expected_total else None,
        "recall_at_5_by_language": {k: round(v[0] / v[1], 4) for k, v in sorted(by_language.items()) if v[1]},
        "relevant": {"expected_flagged": round(flagged_expected / expected_total, 4) if expected_total else None,
                     "other_flagged_per_case": round(flagged_other / n, 2)},
        "sweep": [{"min_semantic": t, "expected_relevant": round(s["expected_relevant"] / expected_total, 4),
                   "other_relevant_per_case": round(s["other_relevant"] / n, 2)} for t, s in sweep.items()],
        "per_case": per_case,
    }
