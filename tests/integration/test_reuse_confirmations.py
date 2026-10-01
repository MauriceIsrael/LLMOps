"""Reuse of validated knowledge (contract 1.10): the server refuses any confirmation that skips the hypotheses."""

import hashlib
import shutil
from pathlib import Path

import pytest
import yaml
from starlette.testclient import TestClient

from mcp_server.core.config import server_config
from tests.integration.test_similarity import CLIENT, MODEL, encode

ROOT = Path(__file__).parent.parent.parent
ALICE, MAINT, ARCHITECT = "alice@example.org", "maint@example.org", "architect@customer-side.example"
ASSUMPTIONS = ["The control plane handles fewer than 10000 managed devices.",
               "Every site keeps an out-of-band access path to its routers."]
BASE = "/api/knowledge/reuse-confirmations"
FP = hashlib.sha256(b"restoration of network configuration after an outage").hexdigest()


def _as(email: str) -> dict:
    return {**CLIENT, "X-Actor-Email": email}


def _set_assumptions(kb: Path, ref_file: str, assumptions):
    path = kb / ref_file
    text = path.read_text(encoding="utf-8")
    fm_text, body = text.split("---\n", 2)[1], text.split("---\n", 2)[2]
    fm = yaml.safe_load(fm_text)
    if assumptions is None:
        fm.pop("assumptions", None)
    else:
        fm["assumptions"] = assumptions
    path.write_text("---\n" + yaml.safe_dump(fm, sort_keys=False, allow_unicode=True) + "---\n" + body, encoding="utf-8")


@pytest.fixture
def env(tmp_path, monkeypatch):
    kb = tmp_path / "kb"
    shutil.copytree(ROOT / "data" / "kb", kb)
    owners = yaml.safe_load((kb / "owners.yaml").read_text())
    owners["owners"]["@core-owner-architecture"]["email"] = ALICE
    owners["owners"]["@maintainers"] = {"email": MAINT, "roles": ["kb:maintain"]}
    (kb / "owners.yaml").write_text(yaml.safe_dump(owners), encoding="utf-8")
    _set_assumptions(kb, "decisions/ADR-0001.md", ASSUMPTIONS)
    monkeypatch.setattr(server_config, "kb_dir", kb)
    monkeypatch.setenv("SERVER_TOKEN", "demo-token")
    monkeypatch.setenv("ENGAGEMENT_TOKENS", "archinex-token:kb:review,kb:delegate")
    monkeypatch.setenv("CANDIDATES_BACKEND", "sql")
    monkeypatch.setenv("GOVERNANCE_DATABASE_URL", f"sqlite:///{tmp_path / 'gov.db'}")
    import mcp_server.core.notifier as notifier

    monkeypatch.setattr(notifier, "notify_owner", lambda owner, event, c: ["log"])
    from pipelines.governance.migrate import migrate_governance
    from pipelines.governance.store import dispose_engines

    dispose_engines()
    migrate_governance(kb, tmp_path / "none", eval_dataset=None)
    from mcp_server.main import create_starlette_app

    yield {"client": TestClient(create_starlette_app()), "kb": kb}
    dispose_engines()


def _body(**over):
    body = {"subject_fingerprint": FP, "subject_label": "Restoration of network configuration after an outage",
            "matched_ref": "ADR-0001", "model": "toy-bow", "scores": {"vector": 0.93}, "outcome": "reused",
            "assumptions": [{"text": a, "status": "holds"} for a in ASSUMPTIONS]}
    body.update(over)
    return body


def _post(env, body, email=ARCHITECT):
    return env["client"].post(BASE, headers=_as(email) if email else CLIENT, json=body)


def test_a_person_is_required_and_the_judgement_is_attributed(env):
    assert _post(env, _body(), email=None).status_code == 403  # a system token cannot confirm a reuse
    res = _post(env, _body())
    assert res.status_code == 201, res.text
    rec = res.json()["data"]
    assert rec["actor"] == f"email:{ARCHITECT}" and rec["outcome"] == "reused" and len(rec["assumptions"]) == 2
    alice = _post(env, _body(), email=ALICE).json()["data"]
    assert alice["actor"] == "@core-owner-architecture"  # a registered expert is recorded by handle


