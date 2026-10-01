"""Evaluation of the similarity search on an annotated FR/EN dataset (lot L13).

The client computes the vectors of the cases (it holds the model); LLMOps computes the metrics and the threshold
sweep deterministically. Thresholds of ``taxonomy/similarity.yaml`` are only ever changed from a documented run:
the first thing a run answers is *how many strong proposals were wrong*, because a strong wrong proposal is the
failure the whole design exists to prevent (decision D8: a human still confirms every reuse).
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from pipelines.governance.evals import ANNOTATION_STATUSES, EvalError, EvalStore
from pipelines.kb_candidates.kb import load_assets
from pipelines.similarity.search import similar
from pipelines.similarity.store import EmbeddingStore, validate_vector

DATASET = "similarity_v1"
FAMILIES = ("cross_lingual", "same_words_different_subject", "same_topic_different_assumptions", "out_of_base")
RELATIONS = ("same_subject", "related_not_same", "same_topic_different_assumptions", "unrelated")
LANGUAGES = ("fr", "en")
SWEEP = [round(0.40 + 0.05 * i, 2) for i in range(12)]  # 0.40 .. 0.95
TOP_K = 10


def validate_expected(expected: Any, kb_dir: str | Path) -> list[dict[str, str]]:
    if not isinstance(expected, list):
        raise EvalError("expected", "'expected' must be a list of {ref, relation} (empty for a subject absent from the base).")
    known = {a.id for a in load_assets(kb_dir)}
    clean = []
    for item in expected:
        if not isinstance(item, dict) or item.get("relation") not in RELATIONS or item.get("ref") not in known:
            raise EvalError("expected", f"each entry needs a known 'ref' and a 'relation' in {list(RELATIONS)}.")
        clean.append({"ref": item["ref"], "relation": item["relation"]})
    return clean


def annotate(store: EvalStore, dataset: str, case_id: str, annotator: str, kb_dir: str | Path,
             expected: Any = None, status: str | None = None) -> dict[str, Any]:
    """Set the expected relations and/or the annotation status; the annotator is the acting expert."""
    import json

    from sqlalchemy import update

    from pipelines.governance.log import now_iso
    from pipelines.governance.store import eval_cases

    case = store.case(dataset, case_id)
    if status is not None and status not in ANNOTATION_STATUSES:
        raise EvalError("annotation_status", f"must be one of {list(ANNOTATION_STATUSES)}.")
    if expected is not None:
        case["expected"] = validate_expected(expected, kb_dir)
    doc = {k: v for k, v in case.items() if k not in ("annotation_status", "annotated_by", "annotated_at")}
    with store.engine.begin() as conn:
        conn.execute(update(eval_cases).where((eval_cases.c.dataset == dataset) & (eval_cases.c.case_id == case_id)).values(
            doc=json.dumps(doc, ensure_ascii=False), annotation_status=status or case["annotation_status"],
            annotated_by=annotator, annotated_at=now_iso()))
    return store.case(dataset, case_id)


def evaluate(cases: list[dict[str, Any]], vectors: dict[str, Any], embeddings: EmbeddingStore, kb_dir: str | Path,
             model: str, lexical_for: Any = None) -> dict[str, Any]:
    per_case: list[dict[str, Any]] = []
    totals: dict[str, float] = defaultdict(float)
    by_family: dict[str, dict[str, float]] = {f: defaultdict(float) for f in FAMILIES}
    by_language: dict[str, dict[str, float]] = {lg: defaultdict(float) for lg in LANGUAGES}
    sweep = {t: {"false_strong": 0, "same_found": 0} for t in SWEEP}
    for case in cases:
        expected = case.get("expected") or []
        same = {e["ref"] for e in expected if e["relation"] == "same_subject"}
        topic = {e["ref"] for e in expected if e["relation"] == "same_topic_different_assumptions"}
        res = similar(embeddings, kb_dir, model, vectors[case["id"]], case.get("query_text"), None, None, TOP_K,
                      lexical_for(case["query_text"]) if lexical_for else None)["results"]
        live = [r for r in res if r["zone"] != "superseded"]
        top3 = {r["ref"] for r in live[:3]}
        strong = {r["ref"] for r in live if r["zone"] == "strong"}
        false_strong = sorted(strong - same - topic)
        trap = sorted(strong & topic)
        found3 = same & top3
        missed_strong = sorted(same - strong)
        for t in SWEEP:
            above = {r["ref"] for r in live if r["score"] >= t}
            sweep[t]["false_strong"] += len(above - same - topic)
            sweep[t]["same_found"] += len(above & same)
        fam, lang = case.get("family"), case.get("language")
        for bucket in (totals, by_family.get(fam or "", defaultdict(float)), by_language.get(lang or "", defaultdict(float))):
            bucket["cases"] += 1
            bucket["same_expected"] += len(same)
            bucket["same_in_top3"] += len(found3)
            bucket["false_strong"] += len(false_strong)
            bucket["reuse_trap_strong"] += len(trap)
            bucket["missed_strong"] += len(missed_strong)
        per_case.append({"case_id": case["id"], "family": fam, "language": lang, "false_strong": false_strong,
                         "reuse_trap_strong": trap, "missed_strong": missed_strong,
                         "top": [{"ref": r["ref"], "score": r["score"], "zone": r["zone"]} for r in live[:3]]})

    def rate(b: dict[str, float]) -> dict[str, Any]:
        exp = b.get("same_expected", 0)
        return {"cases": int(b.get("cases", 0)), "same_subject_expected": int(exp),
                "recall_at_3": round(b.get("same_in_top3", 0) / exp, 4) if exp else None,
                "false_strong": int(b.get("false_strong", 0)), "reuse_trap_strong": int(b.get("reuse_trap_strong", 0)),
                "missed_strong": int(b.get("missed_strong", 0))}

    same_total = sum(1 for c in cases for e in c.get("expected") or [] if e["relation"] == "same_subject")
    table = [{"threshold": t, "false_strong": sweep[t]["false_strong"],
              "recall": round(sweep[t]["same_found"] / same_total, 4) if same_total else None} for t in SWEEP]
    safe = [row for row in table if row["false_strong"] == 0]
    return {"cases": len(cases), "model": model, **rate(totals),
            "by_family": {f: rate(b) for f, b in by_family.items()},
            "by_language": {lg: rate(b) for lg, b in by_language.items()},
            "sweep": table,
            "recommended_strong_threshold": safe[0]["threshold"] if safe else None,
            "recommendation_note": ("lowest threshold with no wrong strong proposal on these cases"
                                    if safe else "no threshold in the sweep avoids every wrong strong proposal"),
            "per_case": per_case}


def check_vectors(cases: list[dict[str, Any]], vectors: Any, dim: int) -> dict[str, Any]:
    if not isinstance(vectors, dict):
        raise EvalError("vectors", "'vectors' must map each case id to its vector.")
    missing = [c["id"] for c in cases if c["id"] not in vectors]
    if missing:
        raise EvalError("vectors", f"missing vector(s) for case(s): {missing[:10]}.")
    for c in cases:
        try:
            validate_vector(vectors[c["id"]], dim)
        except ValueError as exc:
            raise EvalError("vectors", f"{c['id']}: {exc}") from exc
    return vectors
