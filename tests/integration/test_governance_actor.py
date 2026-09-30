"""Identity by e-mail (contract 1.4) and the SQL governance store, on a temporary KB.

A client holding a ``kb:delegate`` token (Archinex) tells LLMOps which expert it acts for
with ``X-Actor-Email``; the same cycle then runs on the file backend and on SQLite.
"""

import shutil
from pathlib import Path

import pytest
import yaml
from starlette.testclient import TestClient

from mcp_server.core.config import server_config
from tests.integration.test_kb_candidates_api import PATTERN

ROOT = Path(__file__).parent.parent.parent
DEMO = {"Authorization": "Bearer demo-token"}
CLIENT = {"Authorization": "Bearer archinex-token"}
PLAIN = {"Authorization": "Bearer reviewer-token"}


def _as(email: str, headers=CLIENT) -> dict:
    return {**headers, "X-Actor-Email": email}


@pytest.fixture(params=["file", "sql"])
def env(request, tmp_path, monkeypatch):
    kb = tmp_path / "kb"
    shutil.copytree(ROOT / "data" / "kb", kb)
    owners = yaml.safe_load((kb / "owners.yaml").read_text())
    owners["owners"]["@core-owner-architecture"]["email"] = "Alice@example.org"
    owners["owners"]["@ciso-office"]["email"] = "bob@example.org"
    owners["owners"]["@maintainers"] = {"email": "maint@example.org", "roles": ["kb:maintain"]}
    (kb / "owners.yaml").write_text(yaml.safe_dump(owners), encoding="utf-8")
    monkeypatch.setattr(server_config, "kb_dir", kb)
    monkeypatch.setenv("CANDIDATES_DIR", str(tmp_path / "candidates"))
    monkeypatch.setenv("SERVER_TOKEN", "demo-token")
    monkeypatch.setenv("ENGAGEMENT_TOKENS", "archinex-token:kb:review,kb:delegate;reviewer-token:kb:review")
    monkeypatch.delenv("GOVERNANCE_DATABASE_URL", raising=False)
    monkeypatch.setenv("CANDIDATES_BACKEND", request.param)
    if request.param == "sql":
        monkeypatch.setenv("GOVERNANCE_DATABASE_URL", f"sqlite:///{tmp_path / 'gov.db'}")
    for var in ("OWNER_NOTIFICATION_WEBHOOK", "NOTIFICATION_WEBHOOK_URL", "KB_CONSUMER_WEBHOOKS", "KB_CONSUMER_NTFY_TOPIC"):
        monkeypatch.delenv(var, raising=False)
    import mcp_server.core.notifier as notifier

    monkeypatch.setattr(notifier, "notify_owner", lambda owner, event, c: ["log"])
    monkeypatch.setattr(notifier, "notify_consumers", lambda event, payload: ["log"])
    from pipelines.governance.store import dispose_engines

    dispose_engines()
    from mcp_server.main import create_starlette_app

    yield {"client": TestClient(create_starlette_app()), "kb": kb, "backend": request.param, "tmp": tmp_path}
    dispose_engines()


def _submit(client) -> dict:
    res = client.post("/api/knowledge/candidates", headers=CLIENT, json={
        "kind": "new_asset", "asset_type": "pattern", "title": "Out-of-band management network",
        "proposed_content": PATTERN, "source": {"system": "archinex", "engagement": "eng-alpha"},
    })
    assert res.status_code == 201, res.text
    return res.json()["data"]


def test_me_requires_a_delegating_token_and_a_registered_email(env):
    client = env["client"]
    assert client.get("/api/knowledge/me", headers=CLIENT).status_code == 403  # no header
    assert client.get("/api/knowledge/me", headers=_as("alice@example.org", PLAIN)).status_code == 403  # no kb:delegate
    assert client.get("/api/knowledge/me", headers=_as("nobody@example.org")).status_code == 403
    res = client.get("/api/knowledge/me", headers=_as("alice@example.org"))  # case-insensitive
    assert res.status_code == 200
    me = res.json()["data"]
    assert me["handle"] == "@core-owner-architecture" and "kb:review" in me["kb_roles"]
    assert me["owned_domains"] and me["pending_reviews"] == 0
    maint = client.get("/api/knowledge/me", headers=_as("maint@example.org")).json()["data"]
    assert "kb:maintain" in maint["kb_roles"]


def test_review_by_actor_only_for_owned_domain(env):
    client = env["client"]
    candidate = _submit(client)
    assert candidate["status"] == "in_review", candidate["checks"]
    cid, owner = candidate["id"], candidate["assigned_owner"]
    assert owner == "@core-owner-architecture"
    url = f"/api/knowledge/candidates/{cid}"
    review = {"action": "accept", "reason": "Generic and proven"}

    # Another expert, not owner of the domain → 403 and the candidate is untouched.
    assert client.patch(url, headers=_as("bob@example.org"), json={**review, "reviewer": "@ciso-office"}).status_code == 403
    # The body cannot name someone else than the acting expert.
    assert client.patch(url, headers=_as("alice@example.org"),
                        json={**review, "reviewer": "@ciso-office"}).status_code == 403
    # Unknown e-mail → 403.
    assert client.patch(url, headers=_as("eve@example.org"), json=review).status_code == 403
    assert client.get(url, headers=CLIENT).json()["data"]["status"] == "in_review"

    # The owner, with no `reviewer` in the body, reviews as themselves.
    res = client.patch(url, headers=_as("alice@example.org"), json=review)
    assert res.status_code == 200, res.text
    done = res.json()["data"]
    assert done["status"] == "accepted" and done["review"]["reviewer"] == owner
    assert any(h["actor"] == owner and h["event"] == "accepted" for h in done["history"])
    assert "alice@example.org" not in str(done).lower()  # the e-mail is not written to the history


def test_maintainer_role_reviews_any_domain(env):
    client = env["client"]
    cid = _submit(client)["id"]
    res = client.patch(f"/api/knowledge/candidates/{cid}", headers=_as("maint@example.org"),
                       json={"action": "reject", "reason": "Out of scope"})
    assert res.status_code == 200 and res.json()["data"]["review"]["reviewer"] == "@maintainers"


def test_without_actor_the_1_3_behaviour_is_unchanged(env):
    client = env["client"]
    cid = _submit(client)["id"]
    res = client.patch(f"/api/knowledge/candidates/{cid}", headers=PLAIN,
                       json={"action": "accept", "reviewer": "@core-owner-architecture", "reason": "ok"})
    assert res.status_code == 200
    # An X-Actor-Email sent with a non-delegating token is ignored, not honoured.
    other = _submit(client)["id"]
    res = client.patch(f"/api/knowledge/candidates/{other}", headers=_as("bob@example.org", PLAIN),
                       json={"action": "accept", "reviewer": "@core-owner-architecture", "reason": "ok"})
    assert res.status_code == 200


def test_queue_survives_a_restart_on_the_sql_backend(env):
    if env["backend"] != "sql":
        pytest.skip("SQL backend only")
    first = _submit(env["client"])
    from mcp_server.main import create_starlette_app
    from pipelines.governance.store import dispose_engines

    dispose_engines()  # simulated restart: new engine, same database
    client = TestClient(create_starlette_app())
    assert client.get(f"/api/knowledge/candidates/{first['id']}", headers=CLIENT).status_code == 200
    second = _submit(client)
    assert second["id"] != first["id"] and second["id"].endswith("0002")
    listed = client.get("/api/knowledge/candidates?status=in_review", headers=CLIENT).json()["data"]
    assert {c["id"] for c in listed} == {first["id"], second["id"]}