def test_reused_needs_every_documented_assumption_judged_and_holding(env):
    one_missing = _body(assumptions=[{"text": ASSUMPTIONS[0], "status": "holds"}])
    assert _post(env, one_missing).status_code == 409
    assert _post(env, _body(assumptions=[])).status_code == 409
    other = _body(assumptions=[{"text": ASSUMPTIONS[0], "status": "holds"}, {"text": "Something else entirely.", "status": "holds"}])
    assert _post(env, other).status_code == 409  # not the asset's own hypotheses
    unknown = _body(assumptions=[{"text": ASSUMPTIONS[0], "status": "holds"}, {"text": ASSUMPTIONS[1], "status": "unknown"}])
    refused = _post(env, unknown)
    assert refused.status_code == 409 and "reused_with_exception" in refused.text
    assert _post(env, _body(assumptions=[{"text": ASSUMPTIONS[0], "status": "nope"}])).status_code == 400


def test_exception_is_motivated_and_rejections_are_explained(env):
    failing = [{"text": ASSUMPTIONS[0], "status": "holds"}, {"text": ASSUMPTIONS[1], "status": "does_not_hold"}]
    assert _post(env, _body(outcome="reused_with_exception", assumptions=failing)).status_code == 400  # no comment
    ok = _post(env, _body(outcome="reused_with_exception", assumptions=failing,
                          comment="Sites are small; the missing path is covered by a supervised manual procedure."))
    assert ok.status_code == 201
    assert _post(env, _body(outcome="reused_with_exception", comment="x" * 20)).status_code == 409  # all hold: not an exception
    assert _post(env, _body(outcome="rejected_assumption_fails", assumptions=failing)).status_code == 201
    all_hold = _body(outcome="rejected_assumption_fails")
    assert _post(env, all_hold).status_code == 409  # nothing fails
    assert _post(env, _body(outcome="rejected_not_same", assumptions=[])).status_code == 400  # a reason is required
    assert _post(env, _body(outcome="rejected_not_same", assumptions=[], comment="Different scope: access, not restoration.")).status_code == 201
    assert _post(env, _body(outcome="deferred", assumptions=[])).status_code == 201
    assert _post(env, _body(outcome="whatever")).status_code == 400


def test_an_asset_without_documented_assumptions_cannot_be_reused(env):
    refused = _post(env, _body(matched_ref="P-002", assumptions=[]))
    assert refused.status_code == 409 and "documents no assumption" in refused.text
    assert _post(env, _body(matched_ref="P-002", outcome="deferred", assumptions=[])).status_code == 201  # deferring is fine
    assert _post(env, _body(matched_ref="NOPE-1", outcome="deferred", assumptions=[])).status_code == 400


def test_a_superseded_asset_cannot_be_reused_but_can_be_rejected(env):
    path = env["kb"] / "decisions" / "ADR-0001.md"
    path.write_text(path.read_text().replace("status: active", "status: superseded", 1))
    assert _post(env, _body()).status_code == 409
    assert _post(env, _body(outcome="rejected_not_same", assumptions=[], comment="Superseded decision.")).status_code == 201


def test_the_subject_label_must_be_anonymised(env):
    assert _post(env, _body(subject_label="Restoration at 10.12.0.1 for the site")).status_code == 400
    assert _post(env, _body(subject_label="Mail from someone@customer.example about restoration")).status_code == 400
    assert _post(env, _body(subject_label="")).status_code == 400
    assert _post(env, _body(subject_fingerprint="abc")).status_code == 400


def _deposit(env):
    client = env["client"]
    pending = client.get("/api/knowledge/embeddings/pending?model=toy-bow", headers=CLIENT).json()["data"]["pending"]
    client.put("/api/knowledge/embeddings", headers=CLIENT, json={**MODEL, "items": [
        {"ref": p["ref"], "text_sha256": p["text_sha256"], "vector": encode(p["text"])} for p in pending]})
    return {p["ref"]: p for p in pending}


