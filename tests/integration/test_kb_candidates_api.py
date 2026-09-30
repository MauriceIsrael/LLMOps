"""End-to-end KB candidate cycle (contract 1.2), on a temporary copy of the knowledge base.

A suggestion submitted through ``POST /api/knowledge/suggestions`` (unchanged input and
output, plus ``candidate_id``) enters the queue, passes the checks, is routed to its
domain owner, is accepted by a ``kb:review`` token, then promoted and published by the
``kb`` CLI — without editing any file by hand.
"""

import json
import os
import shutil
from pathlib import Path

import jsonschema
import pytest
import yaml
from starlette.testclient import TestClient
from typer.testing import CliRunner

from mcp_server.core.config import server_config

ROOT = Path(__file__).parent.parent.parent
DEMO = {"Authorization": "Bearer demo-token"}
REVIEWER = {"Authorization": "Bearer reviewer-token"}
REVIEWER_2 = {"Authorization": "Bearer reviewer-token-2"}

PATTERN = """---
id: PAT-099
title: Out-of-band management network for the automation chain
type: pattern
status: draft
confidence: assumed
phase: [BUILD, RUN]
domain: [network-automation]
related: [P-009]
---

# PAT-099 — Out-of-band management network for the automation chain

## Problem
The automation chain loses reachability to the devices when the data network fails.

## Forces
Restoration must keep working during the outage it restores.

## Solution
Provide a dedicated out-of-band management network, with break-glass access.

## Trade-offs
Extra circuits and cabling.

## When not to use this
Sites with on-site hands available around the clock.
"""


@pytest.fixture
def env(tmp_path, monkeypatch):
    kb = tmp_path / "kb"
    shutil.copytree(ROOT / "data" / "kb", kb)
    monkeypatch.setattr(server_config, "kb_dir", kb)
    monkeypatch.setenv("CANDIDATES_DIR", str(tmp_path / "candidates"))
    monkeypatch.setenv("SERVER_TOKEN", "demo-token")
    monkeypatch.setenv("ENGAGEMENT_TOKENS", "reviewer-token:kb:review;reviewer-token-2:kb:review")
    for var in ("OWNER_NOTIFICATION_WEBHOOK", "NOTIFICATION_WEBHOOK_URL", "KB_CONSUMER_WEBHOOKS", "KB_CONSUMER_NTFY_TOPIC"):
        monkeypatch.delenv(var, raising=False)

    import mcp_server.core.notifier as notifier

    sent = {"owner": [], "consumers": []}
    monkeypatch.setattr(notifier, "notify_owner",
                        lambda owner, event, c: sent["owner"].append((owner["handle"], event, c["id"])) or ["log"])
    monkeypatch.setattr(notifier, "notify_consumers",
                        lambda event, payload: sent["consumers"].append((event, payload)) or ["log"])
    from mcp_server.main import create_starlette_app

    return {"kb": kb, "tmp": tmp_path, "client": TestClient(create_starlette_app()), "sent": sent}


def _schema():
    return json.loads((ROOT / "schemas" / "kb_candidate.schema.json").read_text(encoding="utf-8"))


def test_suggestion_to_publication_without_manual_edit(env):
    client, kb, tmp, sent = env["client"], env["kb"], env["tmp"], env["sent"]

    # 1. Suggestion: same input, same output keys, plus the optional candidate_id.
    res = client.post("/api/knowledge/suggestions", headers=DEMO, json={
        "title": "Out-of-band management network",
        "rationale": "Proven on two engagements: restoration kept working during transport outages.",
        "suggested_change": PATTERN,
        "author": "document-studio",
        "source_engagement": "eng-alpha",
    })
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert {"suggestion_id", "notifications_sent", "message"} <= set(body["data"])
    candidate_id = body["data"]["candidate_id"]

    # 2. Queued, checked, routed to the owner of its domain.
    res = client.get(f"/api/knowledge/candidates/{candidate_id}", headers=DEMO)
    assert res.status_code == 200
    candidate = res.json()["data"]
    jsonschema.validate(candidate, _schema())
    assert candidate["kind"] == "rex" and candidate["asset_type"] == "pattern"
    assert candidate["source"]["system"] == "document-studio"
    assert candidate["status"] == "in_review", candidate["checks"]
    assert candidate["assigned_owner"] == "@core-owner-architecture"
    assert ("@core-owner-architecture", "in_review", candidate_id) in sent["owner"]
    listed = client.get("/api/knowledge/candidates?status=in_review&source=document-studio", headers=DEMO).json()
    assert candidate_id in [c["id"] for c in listed["data"]]

    # 3. Review: the public demo token cannot review; a kb:review token can.
    review = {"action": "accept", "reviewer": "@core-owner-architecture", "reason": "Generic and proven"}
    assert client.patch(f"/api/knowledge/candidates/{candidate_id}", headers=DEMO, json=review).status_code == 403
    res = client.patch(f"/api/knowledge/candidates/{candidate_id}", headers=REVIEWER, json=review)
    assert res.status_code == 200
    assert res.json()["data"]["status"] == "accepted"
    assert client.patch(f"/api/knowledge/candidates/{candidate_id}", headers=REVIEWER, json=review).status_code == 409

    # 4. Promotion and publication by the maintainer CLI (temporary KB, graph and snapshots).
    from pipelines.kb_cli import app

    runner = CliRunner()
    out = runner.invoke(app, ["promote", candidate_id, "--kb-dir", str(kb)])
    assert out.exit_code == 0, out.output
    asset = kb / "patterns" / "PAT-099.md"
    fm = yaml.safe_load(asset.read_text(encoding="utf-8").split("---")[1])
    assert fm["status"] == "active"
    assert fm["confidence"] == "assumed"  # a single engagement, no measure
    assert fm["validated_by"] == ["@core-owner-architecture"]

    db_path = tmp / "knowledge.lbug"
    out = runner.invoke(app, ["publish", "--kb-dir", str(kb), "--db-path", str(db_path),
                              "--snapshot-dir", str(tmp / "snapshots"), "--fixture", str(tmp / "sealed.json")])
    assert out.exit_code == 0, out.output
    published = client.get(f"/api/knowledge/candidates/{candidate_id}", headers=DEMO).json()["data"]
    assert published["status"] == "published"
    assert published["published"]["snapshot_id"]
    assert "PAT-099" in (kb / "CHANGELOG.md").read_text(encoding="utf-8")
    assert sent["consumers"] and sent["consumers"][0][0] == "kb_published"
    snapshot = json.loads((tmp / "snapshots" / "latest.json").read_text(encoding="utf-8"))
    assert "PAT-099" in {a["id"] for a in snapshot["assets"]}


