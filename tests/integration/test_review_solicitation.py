"""Review inbox, reassignment, solicitation, comments, event feed and owners registry (contract 1.5)."""

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
ADMIN = {"Authorization": "Bearer admin-token"}
ALICE, BOB, MAINT = "alice@example.org", "bob@example.org", "maint@example.org"


def _as(email: str) -> dict:
    return {**CLIENT, "X-Actor-Email": email}


@pytest.fixture
def env(tmp_path, monkeypatch):
    kb = tmp_path / "kb"
    shutil.copytree(ROOT / "data" / "kb", kb)
    owners = yaml.safe_load((kb / "owners.yaml").read_text())
    owners["owners"]["@core-owner-architecture"]["email"] = ALICE
    owners["owners"]["@core-owner-architecture"]["discord_webhook"] = "https://example.invalid/hook"
    owners["owners"]["@ciso-office"]["email"] = BOB
    owners["owners"]["@maintainers"] = {"email": MAINT, "roles": ["kb:maintain"]}
    (kb / "owners.yaml").write_text(yaml.safe_dump(owners), encoding="utf-8")
    monkeypatch.setattr(server_config, "kb_dir", kb)
    monkeypatch.setenv("CANDIDATES_DIR", str(tmp_path / "candidates"))
    monkeypatch.setenv("SERVER_TOKEN", "demo-token")
    monkeypatch.setenv("ENGAGEMENT_TOKENS", "archinex-token:kb:review,kb:delegate;admin-token:kb:admin,kb:review")
    monkeypatch.setenv("CANDIDATES_BACKEND", "sql")
    monkeypatch.setenv("GOVERNANCE_DATABASE_URL", f"sqlite:///{tmp_path / 'gov.db'}")
    for var in ("OWNER_NOTIFICATION_WEBHOOK", "NOTIFICATION_WEBHOOK_URL", "KB_CONSUMER_WEBHOOKS", "KB_CONSUMER_NTFY_TOPIC"):
        monkeypatch.delenv(var, raising=False)
    import mcp_server.core.notifier as notifier

    monkeypatch.setattr(notifier, "notify_owner", lambda owner, event, c: ["log"])
    monkeypatch.setattr(notifier, "notify_consumers", lambda event, payload: ["log"])
    from pipelines.governance.migrate import migrate_governance
    from pipelines.governance.store import dispose_engines

    dispose_engines()
    migrate_governance(kb, tmp_path / "none")  # seed the registry (with the e-mails above) in the database
    from mcp_server.main import create_starlette_app

    yield TestClient(create_starlette_app())
    dispose_engines()


def _submit(client, **extra) -> dict:
    res = client.post("/api/knowledge/candidates", headers=CLIENT, json={
        "kind": "new_asset", "asset_type": "pattern", "title": "Out-of-band management network",
        "proposed_content": PATTERN, "source": {"system": "archinex", "engagement": "eng-alpha"}, **extra})
    assert res.status_code == 201, res.text
    return res.json()["data"]


def _principle(client) -> dict:
    text = (ROOT / "data" / "kb" / "principles" / "P-004.md").read_text(encoding="utf-8")
    res = client.post("/api/knowledge/candidates", headers=CLIENT, json={
        "kind": "amendment", "asset_type": "principle", "target_asset_id": "P-004",
        "title": "Graduated autonomy — vendor defaults",
        "proposed_content": text.replace("It is never a design default.", "It is never a design default, nor a vendor default."),
        "source": {"system": "archinex"}, "evidence": [{"kind": "audit", "ref": "audit-2026-04"}]})
    assert res.status_code == 201, res.text
    return res.json()["data"]


def _inbox(client, email):
    res = client.get("/api/knowledge/reviews/inbox", headers=_as(email))
    assert res.status_code == 200, res.text
    return res.json()["data"]["items"]


def _events(client, since=0):
    return client.get(f"/api/knowledge/events?since={since}", headers=CLIENT).json()["data"]


def test_inbox_lists_what_waits_for_the_expert(env):
    assert env.get("/api/knowledge/reviews/inbox", headers=CLIENT).status_code == 403  # no acting expert
    cand = _submit(env)
    items = _inbox(env, ALICE)
    assert [i["candidate_id"] for i in items] == [cand["id"]]
    assert items[0]["reason"] == "review" and items[0]["due_at"] > items[0]["waiting_since"]
    assert _inbox(env, BOB) == []
    submitted = _events(env)["events"][0]
    assert submitted["type"] == "candidate.submitted" and submitted["recipients"] == ["@core-owner-architecture"]


def test_reassignment_moves_the_candidate_and_is_restricted(env):
    cid = _submit(env)["id"]
    url = f"/api/knowledge/candidates/{cid}/assign"
    assert env.post(url, headers=_as(BOB), json={"handle": "@ciso-office"}).status_code == 403  # neither owner nor maintainer
    assert env.post(url, headers=_as(MAINT), json={"handle": "@nobody"}).status_code == 400
    res = env.post(url, headers=_as(MAINT), json={"handle": "@ciso-office", "reason": "Security topic"})
    assert res.status_code == 200 and res.json()["data"]["assigned_owner"] == "@ciso-office"
    assert [i["candidate_id"] for i in _inbox(env, BOB)] == [cid] and _inbox(env, ALICE) == []
    assigned = [e for e in _events(env)["events"] if e["type"] == "candidate.assigned"]
    assert assigned[0]["recipients"] == ["@ciso-office"] and assigned[0]["payload"]["previous"] == "@core-owner-architecture"
    # The new owner may reassign it back; the previous one may not any more.
    assert env.post(url, headers=_as(ALICE), json={"handle": "@maintainers"}).status_code == 403
    assert env.post(url, headers=_as(BOB), json={"handle": "@core-owner-architecture"}).status_code == 200


