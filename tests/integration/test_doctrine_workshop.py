"""Doctrine workshop and evaluations (contract 1.6): templates, dry run, clause simulation,
evaluation dataset in the database, runs and verdict feedback."""

import shutil
from pathlib import Path

import pytest
import yaml
from starlette.testclient import TestClient

from mcp_server.core.config import server_config
from tests.integration.test_kb_candidates_api import PATTERN

ROOT = Path(__file__).parent.parent.parent
CLIENT = {"Authorization": "Bearer archinex-token"}
ALICE, EVALUATOR = "alice@example.org", "eva@example.org"
DS = "/api/knowledge/evals/check_option_v1"


def _as(email: str) -> dict:
    return {**CLIENT, "X-Actor-Email": email}


@pytest.fixture
def env(tmp_path, monkeypatch):
    kb = tmp_path / "kb"
    shutil.copytree(ROOT / "data" / "kb", kb)
    owners = yaml.safe_load((kb / "owners.yaml").read_text())
    owners["owners"]["@core-owner-architecture"]["email"] = ALICE
    owners["owners"]["@ciso-office"]["email"] = EVALUATOR
    owners["owners"]["@ciso-office"]["roles"] = ["kb:evaluate"]
    (kb / "owners.yaml").write_text(yaml.safe_dump(owners), encoding="utf-8")
    monkeypatch.setattr(server_config, "kb_dir", kb)
    monkeypatch.setenv("CANDIDATES_DIR", str(tmp_path / "candidates"))
    monkeypatch.setenv("SERVER_TOKEN", "demo-token")
    monkeypatch.setenv("ENGAGEMENT_TOKENS", "archinex-token:kb:review,kb:delegate")
    monkeypatch.setenv("CANDIDATES_BACKEND", "sql")
    monkeypatch.setenv("GOVERNANCE_DATABASE_URL", f"sqlite:///{tmp_path / 'gov.db'}")
    for var in ("OWNER_NOTIFICATION_WEBHOOK", "NOTIFICATION_WEBHOOK_URL", "KB_CONSUMER_WEBHOOKS", "KB_CONSUMER_NTFY_TOPIC"):
        monkeypatch.delenv(var, raising=False)
    import mcp_server.core.notifier as notifier

    monkeypatch.setattr(notifier, "notify_owner", lambda owner, event, c: ["log"])
    from pipelines.governance.migrate import migrate_governance
    from pipelines.governance.store import dispose_engines

    dispose_engines()
    migrate_governance(kb, tmp_path / "none")
    from mcp_server.main import create_starlette_app

    yield TestClient(create_starlette_app())
    dispose_engines()


def test_templates(env):
    res = env.get("/api/knowledge/templates/pattern", headers=CLIENT).json()["data"]
    assert res["asset_type"] == "pattern" and res["next_id"].startswith("PAT-")
    assert [s["heading"] for s in res["sections"]] == ["Problem", "Solution", "Trade-offs", "When not to use this"]
    domain = next(f for f in res["fields"] if f["name"] == "domain")
    assert "network-automation" in domain["values"] and domain["required"] is True
    assert next(f for f in res["fields"] if f["name"] == "type")["values"] == ["pattern"]
    assert "## Problem" in res["skeleton"]
    assert env.get("/api/knowledge/templates/principle", headers=CLIENT).json()["data"]["next_id"].startswith("P-")
    assert env.get("/api/knowledge/templates/glossary", headers=CLIENT).status_code == 200
    assert env.get("/api/knowledge/templates/bogus", headers=CLIENT).status_code == 404


def test_validate_is_a_dry_run(env):
    body = {"kind": "new_asset", "asset_type": "pattern", "title": "OOB network", "proposed_content": PATTERN,
            "source": {"system": "archinex"}}
    res = env.post("/api/knowledge/candidates/validate", headers=CLIENT, json=body)
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["would_be_status"] == "in_review" and data["assigned_owner"] and len(data["checks"]) == 7
    bad = env.post("/api/knowledge/candidates/validate", headers=CLIENT,
                   json={**body, "proposed_content": "no front matter at all"}).json()["data"]
    assert bad["would_be_status"] == "checks_failed" and bad["assigned_owner"] is None
    assert env.post("/api/knowledge/candidates/validate", headers=CLIENT, json={"kind": "bogus"}).status_code == 400
    assert env.get("/api/knowledge/candidates", headers=CLIENT).json()["data"] == []  # nothing was created


