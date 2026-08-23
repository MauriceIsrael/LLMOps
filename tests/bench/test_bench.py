"""Automated test running the benchmark evaluation harness."""

from pathlib import Path

import pytest

from tests.bench.harness import run_benchmark


@pytest.mark.deterministic
def test_adr_benchmark_harness():
    """Verify benchmark harness executes and evaluates recall and exact match metrics."""
    bench_file = Path("tests/bench/adr_bench.jsonl")
    assert bench_file.exists(), "Benchmark dataset tests/bench/adr_bench.jsonl does not exist"

    db_p = "/tmp/knowledge.lbug" if Path("/tmp/knowledge.lbug").exists() else "data/knowledge.kuzu"
    backend = "ladybug" if str(db_p).endswith(".lbug") else "kuzu"

    report = run_benchmark(bench_file=bench_file, db_path=db_p, backend=backend)
    assert "total_questions" in report
    assert report["total_questions"] >= 10
    assert report["mean_recall"] >= 0.50
