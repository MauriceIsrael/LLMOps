"""Vectors in the governance database (lot L11)."""

from __future__ import annotations

import json
import math
from typing import Any

from sqlalchemy import select

from pipelines.governance.log import now_iso
from pipelines.governance.store import embeddings, get_engine

MAX_DIM = 4096
MAX_BATCH = 500


class EmbeddingError(ValueError):
    def __init__(self, argument: str, reason: str) -> None:
        super().__init__(reason)
        self.argument, self.reason = argument, reason


def validate_vector(vector: Any, dim: int | None = None) -> list[float]:
    if not isinstance(vector, list) or not vector or len(vector) > MAX_DIM:
        raise EmbeddingError("vector", f"'vector' must be a non-empty list of at most {MAX_DIM} numbers.")
    out: list[float] = []
    for x in vector:
        if isinstance(x, bool) or not isinstance(x, int | float) or not math.isfinite(x):
            raise EmbeddingError("vector", "'vector' must contain finite numbers only.")
        out.append(float(x))
    if dim is not None and len(out) != dim:
        raise EmbeddingError("vector", f"the vector has {len(out)} dimensions, the model's space has {dim}.")
    if not any(out):
        raise EmbeddingError("vector", "the null vector carries no information.")
    return out


class EmbeddingStore:
    def __init__(self, url: str | None = None) -> None:
        self.engine = get_engine(url)

    def models(self) -> list[dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(select(embeddings.c.model_id, embeddings.c.model_version, embeddings.c.dim)).all()
        seen: dict[str, dict[str, Any]] = {}
        for r in rows:
            m = seen.setdefault(r.model_id, {"model_id": r.model_id, "versions": set(), "dim": r.dim, "vectors": 0})
            m["versions"].add(r.model_version)
            m["vectors"] += 1
        return [{**m, "versions": sorted(m["versions"])} for m in sorted(seen.values(), key=lambda m: m["model_id"])]

    def model_space(self, model_id: str) -> tuple[int, str] | None:
        """(dimension, version) of a model's space, or ``None`` when no vector exists for it."""
        with self.engine.connect() as conn:
            row = conn.execute(select(embeddings.c.dim, embeddings.c.model_version)
                               .where(embeddings.c.model_id == model_id).limit(1)).first()
        return (row.dim, row.model_version) if row else None

    def put(self, items: list[dict[str, Any]], model_id: str, model_version: str, created_by: str,
            current: dict[str, dict[str, Any]]) -> dict[str, Any]:
        """Deposit vectors. ``current`` maps ref -> {type, text_sha256} of the assets as they are *now*."""
        if not isinstance(model_id, str) or not model_id.strip():
            raise EmbeddingError("model", "'model' is required (identifier of the embedding model).")
        if not isinstance(model_version, str) or not model_version.strip():
            raise EmbeddingError("model_version", "'model_version' is required.")
        if not isinstance(items, list) or not items or len(items) > MAX_BATCH:
            raise EmbeddingError("items", f"'items' must hold between 1 and {MAX_BATCH} vectors.")
        space = self.model_space(model_id)
        if space and space[1] != model_version:
            raise EmbeddingError("model_version", f"model '{model_id}' is stored in version '{space[1]}', not "
                                 f"'{model_version}': vectors of two versions are never compared — re-embed everything "
                                 "(delete the model's vectors first).")
        dim = space[0] if space else None
        rows = []
        for item in items:
            ref = str((item or {}).get("ref") or "")
            if ref not in current:
                raise EmbeddingError("items", f"'{ref}' is not an active asset or control.")
            if item.get("text_sha256") != current[ref]["text_sha256"]:
                raise EmbeddingError("items", f"stale vector for '{ref}': its text changed (expected sha256 "
                                     f"{current[ref]['text_sha256'][:12]}…). Fetch /embeddings/pending again.")
            vector = validate_vector(item.get("vector"), dim)
            dim = dim or len(vector)
            rows.append({"ref": ref, "model_id": model_id, "kind": current[ref]["type"], "model_version": model_version,
                         "dim": dim, "vector": json.dumps(vector), "text_sha256": item["text_sha256"],
                         "language": item.get("language"), "created_by": created_by, "created_at": now_iso()})
        with self.engine.begin() as conn:
            for row in rows:
                conn.execute(embeddings.delete().where((embeddings.c.ref == row["ref"]) & (embeddings.c.model_id == model_id)))
                conn.execute(embeddings.insert().values(**row))
        return {"stored": len(rows), "model": model_id, "model_version": model_version, "dim": dim}

    def hashes(self, model_id: str) -> dict[str, str]:
        with self.engine.connect() as conn:
            rows = conn.execute(select(embeddings.c.ref, embeddings.c.text_sha256)
                                .where(embeddings.c.model_id == model_id)).all()
        return {r.ref: r.text_sha256 for r in rows}

    def vectors(self, model_id: str) -> list[dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(select(embeddings).where(embeddings.c.model_id == model_id)
                                .order_by(embeddings.c.ref)).all()
        return [{"ref": r.ref, "kind": r.kind, "text_sha256": r.text_sha256, "language": r.language,
                 "vector": json.loads(r.vector)} for r in rows]

    def delete_model(self, model_id: str) -> int:
        with self.engine.begin() as conn:
            return int(conn.execute(embeddings.delete().where(embeddings.c.model_id == model_id)).rowcount)