def _clauses(asset_file: str) -> list:
    text = (ROOT / "data" / "kb" / asset_file).read_text(encoding="utf-8")
    return yaml.safe_load(text.split("---")[1])["checks"]


def test_simulate_clauses(env):
    current = _clauses("principles/P-002.md")
    same = env.post("/api/knowledge/checks/simulate", headers=CLIENT, json={"asset_id": "P-002", "checks": current}).json()["data"]
    assert same["regressions"] == [] and same["metrics"]["before"] == same["metrics"]["after"]
    assert same["metrics"]["cases"] == 30

    removed = env.post("/api/knowledge/checks/simulate", headers=CLIENT, json={"asset_id": "P-002", "checks": []}).json()["data"]
    assert removed["regressions"], "removing the clauses must lose expected verdicts"
    assert removed["metrics"]["after"]["violation_recall"] < removed["metrics"]["before"]["violation_recall"]

    broken = env.post("/api/knowledge/checks/simulate", headers=CLIENT, json={
        "asset_id": "P-002", "checks": [{"id": "X", "kind": "nope"}],
        "options": [{"title": "Fully autonomous remediation", "description": "no human approval"}]}).json()["data"]
    assert broken["clause_problems"] and broken["clause_problems"][0]["clause"] == "X"
    assert len(broken["options"]) == 1

    assert env.post("/api/knowledge/checks/simulate", headers=CLIENT, json={"asset_id": "P-999", "checks": []}).status_code == 404
    assert env.post("/api/knowledge/checks/simulate", headers=CLIENT, json={"asset_id": "P-002"}).status_code == 400


def test_evaluation_dataset_annotation_and_runs(env):
    ds = env.get(DS, headers=CLIENT).json()["data"]
    assert len(ds["cases"]) == 30 and ds["validated"] == 0
    case = ds["cases"][0]
    patch = f"{DS}/cases/{case['id']}"
    assert env.patch(patch, headers=CLIENT, json={"annotation_status": "validated"}).status_code == 403  # no actor
    assert env.patch(patch, headers=_as(ALICE), json={"annotation_status": "validated"}).status_code == 403  # no kb:evaluate
    assert env.patch(patch, headers=_as(EVALUATOR), json={"annotation_status": "bogus"}).status_code == 400
    assert env.patch(patch, headers=_as(EVALUATOR), json={"expected": {"P-002": "violates"}}).status_code == 400
    # A payload carrying neither field is refused, not silently ignored.
    assert env.patch(patch, headers=_as(EVALUATOR), json={"expected_status": "violates", "notes": "x"}).status_code == 400
    ok = env.patch(patch, headers=_as(EVALUATOR), json={"annotation_status": "validated"})
    assert ok.status_code == 200 and ok.json()["data"]["annotated_by"] == "@ciso-office"
    assert env.patch(f"{DS}/cases/NOPE", headers=_as(EVALUATOR), json={"annotation_status": "validated"}).status_code == 404

    run = env.post(f"{DS}/runs", headers=_as(EVALUATOR), json={})
    assert run.status_code == 201
    metrics = run.json()["data"]
    assert metrics["cases"] == 30 and 0 <= metrics["violation_recall"] <= 1 and metrics["run_by"] == "@ciso-office"
    only = env.post(f"{DS}/runs", headers=_as(EVALUATOR), json={"validated_only": True}).json()["data"]
    assert only["cases"] == 1
    assert env.get(f"{DS}/runs/{metrics['id']}", headers=CLIENT).json()["data"]["violation_recall"] == metrics["violation_recall"]
    assert env.get(f"{DS}/runs/999", headers=CLIENT).status_code == 404
    assert env.post(f"{DS}/runs", headers=_as(ALICE), json={}).status_code == 403
    types = [e["type"] for e in env.get("/api/knowledge/events", headers=CLIENT).json()["data"]["events"]]
    assert types.count("eval.updated") == 3  # one annotation, two runs

    new = env.post(f"{DS}/cases", headers=_as(EVALUATOR), json={
        "option": {"title": "Manual hotfix in production", "description": "ssh into production"},
        "expected": {"principle:P-001": "violates"}})
    assert new.status_code == 201 and new.json()["data"]["annotation_status"] == "proposed"
    assert len(env.get(DS, headers=CLIENT).json()["data"]["cases"]) == 31


