"""Index of the knowledge base in the reference model's space (issue #94, lot E2).

* ``build_index`` is run by every publication (``kb publish``, ``POST /api/knowledge/publications``) and by
  ``kb embeddings index``: it encodes the active assets whose text changed (same ``text_sha256``: not re-encoded),
  writes them to the ``embeddings`` table and removes the vectors of retired or replaced assets.
* ``snapshot_section`` is what the sealed snapshot declares (D7/D8): the reference model ``{id, version, sha256}`` and
  the fingerprint of the index — the exact text every vector stands for. It depends only on ``data/kb`` and on the pinned
  model, never on the machine (whether the model files are present or not), so ``rebuiltByEmitterTest`` covers it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pipelines import canonical
from pipelines.similarity.encoder import Encoder, settings
from pipelines.similarity.models import ModelSpec, spec_for
from pipelines.similarity.store import MAX_BATCH, EmbeddingStore
from pipelines.similarity.text import embeddable_assets


def index_items(kb_dir: str | Path) -> list[dict[str, str]]:
    """``[{ref, type, text_sha256}]`` of the active assets, in a stable order."""
    return [{"ref": i["ref"], "type": i["type"], "text_sha256": i["text_sha256"]} for i in embeddable_assets(kb_dir)]


def index_fingerprint(spec: ModelSpec, items: list[dict[str, str]]) -> str:
    return canonical.sha256({"model": spec.id, "version": spec.version, "sha256": spec.sha256 or None,
                             "items": [[i["ref"], i["text_sha256"]] for i in items]})


def snapshot_section(kb_dir: str | Path) -> dict[str, Any]:
    """``embedding_model`` and ``embedding_index`` of the sealed snapshot (outside ``payload_sha256``, additive)."""
    spec = spec_for(settings().model)
    items = index_items(kb_dir)
    return {
        "embedding_model": {"id": spec.id, "version": spec.version, "sha256": spec.sha256 or None, "dim": spec.dim,
                            "local": True, "query_prefix": spec.query_prefix, "passage_prefix": spec.passage_prefix},
        "embedding_index": {"model": spec.id, "count": len(items), "items": items,
                            "content_sha256": index_fingerprint(spec, items)},
    }


def build_index(store: EmbeddingStore, kb_dir: str | Path, encoder: Encoder, created_by: str = "publication") -> dict[str, Any]:
    """Bring the reference model's vectors in line with the active assets; returns what was done."""
    spec = encoder.spec
    items = embeddable_assets(kb_dir)
    space = store.model_space(spec.id)
    if space and (space[1] != spec.version or space[0] != spec.dim):
        store.delete_model(spec.id)  # another version of the model: vectors of two versions are never mixed
    stored = store.hashes(spec.id)
    current = {i["ref"]: i for i in items}
    removed = store.delete_refs(spec.id, sorted(set(stored) - set(current)))
    todo = [i for i in items if stored.get(i["ref"]) != i["text_sha256"]]
    for start in range(0, len(todo), MAX_BATCH):
        batch = todo[start:start + MAX_BATCH]
        vectors = encoder.encode([i["text"] for i in batch], "passage")
        store.put([{"ref": i["ref"], "text_sha256": i["text_sha256"], "vector": v, "language": i.get("language")}
                   for i, v in zip(batch, vectors, strict=True)], spec.id, spec.version, created_by, current)
    index = [{"ref": i["ref"], "type": i["type"], "text_sha256": i["text_sha256"]} for i in items]
    return {"model": spec.id, "model_version": spec.version, "model_sha256": spec.sha256 or None, "dim": spec.dim,
            "assets": len(items), "encoded": len(todo), "unchanged": len(items) - len(todo), "removed": removed,
            "content_sha256": index_fingerprint(spec, index)}


def index_after_publication(kb_dir: str | Path) -> dict[str, Any]:
    """Index run at the end of a publication. Never fails the publication: an absent model or governance database is
    reported (``status: skipped``) and the doctrine context keeps its lexical ranking until the next index."""
    from pipelines.governance.store import database_url
    from pipelines.similarity.encoder import reference_encoder

    encoder, status = reference_encoder()
    if encoder is None:
        return {"status": "skipped", "model": status["model"], "reason": f"model {status['status']}: {status.get('reason')}"}
    if not database_url():
        return {"status": "skipped", "model": status["model"], "reason": "no governance database (GOVERNANCE_DATABASE_URL)."}
    try:
        return {"status": "indexed", **build_index(EmbeddingStore(), kb_dir, encoder)}
    except Exception as exc:  # the snapshot is sealed already; the index is rebuilt by 'kb embeddings index'
        return {"status": "failed", "model": status["model"], "reason": str(exc)}
