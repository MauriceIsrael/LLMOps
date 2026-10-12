"""Server-side text encoder (issue #94, lot E1): local, on the processor, reproducible.

``Encoder.encode(texts, kind)`` returns L2-normalised vectors; ``kind`` is ``"query"`` (a subject) or ``"passage"`` (an
asset), which selects the prefix the E5 family requires. Two implementations:

* ``FastEmbedEncoder``: ``fastembed`` (ONNX Runtime, CPU) on the pinned files of ``data/models/`` (checked against their
  SHA-256 before loading). The number of ONNX threads is fixed (``KB_EMBEDDING_THREADS``, default 1) so that the same
  model, snapshot and query always give the same order.
* ``ToyBowEncoder``: the hashed bag of words of the tests (no semantics), kept as an explicit fallback for tests.

Settings (environment):

* ``KB_EMBEDDINGS`` = ``on`` | ``off`` (default: on when the model is present; ``off`` forces the lexical ranking);
* ``KB_EMBEDDING_MODEL`` (default ``intfloat/multilingual-e5-small``; ``toy-bow`` for tests);
* ``KB_EMBEDDING_PROVIDER`` = ``local`` (the only provider of v1; anything else disables the embeddings);
* ``KB_MODELS_DIR`` (default ``data/models``), ``KB_EMBEDDING_THREADS`` (default 1).

The server never downloads anything: an absent or corrupt model means ``status: "absent"`` and the lexical ranking.
"""

from __future__ import annotations

import hashlib
import math
import os
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol

from pipelines.similarity.models import TOY_BOW, ModelSpec, model_dir, spec_for, verify

Kind = Literal["query", "passage"]
STATUSES = ("ready", "absent", "off")


class Encoder(Protocol):
    spec: ModelSpec

    def encode(self, texts: list[str], kind: Kind) -> list[list[float]]: ...


def _normalise(vec: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in vec))
    return [x / n for x in vec] if n else vec


class ToyBowEncoder:
    """Hashed bag of words, 128 dimensions (identical to the toy client of the tests)."""

    spec = TOY_BOW

    def encode(self, texts: list[str], kind: Kind) -> list[list[float]]:
        out = []
        for text in texts:
            vec = [0.0] * TOY_BOW.dim
            for w in re.findall(r"[a-zà-ÿ0-9]+", text.lower()):
                if len(w) > 2:
                    vec[int(hashlib.sha256(w.encode()).hexdigest(), 16) % TOY_BOW.dim] += 1.0
            out.append(_normalise(vec))
        return out


class FastEmbedEncoder:
    """``fastembed`` on a local, verified copy of the model. Loading never touches the network."""

    # One text per ONNX run: the int8 model quantises its activations per run, so a vector encoded in a batch would
    # depend on the other texts of the batch (and an incremental index would differ from a full one).
    BATCH = 1

    def __init__(self, spec: ModelSpec, models_dir: str | Path | None = None, threads: int = 1) -> None:
        problems = verify(spec, models_dir)
        if problems:
            raise FileNotFoundError("; ".join(problems))
        os.environ.setdefault("HF_HUB_OFFLINE", "1")  # belt and braces: the local path below is used as is
        from fastembed import TextEmbedding
        from fastembed.common.model_description import ModelSource, PoolingType

        if spec.id not in {m["model"] for m in TextEmbedding.list_supported_models()}:
            TextEmbedding.add_custom_model(
                model=spec.id, pooling=PoolingType.MEAN, normalization=True, sources=ModelSource(hf=spec.repo),
                dim=spec.dim, model_file=spec.local_name(spec.model_file))
        self.spec = spec
        self.threads = threads
        self._lock = threading.Lock()
        # No CPU memory arena: it keeps the peak of the longest passage for ever (> 1 GB); without it ~500 MB.
        self._model = TextEmbedding(spec.id, specific_model_path=str(model_dir(spec, models_dir)), threads=threads,
                                    local_files_only=True, enable_cpu_mem_arena=False)

    def encode(self, texts: list[str], kind: Kind) -> list[list[float]]:
        prefix = self.spec.query_prefix if kind == "query" else self.spec.passage_prefix
        with self._lock:  # one ONNX session, fixed threads: calls are serialised
            vectors = list(self._model.embed([prefix + t for t in texts], batch_size=self.BATCH))
        return [_normalise([float(x) for x in v]) for v in vectors]


@dataclass(frozen=True)
class Settings:
    enabled: str  # "on" | "off" | "auto"
    model: str
    provider: str
    models_dir: str
    threads: int


def settings() -> Settings:
    raw = os.getenv("KB_EMBEDDINGS", "").strip().lower()
    enabled = "off" if raw in ("off", "0", "false", "no") else "on" if raw in ("on", "1", "true", "yes") else "auto"
    try:
        threads = max(1, int(os.getenv("KB_EMBEDDING_THREADS", "1")))
    except ValueError:
        threads = 1
    return Settings(enabled=enabled, model=os.getenv("KB_EMBEDDING_MODEL", "").strip() or spec_for(None).id,
                    provider=os.getenv("KB_EMBEDDING_PROVIDER", "local").strip().lower() or "local",
                    models_dir=os.getenv("KB_MODELS_DIR", "").strip() or "data/models", threads=threads)


_CACHE: dict[Settings, tuple[Encoder | None, dict[str, Any]]] = {}
_CACHE_LOCK = threading.Lock()


def _load(s: Settings) -> tuple[Encoder | None, dict[str, Any]]:
    try:
        spec = spec_for(s.model)
    except ValueError as exc:
        return None, {"model": s.model, "version": None, "sha256": None, "dim": None, "local": True,
                      "provider": s.provider, "status": "absent", "reason": str(exc)}
    info: dict[str, Any] = {"model": spec.id, "version": spec.version, "sha256": spec.sha256 or None, "dim": spec.dim,
                            "local": True, "provider": s.provider, "status": "absent", "reason": None}
    if s.enabled == "off":
        return None, {**info, "status": "off", "reason": "KB_EMBEDDINGS=off: lexical ranking only."}
    if s.provider != "local":
        return None, {**info, "status": "off",
                      "reason": f"provider '{s.provider}' is not available (v1: local only); lexical ranking."}
    if spec.id == TOY_BOW.id:
        return ToyBowEncoder(), {**info, "status": "ready"}
    try:
        encoder = FastEmbedEncoder(spec, s.models_dir, s.threads)
    except ImportError:
        return None, {**info, "reason": "the 'fastembed' package is not installed (poetry install)."}
    except FileNotFoundError as exc:
        return None, {**info, "reason": f"{exc}. Run 'kb models fetch'."}
    except Exception as exc:  # a broken model must never break the doctrine context: lexical fallback
        return None, {**info, "reason": f"the model could not be loaded: {exc}"}
    return encoder, {**info, "status": "ready", "threads": s.threads}


def reference_encoder() -> tuple[Encoder | None, dict[str, Any]]:
    """The reference encoder of the server (loaded once per settings) and its status for ``health``."""
    s = settings()
    with _CACHE_LOCK:
        if s not in _CACHE:
            _CACHE[s] = _load(s)
        return _CACHE[s]


def embedding_status() -> dict[str, Any]:
    """``{model, version, sha256, dim, local: true, provider, status: ready|absent|off, reason}`` (loads the model once)."""
    return dict(reference_encoder()[1])


def reset_cache() -> None:
    """Forget loaded encoders (tests, or after ``kb models fetch`` in the same process)."""
    with _CACHE_LOCK:
        _CACHE.clear()