def test_private_ip_is_blocked_and_redacted(env):
    client = env["client"]
    res = client.post("/api/knowledge/candidates", headers=DEMO, json={
        "kind": "new_asset",
        "asset_type": "pattern",
        "title": "Management VLAN addressing",
        "proposed_content": PATTERN.replace("PAT-099", "PAT-098") + "\nThe management gateway is 10.12.0.1.\n",
        "source": {"system": "archinex", "production_mode": "llm-derived"},
    })
    assert res.status_code == 201
    candidate = res.json()["data"]
    assert candidate["status"] == "checks_failed"
    anonymization = next(c for c in candidate["checks"] if c["name"] == "anonymization")
    assert anonymization["status"] == "fail" and "10.12.0.1" in anonymization["detail"]
    llm = next(c for c in candidate["checks"] if c["name"] == "llm_unreviewed")
    assert llm["status"] == "warn"

    as_demo = client.get(f"/api/knowledge/candidates/{candidate['id']}", headers=DEMO).json()["data"]
    assert as_demo["proposed_content"].startswith("[redacted")
    as_reviewer = client.get(f"/api/knowledge/candidates/{candidate['id']}", headers=REVIEWER).json()["data"]
    assert "10.12.0.1" in as_reviewer["proposed_content"]
    res = client.patch(f"/api/knowledge/candidates/{candidate['id']}", headers=REVIEWER,
                       json={"action": "accept", "reviewer": "@core-owner-architecture"})
    assert res.status_code == 409


def test_candidate_api_errors(env):
    client = env["client"]
    assert client.post("/api/knowledge/candidates", headers=DEMO, content=b"nope").status_code == 400
    res = client.post("/api/knowledge/candidates", headers=DEMO, json={"kind": "idea"})
    assert res.status_code == 400 and res.json()["argument"] == "kind"
    assert client.get("/api/knowledge/candidates/CAND-20990101-0001", headers=DEMO).status_code == 404
    assert client.get("/api/knowledge/candidates/not-an-id", headers=DEMO).status_code == 404
    assert client.get("/api/knowledge/candidates").status_code == 401
    res = client.patch("/api/knowledge/candidates/CAND-20990101-0001", headers=REVIEWER,
                       json={"action": "accept", "reviewer": "@maintainers"})
    assert res.status_code == 404


def test_principle_needs_two_reviewers(env):
    client = env["client"]
    principle = (ROOT / "data" / "kb" / "principles" / "P-004.md").read_text(encoding="utf-8")
    amended = principle.replace("It is never a design default.", "It is never a design default, nor a vendor default.")
    res = client.post("/api/knowledge/candidates", headers=DEMO, json={
        "kind": "amendment", "asset_type": "principle", "target_asset_id": "P-004",
        "title": "Graduated autonomy — vendor defaults", "proposed_content": amended,
        "source": {"system": "archinex", "author": "architect"},
        "evidence": [{"kind": "audit", "ref": "audit-2026-04"}],
    })
    candidate = res.json()["data"]
    assert candidate["status"] == "in_review" and candidate["second_review_required"] is True
    url = f"/api/knowledge/candidates/{candidate['id']}"
    first = client.patch(url, headers=REVIEWER, json={"action": "accept", "reviewer": "@core-owner-architecture"})
    assert first.json()["data"]["status"] == "in_review"
    same = client.patch(url, headers=REVIEWER_2, json={"action": "accept", "reviewer": "@core-owner-architecture"})
    assert same.status_code == 400
    second = client.patch(url, headers=REVIEWER_2, json={"action": "accept", "reviewer": "@maintainers"})
    assert second.status_code == 200 and second.json()["data"]["status"] == "accepted"


def test_repository_is_the_configured_directory(env):
    env["client"].post("/api/knowledge/candidates", headers=DEMO, json={
        "kind": "rex", "title": "Note", "proposed_content": "Short REX.", "source": {"system": "mcp"},
    })
    assert list((env["tmp"] / "candidates").glob("CAND-*.json"))
    assert os.environ["CANDIDATES_DIR"] == str(env["tmp"] / "candidates")
