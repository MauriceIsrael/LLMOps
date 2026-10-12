"""Unit tests — local semantic search (issue #94): encoder, model files, index, hybrid doctrine context.

No real model here: the toy encoder (hashed bag of words) or hand-written semantic scores stand in for it. The
evaluation with the real model is tests/eval/test_semantic_fr_en.py (opt-in).
"""

import hashlib
import io
import math
import shutil
import socket
from pathlib import Path

import pytest

from pipelines.doctrine.context import MIN_SEMANTIC, build_doctrine_context, combine, rank
from pipelines.similarity import encoder as encoder_mod
from pipelines.similarity import models as models_mod
from pipelines.similarity import semantic as semantic_mod
from pipelines.similarity.encoder import (
    ToyBowEncoder,
    embedding_status,
    reference_encoder,
    reset_cache,
)
from pipelines.similarity.index import build_index, index_after_publication, snapshot_section
from pipelines.similarity.models import E5_SMALL, ModelSpec, fetch, verify
from pipelines.similarity.semantic import calibrate, cosine_unit
from tests.unit.test_check_option import index  # noqa: F401  (pytest fixture: synthetic doctrine)

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _fresh(monkeypatch):
    for var in ("KB_EMBEDDINGS", "KB_EMBEDDING_MODEL", "KB_EMBEDDING_PROVIDER", "KB_MODELS_DIR", "KB_HYBRID_WEIGHT"):
        monkeypatch.delenv(var, raising=False)
    reset_cache()
    semantic_mod.reset()
    yield
    reset_cache()
    semantic_mod.reset()


# ---------------------------------------------------------------------------
# Encoder and settings
# ---------------------------------------------------------------------------

def test_toy_encoder_is_normalised_and_deterministic():
    enc = ToyBowEncoder()
    a, b = enc.encode(["closed loop remediation", "closed loop remediation"], "passage")
    assert a == b and len(a) == 128
    assert math.isclose(sum(x * x for x in a), 1.0, rel_tol=1e-9)


def test_absent_model_means_lexical_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv("KB_MODELS_DIR", str(tmp_path / "empty"))
    enc, status = reference_encoder()
    assert enc is None
    assert status["status"] == "absent" and status["local"] is True
    assert status["model"] == E5_SMALL.id and status["sha256"] == E5_SMALL.sha256
    assert "kb models fetch" in status["reason"] or "fastembed" in status["reason"]


def test_embeddings_off_and_external_provider_disable_the_model(monkeypatch):
    monkeypatch.setenv("KB_EMBEDDING_MODEL", "toy-bow")
    monkeypatch.setenv("KB_EMBEDDINGS", "off")
    assert embedding_status()["status"] == "off"
    monkeypatch.setenv("KB_EMBEDDINGS", "on")
    monkeypatch.setenv("KB_EMBEDDING_PROVIDER", "openai")
    status = embedding_status()
    assert status["status"] == "off" and status["local"] is True and "local only" in status["reason"]
    monkeypatch.setenv("KB_EMBEDDING_PROVIDER", "local")
    assert embedding_status()["status"] == "ready"


def test_unknown_model_is_reported_not_raised(monkeypatch):
    monkeypatch.setenv("KB_EMBEDDING_MODEL", "nope/unknown")
    status = embedding_status()
    assert status["status"] == "absent" and "unknown embedding model" in status["reason"]


# ---------------------------------------------------------------------------
# Model files: pinned SHA-256, offline after the fetch
# ---------------------------------------------------------------------------

def _fake_spec(content: bytes) -> ModelSpec:
    return ModelSpec(id="acme/tiny", version="abc123", repo="acme/tiny",
                     files={"onnx/model.onnx": hashlib.sha256(content).hexdigest()}, model_file="onnx/model.onnx", dim=4)


