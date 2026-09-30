"""Simulation of proposed check clauses against the evaluation cases (lot L7). No write."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from pipelines.doctrine.checks import parse_checks, validate_clause
from pipelines.doctrine.evaluation import Judge, evaluate_cases
from pipelines.doctrine.index import DoctrineIndex
from pipelines.doctrine.judge import check_option as run_judge


def judge_for(index: DoctrineIndex) -> Judge:
    def judge(option: dict[str, Any], subject: str | None, frameworks: list[str]) -> list[dict[str, Any]]:
        verdicts: list[dict[str, Any]] = run_judge(index, option=option, subject=subject, frameworks=frameworks)["verdicts"]
        return verdicts

    return judge


def with_clauses(index: DoctrineIndex, asset_id: str, raw_checks: list[Any]) -> DoctrineIndex:
    """Copy of the index where the clauses of ``asset_id`` are replaced (the asset is treated as active)."""
    clauses = parse_checks(raw_checks, "draft")
    entries = [replace(e, checks=clauses, status="active") if e.id == asset_id else e for e in index.entries]
    return DoctrineIndex(entries=entries, vocabulary=index.vocabulary)


def _view(verdicts: list[dict[str, Any]], typed_id: str) -> list[dict[str, Any]]:
    return [{"check_id": v["check_id"], "verdict": v["verdict"], "matched_terms": v["matched_terms"]}
            for v in verdicts if v["typed_id"] == typed_id and v["verdict"] != "unassessed"]


def _hit(views: list[dict[str, Any]], expected: str | None) -> bool:
    if expected == "violates":
        return any(v["verdict"] == "violates" for v in views)
    if expected == "supports":
        return any(v["verdict"] == "supports" for v in views) and not any(v["verdict"] == "violates" for v in views)
    return False


def _metrics(report: dict[str, Any]) -> dict[str, Any]:
    return {k: report[k] for k in ("violation_recall", "supports_recall", "unexpected_violations", "expected_violations")}


def simulate(index: DoctrineIndex, asset_id: str, raw_checks: Any, cases: list[dict[str, Any]],
             options: list[dict[str, Any]] | None = None, frameworks: list[str] | None = None) -> dict[str, Any]:
    entry = index.get(asset_id)
    if entry is None:
        raise LookupError(asset_id)
    if not isinstance(raw_checks, list):
        raise ValueError("'checks' must be a list of clauses.")
    problems = [{"clause": (c.get("id") if isinstance(c, dict) else None), "problems": p}
                for c in raw_checks if (p := validate_clause(c))]
    before, after = judge_for(index), judge_for(with_clauses(index, asset_id, raw_checks))
    typed_id = entry.typed_id

    changes = []
    for case in cases:
        b = _view(before(case["option"], case.get("subject"), case.get("frameworks") or []), typed_id)
        a = _view(after(case["option"], case.get("subject"), case.get("frameworks") or []), typed_id)
        expected = (case.get("expected") or {}).get(typed_id)
        changes.append({"case_id": case["id"], "title": case["option"].get("title"), "expected": expected,
                        "before": b, "after": a, "changed": b != a,
                        "regression": _hit(b, expected) and not _hit(a, expected),
                        "improvement": expected is not None and not _hit(b, expected) and _hit(a, expected)})
    annotated = [c for c in cases if c.get("expected")]
    metrics = {
        "cases": len(cases),
        "before": _metrics(evaluate_cases(annotated, before)),
        "after": _metrics(evaluate_cases(annotated, after)),
    }
    free = []
    for opt in options or []:
        subject = opt.get("subject")
        free.append({"title": opt.get("title"),
                     "before": _view(before(opt, subject, frameworks or []), typed_id),
                     "after": _view(after(opt, subject, frameworks or []), typed_id)})
    return {"asset_id": asset_id, "typed_id": typed_id, "clause_problems": problems, "metrics": metrics,
            "regressions": [c["case_id"] for c in changes if c["regression"]],
            "improvements": [c["case_id"] for c in changes if c["improvement"]],
            "cases": [c for c in changes if c["changed"] or c["regression"] or c["improvement"]],
            "options": free}
