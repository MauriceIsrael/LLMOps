"""Server-side promotion, publication and health indicators (contract 1.8), on temporary copies."""

import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml
from starlette.testclient import TestClient

from mcp_server.core.config import server_config
from tests.integration.test_kb_candidates_api import PATTERN

ROOT = Path(__file__).parent.parent.parent
CLIENT = {"Authorization": "Bearer archinex-token"}
ALICE, MAINT = "alice@example.org", "maint@example.org"


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
    db = tmp_path / "knowledge.lbug"
    shutil.copy(ROOT / "data" / "knowledge.lbug", db)
    (tmp_path / "data").mkdir()
    monkeypatch.chdir(tmp_path)  # snapshots are written under ./data/snapshots
    monkeypatch.setattr(server_config, "kb_dir", kb)
    monkeypatch.setattr(server_config, "knowledge_db_path", db)
    monkeypatch.setenv("SERVER_TOKEN", "demo-token")
    monkeypatch.setenv("ENGAGEMENT_TOKENS", "archinex-token:kb:review,kb:delegate")
    monkeypatch.setenv("CANDIDATES_BACKEND", "sql")
    monkeypatch.setenv("GOVERNANCE_DATABASE_URL", f"sqlite:///{tmp_path / 'gov.db'}")
    monkeypatch.delenv("LLMOPS_STORAGE_PERSISTENT", raising=False)
    for var in ("OWNER_NOTIFICATION_WEBHOOK", "NOTIFICATION_WEBHOOK_URL", "KB_CONSUMER_WEBHOOKS", "KB_CONSUMER_NTFY_TOPIC"):
        monkeypatch.delenv(var, raising=False)
    import mcp_server.core.notifier as notifier

    monkeypatch.setattr(notifier, "notify_owner", lambda owner, event, c: ["log"])
    monkeypatch.setattr(notifier, "notify_consumers", lambda event, payload: ["log"])
    from pipelines.governance.migrate import migrate_governance
    from pipelines.governance.store import dispose_engines

    dispose_engines()
    migrate_governance(kb, tmp_path / "none", eval_dataset=ROOT / "tests" / "evals" / "datasets" / "check_option_v1.jsonl")
    from mcp_server.main import create_starlette_app

    yield {"client": TestClient(create_starlette_app()), "kb": kb, "db": db, "tmp": tmp_path}
    dispose_engines()


def _accepted_candidate(client) -> str:
    res = client.post("/api/knowledge/candidates", headers=CLIENT, json={
        "kind": "new_asset", "asset_type": "pattern", "title": "Out-of-band management network",
        "proposed_content": PATTERN, "source": {"system": "archinex", "engagement": "eng-alpha"}})
    cid = res.json()["data"]["id"]
    done = client.patch(f"/api/knowledge/candidates/{cid}", headers=_as(ALICE), json={"action": "accept", "reason": "Generic and proven"})
    assert done.json()["data"]["status"] == "accepted", done.text
    return cid


def test_promote_is_reserved_to_maintainers_and_needs_an_accepted_candidate(env):
    client = env["client"]
    cid = _accepted_candidate(client)
    assert client.post(f"/api/knowledge/candidates/{cid}/promote", headers=_as(ALICE)).status_code == 403
    assert client.post("/api/knowledge/candidates/CAND-20260101-0001/promote", headers=_as(MAINT)).status_code == 404
    other = client.post("/api/knowledge/candidates", headers=CLIENT, json={
        "kind": "rex", "title": "Note", "proposed_content": "Short REX.", "source": {"system": "mcp"}}).json()["data"]["id"]
    assert client.post(f"/api/knowledge/candidates/{other}/promote", headers=_as(MAINT)).status_code == 409
    res = client.post(f"/api/knowledge/candidates/{cid}/promote", headers=_as(MAINT))
    assert res.status_code == 200, res.text
    assert res.json()["warnings"] == [] and res.json()["data"]["promoted"]["asset_id"] == "PAT-099"
    fm = yaml.safe_load((env["kb"] / "patterns" / "PAT-099.md").read_text().split("---")[1])
    assert fm["status"] == "active" and fm["validated_by"] == ["@core-owner-architecture"]
    assert client.post(f"/api/knowledge/candidates/{cid}/promote", headers=_as(MAINT)).status_code == 409  # already promoted


