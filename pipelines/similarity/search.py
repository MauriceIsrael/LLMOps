"""Hybrid similarity search (lot L11): cosine over client-supplied vectors + the deterministic lexical engine.

Nothing here decides a reuse: ``zone`` orders and labels, and every result carries ``requires_confirmation: true``
(decision D8). Same inputs, same output.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import yaml

from pipelines.kb_candidates.kb import KbAsset, load_assets
from pipelines.similarity.store import EmbeddingError, EmbeddingStore, validate_vector

DEFAULT_CONFIG: dict[str, Any] = {
    "status": "uncalibrated",
    "weights": {"vector": 0.70, "lexical": 0.25, "domain": 0.05},
    "thresholds": {"strong": 0.80, "possible": 0.60},
}
MAX_TOP_K = 50


def load_config(kb_dir: str | Path) -> dict[str, Any]:
    path = Path(kb_dir) / "taxonomy" / "similarity.yaml"
    if not path.is_file():
        return DEFAULT_CONFIG
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {
        "status": str(data.get("status") or "uncalibrated"),
        "weights": {**DEFAULT_CONFIG["weights"], **(data.get("weights") or {})},
        "thresholds": {**DEFAULT_CONFIG["thresholds"], **(data.get("thresholds") or {})},
    }


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def _zone(score: float, status: str, thresholds: dict[str, float]) -> str:
    if status == "superseded":
        return "superseded"
    if score >= thresholds["strong"]:
        return "strong"
    return "possible" if score >= thresholds["possible"] else "weak"


def _provenance(asset: KbAsset) -> dict[str, Any]:
    fm = asset.frontmatter
    assumptions = [str(a) for a in (fm.get("assumptions") or []) if str(a).strip()]
    return {
        "status": str(fm.get("status") or ""),
        "domain": [str(d) for d in (fm.get("domain") or [])],
        "last_reviewed": fm.get("last_reviewed"),
        "review_by": fm.get("review_by"),
        "validated_by": [str(v) for v in (fm.get("validated_by") or [])],
        "validated_at": fm.get("validated_at"),
        "superseded_by": fm.get("superseded_by"),
        "assumptions": assumptions,
        "assumptions_documented": bool(assumptions),
    }


def similar(
    store: EmbeddingStore,
    kb_dir: str | Path,
    model: str,
    vector: Any,
    query_text: str | None = None,
    types: list[str] | None = None,
    domains: list[str] | None = None,
    top_k: int = 10,
    lexical: Any = None,
    judgements: dict[str, list[dict[str, Any]]] | None = None,
    summary: dict[str, dict[str, int]] | None = None,
) -> dict[str, Any]:
    """``lexical(asset_id) -> float | None`` is the deterministic relevance of the doctrine engine for the query."""
    space = store.model_space(model)
    if space is None:
        known = [m["model_id"] for m in store.models()]
        raise EmbeddingError("model", f"no vector stored for model '{model}' (known models: {known}).")
    query = validate_vector(vector, space[0])
    config = load_config(kb_dir)
    w, th = config["weights"], config["thresholds"]
    assets = {a.id: a for a in load_assets(kb_dir)}
    wanted = {d for d in (domains or []) if d}
    results = []
    for item in store.vectors(model):
        asset = assets.get(item["ref"])
        if asset is None or (types and asset.type not in types):
            continue
        prov = _provenance(asset)
        parts = {"vector": max(0.0, cosine(query, item["vector"]))}
        weights = {"vector": w["vector"]}
        if query_text and lexical is not None:
            rel = lexical(asset.id)
            if rel is not None:
                parts["lexical"], weights["lexical"] = float(rel), w["lexical"]
        if wanted:
            hit = any(d == a or a.startswith(d.rstrip("/") + "/") for d in wanted for a in prov["domain"])
            parts["domain"], weights["domain"] = 1.0 if hit else 0.0, w["domain"]
        combined = sum(weights[k] * parts[k] for k in parts) / sum(weights.values())
        results.append({
            "ref": asset.id, "type": asset.type, "title": asset.title,
            "score": round(combined, 4), "scores": {k: round(v, 4) for k, v in parts.items()},
            "zone": _zone(combined, prov["status"], th),
            "requires_confirmation": True,  # decision D8: no automatic reuse, whatever the score
            "stale": item["text_sha256"] != _current_hash(asset),
            **prov,
        })
        past = (judgements or {}).get(asset.id, [])
        results[-1]["judgements"] = past
        # A confirmation made on other hypotheses than the asset's current ones no longer stands.
        results[-1]["previous_confirmation_outdated"] = any(
            j["outcome"] in ("reused", "reused_with_exception") and j["assumptions_changed_since"] for j in past)
        results[-1]["reuse_summary"] = (summary or {}).get(asset.id, {})
    results.sort(key=lambda r: (-r["score"], r["ref"]))
    return {"model": model, "dim": space[0], "model_version": space[1], "config": config,
            "results": results[: max(1, min(int(top_k), MAX_TOP_K))]}


def _current_hash(asset: KbAsset) -> str:
    from pipelines.similarity.text import asset_text, text_sha256

    return text_sha256(asset_text(asset))
