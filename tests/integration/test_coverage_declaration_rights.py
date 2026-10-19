"""Who may declare a framework covered (issue #90).

``POST /api/frameworks/{fw}/coverage-declaration`` used to ask only for a registered expert: the owner of an unrelated domain
could declare NIS2 covered. The declarer must now own the primary domain of the framework (or hold ``kb:maintain``, or hold
the review role on that domain through an assertion or a delegation). Every decision is audited.
"""

import shutil
from pathlib import Path

import pytest
import yaml
from starlette.testclient import TestClient

from mcp_server.core.assertion import (
    generate_ed25519_keypair,
    get_jwks_registry,
    get_replay_store,
    sign_actor_assertion,
)
from mcp_server.core.config import server_config
from pipelines.frameworks.coverage import framework_primary_domain

ROOT = Path(__file__).parent.parent.parent
CLIENT = {"Authorization": "Bearer archinex-token"}
SEC, MAINT, OTHER = "sec@example.org", "maint@example.org", "bob@example.org"
URL = "/api/frameworks/NIS2/coverage-declaration"


def _as(email: str) -> dict:
    return {**CLIENT, "X-Actor-Email": email}


@pytest.fixture
def env(tmp_path, monkeypatch):
    kb = tmp_path / "kb"
    shutil.copytree(ROOT / "data" / "kb", kb)
    owners = yaml.safe_load((kb / "owners.yaml").read_text(encoding="utf-8"))
    owners["owners"]["@security-compliance-team"]["email"] = SEC
    owners["owners"]["@ciso-office"]["email"] = OTHER  # a registered expert who owns other domains
    owners["owners"]["@maintainers"] = {"email": MAINT, "roles": ["kb:maintain"]}
    (kb / "owners.yaml").write_text(yaml.safe_dump(owners), encoding="utf-8")
    monkeypatch.setattr(server_config, "kb_dir", kb)
    monkeypatch.setenv("CANDIDATES_DIR", str(tmp_path / "candidates"))
    monkeypatch.setenv("CANDIDATES_BACKEND", "file")
    monkeypatch.setenv("SERVER_TOKEN", "demo-token")
    monkeypatch.setenv("ENGAGEMENT_TOKENS", "archinex-token:kb:review,kb:delegate")
    monkeypatch.delenv("LLMOPS_REQUIRE_SIGNED_ACTOR", raising=False)
    monkeypatch.delenv("ARCHINEX_JWKS", raising=False)
    import mcp_server.core.notifier as notifier

    monkeypatch.setattr(notifier, "notify_owner", lambda owner, event, c: ["log"])
    monkeypatch.setattr(notifier, "notify_consumers", lambda event, payload: ["log"])
    registry = get_jwks_registry()
    registry.clear()
    get_replay_store().clear()
    key, jwk = generate_ed25519_keypair(kid="rights")
    registry.add_jwk(jwk)
    from mcp_server.main import create_starlette_app

    yield {"client": TestClient(create_starlette_app()), "kb": kb, "key": key}
    registry.clear()
    get_replay_store().clear()


def test_the_primary_domain_of_a_framework_is_the_one_its_controls_use_most(env):
    assert framework_primary_domain("NIS2", env["kb"]) == "security-governance"
    assert framework_primary_domain("nis2", env["kb"]) == "security-governance"  # the framework name is not case sensitive
    assert framework_primary_domain("NOT-A-FRAMEWORK", env["kb"]) is None


def test_an_explicit_primary_domain_wins(env):
    path = env["kb"] / "controls" / "frameworks.yaml"
    meta = yaml.safe_load(path.read_text(encoding="utf-8"))
    meta["NIS2"]["primary_domain"] = "iam"
    path.write_text(yaml.safe_dump(meta, allow_unicode=True), encoding="utf-8")
    assert framework_primary_domain("NIS2", env["kb"]) == "iam"


def test_the_owner_of_an_unrelated_domain_cannot_declare(env):
    refused = env["client"].post(URL, headers=_as(OTHER))
    assert refused.status_code == 403, refused.text
    assert "security-governance" in refused.json()["reason"]


def test_the_owner_of_the_primary_domain_and_a_maintainer_can(env):
    for email, handle in ((SEC, "@security-compliance-team"), (MAINT, "@maintainers")):
        res = env["client"].post(URL, headers=_as(email))
        assert res.status_code == 200, res.text
        assert res.json()["data"]["declared_by"] == handle


def test_a_domain_role_in_a_signed_assertion_is_enough(env):
    """RBAC 1.37: the review role on the domain, granted by the signer, replaces ownership of it."""
    token = sign_actor_assertion(env["key"], sub=OTHER, kid="rights", email=OTHER,
                                 domain_roles={"security-governance": ["kb:review"]})
    res = env["client"].post(URL, headers={**CLIENT, "X-Actor-Token": token})
    assert res.status_code == 200, res.text
    denied_token = sign_actor_assertion(env["key"], sub=OTHER, kid="rights", email=OTHER,
                                        domain_roles={"iam/*": ["kb:review"]})
    res = env["client"].post(URL, headers={**CLIENT, "X-Actor-Token": denied_token})
    assert res.status_code == 403


def test_every_decision_is_audited_with_the_declarer(env):
    env["client"].post(URL, headers=_as(OTHER))
    env["client"].post(URL, headers=_as(SEC))
    events = env["client"].get("/api/knowledge/audit?action=declare_framework_coverage", headers=CLIENT).json()["data"]["events"]
    seen = {(e["actor"], e["outcome"], e["resource"]) for e in events}
    assert ("@ciso-office", "denied", "NIS2") in seen and ("@security-compliance-team", "allowed", "NIS2") in seen
