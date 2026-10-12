"""Decision on each check clause (contract 1.26, #105): list, validate / amend / reject, publish, the judge applies."""

import json
import shutil
from pathlib import Path

import pytest
import yaml
from starlette.testclient import TestClient

from mcp_server.core.config import server_config

ROOT = Path(__file__).parent.parent.parent
CLIENT = {"Authorization": "Bearer archinex-token"}
SEC, MAINT, OTHER = "sec@example.org", "maint@example.org", "bob@example.org"
NO_BACKUP = {"title": "Single site", "description": "One data centre, no backup and no disaster recovery plan."}


def _as(email: str) -> dict:
    return {**CLIENT, "X-Actor-Email": email}


@pytest.fixture
def env(tmp_path, monkeypatch):
    kb = tmp_path / "kb"
    shutil.copytree(ROOT / "data" / "kb", kb)
    owners = yaml.safe_load((kb / "owners.yaml").read_text())
    owners["owners"]["@security-compliance-team"]["email"] = SEC  # owns business-continuity (NIS2-ART21-2C)
    owners["owners"]["@core-owner-architecture"]["email"] = OTHER
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
    monkeypatch.setenv("KB_EMBEDDINGS", "off")
    monkeypatch.delenv("LLMOPS_STORAGE_PERSISTENT", raising=False)
    import mcp_server.core.notifier as notifier

    monkeypatch.setattr(notifier, "notify_owner", lambda owner, event, c: ["log"])
    monkeypatch.setattr(notifier, "notify_consumers", lambda event, payload: ["log"])
    from pipelines.governance.migrate import migrate_governance
    from pipelines.governance.store import dispose_engines

    dispose_engines()
    migrate_governance(kb, tmp_path / "none", eval_dataset=None)
    from mcp_server.main import create_starlette_app

    yield {"client": TestClient(create_starlette_app()), "kb": kb}
    dispose_engines()


def _fm(kb: Path, rel: str) -> dict:
    return yaml.safe_load((kb / rel).read_text(encoding="utf-8").split("---")[1])


def _verdicts(client, option: dict) -> list[dict]:
    res = client.post("/api/knowledge/check", headers=CLIENT, json={"option": option, "frameworks": ["NIS2"]})
    assert res.status_code == 200, res.text
    return [v for v in res.json()["data"]["verdicts"] if v["typed_id"] == "control:NIS2-ART21-2C" and v["verdict"] != "unassessed"]


def test_list_decide_publish_then_the_judge_blocks(env):
    client, kb = env["client"], env["kb"]

    listed = client.get("/api/knowledge/checks?framework=NIS2&status=draft", headers=_as(SEC)).json()["data"]
    row = next(r for r in listed["clauses"] if r["check_id"] == "NIS2-ART21-2C-C1")
    assert row["kind"] == "forbids" and row["status"] == "draft" and row["may_decide"] is True
    assert row["asset_excerpt"] and row["severity"] == "mandatory" and "business-continuity" in row["domain"]
    assert any(m["asset_id"] == "NIS2-ART23-4" for m in listed["mandatory_without_clause"])
    assert listed["pending_publication"] == 0
    other = client.get("/api/knowledge/checks?asset_id=NIS2-ART21-2C", headers=_as(OTHER)).json()["data"]
    assert {r["may_decide"] for r in other["clauses"]} == {False}

    # Draft: the judge reports the violation, but only as a draft (it does not block).
    assert [v["check_status"] for v in _verdicts(client, NO_BACKUP)] == ["draft"]

    url = "/api/knowledge/assets/NIS2-ART21-2C/checks/NIS2-ART21-2C-C1"
    assert client.patch(url, headers=_as(OTHER), json={"decision": "validate"}).status_code == 403
    assert client.patch(url, headers=_as(SEC), json={"decision": "bogus"}).status_code == 400
    assert client.patch(url, headers=_as(SEC), json={"decision": "reject"}).status_code == 400  # comment required
    assert client.patch("/api/knowledge/assets/NIS2-ART21-2C/checks/NOPE", headers=_as(SEC),
                        json={"decision": "validate"}).status_code == 404

    done = client.patch(url, headers=_as(SEC), json={"decision": "validate"})
    assert done.status_code == 200, done.text
    assert done.json()["data"]["status"] == "validated" and done.json()["data"]["review"]["by"] == "@security-compliance-team"
    fm = _fm(kb, "controls/NIS2/NIS2-ART21-2C.md")
    assert [c["status"] for c in fm["checks"]] == ["validated", "draft"] and fm["checks_status"] == "partial"
    assert fm["revision"] == 3

    # The second clause is amended (validated with corrected terms); a rejected clause would no longer be evaluated.
    amended = client.patch("/api/knowledge/assets/NIS2-ART21-2C/checks/NIS2-ART21-2C-C2", headers=_as(SEC), json={
        "decision": "amend", "comment": "Recovery objectives are enough evidence",
        "clause": {"expect": {"terms_any": ["off-site", "hors site", "rpo", "rto"]}}})
    assert amended.status_code == 200, amended.text
    assert amended.json()["data"]["expect"] == {"terms_any": ["off-site", "hors site", "rpo", "rto"]}
    assert _fm(kb, "controls/NIS2/NIS2-ART21-2C.md")["checks_status"] == "validated"

    trail = [json.loads(line) for line in (kb / "clause-decisions.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [(d["check_id"], d["decision"], d["published_in"]) for d in trail] == [
        ("NIS2-ART21-2C-C1", "validate", None), ("NIS2-ART21-2C-C2", "amend", None)]

    # Nothing changes for the judge until the publication (re-ingestion + sealed snapshot).
    assert client.post("/api/knowledge/publications", headers=_as(SEC)).status_code == 403
    pub = client.post("/api/knowledge/publications", headers=_as(MAINT))
    assert pub.status_code == 200, pub.text
    assert pub.json()["data"]["clause_decisions"] == ["NIS2-ART21-2C/NIS2-ART21-2C-C1", "NIS2-ART21-2C/NIS2-ART21-2C-C2"]
    assert "clause `NIS2-ART21-2C-C1` of `NIS2-ART21-2C` validated by @security-compliance-team" in (
        kb / "CHANGELOG.md").read_text(encoding="utf-8")
    assert client.get("/api/knowledge/checks", headers=_as(SEC)).json()["data"]["pending_publication"] == 0

    assert [v["check_status"] for v in _verdicts(client, NO_BACKUP)] == ["validated"]
    assert client.post("/api/knowledge/publications", headers=_as(MAINT)).json()["data"]["published"] == []


def test_a_rejected_clause_is_no_longer_evaluated(env):
    client = env["client"]
    res = client.patch("/api/knowledge/assets/NIS2-ART21-2C/checks/NIS2-ART21-2C-C1", headers=_as(MAINT),
                       json={"decision": "reject", "comment": "Too broad"})
    assert res.status_code == 200 and res.json()["data"]["status"] == "rejected"
    assert client.post("/api/knowledge/publications", headers=_as(MAINT)).status_code == 200
    assert _verdicts(client, NO_BACKUP) == []
    rejected = client.get("/api/knowledge/checks?status=rejected", headers=_as(MAINT)).json()["data"]
    assert [r["check_id"] for r in rejected["clauses"]] == ["NIS2-ART21-2C-C1"]
