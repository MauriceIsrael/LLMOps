"""K21 (ADR-KH-01 A10): what one engagement changes in the reference rules: justified deactivations and local rules."""

import copy
import shutil
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from mcp_server.core.config import server_config
from pipelines.engagement.access import get_access
from pipelines.engagement.snapshot import seal, verify
from pipelines.governance.store import dispose_engines

ROOT = Path(__file__).resolve().parents[2]
ARCHINEX = "arx-token"
OPERATOR = {"Authorization": "Bearer demo-token"}
EMAILS = {"admin": "ada@example.org", "decider": "dan@example.org", "contributor": "carl@example.org", "reader": "rita@example.org"}
ENG = "eng-r"
BASE = f"/api/engagements/{ENG}"
SPLIT = "TRG-active-active-split-brain"
LOCAL = {
    "trigger_id": "TRG-local-ptp-holdover", "version": 1,
    "when": [{"key": "topology.dc_count", "op": "gte", "value": 2}],
    "question": {"fr": "Quel mécanisme de secours pour la synchronisation de temps entre les sites ?", "en": "Which fallback keeps time synchronised between sites?"},
    "rationale": {"fr": "Le programme impose une dérive inférieure à 1 µs.", "en": "The programme requires drift under 1 µs."},
    "initial_level": "L1_framed", "suggested_role": "network-architect", "mandatory": False,
}


def as_(role):
    return {"Authorization": f"Bearer {ARCHINEX}", "X-Actor-Email": EMAILS[role]}


@pytest.fixture
def client(monkeypatch, tmp_path):
    snaps = tmp_path / "snaps"
    snaps.mkdir()
    shutil.copy(ROOT / "data/snapshots/latest.json", snaps / "latest.json")
    monkeypatch.setenv("SERVER_TOKEN", "demo-token")
    monkeypatch.setenv("ENGAGEMENT_TOKENS", f"{ARCHINEX}:*,eng:delegate")
    monkeypatch.setenv("GOVERNANCE_DATABASE_URL", f"sqlite:///{tmp_path}/gov.db")
    monkeypatch.setattr(server_config, "engagements_dir", tmp_path)
    from mcp_server.knowledge import tools as knowledge_tools

    monkeypatch.setattr(knowledge_tools, "SNAPSHOTS_DIR", snaps)
    dispose_engines()
    from mcp_server.main import create_starlette_app

    c = TestClient(create_starlette_app(), raise_server_exceptions=False)
    assert c.post("/api/engagements", headers=OPERATOR, json={
        "engagement": ENG, "confidentiality": "internal", "admin_email": EMAILS["admin"], "admin_handle": "@ada"}).status_code == 201
    get_access().replace_members(ENG, [
        {"email": EMAILS["admin"], "handle": "@ada", "role": "admin"}, {"email": EMAILS["decider"], "handle": "@dan", "role": "decider"},
        {"email": EMAILS["contributor"], "handle": "@carl", "role": "contributor"}, {"email": EMAILS["reader"], "handle": "@rita", "role": "reader"}], "test")
    assert c.post(f"{BASE}/subjects", headers=as_("contributor"), json={"name": "mcx-services"}).status_code == 201
    yield c
    dispose_engines()


def decide(client, count=2, mode="active-active", supersedes=None):
    facts = [{"key": "topology.dc_count", "value": count, "source_excerpt": f"{count} sites"}]
    if mode:
        facts.append({"key": "topology.mode", "value": mode, "source_excerpt": mode})
    body = {"subject": "mcx-services", "decision": "Topology", "rationale": "Availability.", "reversibility": "costly", "facts": facts}
    if supersedes:
        body["supersedes"] = supersedes
    d = client.post(f"{BASE}/decisions", headers=as_("contributor"), json=body).json()["data"]["decision"]
    out = client.post(f"{BASE}/decisions/{d['id']}/assert", headers=as_("admin"))
    assert out.status_code == 200, out.text
    return d, out.json()["data"]


def derived(client):
    res = client.get(f"{BASE}/lineage", headers=as_("reader"))
    assert res.status_code == 200, res.text
    return {i["trigger_id"]: i for i in res.json()["data"]["derived"]}


def rules(client):
    res = client.get(f"{BASE}/rules", headers=as_("reader"))
    assert res.status_code == 200, res.text
    return res.json()["data"]