def test_fetch_checks_the_pinned_hash_and_skips_intact_files(tmp_path, monkeypatch):
    content = b"onnx-bytes"
    spec = _fake_spec(content)
    calls = []

    def fake_urlopen(url, timeout=0):
        calls.append(url)
        return io.BytesIO(content)

    monkeypatch.setattr(models_mod.urllib.request, "urlopen", fake_urlopen)
    assert verify(spec, tmp_path) and "missing" in verify(spec, tmp_path)[0]
    path = fetch(spec, tmp_path, quiet=True)
    assert (path / "model.onnx").read_bytes() == content and verify(spec, tmp_path) == []
    assert calls == ["https://huggingface.co/acme/tiny/resolve/abc123/onnx/model.onnx"]
    fetch(spec, tmp_path, quiet=True)
    assert len(calls) == 1  # intact: not downloaded again


def test_fetch_refuses_a_file_that_does_not_match(tmp_path, monkeypatch):
    spec = _fake_spec(b"expected")
    monkeypatch.setattr(models_mod.urllib.request, "urlopen", lambda url, timeout=0: io.BytesIO(b"tampered"))
    with pytest.raises(RuntimeError, match="does not match"):
        fetch(spec, tmp_path, quiet=True)
    assert not any((tmp_path / spec.dirname).iterdir())  # nothing half-installed


def test_a_corrupt_model_is_never_loaded(tmp_path, monkeypatch):
    target = tmp_path / E5_SMALL.dirname
    target.mkdir(parents=True)
    for remote in E5_SMALL.files:
        (target / E5_SMALL.local_name(remote)).write_bytes(b"corrupt")
    monkeypatch.setenv("KB_MODELS_DIR", str(tmp_path))
    enc, status = reference_encoder()
    assert enc is None and status["status"] == "absent"


# ---------------------------------------------------------------------------
# Scores: rounded, calibrated, reproducible
# ---------------------------------------------------------------------------

def test_cosine_is_rounded_and_calibration_is_bounded():
    assert cosine_unit([0.6, 0.8], [0.8, 0.6]) == 0.96
    assert calibrate(0.5, E5_SMALL) == 0.0 and calibrate(0.99, E5_SMALL) == 1.0
    assert calibrate(E5_SMALL.floor + (E5_SMALL.ceil - E5_SMALL.floor) / 2, E5_SMALL) == 0.5


def test_combine_takes_the_maximum_or_a_weighted_mean():
    assert combine(0.3, None) == 0.3
    assert combine(0.0, 0.9) == 0.9 and combine(0.7, 0.2) == 0.7
    assert combine(0.4, 0.8, weight=0.5) == 0.6


# ---------------------------------------------------------------------------
# Hybrid doctrine context (D9: it orders, it never decides)
# ---------------------------------------------------------------------------

def test_without_semantic_scores_the_package_is_the_lexical_one(index):  # noqa: F811
    ctx = build_doctrine_context(index, "closed loop remediation", frameworks=["FW1"])
    assert ctx["relevance_method"] == "lexical" and ctx["embedding"] is None
    for item in ctx["items"]:
        assert item["relevance_method"] == "lexical" and item["semantic_relevance"] is None
        assert item["combined_relevance"] == round(next(
            s.relevance for s in rank(index, "closed loop remediation", frameworks=["FW1"]) if s.entry.id == item["id"]), 4)
    # Same order as before the change: type priority, relevance, identifier.
    assert [i["id"] for i in ctx["items"]] == ["P-100", "FW1-01", "FW1-02", "PAT-100", "FW2-01"]
    assert {i["id"]: i["relevant"] for i in ctx["items"]}["FW1-02"] is False


def test_required_controls_are_all_kept_and_sorted_by_semantic_relevance(index):  # noqa: F811
    semantic = {"FW1-02": 0.9, "FW1-01": 0.1, "P-100": 0.2, "P-101": 0.3}
    ctx = build_doctrine_context(index, "chiffrement des données", frameworks=["FW1"], semantic=semantic,
                                 embedding={"model": "m", "version": "1"})
    required = [i for i in ctx["items"] if i["required"]]
    assert [i["id"] for i in required] == ["FW1-02", "FW1-01"]
    assert required[0]["relevant"] is True and required[0]["relevance_method"] == "semantic"
    assert required[1]["relevant"] is False
    assert required[0]["semantic_relevance"] == 0.9 and required[0]["relevance"] == 0.0
    assert ctx["relevance_method"] == "hybrid" and ctx["embedding"] == {"model": "m", "version": "1"}
    # A non-required asset below the semantic threshold stays out.
    assert "P-101" not in {i["id"] for i in ctx["items"]}