def test_verdict_feedback_conversion(env):
    body = {"typed_id": "principle:P-002", "check_id": "P-002-C1", "feedback": "wrong_violation",
            "justification": "The approval is given by the change board, not at run time.",
            "option": {"title": "Board-approved remediation", "description": "The board approves the playbook once."},
            "subject": "Remediation"}
    assert env.post("/api/knowledge/verdict-feedback", headers=CLIENT, json={**body, "justification": " "}).status_code == 400
    assert env.post("/api/knowledge/verdict-feedback", headers=CLIENT, json={**body, "feedback": "meh"}).status_code == 400
    created = env.post("/api/knowledge/verdict-feedback", headers=_as(ALICE), json=body)
    assert created.status_code == 201
    fid = created.json()["data"]["id"]
    assert created.json()["data"]["reporter"] == "@core-owner-architecture" and created.json()["data"]["status"] == "open"
    assert [f["id"] for f in env.get("/api/knowledge/verdict-feedback?status=open", headers=CLIENT).json()["data"]] == [fid]

    url = f"/api/knowledge/verdict-feedback/{fid}/convert"
    assert env.post(url, headers=_as(ALICE), json={"to": "dismiss"}).status_code == 403  # not an evaluator
    assert env.post(url, headers=_as(EVALUATOR), json={"to": "eval_case", "expected": "maybe"}).status_code == 400
    done = env.post(url, headers=_as(EVALUATOR), json={"to": "eval_case", "expected": "supports"})
    assert done.status_code == 200 and done.json()["data"]["converted_to"].startswith("eval_case:CO-")
    cases = env.get(DS, headers=CLIENT).json()["data"]["cases"]
    assert cases[-1]["expected"] == {"principle:P-002": "supports"} and cases[-1]["annotation_status"] == "proposed"
    assert env.post(url, headers=_as(EVALUATOR), json={"to": "dismiss"}).status_code == 409  # already converted

    second = env.post("/api/knowledge/verdict-feedback", headers=CLIENT, json=body).json()["data"]["id"]
    text = (ROOT / "data" / "kb" / "principles" / "P-004.md").read_text(encoding="utf-8")
    amend = env.post(f"/api/knowledge/verdict-feedback/{second}/convert", headers=_as(EVALUATOR), json={
        "to": "amendment", "asset_type": "principle", "target_asset_id": "P-004",
        "proposed_content": text.replace("It is never a design default.", "It is never a design default, nor a vendor default.")})
    assert amend.status_code == 200, amend.text
    cid = amend.json()["data"]["converted_to"].split(":")[1]
    cand = env.get(f"/api/knowledge/candidates/{cid}", headers=CLIENT).json()["data"]
    assert cand["kind"] == "amendment" and cand["source"]["author"] == "@ciso-office"
    third = env.post("/api/knowledge/verdict-feedback", headers=CLIENT, json=body).json()["data"]["id"]
    assert env.post(f"/api/knowledge/verdict-feedback/{third}/convert", headers=_as(EVALUATOR),
                    json={"to": "dismiss"}).json()["data"]["status"] == "dismissed"


def test_evaluation_features_need_the_database(env, monkeypatch, tmp_path):
    monkeypatch.delenv("GOVERNANCE_DATABASE_URL")
    monkeypatch.setenv("CANDIDATES_BACKEND", "file")
    monkeypatch.setenv("CANDIDATES_DIR", str(tmp_path / "file-queue"))
    assert env.get(DS, headers=CLIENT).status_code == 503
    # Templates, dry run and simulation (default dataset from the JSONL) work without it.
    assert env.get("/api/knowledge/templates/pattern", headers=CLIENT).status_code == 200
    sim = env.post("/api/knowledge/checks/simulate", headers=CLIENT, json={"asset_id": "P-002", "checks": _clauses("principles/P-002.md")})
    assert sim.status_code == 200 and sim.json()["data"]["metrics"]["cases"] == 30
