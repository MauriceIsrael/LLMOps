"""Similarity evaluation (L13): the annotated FR/EN dataset, annotation by an evaluator, runs with client vectors."""

import json
import shutil
from pathlib import Path

import pytest
import yaml
from starlette.testclient import TestClient

from mcp_server.core.config import server_config
from pipelines.kb_candidates.kb import load_assets
from tests.integration.test_similarity import CLIENT, MODEL, encode

ROOT = Path(__file__).parent.parent.parent
DATASET_FILE = ROOT / "tests" / "evals" / "datasets" / "similarity_v1.jsonl"
EVA, ALICE = "eva@example.org", "alice@example.org"
BASE = "/api/knowledge/similarity-evals/similarity_v1"


def _as(email: str) -> dict:
    return {**CLIENT, "X-Actor-Email": email}


def _cases_file():
    return [json.loads(line) for line in DATASET_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_the_seed_dataset_is_consistent_with_the_knowledge_base():
    cases = _cases_file()
    known = {a.id: a for a in load_assets(ROOT / "data" / "kb")}
    assert len(cases) >= 16 and len({c["id"] for c in cases}) == len(cases)
    assert {c["family"] for c in cases} == {"cross_lingual", "same_words_different_subject",
                                            "same_topic_different_assumptions", "out_of_base"}
    assert {c["language"] for c in cases} == {"fr", "en"}
    relations = {"same_subject", "related_not_same", "same_topic_different_assumptions", "unrelated"}
    for c in cases:
        assert c["annotation_status"] == "proposed" and c["annotated_by"] == "coding-agent"  # never validated by the agent
        for e in c["expected"]:
            assert e["ref"] in known and known[e["ref"]].frontmatter.get("status") == "active" and e["relation"] in relations
        if c["family"] == "out_of_base":
            assert c["expected"] == []
        if c["family"] == "cross_lingual":
            assert any(e["relation"] == "same_subject" for e in c["expected"])
    fr = [c for c in cases if c["language"] == "fr" and c["family"] == "cross_lingual"]
    assert len(fr) >= 4  # the French -> English direction is covered


@pytest.fixture
def env(tmp_path, monkeypatch):
    kb = tmp_path / "kb"
    shutil.copytree(ROOT / "data" / "kb", kb)
    owners = yaml.safe_load((kb / "owners.yaml").read_text())
    owners["owners"]["@core-owner-architecture"]["email"] = ALICE
    owners["owners"]["@ciso-office"]["email"] = EVA
    owners["owners"]["@ciso-office"]["roles"] = ["kb:evaluate"]
    (kb / "owners.yaml").write_text(yaml.safe_dump(owners), encoding="utf-8")
    monkeypatch.setattr(server_config, "kb_dir", kb)
    monkeypatch.setenv("SERVER_TOKEN", "demo-token")
    monkeypatch.setenv("ENGAGEMENT_TOKENS", "archinex-token:kb:review,kb:delegate")
    monkeypatch.setenv("CANDIDATES_BACKEND", "sql")
    monkeypatch.setenv("GOVERNANCE_DATABASE_URL", f"sqlite:///{tmp_path / 'gov.db'}")
    from pipelines.governance.migrate import migrate_governance
    from pipelines.governance.store import dispose_engines

    dispose_engines()
    result = migrate_governance(kb, tmp_path / "none", eval_dataset=None)
    assert result["similarity_cases"]["imported"] == len(_cases_file())
    from mcp_server.main import create_starlette_app

    client = TestClient(create_starlette_app())
    pending = client.get("/api/knowledge/embeddings/pending?model=toy-bow", headers=CLIENT).json()["data"]["pending"]
    texts = {p["ref"]: p["text"] for p in pending}
    client.put("/api/knowledge/embeddings", headers=CLIENT, json={**MODEL, "items": [
        {"ref": p["ref"], "text_sha256": p["text_sha256"], "vector": encode(p["text"])} for p in pending]})
    yield {"client": client, "texts": texts}
    dispose_engines()


def _oracle_vectors(texts, cases, wrong=()):
    """The mean vector of the same-subject assets (a perfect encoder), except for ``wrong`` cases."""
    vectors = {}
    for c in cases:
        same = [e["ref"] for e in c["expected"] if e["relation"] == "same_subject"]
        if same:
            vecs = [encode(texts[r]) for r in same]
            vectors[c["id"]] = [sum(col) / len(vecs) for col in zip(*vecs, strict=True)]
        else:
            vectors[c["id"]] = encode(c["query_text"])
    for case_id, ref in wrong:
        vectors[case_id] = encode(texts[ref])
    return vectors


def _run(env, vectors, headers=None, **extra):
    return env["client"].post(f"{BASE}/runs", headers=headers or _as(EVA), json={"model": "toy-bow", "vectors": vectors, **extra})


def test_dataset_is_readable_and_annotation_needs_an_evaluator(env):
    client = env["client"]
    ds = client.get(BASE, headers=CLIENT).json()["data"]
    assert len(ds["cases"]) == len(_cases_file()) and ds["validated"] == 0
    assert all("query_text" in c and "language" in c for c in ds["cases"])
    url = f"{BASE}/cases/SIM-001"
    assert client.patch(url, headers=CLIENT, json={"annotation_status": "validated"}).status_code == 403
    assert client.patch(url, headers=_as(ALICE), json={"annotation_status": "validated"}).status_code == 403
    assert client.patch(url, headers=_as(EVA), json={}).status_code == 400
    assert client.patch(url, headers=_as(EVA), json={"expected": [{"ref": "NOPE-1", "relation": "same_subject"}]}).status_code == 400
    assert client.patch(url, headers=_as(EVA), json={"expected": [{"ref": "P-002", "relation": "maybe"}]}).status_code == 400
    ok = client.patch(url, headers=_as(EVA), json={"annotation_status": "validated"})
    assert ok.status_code == 200 and ok.json()["data"]["annotated_by"] == "@ciso-office"
    assert client.patch(f"{BASE}/cases/NOPE", headers=_as(EVA), json={"annotation_status": "validated"}).status_code == 404


def test_a_perfect_encoder_finds_every_subject_and_has_no_wrong_strong_proposal(env):
    cases = _cases_file()
    res = _run(env, _oracle_vectors(env["texts"], cases))
    assert res.status_code == 201, res.text
    run = res.json()["data"]
    cross = run["by_family"]["cross_lingual"]
    assert cross["recall_at_3"] == 1.0 and cross["missed_strong"] == 0
    assert run["by_language"]["fr"]["same_subject_expected"] > 0 and run["by_language"]["en"]["same_subject_expected"] > 0
    assert run["false_strong"] == 0 and run["recommended_strong_threshold"] is not None
    assert len(run["sweep"]) == 12 and {"threshold", "false_strong", "recall"} <= set(run["sweep"][0])
    assert run["sweep"][0]["false_strong"] >= run["sweep"][-1]["false_strong"]  # a higher bar never adds false strong
    assert len(run["per_case"]) == len(cases)
    again = env["client"].get(f"{BASE}/runs/{run['id']}", headers=CLIENT).json()["data"]
    assert again["false_strong"] == 0 and again["run_by"] == "@ciso-office"


def test_a_strong_proposal_for_a_subject_absent_from_the_base_is_counted_and_blocks_the_recommendation(env):
    cases = _cases_file()
    run = _run(env, _oracle_vectors(env["texts"], cases, wrong=[("SIM-301", "P-002")])).json()["data"]
    assert run["by_family"]["out_of_base"]["false_strong"] == 1 and run["false_strong"] == 1
    bad = next(c for c in run["per_case"] if c["case_id"] == "SIM-301")
    assert bad["false_strong"] == ["P-002"]
    assert run["recommended_strong_threshold"] is None  # a perfect match for an absent subject is above every bar
    assert "no threshold" in run["recommendation_note"]


def test_same_topic_different_assumptions_is_reported_apart_from_false_strong(env):
    cases = _cases_file()
    # The query for SIM-201 is encoded as P-002 itself: a strong topic match, which only the hypotheses can sort out.
    run = _run(env, _oracle_vectors(env["texts"], cases, wrong=[("SIM-201", "P-002")])).json()["data"]
    fam = run["by_family"]["same_topic_different_assumptions"]
    assert fam["reuse_trap_strong"] >= 1 and fam["false_strong"] == 0


def test_run_validation_and_validated_only(env):
    cases = _cases_file()
    vectors = _oracle_vectors(env["texts"], cases)
    assert _run(env, vectors, headers=CLIENT).status_code == 403  # a system token cannot run an evaluation
    assert _run(env, {k: v for k, v in list(vectors.items())[:3]}).status_code == 400  # missing vectors
    assert _run(env, {**vectors, "SIM-001": [1.0, 2.0]}).status_code == 400  # wrong dimension
    assert env["client"].post(f"{BASE}/runs", headers=_as(EVA), json={"model": "ghost", "vectors": vectors}).status_code == 400
    assert _run(env, vectors, validated_only=True).status_code == 400  # nothing validated yet
    for cid in ("SIM-001", "SIM-002"):
        assert env["client"].patch(f"{BASE}/cases/{cid}", headers=_as(EVA), json={"annotation_status": "validated"}).status_code == 200
    only = _run(env, {k: vectors[k] for k in ("SIM-001", "SIM-002")}, validated_only=True)
    assert only.status_code == 201 and only.json()["data"]["cases"] == 2 and only.json()["data"]["validated_cases"] == 2