def test_semantic_relevance_brings_in_doctrine_the_words_miss(index):  # noqa: F811
    lexical = {i["id"] for i in build_doctrine_context(index, "validation par une personne")["items"]}
    assert "P-100" not in lexical
    ctx = build_doctrine_context(index, "validation par une personne", semantic={"P-100": MIN_SEMANTIC})
    assert [i["id"] for i in ctx["items"]] == ["P-100"] and ctx["items"][0]["relevant"] is True


def test_hybrid_items_keep_their_lexical_relevance(index):  # noqa: F811
    ctx = build_doctrine_context(index, "closed loop remediation", semantic={"P-100": 0.1, "PAT-100": 0.95})
    by_id = {i["id"]: i for i in ctx["items"]}
    assert by_id["P-100"]["relevance_method"] == "hybrid" and by_id["P-100"]["relevance"] > 0
    assert by_id["PAT-100"]["combined_relevance"] == 0.95


def test_ties_are_broken_by_identifier(index):  # noqa: F811
    semantic = {"FW1-01": 0.7, "FW1-02": 0.7}
    ids = [s.entry.id for s in rank(index, "zzz", frameworks=["FW1"], semantic=semantic)]
    assert ids == ["FW1-01", "FW1-02"]


# ---------------------------------------------------------------------------
# Index at publication (toy encoder, SQLite governance database)
# ---------------------------------------------------------------------------

@pytest.fixture
def gov(tmp_path, monkeypatch):
    kb = tmp_path / "kb"
    shutil.copytree(ROOT / "data" / "kb", kb)
    monkeypatch.setenv("GOVERNANCE_DATABASE_URL", f"sqlite:///{tmp_path / 'gov.db'}")
    from pipelines.governance.store import dispose_engines
    from pipelines.similarity.store import EmbeddingStore

    dispose_engines()
    yield kb, EmbeddingStore()
    dispose_engines()


def _retire(path: Path) -> None:
    path.write_text(path.read_text(encoding="utf-8").replace("status: active", "status: superseded", 1), encoding="utf-8")


def test_build_index_encodes_only_what_changed_and_drops_retired_assets(gov):
    kb, store = gov
    enc = ToyBowEncoder()
    first = build_index(store, kb, enc)
    assert first["encoded"] == first["assets"] > 50 and first["removed"] == 0
    assert store.model_space("toy-bow") == (128, "1")
    again = build_index(store, kb, enc)
    assert again["encoded"] == 0 and again["unchanged"] == first["assets"]
    assert again["content_sha256"] == first["content_sha256"]

    p = kb / "principles" / "P-002-human-in-the-loop.md"
    if not p.exists():
        p = next((kb / "principles").glob("P-002*.md"))
    p.write_text(p.read_text(encoding="utf-8").replace("Detection is automatic", "Detection is always automatic"),
                 encoding="utf-8")
    _retire(next((kb / "principles").glob("P-003*.md")))
    third = build_index(store, kb, enc)
    assert third["encoded"] == 1 and third["removed"] == 1 and third["assets"] == first["assets"] - 1
    assert "P-003" not in store.hashes("toy-bow")
    assert third["content_sha256"] != first["content_sha256"]


def test_index_after_publication_reports_instead_of_failing(gov, monkeypatch):
    kb, _ = gov
    monkeypatch.setenv("KB_EMBEDDINGS", "off")
    assert index_after_publication(kb)["status"] == "skipped"
    monkeypatch.setenv("KB_EMBEDDINGS", "on")
    monkeypatch.setenv("KB_EMBEDDING_MODEL", "toy-bow")
    res = index_after_publication(kb)
    assert res["status"] == "indexed" and res["model"] == "toy-bow" and res["encoded"] > 0
    monkeypatch.delenv("GOVERNANCE_DATABASE_URL")
    monkeypatch.delenv("CANDIDATES_BACKEND", raising=False)
    assert index_after_publication(kb)["status"] == "skipped"


