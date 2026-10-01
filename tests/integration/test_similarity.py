"""Semantic similarity (contract 1.9): vectors computed by the client, stale/foreign vectors refused, hybrid ranking.

LLMOps holds no model: the tests use a toy deterministic encoder (hashed bag of words) as the "client".
"""

import hashlib
import math
import re
import shutil
from pathlib import Path

import pytest
import yaml
from starlette.testclient import TestClient

from mcp_server.core.config import server_config

ROOT = Path(__file__).parent.parent.parent
CLIENT = {"Authorization": "Bearer archinex-token"}
MAINT, ALICE = "maint@example.org", "alice@example.org"
DIM = 128
MODEL = {"model": "toy-bow", "model_version": "1"}


def encode(text: str) -> list[float]:
    vec = [0.0] * DIM
    for w in re.findall(r"[a-zà-ÿ0-9]+", text.lower()):
        if len(w) > 2:
            vec[int(hashlib.sha256(w.encode()).hexdigest(), 16) % DIM] += 1.0
    n = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / n for x in vec]


def _as(email: str) -> dict:
    return {**CLIENT, "X-Actor-Email": email}


@pytest.fixture
def env(tmp_path, monkeypatch):
    kb = tmp_path / "kb"
    shutil.copytree(ROOT / "data" / "kb", kb)
    owners = yaml.safe_load((kb / "owners.yaml").read_text())
    owners["owners"]["@core-owner-architecture"]["email"] = ALICE
    owners["owners"]["@maintainers"] = {"email": MAINT, "roles": ["kb:maintain"]}
    (kb / "owners.yaml").write_text(yaml.safe_dump(owners), encoding="utf-8")
    monkeypatch.setattr(server_config, "kb_dir", kb)
    monkeypatch.setenv("SERVER_TOKEN", "demo-token")
    monkeypatch.setenv("ENGAGEMENT_TOKENS", "archinex-token:kb:review,kb:delegate")
    monkeypatch.setenv("CANDIDATES_BACKEND", "sql")
    monkeypatch.setenv("GOVERNANCE_DATABASE_URL", f"sqlite:///{tmp_path / 'gov.db'}")
    from pipelines.governance.migrate import migrate_governance
    from pipelines.governance.store import dispose_engines

    dispose_engines()
    migrate_governance(kb, tmp_path / "none", eval_dataset=None)
    from mcp_server.main import create_starlette_app

    yield {"client": TestClient(create_starlette_app()), "kb": kb}
    dispose_engines()


def _pending(client, model="toy-bow"):
    res = client.get(f"/api/knowledge/embeddings/pending?model={model}", headers=CLIENT)
    assert res.status_code == 200, res.text
    return res.json()["data"]


def _deposit(client, items=None, headers=CLIENT, **model):
    items = items if items is not None else [
        {"ref": p["ref"], "text_sha256": p["text_sha256"], "vector": encode(p["text"]), "language": "en"}
        for p in _pending(client)["pending"]]
    return client.put("/api/knowledge/embeddings", headers=headers, json={**MODEL, **model, "items": items})


def test_pending_lists_the_text_to_encode(env):
    assert env["client"].get("/api/knowledge/embeddings/pending?model=toy-bow",
                             headers={"Authorization": "Bearer demo-token"}).status_code == 403
    assert env["client"].get("/api/knowledge/embeddings/pending", headers=CLIENT).status_code == 400
    data = _pending(env["client"])
    refs = {p["ref"]: p for p in data["pending"]}
    assert len(refs) > 80 and {p["reason"] for p in refs.values()} == {"missing"}
    assert {p["type"] for p in refs.values()} == {"principle", "pattern", "decision", "control"}
    p002 = refs["P-002"]
    assert p002["text"].startswith(p002["title"]) and len(p002["text_sha256"]) == 64
    assert data["pending"] == _pending(env["client"])["pending"]  # stable order and content


def test_deposit_then_nothing_pending_and_stale_detection(env):
    client = env["client"]
    res = _deposit(client)
    assert res.status_code == 200 and res.json()["data"]["dim"] == DIM
    assert _pending(client)["pending"] == []
    # An asset changes: its vector becomes stale and is listed again.
    path = env["kb"] / "principles" / "P-002.md"
    path.write_text(path.read_text().replace("## Statement", "## Statement\nA changed sentence about approvals.", 1))
    pending = _pending(client)["pending"]
    assert [(p["ref"], p["reason"]) for p in pending] == [("P-002", "stale")]


