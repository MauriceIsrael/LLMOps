"""Evaluation of the option judge on an annotated dataset (shared by the script and the API).

Each case lists the expected verdict per typed_id (``violates`` or ``supports``). The main
metric is the **recall of expected violations**; also reported are the supports recall and the
unexpected violations on annotated assets.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

# judge(option, subject, frameworks) -> the verdicts of the option
Judge = Callable[[dict[str, Any], str | None, list[str]], list[dict[str, Any]]]


def evaluate_cases(cases: list[dict[str, Any]], judge: Judge) -> dict[str, Any]:
    rows: list[tuple[str, str, str, str, list[str], bool]] = []
    counts = {"supports": 0, "violates": 0, "unassessed": 0}
    tp = fn = sup_ok = sup_total = unexpected = 0
    for case in cases:
        verdicts = judge(case["option"], case.get("subject"), case.get("frameworks") or [])
        got: dict[str, set[str]] = {}
        for v in verdicts:
            counts[v["verdict"]] = counts.get(v["verdict"], 0) + 1
            got.setdefault(v["typed_id"], set()).add(v["verdict"])
        for typed_id, expected in case["expected"].items():
            seen = got.get(typed_id, set())
            if expected == "violates":
                hit = "violates" in seen
                tp += hit
                fn += not hit
            else:
                sup_total += 1
                hit = "supports" in seen and "violates" not in seen
                sup_ok += hit
                unexpected += "violates" in seen
            rows.append((case["id"], case.get("sector", ""), typed_id, expected, sorted(seen) or ["-"], hit))
    expected_violations = tp + fn
    return {
        "cases": len(cases),
        "validated_cases": sum(1 for c in cases if c.get("annotation_status") == "validated"),
        "expected_violations": expected_violations,
        "violation_recall": tp / expected_violations if expected_violations else 1.0,
        "supports_recall": sup_ok / sup_total if sup_total else 1.0,
        "unexpected_violations": unexpected,
        "verdict_counts": counts,
        "rows": rows,
    }


def summarize(report: dict[str, Any]) -> dict[str, Any]:
    """JSON-friendly report: metrics plus the missed annotations."""
    return {
        **{k: v for k, v in report.items() if k != "rows"},
        "misses": [{"case_id": r[0], "typed_id": r[2], "expected": r[3], "got": r[4]}
                   for r in report["rows"] if not r[5]],
    }