def test_similar_remembers_judgements_and_flags_outdated_confirmations(env):
    client = env["client"]
    texts = _deposit(env)
    query = {"model": "toy-bow", "vector": encode(texts["ADR-0001"]["text"]), "subject_fingerprint": FP, "top_k": 3}
    first = client.post("/api/knowledge/similar", headers=CLIENT, json=query).json()["data"]["results"][0]
    assert first["ref"] == "ADR-0001" and first["assumptions"] == ASSUMPTIONS and first["assumptions_documented"] is True
    assert first["judgements"] == [] and first["previous_confirmation_outdated"] is False

    assert _post(env, _body(outcome="rejected_not_same", assumptions=[], comment="Different scope.")).status_code == 201
    assert _post(env, _body()).status_code == 201
    again = client.post("/api/knowledge/similar", headers=CLIENT, json=query).json()["data"]["results"][0]
    assert [j["outcome"] for j in again["judgements"]] == ["reused", "rejected_not_same"]  # newest first
    assert again["previous_confirmation_outdated"] is False
    assert again["reuse_summary"] == {"reused": 1, "rejected_not_same": 1}
    other = client.post("/api/knowledge/similar", headers=CLIENT,
                        json={**query, "subject_fingerprint": hashlib.sha256(b"another subject").hexdigest()}).json()["data"]["results"][0]
    assert other["judgements"] == []  # judgements belong to a subject; the summary is global

    # The decision's hypotheses change: the earlier confirmation no longer stands.
    _set_assumptions(env["kb"], "decisions/ADR-0001.md", [*ASSUMPTIONS, "A new hypothesis about the supplier."])
    changed = client.post("/api/knowledge/similar", headers=CLIENT, json=query).json()["data"]["results"][0]
    assert changed["previous_confirmation_outdated"] is True
    assert _post(env, _body()).status_code == 409  # the old hypotheses are not the current ones: judge the new list


def test_history_filters_and_scope(env):
    _post(env, _body())
    _post(env, _body(outcome="deferred", assumptions=[]))
    client = env["client"]
    assert client.get(BASE, headers={"Authorization": "Bearer demo-token"}).status_code == 403
    assert len(client.get(BASE, headers=CLIENT).json()["data"]) == 2
    only = client.get(f"{BASE}?outcome=deferred", headers=CLIENT).json()["data"]
    assert [r["outcome"] for r in only] == ["deferred"]
    assert client.get(f"{BASE}?outcome=bogus", headers=CLIENT).status_code == 400
    assert len(client.get(f"{BASE}?matched_ref=ADR-0001&subject_fingerprint={FP}", headers=CLIENT).json()["data"]) == 2


def test_a_decision_candidate_without_assumptions_is_warned(env):
    client = env["client"]
    adr = "ADR-" + "0099"  # a literal would be read as a (dangling) reference to a real ADR
    decision = """---
id: {adr}
title: Use a dedicated out-of-band network for restoration
type: decision
status: proposed
confidence: assumed
phase: [BUILD]
domain: [network-automation]
{extra}---

# {adr} — Use a dedicated out-of-band network

## Context
Restoration must keep working during the outage it restores.

## Options considered
Shared data network; dedicated out-of-band network.

## Decision
Dedicated out-of-band network.

## Consequences
Extra circuits and cabling.
"""
    def schema_check(extra):
        res = client.post("/api/knowledge/candidates/validate", headers=CLIENT, json={
            "kind": "new_asset", "asset_type": "decision", "title": "OOB network decision",
            "proposed_content": decision.format(extra=extra, adr=adr), "source": {"system": "archinex"}})
        assert res.status_code == 200, res.text
        return next(c for c in res.json()["data"]["checks"] if c["name"] == "schema")

    warned = schema_check("")
    assert warned["status"] == "warn" and "assumptions" in warned["detail"]
    ok = schema_check("assumptions:\n  - The control plane handles fewer than 10000 managed devices.\n")
    assert ok["status"] == "pass"
