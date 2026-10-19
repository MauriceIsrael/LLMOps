"""Signed actor assertions through HTTP, and the strict mode that refuses the raw ``X-Actor-Email`` header (issue #144).

Without the strict mode (the default, kept for the contract server and the tests) the raw header still names the acting
expert behind a ``kb:delegate`` token. With ``LLMOPS_REQUIRE_SIGNED_ACTOR=true`` a request that names its actor by the raw
header alone is refused (401 ``signed_actor_required``), audited, and only a signed assertion identifies a person.
"""

import json
import shutil
import time
from pathlib import Path

import jwt
import pytest
import yaml
from starlette.testclient import TestClient

from mcp_server.core.assertion import (
    generate_ed25519_keypair,
    get_jwks_registry,
    get_replay_store,
    get_revocation_store,
    sign_actor_assertion,
)
from mcp_server.core.config import server_config

ROOT = Path(__file__).parent.parent.parent
SERVICE = {"Authorization": "Bearer service-token"}
ALICE, MAINT = "alice@example.org", "maint@example.org"
KID = "archinex-test"

PATTERN = """---
id: PAT-098
title: Break-glass access path for the automation chain
type: pattern
status: draft
confidence: assumed
phase: [BUILD, RUN]
domain: [network-automation]
related: [P-009]
---

# PAT-098 — Break-glass access path for the automation chain

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
    owners = yaml.safe_load((kb / "owners.yaml").read_text(encoding="utf-8"))
    owners["owners"]["@core-owner-architecture"]["email"] = ALICE
    owners["owners"]["@maintainers"] = {"email": MAINT, "roles": ["kb:maintain"]}
    (kb / "owners.yaml").write_text(yaml.safe_dump(owners), encoding="utf-8")
    monkeypatch.setattr(server_config, "kb_dir", kb)
    monkeypatch.setenv("CANDIDATES_DIR", str(tmp_path / "candidates"))
    monkeypatch.setenv("CANDIDATES_BACKEND", "file")
    monkeypatch.setenv("SERVER_TOKEN", "demo-token")
    monkeypatch.setenv("ENGAGEMENT_TOKENS", "service-token:kb:review,kb:delegate")
    for var in ("LLMOPS_REQUIRE_SIGNED_ACTOR", "ARCHINEX_JWKS", "ARCHINEX_JWKS_URL", "ARCHINEX_ASSERTION_MAX_TTL",
                "ARCHINEX_CLOCK_SKEW", "OWNER_NOTIFICATION_WEBHOOK", "NOTIFICATION_WEBHOOK_URL", "KB_CONSUMER_WEBHOOKS"):
        monkeypatch.delenv(var, raising=False)
    import mcp_server.core.notifier as notifier

    monkeypatch.setattr(notifier, "notify_owner", lambda owner, event, c: ["log"])
    monkeypatch.setattr(notifier, "notify_consumers", lambda event, payload: ["log"])

    registry = get_jwks_registry()
    registry.clear()
    get_replay_store().clear()
    get_revocation_store().clear()
    private_key, jwk = generate_ed25519_keypair(kid=KID)
    registry.add_jwk(jwk)

    from mcp_server.main import create_starlette_app

    yield {"client": TestClient(create_starlette_app()), "key": private_key, "jwk": jwk, "monkeypatch": monkeypatch}
    registry.clear()
    get_replay_store().clear()
    get_revocation_store().clear()


def _assertion(env, email, **kwargs):
    return sign_actor_assertion(env["key"], sub=email, kid=KID, email=email, **kwargs)


def _signed(env, email, **kwargs):
    return {**SERVICE, "X-Actor-Token": _assertion(env, email, **kwargs)}


def _legacy(email):
    return {**SERVICE, "X-Actor-Email": email}


def _strict(env):
    env["monkeypatch"].setenv("LLMOPS_REQUIRE_SIGNED_ACTOR", "true")


# ------------------------------------------------------------------ strict mode


def test_default_mode_keeps_the_raw_header(env):
    res = env["client"].get("/api/knowledge/me", headers=_legacy(ALICE))
    assert res.status_code == 200 and res.json()["data"]["handle"] == "@core-owner-architecture"


def test_strict_mode_refuses_the_raw_header_and_audits_it(env):
    _strict(env)
    res = env["client"].get("/api/knowledge/me", headers=_legacy(ALICE))
    assert res.status_code == 401
    body = res.json()
    assert body["error"] == "signed_actor_required" and "X-Actor-Token" in body["reason"]

    audit = env["client"].get("/api/knowledge/audit?outcome=denied", headers=SERVICE).json()
    events = audit["data"]["events"]
    assert any(e["actor"] == ALICE and e["outcome"] == "denied" and e["auth_method"] == "header"
               and e["detail"].get("code") == "signed_actor_required" for e in events), events


def test_strict_mode_accepts_a_valid_assertion(env):
    _strict(env)
    res = env["client"].get("/api/knowledge/me", headers=_signed(env, ALICE))
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["handle"] == "@core-owner-architecture" and data["auth_method"] == "assertion"


def test_strict_mode_ignores_a_raw_header_next_to_a_valid_assertion(env):
    """The assertion names the actor; a different e-mail in the raw header must not take over."""
    _strict(env)
    res = env["client"].get("/api/knowledge/me", headers={**_signed(env, ALICE), "X-Actor-Email": MAINT})
    assert res.status_code == 200 and res.json()["data"]["handle"] == "@core-owner-architecture"


def test_strict_mode_leaves_requests_without_an_actor_alone(env):
    _strict(env)
    assert env["client"].get("/health").status_code == 200
    assert env["client"].get("/.well-known/jwks.json").status_code == 200
    assert env["client"].get("/api/knowledge/context?subject=resilience", headers=SERVICE).status_code != 401


def test_a_bad_assertion_is_refused_in_both_modes(env):
    forged = jwt.encode({"iss": "archinex", "aud": "knowledge-hub", "sub": ALICE, "email": ALICE,
                         "jti": "forged-1", "exp": int(time.time()) + 60},
                        __import__("cryptography.hazmat.primitives.asymmetric.ed25519", fromlist=["x"]).Ed25519PrivateKey.generate(),
                        algorithm="EdDSA", headers={"kid": KID})
    for strict in (False, True):
        if strict:
            _strict(env)
        res = env["client"].get("/api/knowledge/me", headers={**SERVICE, "X-Actor-Token": forged})
        assert res.status_code == 401 and res.json()["error"] == "invalid_signature"


def test_an_assertion_cannot_be_replayed(env):
    _strict(env)
    headers = _signed(env, ALICE)
    assert env["client"].get("/api/knowledge/me", headers=headers).status_code == 200
    again = env["client"].get("/api/knowledge/me", headers=headers)
    assert again.status_code == 403 and again.json()["error"] == "replay_detected"


def test_separation_of_duties_holds_in_strict_mode(env):
    """The author of a candidate cannot accept it, whoever signs; another expert can."""
    _strict(env)
    client = env["client"]
    sub = client.post("/api/knowledge/candidates", headers=_signed(env, ALICE), json={
        "kind": "new_asset", "asset_type": "pattern", "title": "Break-glass access path",
        "proposed_content": PATTERN, "source": {"system": "archinex", "engagement": "strict-test"}})
    assert sub.status_code == 201, sub.text
    cid = sub.json()["data"]["id"]
    own = client.patch(f"/api/knowledge/candidates/{cid}", headers=_signed(env, ALICE), json={"action": "accept", "reason": "mine"})
    assert own.status_code == 400 and "separation_of_duties" in json.dumps(own.json())
    other = client.patch(f"/api/knowledge/candidates/{cid}", headers=_signed(env, MAINT), json={"action": "accept", "reason": "independent"})
    assert other.status_code == 200, other.text


# ------------------------------------------------------------------ keys and lifetime


def _no_trusted_key():
    get_jwks_registry().clear()


def test_a_key_declared_in_the_environment_is_trusted(env):
    """ARCHINEX_JWKS holds the key set; an assertion signed by a key that is not declared is ``unknown_key``."""
    _no_trusted_key()
    assert env["client"].get("/api/knowledge/me", headers=_signed(env, ALICE)).status_code == 401  # nothing declared yet

    env["monkeypatch"].setenv("ARCHINEX_JWKS", json.dumps({"keys": [env["jwk"]]}))
    assert env["client"].get("/api/knowledge/me", headers=_signed(env, ALICE)).status_code == 200

    other_key, _ = generate_ed25519_keypair(kid="not-declared")
    stranger = sign_actor_assertion(other_key, sub=ALICE, kid="not-declared", email=ALICE)
    res = env["client"].get("/api/knowledge/me", headers={**SERVICE, "X-Actor-Token": stranger})
    assert res.status_code == 401 and res.json()["error"] == "unknown_key"
    assert "ARCHINEX_JWKS" in res.json()["reason"]


def test_a_key_declared_in_a_file_is_trusted_and_a_rotated_file_is_read_again(env, tmp_path):
    _no_trusted_key()
    path = tmp_path / "jwks.json"
    path.write_text(json.dumps({"keys": [env["jwk"]]}), encoding="utf-8")
    env["monkeypatch"].setenv("ARCHINEX_JWKS_FILE", str(path))
    assert env["client"].get("/api/knowledge/me", headers=_signed(env, ALICE)).status_code == 200

    new_key, new_jwk = generate_ed25519_keypair(kid="rotated")
    path.write_text(json.dumps({"keys": [env["jwk"], new_jwk]}), encoding="utf-8")
    __import__("os").utime(path, ns=(time.time_ns() + 10**9, time.time_ns() + 10**9))
    token = sign_actor_assertion(new_key, sub=ALICE, kid="rotated", email=ALICE)
    assert env["client"].get("/api/knowledge/me", headers={**SERVICE, "X-Actor-Token": token}).status_code == 200


def test_a_malformed_or_missing_key_source_trusts_nothing(env, tmp_path):
    _no_trusted_key()
    env["monkeypatch"].setenv("ARCHINEX_JWKS", "{not json")
    env["monkeypatch"].setenv("ARCHINEX_JWKS_FILE", str(tmp_path / "absent.json"))
    res = env["client"].get("/api/knowledge/me", headers=_signed(env, ALICE))
    assert res.status_code == 401 and res.json()["error"] == "unknown_key"


class _JwksServer:
    """A loopback server publishing a key set, that can be stopped to simulate an outage."""

    def __init__(self, document):
        from http.server import BaseHTTPRequestHandler, HTTPServer

        body = json.dumps(document).encode()

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        import threading

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/jwks.json"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def stop(self):
        self.server.shutdown()
        self.server.server_close()


def test_a_key_set_published_at_a_url_is_trusted_and_fails_closed(env):
    import mcp_server.core.assertion as assertion_module

    _no_trusted_key()
    server = _JwksServer({"keys": [env["jwk"]]})
    env["monkeypatch"].setenv("ARCHINEX_JWKS_URL", server.url)
    try:
        assert env["client"].get("/api/knowledge/me", headers=_signed(env, ALICE)).status_code == 200
        # Still inside the cache lifetime: an outage changes nothing yet.
        server.stop()
        assert env["client"].get("/api/knowledge/me", headers=_signed(env, ALICE)).status_code == 200
        # Past the cache lifetime and still unreachable: the keys that came from the URL are no longer trusted.
        env["monkeypatch"].setattr(assertion_module, "JWKS_URL_TTL_SECONDS", 0)
        env["monkeypatch"].setattr(assertion_module, "JWKS_URL_RETRY_SECONDS", 0)
        res = env["client"].get("/api/knowledge/me", headers=_signed(env, ALICE))
        assert res.status_code == 401 and res.json()["error"] == "unknown_key"
    finally:
        server.stop()


def test_an_unreachable_url_trusts_nothing_from_the_start(env):
    _no_trusted_key()
    env["monkeypatch"].setenv("ARCHINEX_JWKS_URL", "http://127.0.0.1:9/jwks.json")
    res = env["client"].get("/api/knowledge/me", headers=_signed(env, ALICE))
    assert res.status_code == 401 and res.json()["error"] == "unknown_key"


def test_a_plain_http_url_outside_loopback_is_not_used(env):
    _no_trusted_key()
    env["monkeypatch"].setenv("ARCHINEX_JWKS_URL", "http://keys.example.org/jwks.json")
    res = env["client"].get("/api/knowledge/me", headers=_signed(env, ALICE))
    assert res.status_code == 401 and res.json()["error"] == "unknown_key"


def test_strict_mode_without_any_key_says_so_at_startup_and_refuses_cleanly(env, caplog):
    import logging

    from mcp_server.main import create_starlette_app

    _no_trusted_key()
    _strict(env)
    with caplog.at_level(logging.ERROR, logger="mcp_server.identity"):
        client = TestClient(create_starlette_app())
    assert any("no trusted key is declared" in r.message and "ARCHINEX_JWKS_FILE" in r.message for r in caplog.records)
    res = client.get("/api/knowledge/me", headers=_signed(env, ALICE))
    assert res.status_code == 401 and res.json()["error"] == "unknown_key"
    legacy = client.get("/api/knowledge/me", headers=_legacy(ALICE))
    assert legacy.status_code == 401 and legacy.json()["error"] == "signed_actor_required"


def test_an_assertion_valid_for_too_long_is_refused(env):
    _strict(env)
    res = env["client"].get("/api/knowledge/me", headers=_signed(env, ALICE, exp_seconds=3600))
    assert res.status_code == 401 and res.json()["error"] == "lifetime_too_long"
    env["monkeypatch"].setenv("ARCHINEX_ASSERTION_MAX_TTL", "7200")
    assert env["client"].get("/api/knowledge/me", headers=_signed(env, ALICE, exp_seconds=3600)).status_code == 200


def test_a_small_clock_difference_is_tolerated(env):
    now = int(time.time())

    def token(skew):
        return jwt.encode({"iss": "archinex", "aud": "knowledge-hub", "sub": ALICE, "email": ALICE,
                           "jti": f"skew-{skew}", "iat": now + skew, "nbf": now + skew, "exp": now + skew + 300},
                          env["key"], algorithm="EdDSA", headers={"kid": KID})

    ok = env["client"].get("/api/knowledge/me", headers={**SERVICE, "X-Actor-Token": token(20)})
    assert ok.status_code == 200, ok.text  # 20 s ahead: inside the default 30 s tolerance
    late = env["client"].get("/api/knowledge/me", headers={**SERVICE, "X-Actor-Token": token(120)})
    assert late.status_code == 401