def audit(client):
    return client.get(f"{BASE}/audit", headers=as_("admin")).json()["data"]["events"]


# --- deactivating a reference rule ---------------------------------------------------------------------------------


def test_the_overview_lists_the_reference_rules_and_which_are_deactivated(client):
    data = rules(client)
    assert {r["trigger_id"] for r in data["reference"]} >= {SPLIT, "TRG-multisite-replication"} and data["local"] == []
    assert all(r["disabled"] is False for r in data["reference"])


def test_only_a_decider_deactivates_and_a_justification_is_mandatory(client):
    assert client.post(f"{BASE}/rules/{SPLIT}/disable", headers=as_("contributor"), json={"justification": "x"}).status_code == 403
    bare = client.post(f"{BASE}/rules/{SPLIT}/disable", headers=as_("decider"), json={})
    assert bare.status_code == 400 and bare.json()["argument"] == "justification"
    assert client.post(f"{BASE}/rules/{SPLIT}/disable", headers=as_("decider"), json={"justification": "   "}).status_code == 400
    unknown = client.post(f"{BASE}/rules/TRG-nope/disable", headers=as_("decider"), json={"justification": "x"})
    assert unknown.status_code == 404 and unknown.json()["error"] == "unknown_rule"
    assert [r for r in rules(client)["reference"] if r["disabled"]] == []  # nothing happened


def test_a_deactivated_rule_opens_nothing_and_what_it_opened_is_contested_not_deleted(client):
    decide(client)
    assert derived(client)[SPLIT]["foundation"] == "sound"
    res = client.post(f"{BASE}/rules/{SPLIT}/disable", headers=as_("decider"), json={"justification": "Three-site witness already contracted"})
    assert res.status_code == 200 and res.json()["data"]["cascade"]["contested"] == ["active-active-split-brain"]
    item = derived(client)[SPLIT]
    assert item["foundation"] == "foundation_contested" and item["cause"] == {"rule_disabled": True} and item["resolved"] is True
    assert [r["justification"] for r in rules(client)["reference"] if r["trigger_id"] == SPLIT] == ["Three-site witness already contracted"]
    again = client.post(f"{BASE}/rules/{SPLIT}/disable", headers=as_("decider"), json={"justification": "y"})
    assert again.status_code == 409 and again.json()["error"] == "already_disabled"


def test_a_deactivated_rule_stays_closed_when_the_facts_change_and_reopens_when_re_enabled(client):
    client.post(f"{BASE}/rules/{SPLIT}/disable", headers=as_("decider"), json={"justification": "Not applicable"})
    d, out = decide(client)
    assert "active-active-split-brain" not in out["cascade"]["created"] and SPLIT not in derived(client)
    back = client.post(f"{BASE}/rules/{SPLIT}/enable", headers=as_("decider"), json={})
    assert back.status_code == 200 and back.json()["data"]["cascade"]["created"] == ["active-active-split-brain"]
    assert client.post(f"{BASE}/rules/{SPLIT}/enable", headers=as_("decider"), json={}).status_code == 409


def test_a_mandatory_rule_is_deactivated_only_with_a_justification_traced_in_the_audit(client):
    nis2 = "TRG-nis2-business-continuity"
    assert client.post(f"{BASE}/rules/{nis2}/disable", headers=as_("decider"), json={}).status_code == 400
    ok = client.post(f"{BASE}/rules/{nis2}/disable", headers=as_("decider"), json={"justification": "Entity is out of NIS2 scope (legal opinion 12)"})
    assert ok.status_code == 200
    event = next(e for e in audit(client) if e["action"] == "rule_disable")
    assert event["detail"]["mandatory"] is True and "legal opinion 12" in event["detail"]["justification"] and event["actor"] == "@dan"


def test_replaying_a_deactivation_creates_nothing_more_in_the_audit_than_the_first(client):
    client.post(f"{BASE}/rules/{SPLIT}/disable", headers=as_("decider"), json={"justification": "x"})
    client.post(f"{BASE}/rules/{SPLIT}/disable", headers=as_("decider"), json={"justification": "x"})
    assert len([e for e in audit(client) if e["action"] == "rule_disable"]) == 1


# --- local rules ---------------------------------------------------------------------------------------------------


