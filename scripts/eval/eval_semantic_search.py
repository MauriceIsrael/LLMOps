"""Evaluate the local semantic search (issue #94, lot E5) on tests/fixtures/similarity/fr-en-doctrine.yaml.

Compares the hybrid ranking (lexical + the server's local embedding model) with the lexical baseline: recall at 5
(share of the expected asset ids in the first 5), per language, and the sweep of the ``relevant`` threshold used to
calibrate ``MIN_SEMANTIC``. Needs the model (``kb models fetch``); never calls the network itself.

Usage:
    poetry run python scripts/eval/eval_semantic_search.py [--cases PATH] [--min-recall 0.8] [--json OUT] [--verbose]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

DEFAULT_CASES = ROOT_DIR / "tests" / "fixtures" / "similarity" / "fr-en-doctrine.yaml"


def run(cases_path: Path, weight: float | None = None) -> dict:
    os.environ.setdefault("KB_EMBEDDINGS", "on")
    from mcp_server.core.config import server_config
    from mcp_server.knowledge.tools import _doctrine_index
    from pipelines.doctrine.context import DEFAULT_HYBRID_WEIGHT, MIN_SEMANTIC
    from pipelines.doctrine.semantic_eval import evaluate, load_cases
    from pipelines.similarity.encoder import reference_encoder
    from pipelines.similarity.semantic import scorer_for

    encoder, status = reference_encoder()
    if encoder is None:
        raise SystemExit(f"embedding model {status['model']} is {status['status']}: {status.get('reason')}")
    index = _doctrine_index()
    cases = load_cases(cases_path)
    scorer = scorer_for(encoder)
    t0 = time.perf_counter()
    scorer.vectors(server_config.kb_dir)
    index_seconds = time.perf_counter() - t0

    def semantic(subject: str) -> dict[str, float]:
        return {ref: s["semantic"] for ref, s in scorer.scores(server_config.kb_dir, subject).items()}

    w = DEFAULT_HYBRID_WEIGHT if weight is None else weight
    t0 = time.perf_counter()
    hybrid = evaluate(index, cases, semantic, weight=w, min_semantic=MIN_SEMANTIC)
    per_query_ms = (time.perf_counter() - t0) * 1000 / max(1, len(cases))
    lexical = evaluate(index, cases, None, min_semantic=MIN_SEMANTIC)
    return {"model": {k: status[k] for k in ("model", "version", "sha256", "local")}, "min_semantic": MIN_SEMANTIC,
            "weight": w, "timing": {"encode_assets_s": round(index_seconds, 2), "per_query_ms": round(per_query_ms, 1)},
            "hybrid": hybrid, "lexical": lexical}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--min-recall", type=float, default=0.8)
    parser.add_argument("--weight", type=float, default=None, help="KB_HYBRID_WEIGHT to evaluate (default: maximum).")
    parser.add_argument("--json", type=Path, default=None, help="Write the full report here.")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    report = run(args.cases, args.weight)
    h, lx = report["hybrid"], report["lexical"]
    print(f"model {report['model']['model']} @ {report['model']['version'][:12]} (local)")
    print(f"cases {h['cases']}  recall@5 hybrid {h['recall_at_5']}  lexical {lx['recall_at_5']}")
    print(f"  by language: hybrid {h['recall_at_5_by_language']}  lexical {lx['recall_at_5_by_language']}")
    print(f"  relevant flag (as served): hybrid {h['relevant']}  lexical {lx['relevant']}")
    print(f"  timing: {report['timing']}")
    print("  relevant-threshold sweep (min_semantic: expected flagged / other flagged per case):")
    for row in h["sweep"]:
        mark = "  <- MIN_SEMANTIC" if row["min_semantic"] == report["min_semantic"] else ""
        print(f"    {row['min_semantic']:.2f}: {row['expected_relevant']:.3f} / {row['other_relevant_per_case']}{mark}")
    if args.verbose:
        for c in h["per_case"]:
            if len(c["hits"]) < len(c["expected"]):
                print(f"  miss {c['id']}: expected rank {c['expected_rank']}, top {[t['id'] for t in c['top']]}")
    if args.json:
        args.json.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    ok = (h["recall_at_5"] or 0) >= args.min_recall and (h["recall_at_5_by_language"].get("en", 1)
                                                        >= lx["recall_at_5_by_language"].get("en", 0))
    print("OK" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    os._exit(code)  # the graph database's threads would otherwise keep the process alive
