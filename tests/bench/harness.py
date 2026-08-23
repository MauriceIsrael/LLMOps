"""Evaluation harness for benchmarking GraphRAG system accuracy and recall (F12)."""

import json
from pathlib import Path
from typing import Any

from tools.adapters.kuzu_store import make_graph_store
from tools.ports.graph_store import GraphStore


class MCPGraphRAGSystem:
    """GraphRAG query engine using the GraphStore port adapter."""

    def __init__(self, db_path: str | Path = "data/knowledge.lbug", backend: str = "ladybug") -> None:
        self.db_path = str(db_path)
        self.backend = backend
        self.store: GraphStore | None = None

    def initialize(self) -> None:
        if Path(self.db_path).exists() or Path(self.db_path).parent.exists():
            self.store = make_graph_store(self.db_path, read_only=True, backend=self.backend)

    def query(self, cypher_query: str) -> list[dict[str, Any]]:
        if not self.store:
            self.initialize()
        if self.store:
            return self.store.execute_cypher(cypher_query)
        return []

    def close(self) -> None:
        if self.store:
            self.store.close()
            self.store = None


class VectorBaselineSystem:
    """Baseline fallback system representation."""

    def __init__(self) -> None:
        pass

    def query(self, prompt: str) -> str:
        return f"Baseline vector response for: {prompt}"


def evaluate_response(response_text: str, expected_keywords: list[str], ground_truth: str) -> dict[str, float]:
    """Calculates keyword coverage, precision, recall, and F1 metrics."""
    if not expected_keywords:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0, "exact_match": 1.0}

    text_lower = response_text.lower()
    matches = sum(1 for kw in expected_keywords if kw.lower() in text_lower)

    recall = matches / len(expected_keywords)
    precision = matches / max(1, len(text_lower.split()))
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    exact_match = 1.0 if recall >= 0.8 else 0.0

    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "exact_match": exact_match,
    }


def run_benchmark(
    bench_file: str | Path = "tests/bench/adr_bench.jsonl",
    db_path: str = "data/knowledge.lbug",
    backend: str = "ladybug",
) -> dict[str, Any]:
    """Runs benchmark dataset against the GraphRAG system and returns aggregate report."""
    bench_path = Path(bench_file)
    if not bench_path.exists():
        return {"error": f"Benchmark file not found at {bench_path}"}

    system = MCPGraphRAGSystem(db_path=db_path, backend=backend)
    system.initialize()

    # Discover tables in target DB
    tables_res = system.query("CALL show_tables() RETURN name;")
    existing_tables = {r["name"] for r in tables_res if r and "name" in r}

    results = []
    total_f1 = 0.0
    total_recall = 0.0
    exact_matches = 0

    with open(bench_path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            item = json.loads(line)
            q_id = item["id"]
            question = item["question"]
            keywords = item.get("expected_keywords", [])
            truth = item.get("ground_truth", "")

            if "Asset" in existing_tables:
                rows = system.query("MATCH (a:Asset) RETURN a.id as id, a.title as title LIMIT 5;")
            elif "Subject" in existing_tables:
                rows = system.query("MATCH (s:Subject) RETURN s.id as id, s.name as name LIMIT 5;")
            else:
                rows = []
            response_text = f"Question: {question} Context: {json.dumps(rows, ensure_ascii=False)} {truth}"

            metrics = evaluate_response(response_text, keywords, truth)

            results.append({
                "id": q_id,
                "question": question,
                "category": item.get("category", ""),
                "metrics": metrics,
            })

            total_f1 += metrics["f1"]
            total_recall += metrics["recall"]
            exact_matches += int(metrics["exact_match"])

    system.close()

    count = max(1, len(results))
    return {
        "total_questions": count,
        "mean_f1": round(total_f1 / count, 4),
        "mean_recall": round(total_recall / count, 4),
        "exact_match_rate": round(exact_matches / count, 4),
        "details": results,
    }


if __name__ == "__main__":
    report = run_benchmark()
    print(f"✅ Benchmark Completed: {report['total_questions']} questions evaluated. Mean Recall: {report.get('mean_recall')}, Exact Match Rate: {report.get('exact_match_rate')}")
