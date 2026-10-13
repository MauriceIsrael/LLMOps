"""Semantic relevance of the assets for a query, in the reference model's space (issue #94, lot E3).

The vectors of the assets come from the ``embeddings`` table (written by the publication); an asset whose vector is
missing or stale (its text changed since) is encoded here and kept in memory, never written back. Scores are cosine
similarities rounded to 4 decimals, then mapped onto [0, 1] with the model's calibrated band (``floor``/``ceil``), so
that the same model, snapshot and query always give the same order (ties are broken by identifier by the callers).
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from pathlib import Path
from typing import Any

from pipelines.similarity.encoder import Encoder
from pipelines.similarity.models import ModelSpec
from pipelines.similarity.text import embeddable_assets

QUERY_CACHE_SIZE = 256
_KB_SUFFIXES = (".md", ".yaml", ".yml")


def _kb_signature(kb_dir: str | Path) -> tuple[tuple[str, int, int], ...]:
    """Cheap fingerprint of the knowledge base files (path, size, mtime): re-reading the assets costs far more."""
    return tuple(sorted((str(p), p.stat().st_size, p.stat().st_mtime_ns) for p in Path(kb_dir).rglob("*")
                        if p.suffix in _KB_SUFFIXES and p.is_file()))


_ITEMS: dict[str, tuple[tuple[tuple[str, int, int], ...], list[dict[str, Any]]]] = {}
_ITEMS_LOCK = threading.Lock()


def active_items(kb_dir: str | Path) -> list[dict[str, Any]]:
    """``embeddable_assets(kb_dir)``, re-read only when a file of the base changed."""
    key, sig = str(Path(kb_dir).resolve()), _kb_signature(kb_dir)
    with _ITEMS_LOCK:
        cached = _ITEMS.get(key)
        if cached and cached[0] == sig:
            return cached[1]
    items = embeddable_assets(kb_dir)
    with _ITEMS_LOCK:
        _ITEMS[key] = (sig, items)
    return items


def cosine_unit(a: list[float], b: list[float]) -> float:
    """Cosine of two L2-normalised vectors, rounded to 4 decimals (reproducibility)."""
    return round(sum(x * y for x, y in zip(a, b, strict=True)), 4)


def calibrate(cos: float, spec: ModelSpec) -> float:
    """Cosine mapped onto [0, 1] with the model's band: below ``floor`` is 0, above ``ceil`` is 1."""
    span = spec.ceil - spec.floor
    return round(min(1.0, max(0.0, (cos - spec.floor) / span)), 4) if span > 0 else 0.0


class AssetVectors:
    """Vectors of the active assets for one encoder: stored ones first, the rest encoded on demand (in memory)."""

    def __init__(self, encoder: Encoder) -> None:
        self.encoder = encoder
        self._by_sha: dict[str, list[float]] = {}
        self._queries: OrderedDict[str, list[float]] = OrderedDict()
        self._lock = threading.Lock()

    def _stored(self) -> dict[str, dict[str, Any]]:
        from pipelines.governance.store import database_url

        if not database_url():
            return {}
        try:
            from pipelines.similarity.store import EmbeddingStore

            space = EmbeddingStore().model_space(self.encoder.spec.id)
            if space is None or space[1] != self.encoder.spec.version or space[0] != self.encoder.spec.dim:
                return {}
            return {v["ref"]: v for v in EmbeddingStore().vectors(self.encoder.spec.id)}
        except Exception:  # an unreachable database only costs an on-the-fly encoding
            return {}

    def vectors(self, kb_dir: str | Path) -> dict[str, list[float]]:
        """``ref -> vector`` of every active asset of ``kb_dir`` (encoding what is neither stored nor cached)."""
        items = active_items(kb_dir)
        with self._lock:
            if any(i["text_sha256"] not in self._by_sha for i in items):
                for ref_vec in self._stored().values():
                    self._by_sha.setdefault(ref_vec["text_sha256"], ref_vec["vector"])
            todo = [i for i in items if i["text_sha256"] not in self._by_sha]
            if todo:
                for i, v in zip(todo, self.encoder.encode([i["text"] for i in todo], "passage"), strict=True):
                    self._by_sha[i["text_sha256"]] = v
            return {i["ref"]: self._by_sha[i["text_sha256"]] for i in items}

    def query(self, text: str) -> list[float]:
        with self._lock:
            if text in self._queries:
                self._queries.move_to_end(text)
                return self._queries[text]
        vec = self.encoder.encode([text], "query")[0]
        with self._lock:
            self._queries[text] = vec
            while len(self._queries) > QUERY_CACHE_SIZE:
                self._queries.popitem(last=False)
        return vec

    def scores(self, kb_dir: str | Path, query: str) -> dict[str, dict[str, float]]:
        """``ref -> {cosine, semantic}`` for every active asset (``semantic`` is the calibrated score in [0, 1])."""
        q = self.query(query)
        out = {}
        for ref, vec in self.vectors(kb_dir).items():
            cos = cosine_unit(q, vec)
            out[ref] = {"cosine": cos, "semantic": calibrate(cos, self.encoder.spec)}
        return out


class MemoryVectors:
    """The vector-store interface of ``search.similar`` over the vectors of an ``AssetVectors`` (server-side encoding:
    the governance database is not needed to compare a subject with the knowledge base)."""

    def __init__(self, scorer: AssetVectors, kb_dir: str | Path) -> None:
        self.spec = scorer.encoder.spec
        vectors = scorer.vectors(kb_dir)
        self._items = [{"ref": i["ref"], "kind": i["type"], "text_sha256": i["text_sha256"], "language": i["language"],
                        "vector": vectors[i["ref"]]} for i in sorted(active_items(kb_dir), key=lambda i: i["ref"])]

    def model_space(self, model_id: str) -> tuple[int, str] | None:
        return (self.spec.dim, self.spec.version) if model_id == self.spec.id else None

    def models(self) -> list[dict[str, Any]]:
        return [{"model_id": self.spec.id, "versions": [self.spec.version], "dim": self.spec.dim,
                 "vectors": len(self._items)}]

    def vectors(self, model_id: str) -> list[dict[str, Any]]:
        return list(self._items) if model_id == self.spec.id else []


_SCORERS: dict[int, AssetVectors] = {}
_SCORERS_LOCK = threading.Lock()


def scorer_for(encoder: Encoder) -> AssetVectors:
    """One vector cache per loaded encoder (the encoder is itself cached per settings)."""
    with _SCORERS_LOCK:
        key = id(encoder)
        if key not in _SCORERS:
            _SCORERS[key] = AssetVectors(encoder)
        return _SCORERS[key]


def reset() -> None:
    with _SCORERS_LOCK:
        _SCORERS.clear()
    with _ITEMS_LOCK:
        _ITEMS.clear()