def test_advice_request_comments_and_cursor(env):
    cid = _submit(env)["id"]
    ask = env.post(f"/api/knowledge/candidates/{cid}/request-review", headers=_as(ALICE),
                   json={"handle": "@ciso-office", "kind": "advice", "message": "Security view please"})
    assert ask.status_code == 201 and ask.json()["data"]["kind"] == "advice"
    advice = _inbox(env, BOB)
    assert advice[0]["reason"] == "advice" and advice[0]["message"] == "Security view please"
    assert env.post(f"/api/knowledge/candidates/{cid}/request-review", headers=_as(ALICE),
                    json={"handle": "@ciso-office", "kind": "bogus"}).status_code == 400
    assert env.post(f"/api/knowledge/candidates/{cid}/request-review", headers=_as("eve@example.org"),
                    json={"handle": "@ciso-office"}).status_code == 403

    posted = env.post(f"/api/knowledge/candidates/{cid}/comments", headers=_as(BOB), json={"body": "Looks fine to me."})
    assert posted.status_code == 201 and posted.json()["data"]["author"] == "@ciso-office"
    assert env.post(f"/api/knowledge/candidates/{cid}/comments", headers=_as(BOB), json={"body": " "}).status_code == 400
    listed = env.get(f"/api/knowledge/candidates/{cid}/comments", headers=CLIENT).json()["data"]
    assert [c["body"] for c in listed] == ["Looks fine to me."]
    # A comment is not a decision: the candidate is still waiting.
    assert env.get(f"/api/knowledge/candidates/{cid}", headers=CLIENT).json()["data"]["status"] == "in_review"

    feed = _events(env)
    assert [e["type"] for e in feed["events"]] == ["candidate.submitted", "review.requested", "candidate.commented"]
    assert _events(env, since=feed["next_cursor"])["events"] == []  # cursor idempotence
    assert env.get("/api/knowledge/events?since=abc", headers=CLIENT).status_code == 400


def test_second_review_is_requested_and_closed(env):
    cand = _principle(env)
    assert cand["second_review_required"] is True
    url = f"/api/knowledge/candidates/{cand['id']}"
    assert env.patch(url, headers=_as(ALICE), json={"action": "accept"}).status_code == 200
    types = [e["type"] for e in _events(env)["events"]]
    assert "review.requested" in types
    second = _inbox(env, MAINT)
    assert second[0]["reason"] == "second_review" and second[0]["candidate_id"] == cand["id"]
    assert _inbox(env, ALICE) == []
    done = env.patch(url, headers=_as(MAINT), json={"action": "accept"})
    assert done.json()["data"]["status"] == "accepted" and _inbox(env, MAINT) == []
    from pipelines.governance.log import get_log

    assert get_log().requests(handle="@maintainers") == []  # the request was closed by the review
    reviewed = [e for e in _events(env)["events"] if e["type"] == "candidate.reviewed"]
    assert [e["payload"]["status"] for e in reviewed] == ["in_review", "accepted"]


def test_reminders_emit_events(env):
    cand = _submit(env)
    from pipelines.kb_candidates.service import CandidateService

    service = CandidateService(kb_dir=server_config.kb_dir, notify_owner=lambda o, e, c: ["log"])
    later = datetime.now(UTC) + timedelta(days=10)
    assert [c["id"] for c in service.remind(now=later)] == [cand["id"]]
    assert _events(env)["events"][-1]["type"] == "reminder.due"


def test_owners_registry_read_and_admin_update(env):
    listed = env.get("/api/knowledge/owners", headers=CLIENT).json()["data"]
    assert listed["default_owner"] == "@maintainers"
    assert "discord_webhook" not in str(listed)  # notification secrets are never exposed
    payload = {**listed, "owners": [{**o, "roles": o["roles"] + (["kb:evaluate"] if o["handle"] == "@ciso-office" else [])}
                                    for o in listed["owners"]]}
    assert env.put("/api/knowledge/owners", headers=_as(ALICE), json=payload).status_code == 403  # not an admin
    assert env.put("/api/knowledge/owners", headers=CLIENT, json=payload).status_code == 403  # delegate token, no admin
    bad = {**payload, "default_owner": "@nobody"}
    assert env.put("/api/knowledge/owners", headers=ADMIN, json=bad).status_code == 400
    dup = {**payload, "owners": [{**o, "email": ALICE} for o in payload["owners"][:2]] + payload["owners"][2:]}
    assert env.put("/api/knowledge/owners", headers=ADMIN, json=dup).status_code == 400
    assert env.put("/api/knowledge/owners", headers=ADMIN, json=payload).status_code == 200
    assert "kb:evaluate" in env.get("/api/knowledge/me", headers=_as(BOB)).json()["data"]["kb_roles"]
    from pipelines.governance.registry import load_registry_from_db

    assert load_registry_from_db().owner("@core-owner-architecture").discord_webhook == "https://example.invalid/hook"
    assert [e["type"] for e in _events(env)["events"]][-1] == "owners.updated"


def test_governance_features_need_the_database(env, monkeypatch, tmp_path):
    monkeypatch.delenv("GOVERNANCE_DATABASE_URL")
    monkeypatch.setenv("CANDIDATES_BACKEND", "file")
    monkeypatch.setenv("CANDIDATES_DIR", str(tmp_path / "file-queue"))
    assert env.get("/api/knowledge/events", headers=CLIENT).status_code == 503
    assert env.get("/api/knowledge/reviews/inbox", headers=_as(ALICE)).status_code == 200  # derived from the queue
