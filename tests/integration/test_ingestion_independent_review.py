"""A mandatory control is never promoted on one person's word (issue #91).

A maintainer can decide any row of a framework ingestion and also apply the ingestion: until now the same person could accept
a ``severity: mandatory`` control and promote it, with no independent eye. The maintainer who applies must now be someone other
than the reviewer who decided each mandatory row; the rows they decided themselves stay pending for another maintainer.
"""

import shutil
from pathlib import Path

import pytest
import yaml
from starlette.testclient import TestClient

from mcp_server.core.config import server_config
from pipelines.frameworks.api import requires_independent_apply
from tests.integration.nis2_baseline import rewind_nis2

ROOT = Path(__file__).parent.parent.parent
EXCERPT = ROOT / "tests" / "fixtures" / "frameworks" / "nis2_excerpt.txt"
CLIENT = {"Authorization": "Bearer archinex-token"}
SEC, MAINT, MAINT2 = "sec@example.org", "maint@example.org", "maint2@example.org"
BASE = "/api/frameworks/ingestions"
ROWS = ("NIS2-ART21-2B", "NIS2-ART21-2C", "NIS2-ART23-4")


def _as(email: str) -> dict:
    return {**CLIENT, "X-Actor-Email": email}


@pytest.fixture
def env(tmp_path, monkeypatch):
    kb = tmp_path / "kb"
    shutil.copytree(ROOT / "data" / "kb", kb)
    rewind_nis2(kb)
    owners = yaml.safe_load((kb / "owners.yaml").read_text(encoding="utf-8"))
    owners["owners"]["@security-compliance-team"]["email"] = SEC
    owners["owners"]["@maintainers"] = {"email": MAINT, "roles": ["kb:maintain"]}
    owners["owners"]["@maintainers-2"] = {"email": MAINT2, "roles": ["kb:maintain"]}
    (kb / "owners.yaml").write_text(yaml.safe_dump(owners), encoding="utf-8")
    monkeypatch.setattr(server_config, "kb_dir", kb)
    monkeypatch.setenv("CANDIDATES_DIR", str(tmp_path / "candidates"))
    monkeypatch.setenv("SERVER_TOKEN", "demo-token")
    monkeypatch.setenv("ENGAGEMENT_TOKENS", "archinex-token:kb:review,kb:delegate")
    monkeypatch.setenv("CANDIDATES_BACKEND", "sql")
    monkeypatch.setenv("GOVERNANCE_DATABASE_URL", f"sqlite:///{tmp_path / 'gov.db'}")
    monkeypatch.delenv("LLM_ENDPOINT", raising=False)
    monkeypatch.delenv("LLMOPS_REQUIRE_SIGNED_ACTOR", raising=False)
    import mcp_server.core.notifier as notifier

    monkeypatch.setattr(notifier, "notify_owner", lambda owner, event, c: ["log"])
    monkeypatch.setattr(notifier, "notify_consumers", lambda event, payload: ["log"])
    from pipelines.governance.migrate import migrate_governance
    from pipelines.governance.store import dispose_engines

    dispose_engines()
    migrate_governance(kb, tmp_path / "none", eval_dataset=None)
    from mcp_server.main import create_starlette_app

    client = TestClient(create_starlette_app())
    res = client.post(BASE, headers=_as(MAINT), data={"framework": "NIS2", "version": "2022/2555"},
                      files={"file": ("nis2_excerpt.txt", EXCERPT.read_bytes(), "text/plain")})
    assert res.status_code == 201, res.text
    yield {"client": client, "iid": res.json()["data"]["id"], "kb": kb}
    dispose_engines()


def _decide(env, req, email, decision="accept"):
    res = env["client"].patch(f"{BASE}/{env['iid']}/rows/{req}", headers=_as(email), json={"decision": decision, "comment": "ok"})
    assert res.status_code == 200, res.text


def _apply(env, email):
    return env["client"].post(f"{BASE}/{env['iid']}/apply", headers=_as(email))


def _validated_by(env, req):
    """Who validated the control in the knowledge base: ``None`` when it is not there, ``[]`` when nobody did yet."""
    path = env["kb"] / "controls" / "NIS2" / f"{req}.md"
    if not path.exists():
        return None
    return yaml.safe_load(path.read_text(encoding="utf-8").split("---")[1]).get("validated_by") or []


def test_the_maintainer_who_decided_mandatory_rows_cannot_apply_them(env):
    for req in ROWS:
        _decide(env, req, MAINT)
    refused = _apply(env, MAINT)
    assert refused.status_code == 409, refused.text
    assert "separation_of_duties" in refused.text and all(req in refused.text for req in ROWS)
    # Nothing was promoted, and the rows are still waiting.
    assert [_validated_by(env, req) for req in ROWS] == [[], [], None]
    detail = env["client"].get(f"{BASE}/{env['iid']}", headers=CLIENT).json()["data"]
    assert detail["decided"] == 3 and detail["status"] == "reviewing"

    # Another maintainer applies them: that is the independent eye.
    applied = _apply(env, MAINT2)
    assert applied.status_code == 200, applied.text
    assert sorted(applied.json()["data"]["promoted"]) == sorted(ROWS) and applied.json()["data"]["failed"] == []
    assert all(_validated_by(env, req) for req in ROWS)


def test_rows_decided_by_someone_else_are_applied_and_the_others_wait(env):
    _decide(env, "NIS2-ART23-4", SEC)
    _decide(env, "NIS2-ART21-2B", MAINT)
    out = _apply(env, MAINT)
    assert out.status_code == 200, out.text
    data = out.json()["data"]
    assert data["promoted"] == ["NIS2-ART23-4"]
    assert [f["requirement"] for f in data["failed"]] == ["NIS2-ART21-2B"] and "separation_of_duties" in data["failed"][0]["reason"]
    assert _validated_by(env, "NIS2-ART23-4") == ["@security-compliance-team"] and _validated_by(env, "NIS2-ART21-2B") == []

    later = _apply(env, MAINT2)
    assert later.status_code == 200 and later.json()["data"]["promoted"] == ["NIS2-ART21-2B"]


def test_a_rejection_needs_no_second_person(env):
    _decide(env, "NIS2-ART21-2B", MAINT, decision="reject")
    out = _apply(env, MAINT)
    assert out.status_code == 200, out.text
    assert out.json()["data"]["rejected"] == ["NIS2-ART21-2B"] and out.json()["data"]["promoted"] == []


def test_only_mandatory_accepted_rows_need_an_independent_applier():
    mandatory = {"decision": "accept", "reviewer": "@m", "draft": "---\nseverity: mandatory\n---\nbody"}
    assert requires_independent_apply(mandatory, "@m")
    assert requires_independent_apply({**mandatory, "decision": "amend"}, "@m")
    assert not requires_independent_apply(mandatory, "@other")  # someone else applies
    assert not requires_independent_apply({**mandatory, "decision": "reject"}, "@m")  # nothing is promoted
    assert not requires_independent_apply({**mandatory, "draft": "---\nseverity: recommended\n---\nbody"}, "@m")
    assert requires_independent_apply({**mandatory, "draft": "---\nid: X\n---\nno severity"}, "@m")  # unknown counts as mandatory