def test_a_local_rule_is_proposed_then_asserted_by_another_decider_and_only_then_applies(client):
    decide(client)
    assert client.post(f"{BASE}/rules", headers=as_("reader"), json=LOCAL).status_code == 403
    proposed = client.post(f"{BASE}/rules", headers=as_("decider"), json=LOCAL)
    assert proposed.status_code == 201, proposed.text
    assert proposed.json()["data"]["adjustment"]["status"] == "proposed" and proposed.json()["data"]["adjustment"]["author"] == "@dan"
    assert "TRG-local-ptp-holdover" not in derived(client)  # a proposal derives nothing
    own = client.post(f"{BASE}/rules/{LOCAL['trigger_id']}/assert", headers=as_("decider"))
    assert own.status_code == 409 and own.json()["error"] == "self_validation"
    assert client.post(f"{BASE}/rules/{LOCAL['trigger_id']}/assert", headers=as_("contributor")).status_code == 403
    ok = client.post(f"{BASE}/rules/{LOCAL['trigger_id']}/assert", headers=as_("admin"))
    assert ok.status_code == 200 and ok.json()["data"]["cascade"]["created"] == ["local-ptp-holdover"]
    item = derived(client)["TRG-local-ptp-holdover"]
    assert item["scope"] == "local" and item["knowledge_ref"] is None and item["resolved"] is True and item["suggested_role"] == "network-architect"


def test_a_local_rule_has_the_checks_of_a_reference_rule(client):
    def refused(**over):
        res = client.post(f"{BASE}/rules", headers=as_("contributor"), json={**LOCAL, **over})
        assert res.status_code == 400, res.text
        return res.json()

    bad_key = refused(when=[{"key": "no.such_key", "op": "eq", "value": 1}])
    assert bad_key["code"] == "UNKNOWN_FACT_KEY" and bad_key["argument"] == "when[0].key"
    assert refused(when=[{"key": "topology.dc_count", "op": "gte", "value": "2"}])["argument"] == "when[0].value"
    assert refused(trigger_id="TRG-ptp")["argument"] == "trigger_id"  # the TRG-local- namespace is the engagement's own
    assert refused(asset="NO-SUCH-ASSET")["argument"] == "asset"
    assert refused(initial_level="L3_decided")["argument"] == "initial_level"
    assert refused(unexpected=1)["argument"] == "unexpected"
    assert refused(trigger_id=SPLIT)["argument"] == "trigger_id"
    assert rules(client)["local"] == []  # nothing was stored


def test_a_local_rule_may_cite_a_carrier_and_a_mandatory_control_requires_mandatory(client):
    ok = client.post(f"{BASE}/rules", headers=as_("contributor"), json={**LOCAL, "asset": "P-009"})
    assert ok.status_code == 201
    refused = client.post(f"{BASE}/rules", headers=as_("contributor"), json={**LOCAL, "trigger_id": "TRG-local-x", "asset": "NIS2-ART21-2C"})
    assert refused.status_code == 400 and refused.json()["code"] == "MANDATORY_REQUIRED"


def test_a_local_rule_can_be_withdrawn_and_what_it_opened_is_contested(client):
    decide(client)
    client.post(f"{BASE}/rules", headers=as_("contributor"), json=LOCAL)
    client.post(f"{BASE}/rules/{LOCAL['trigger_id']}/assert", headers=as_("decider"))
    assert derived(client)["TRG-local-ptp-holdover"]["foundation"] == "sound"
    assert client.post(f"{BASE}/rules/{LOCAL['trigger_id']}/withdraw", headers=as_("reader")).status_code == 403
    res = client.post(f"{BASE}/rules/{LOCAL['trigger_id']}/withdraw", headers=as_("admin"))
    assert res.status_code == 200 and res.json()["data"]["cascade"]["contested"] == ["local-ptp-holdover"]
    item = derived(client)["TRG-local-ptp-holdover"]
    assert item["foundation"] == "foundation_contested" and item["cause"] == {"rule_missing": True} and item["resolved"] is True
    assert client.post(f"{BASE}/rules", headers=as_("contributor"), json=LOCAL).status_code == 201  # may be proposed again