def test_refused_deposits(env):
    client = env["client"]
    good = _pending(client)["pending"][0]
    item = {"ref": good["ref"], "text_sha256": good["text_sha256"], "vector": encode(good["text"])}
    assert _deposit(client, [{**item, "text_sha256": "0" * 64}]).status_code == 400  # not this text
    assert _deposit(client, [{**item, "ref": "P-999"}]).status_code == 400  # unknown asset
    assert _deposit(client, [{**item, "vector": []}]).status_code == 400
    assert _deposit(client, [{**item, "vector": [0.0] * DIM}]).status_code == 400  # null vector
    assert _deposit(client, [{**item, "vector": ["x"] * DIM}]).status_code == 400
    assert _deposit(client, [item], model="").status_code == 400
    assert _deposit(client, [item], model_version="").status_code == 400
    assert _deposit(client, [item], headers=_as(ALICE)).status_code == 403  # an expert without kb:maintain
    assert _deposit(client, [item], headers=_as(MAINT)).status_code == 200  # a maintainer
    assert _deposit(client, [{**item, "vector": [1.0] * (DIM - 1)}]).status_code == 400  # other dimension
    assert _deposit(client, [item], model_version="2").status_code == 400  # two versions are never mixed


def _similar(client, **body):
    return client.post("/api/knowledge/similar", headers=CLIENT, json={"model": "toy-bow", "top_k": 5, **body})


def test_similar_ranks_deterministically_and_never_decides(env):
    client = env["client"]
    assert _similar(client, vector=encode("x")).status_code == 400  # no vector stored yet for the model
    _deposit(client)
    pending_all = {p["ref"]: p for p in client.get("/api/knowledge/embeddings/pending?model=other", headers=CLIENT).json()["data"]["pending"]}
    query = pending_all["P-002"]["text"]
    res = _similar(client, vector=encode(query))
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    top = data["results"][0]
    assert top["ref"] == "P-002" and top["zone"] == "strong" and top["score"] > 0.99
    assert all(r["requires_confirmation"] is True for r in data["results"])  # whatever the score (decision D8)
    assert {"status", "validated_by", "last_reviewed", "assumptions", "assumptions_documented"} <= set(top)
    assert data["config"]["status"] == "uncalibrated"
    assert _similar(client, vector=encode(query)).json()["data"] == data  # deterministic
    only_patterns = _similar(client, vector=encode(query), types=["pattern"]).json()["data"]["results"]
    assert only_patterns and {r["type"] for r in only_patterns} == {"pattern"}


def test_similar_validation_and_lexical_blend(env):
    client = env["client"]
    _deposit(client)
    assert _similar(client, vector=[1.0] * 5).status_code == 400  # wrong dimension
    assert _similar(client, vector="nope").status_code == 400
    assert client.post("/api/knowledge/similar", headers=CLIENT, json={"model": "ghost", "vector": encode("x")}).status_code == 400
    assert client.post("/api/knowledge/similar", headers={"Authorization": "Bearer demo-token"},
                       json={"model": "toy-bow", "vector": encode("x")}).status_code == 403
    q = "closed loop remediation with human approval before execution"
    plain = _similar(client, vector=encode(q)).json()["data"]["results"]
    mixed = _similar(client, vector=encode(q), query_text=q).json()["data"]["results"]
    assert "lexical" not in plain[0]["scores"] and "lexical" in mixed[0]["scores"]
    with_domain = _similar(client, vector=encode(q), domains=["network-automation"]).json()["data"]["results"]
    assert "domain" in with_domain[0]["scores"]


def test_superseded_asset_is_never_presented_as_valid(env):
    client = env["client"]
    text = next(p["text"] for p in _pending(client, "m2")["pending"] if p["ref"] == "P-002")
    _deposit(client)
    path = env["kb"] / "principles" / "P-002.md"
    path.write_text(path.read_text().replace("status: active", "status: superseded", 1))
    res = client.post("/api/knowledge/similar", headers=CLIENT, json={"model": "toy-bow", "vector": encode(text), "top_k": 50})
    zones = {r["ref"]: r["zone"] for r in res.json()["data"]["results"]}
    assert zones["P-002"] == "superseded"


def test_health_reports_embeddings(env):
    client = env["client"]
    _deposit(client)
    emb = client.get("/api/knowledge/health", headers=CLIENT).json()["data"]["embeddings"]
    assert emb[0]["model_id"] == "toy-bow" and emb[0]["missing"] == 0 and emb[0]["stale"] == 0
    assert emb[0]["vectors"] == emb[0]["active_assets"]