def test_demo_mode_announces_the_ephemeral_storage(env, monkeypatch):
    monkeypatch.setenv("LLMOPS_STORAGE_PERSISTENT", "false")
    client = env["client"]
    cid = _accepted_candidate(client)
    res = client.post(f"/api/knowledge/candidates/{cid}/promote", headers=_as(MAINT))
    assert res.json()["warnings"] == ["ephemeral-storage"]
    health = client.get("/api/knowledge/health", headers=CLIENT).json()["data"]
    assert health["storage"] == {"persistent": False, "mode": "demo"}


def test_publication_rebuilds_the_graph_and_seals_a_snapshot(env):
    client = env["client"]
    assert client.post("/api/knowledge/publications", headers=_as(ALICE)).status_code == 403
    nothing = client.post("/api/knowledge/publications", headers=_as(MAINT))
    assert nothing.status_code == 200 and nothing.json()["data"]["published"] == []

    cid = _accepted_candidate(client)
    client.post(f"/api/knowledge/candidates/{cid}/promote", headers=_as(MAINT))
    res = client.post("/api/knowledge/publications", headers=_as(MAINT))
    assert res.status_code == 200, res.text
    out = res.json()["data"]
    assert out["published"] == [cid] and out["snapshot_id"].startswith("snapshot-")
    assert (env["tmp"] / "data" / "snapshots" / "latest.json").is_file()
    assert "PAT-099" in (env["kb"] / "CHANGELOG.md").read_text()
    cand = client.get(f"/api/knowledge/candidates/{cid}", headers=CLIENT).json()["data"]
    assert cand["status"] == "published" and cand["published"]["snapshot_id"] == out["snapshot_id"]
    # The served graph now holds the new asset.
    assert client.get("/api/knowledge/search?q=out-of-band", headers=CLIENT).status_code == 200
    from mcp_server.knowledge.tools import get_asset

    assert get_asset("PAT-099")["status"] == "ok"
    types = [e["type"] for e in client.get("/api/knowledge/events", headers=CLIENT).json()["data"]["events"]]
    assert "candidate.promoted" in types and "candidate.published" in types
    assert client.post("/api/knowledge/publications", headers=_as(MAINT)).json()["data"]["published"] == []  # idempotent


def test_health_indicators(env):
    client = env["client"]
    assert client.get("/api/knowledge/health", headers={"Authorization": "Bearer demo-token"}).status_code == 403
    cid = client.post("/api/knowledge/candidates", headers=CLIENT, json={
        "kind": "new_asset", "asset_type": "pattern", "title": "Out-of-band management network",
        "proposed_content": PATTERN, "source": {"system": "archinex"}}).json()["data"]["id"]
    # Age the candidate: it entered review three weeks ago.
    from pipelines.kb_candidates.repository import get_repository

    repo = get_repository()
    cand = repo.get(cid)
    old = (datetime.now(UTC) - timedelta(days=21)).strftime("%Y-%m-%dT%H:%M:%SZ")
    for h in cand["history"]:
        if h["event"] == "in_review":
            h["at"] = old
    repo.save(cand)

    # A run of the evaluation feeds the clause indicators.
    assert client.post("/api/knowledge/evals/check_option_v1/runs", headers=_as(MAINT), json={}).status_code == 201

    health = client.get("/api/knowledge/health", headers=CLIENT).json()["data"]
    assert health["storage"] == {"persistent": True, "mode": "normal"}
    assert health["assets"]["active"] > 30 and health["assets"]["by_type"]["principle"] > 0
    assert health["assets"]["unvalidated"]["count"] > 0
    assert health["clauses"]["total"] > 0 and 0 <= health["clauses"]["unassessed_verdict_share"] <= 1
    assert health["coverage"]["NIS2"]["status"] in ("partial", "covered", "missing")
    assert health["queue"]["by_status"]["in_review"] == 1
    assert health["queue"]["per_owner"]["@core-owner-architecture"]["oldest_business_days"] >= 10
    assert [o["candidate_id"] for o in health["queue"]["overdue"]] == [cid]
    assert health["evaluation"]["cases"] == 30 and health["evaluation"]["last_run"]["cases"] == 30
    assert health["last_snapshot"] is None  # nothing published in this temporary environment