def test_a_local_rule_never_reaches_the_knowledge_base_snapshot(client):
    client.post(f"{BASE}/rules", headers=as_("contributor"), json=LOCAL)
    client.post(f"{BASE}/rules/{LOCAL['trigger_id']}/assert", headers=as_("decider"))
    for path in ("data/snapshots/latest.json", "fixtures/sealed_snapshot.json"):
        assert "TRG-local" not in (ROOT / path).read_text(encoding="utf-8")
    assert not list((ROOT / "data/kb/triggers").glob("TRG-local-*"))


# --- the sealed snapshot -------------------------------------------------------------------------------------------


def export(client):
    ref = client.post(f"{BASE}/exports", headers=as_("admin"))
    assert ref.status_code in (200, 201), ref.text
    return client.get(f"{BASE}/exports/{ref.json()['data']['snapshotRef']['snapshotId']}", headers=as_("reader")).json()


def test_the_snapshot_carries_the_deactivations_and_the_local_rules(client):
    decide(client)
    client.post(f"{BASE}/rules/{SPLIT}/disable", headers=as_("decider"), json={"justification": "Witness contracted"})
    client.post(f"{BASE}/rules", headers=as_("contributor"), json=LOCAL)
    before = export(client)
    assert before["schemaVersion"] == "1.5" and verify(before) == []
    adj = before["data"]["rule_adjustments"]
    assert [(d["trigger_id"], d["justification"], d["disabled_by"], d["resolved"]) for d in adj["disabled"]] == [(SPLIT, "Witness contracted", "@dan", True)]
    assert adj["local_rules"][0]["assertion_level"] == "proposed" and adj["local_rules"][0]["author"] == "@carl"
    client.post(f"{BASE}/rules/{LOCAL['trigger_id']}/assert", headers=as_("admin"))
    after = export(client)
    assert after["checksum"] != before["checksum"] and verify(after) == []
    assert after["data"]["rule_adjustments"]["local_rules"][0]["validated_by"] == "@ada"
    lineage = {i["trigger_id"]: i for i in after["data"]["lineage"]["items"]}
    assert lineage["TRG-local-ptp-holdover"]["scope"] == "local" and lineage[SPLIT]["foundation"] == "foundation_contested"


def test_the_verification_stops_an_adjustment_nobody_answers_for(client):
    client.post(f"{BASE}/rules/{SPLIT}/disable", headers=as_("decider"), json={"justification": "Witness contracted"})
    client.post(f"{BASE}/rules", headers=as_("contributor"), json=LOCAL)
    client.post(f"{BASE}/rules/{LOCAL['trigger_id']}/assert", headers=as_("admin"))
    env = export(client)

    def codes(mutate):
        data = copy.deepcopy(env["data"])
        mutate(data)
        return {p.code for p in verify(seal(data, ENG, "2026-10-04T00:00:00Z", "x"))}

    assert "DISABLED_WITHOUT_JUSTIFICATION" in codes(lambda d: d["rule_adjustments"]["disabled"][0].update(justification=" "))
    assert "DISABLED_UNKNOWN_RULE" in codes(lambda d: d["rule_adjustments"]["disabled"][0].update(resolved=False))
    assert "SELF_VALIDATION" in codes(lambda d: d["rule_adjustments"]["local_rules"][0].update(validated_by=d["rule_adjustments"]["local_rules"][0]["author"]))
    assert "ASSERTED_WITHOUT_PERSON" in codes(lambda d: d["rule_adjustments"]["local_rules"][0].update(validated_by=""))
    assert "VALIDATOR_ON_PROPOSED" in codes(lambda d: d["rule_adjustments"]["local_rules"][0].update(status="proposed"))
    assert "LOCAL_RULE_ID" in codes(lambda d: d["rule_adjustments"]["local_rules"][0].update(trigger_id="TRG-ptp"))


def test_a_local_rule_withdrawn_does_not_block_the_export(client):
    decide(client)
    client.post(f"{BASE}/rules", headers=as_("contributor"), json=LOCAL)
    client.post(f"{BASE}/rules/{LOCAL['trigger_id']}/assert", headers=as_("decider"))
    client.post(f"{BASE}/rules/{LOCAL['trigger_id']}/withdraw", headers=as_("admin"))
    env = export(client)
    assert verify(env) == [] and env["data"]["rule_adjustments"]["local_rules"][0]["status"] == "withdrawn"
