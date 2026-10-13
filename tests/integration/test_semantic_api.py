"""Local semantic search through the REST API (issue #94): health, doctrine context, server-side /similar, publication.

The toy encoder (``KB_EMBEDDING_MODEL=toy-bow``) stands in for the real model; additive fields only.
"""

import json

import pytest

from pipelines.similarity import semantic as semantic_mod
from pipelines.similarity.encoder import reset_cache
from tests.integration.test_promotion_health import (  # noqa: F401
    MAINT,
    _accepted_candidate,
    _as,
    env,
)
from tests.integration.test_similarity import CLIENT, encode

TOY = {"KB_EMBEDDINGS": "on", "KB_EMBEDDING_MODEL": "toy-bow"}


@pytest.fixture(autouse=True)
def _fresh():
    reset_cache()
    semantic_mod.reset()
    yield
    reset_cache()
    semantic_mod.reset()


def _toy(monkeypatch):
    for k, v in TOY.items():
        monkeypatch.setenv(k, v)


def test_health_exposes_the_local_embedding_model(env, monkeypatch):  # noqa: F811
    client = env["client"]
    off = client.get("/health").json()["embedding"]
    assert off["local"] is True and off["status"] == "off" and off["model"] == "intfloat/multilingual-e5-small"
    monkeypatch.setenv("KB_EMBEDDINGS", "on")
    monkeypatch.setenv("KB_MODELS_DIR", str(env["tmp"] / "no-models"))
    reset_cache()
    absent = client.get("/health").json()["embedding"]
    assert absent["status"] == "absent" and absent["local"] is True
    _toy(monkeypatch)
    ready = client.get("/health").json()["embedding"]
    assert ready == {**ready, "model": "toy-bow", "status": "ready", "local": True}


def test_context_route_is_hybrid_with_a_model_and_lexical_without(env, monkeypatch):  # noqa: F811
    client = env["client"]
    url = "/api/knowledge/context?subject=incident%20handling%20and%20remediation&frameworks=NIS2&max_items=40"
    first = client.get(url, headers=CLIENT)
    assert first.status_code == 200, first.text
    lexical = first.json()["data"]
    assert lexical["relevance_method"] == "lexical" and lexical["embedding"] is None
    _toy(monkeypatch)
    hybrid = client.get(url, headers=CLIENT).json()["data"]
    assert hybrid["relevance_method"] == "hybrid" and hybrid["embedding"]["model"] == "toy-bow"
    required = [i for i in hybrid["items"] if i["required"]]
    assert {i["id"] for i in required} == {i["id"] for i in lexical["items"] if i["required"]}  # all still included
    assert required[0]["id"] == "NIS2-ART21-2B" and required[0]["relevant"] is True
    for item in hybrid["items"]:
        assert {"relevance", "semantic_relevance", "combined_relevance", "relevance_method", "relevant"} <= set(item)
    assert client.get(url, headers=CLIENT).json()["data"] == hybrid  # reproducible


def test_similar_encodes_on_the_server_when_only_query_text_is_sent(env, monkeypatch):  # noqa: F811
    client = env["client"]
    body = {"query_text": "incident handling and remediation", "top_k": 5}
    off = client.post("/api/knowledge/similar", headers=CLIENT, json=body)
    assert off.status_code == 503 and "server-side encoding unavailable" in off.json()["reason"]
    _toy(monkeypatch)
    res = client.post("/api/knowledge/similar", headers=CLIENT, json=body)
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["encoded_by"] == "server" and data["model"] == "toy-bow" and len(data["results"]) == 5
    assert data["results"][0]["ref"] == "NIS2-ART21-2B"
    assert all(r["requires_confirmation"] is True and "cosine" in r["scores"] for r in data["results"])
    mismatch = client.post("/api/knowledge/similar", headers=CLIENT, json={**body, "model": "other-model"})
    assert mismatch.status_code == 409 and mismatch.json()["error"] == "model-mismatch"
    assert client.post("/api/knowledge/similar", headers=CLIENT, json={**body, "model": "toy-bow"}).status_code == 200


def test_client_vectors_keep_working_as_before(env, monkeypatch):  # noqa: F811
    """A vector computed by the client is compared with the stored vectors of its own model (contract 1.9)."""
    client = env["client"]
    _toy(monkeypatch)
    pending = client.get("/api/knowledge/embeddings/pending?model=client-bow", headers=CLIENT).json()["data"]["pending"]
    items = [{"ref": p["ref"], "text_sha256": p["text_sha256"], "vector": encode(p["text"])} for p in pending]
    put = client.put("/api/knowledge/embeddings", headers=CLIENT,
                     json={"model": "client-bow", "model_version": "1", "items": items})
    assert put.status_code == 200, put.text
    res = client.post("/api/knowledge/similar", headers=CLIENT,
                      json={"model": "client-bow", "vector": encode("incident handling"), "top_k": 3})
    assert res.status_code == 200 and res.json()["data"]["encoded_by"] == "client"
    assert "cosine" not in res.json()["data"]["results"][0]["scores"]


def test_publication_indexes_the_assets_and_seals_the_model(env, monkeypatch):  # noqa: F811
    client = env["client"]
    _toy(monkeypatch)
    cid = _accepted_candidate(client)
    client.post(f"/api/knowledge/candidates/{cid}/promote", headers=_as(MAINT))
    res = client.post("/api/knowledge/publications", headers=_as(MAINT))
    assert res.status_code == 200, res.text
    index = res.json()["data"]["embedding_index"]
    assert index["status"] == "indexed" and index["model"] == "toy-bow" and index["encoded"] == index["assets"] > 50
    from pipelines.similarity.store import EmbeddingStore

    assert "PAT-099" in EmbeddingStore().hashes("toy-bow")
    snap = json.loads((env["tmp"] / "data" / "snapshots" / "latest.json").read_text(encoding="utf-8"))
    assert snap["embedding_model"]["id"] == "toy-bow" and snap["embedding_model"]["local"] is True
    refs = {i["ref"] for i in snap["embedding_index"]["items"]}
    assert "PAT-099" in refs and snap["embedding_index"]["count"] == index["assets"]
    assert snap["embedding_index"]["content_sha256"] == index["content_sha256"]
