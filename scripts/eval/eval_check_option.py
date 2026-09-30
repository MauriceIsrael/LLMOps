"""Evaluate the option judge (check_option) on tests/evals/datasets/check_option_v1.jsonl.

Each case lists the expected verdict per typed_id (``violates`` or ``supports``).
The main metric is the **recall of expected violations**: the share of expected
``violates`` for which the judge reports a ``violates`` verdict on that typed_id.
Also reported: supports recall and unexpected violations (on annotated assets).

The annotations are proposed by the coding agent and must be validated by a human
(``annotation_status``); the target recall (>= 80 %) applies to validated annotations.

Usage:
    poetry run python scripts/eval/eval_check_option.py [--dataset PATH] [--min-recall 0.8] [--verbose]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

DEFAULT_DATASET = ROOT_DIR / "tests" / "evals" / "datasets" / "check_option_v1.jsonl"


def load_cases(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def evaluate(cases: list[dict[str, Any]]) -> dict[str, Any]:
    from mcp_server.knowledge.tools import check_option
    from pipelines.doctrine.evaluation import evaluate_cases

    def judge(option: dict[str, Any], subject: str | None, frameworks: list[str]) -> list[dict[str, Any]]:
        res = check_option(option, subject=subject, frameworks=frameworks)
        if res.get("status") != "ok":
            raise RuntimeError(f"check_option failed: {res}")
        verdicts: list[dict[str, Any]] = res["data"]["verdicts"]
        return verdicts

    return evaluate_cases(cases, judge)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--db", action="store_true",
                        help="Read the dataset 'check_option_v1' from the governance database (default when configured).")
    parser.add_argument("--min-recall", type=float, default=None, help="Fail (exit 1) below this violation recall.")
    parser.add_argument("--verbose", action="store_true", help="Print every annotated verdict.")
    args = parser.parse_args()

    from pipelines.governance.store import database_url

    use_db = (args.db or (database_url() is not None and args.dataset == DEFAULT_DATASET)) and args.dataset == DEFAULT_DATASET
    if use_db:
        from pipelines.governance.evals import EvalStore

        store = EvalStore()
        cases = store.cases("check_option_v1") if store.has_dataset("check_option_v1") else load_cases(args.dataset)
    else:
        cases = load_cases(args.dataset)
    report = evaluate(cases)
    misses = [r for r in report["rows"] if not r[5]]
    for case_id, sector, typed_id, expected, got, hit in (report["rows"] if args.verbose else misses):
        print(f"{'OK  ' if hit else 'MISS'} {case_id} [{sector}] {typed_id}: expected {expected}, got {', '.join(got)}")
    print()
    print(f"dataset: {args.dataset.relative_to(ROOT_DIR) if args.dataset.is_relative_to(ROOT_DIR) else args.dataset}")
    print(f"cases: {report['cases']} (validated annotations: {report['validated_cases']})")
    print(f"violation recall: {report['violation_recall']:.1%} of {report['expected_violations']} expected violations")
    print(f"supports recall: {report['supports_recall']:.1%}")
    print(f"unexpected violations on annotated assets: {report['unexpected_violations']}")
    if report["validated_cases"] < report["cases"]:
        print("note: annotations proposed by the coding agent — the >= 80 % target applies once a human validates them.")
    if args.min_recall is not None and report["violation_recall"] < args.min_recall:
        print(f"FAIL: violation recall below {args.min_recall:.0%}")
        return 1
    return 0


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    os._exit(code)