def test_snapshot_section_depends_on_the_base_and_the_pinned_model_only(monkeypatch):
    kb = ROOT / "data" / "kb"
    monkeypatch.setenv("KB_EMBEDDINGS", "off")
    off = snapshot_section(kb)
    monkeypatch.setenv("KB_EMBEDDINGS", "on")
    monkeypatch.setenv("KB_MODELS_DIR", "/nonexistent")
    assert snapshot_section(kb) == off
    assert off["embedding_model"]["id"] == E5_SMALL.id and off["embedding_model"]["sha256"] == E5_SMALL.sha256
    assert off["embedding_model"]["local"] is True
    assert off["embedding_index"]["count"] == len(off["embedding_index"]["items"]) > 50
    assert off["embedding_index"]["content_sha256"].startswith("sha256:")


def test_asset_vectors_use_stored_vectors_and_encode_the_rest_in_memory(gov, monkeypatch):
    kb, store = gov
    enc = ToyBowEncoder()
    build_index(store, kb, enc)
    calls = []
    real = enc.encode

    def counting(texts, kind):
        calls.append((kind, len(texts)))
        return real(texts, kind)

    monkeypatch.setattr(enc, "encode", counting)
    scorer = semantic_mod.AssetVectors(enc)
    scores = scorer.scores(kb, "closed loop remediation")
    assert calls == [("query", 1)]  # every asset vector came from the table
    assert all(0.0 <= s["semantic"] <= 1.0 for s in scores.values())
    assert scorer.scores(kb, "closed loop remediation") == scores and calls == [("query", 1)]  # cached query


# ---------------------------------------------------------------------------
# Server side: fallback, reproducibility, no network
# ---------------------------------------------------------------------------

def _guard_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("outgoing network call during a query")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


def test_doctrine_context_falls_back_to_lexical_when_the_model_is_absent(monkeypatch, tmp_path):
    from mcp_server.knowledge.tools import get_doctrine_context

    monkeypatch.setenv("KB_EMBEDDINGS", "on")
    monkeypatch.setenv("KB_MODELS_DIR", str(tmp_path))
    _guard_network(monkeypatch)
    res = get_doctrine_context("closed loop remediation", frameworks=["NIS2"])
    assert res["status"] == "ok" and res["data"]["relevance_method"] == "lexical"
    assert {i["relevance_method"] for i in res["data"]["items"]} == {"lexical"}
    monkeypatch.setenv("KB_EMBEDDINGS", "off")
    assert get_doctrine_context("closed loop remediation", frameworks=["NIS2"]) == res


def test_doctrine_context_is_reproducible_and_offline_with_a_model(monkeypatch):
    from mcp_server.knowledge.tools import get_doctrine_context

    monkeypatch.setenv("KB_EMBEDDINGS", "on")
    monkeypatch.setenv("KB_EMBEDDING_MODEL", "toy-bow")
    monkeypatch.delenv("GOVERNANCE_DATABASE_URL", raising=False)
    monkeypatch.delenv("CANDIDATES_BACKEND", raising=False)
    _guard_network(monkeypatch)
    first = get_doctrine_context("incident handling and remediation", frameworks=["NIS2"])
    reset_cache()
    semantic_mod.reset()
    second = get_doctrine_context("incident handling and remediation", frameworks=["NIS2"])
    assert first == second and first["data"]["relevance_method"] == "hybrid"
    assert first["data"]["embedding"]["model"] == "toy-bow" and first["data"]["embedding"]["local"] is True
    required = [i for i in first["data"]["items"] if i["required"]]
    assert len(required) >= 10 and required[0]["id"] == "NIS2-ART21-2B" and required[0]["relevant"] is True
    assert all(isinstance(i["semantic_relevance"], float) for i in first["data"]["items"])


def test_settings_are_read_from_the_environment(monkeypatch):
    monkeypatch.setenv("KB_EMBEDDING_THREADS", "x")
    assert encoder_mod.settings().threads == 1
    monkeypatch.setenv("KB_EMBEDDING_THREADS", "4")
    monkeypatch.setenv("KB_EMBEDDINGS", "no")
    s = encoder_mod.settings()
    assert s.threads == 4 and s.enabled == "off" and s.model == E5_SMALL.id
