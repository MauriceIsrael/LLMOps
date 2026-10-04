"""K20 (ADR-KH-01 A10): an asserted decision opens more precise subjects; the engine derives no decision and keeps the truth."""

import copy
import json
import shutil
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from mcp_server.core.config import server_config
from pipelines import canonical
from pipelines.engagement.access import get_access
from pipelines.engagement.snapshot import seal, verify
from pipelines.governance.store import dispose_engines

ROOT = Path(__file__).resolve().parents[2]
ARCHINEX = "arx-token"
OPERATOR = {"Authorization": "Bearer demo-token"}
EMAILS = {"admin": "ada@example.org", "decider": "dan@example.org", "contributor": "carl@example.org", "reader": "rita@example.org"}
MEMBERS = [{"email": EMAILS["admin"], "handle": "@ada", "role": "admin"}, {"email": EMAILS["decider"], "handle": "@dan", "role": "decider"},
           {"email": EMAILS["contributor"], "handle": "@carl", "role": "contributor"}, {"email": EMAILS["reader"], "handle": "@rita", "role": "reader"}]
ENG = "eng-c"
BASE = f"/api/engagements/{ENG}"


def facts(count, mode="active-active"):
    out = [{"key": "topology.dc_count", "value": count, "source_excerpt": f"{count} data centres"}]
    if mode:
        out.append({"key": "topology.mode", "value": mode, "source_excerpt": mode})
    return out


def as_(role):
    return {"Authorization": f"Bearer {ARCHINEX}", "X-Actor-Email": EMAILS[role]}


@pytest.fixture
def snaps(tmp_path):
    d = tmp_path / "snaps"
    d.mkdir()
    shutil.copy(ROOT / "data/snapshots/latest.json", d / "latest.json")
    return d


def setup(monkeypatch, tmp_path, snaps, eng=ENG):
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
        "engagement": eng, "confidentiality": "internal", "admin_email": EMAILS["admin"], "admin_handle": "@ada"}).status_code == 201
    get_access().replace_members(eng, MEMBERS, "test")
    assert c.post(f"/api/engagements/{eng}/subjects", headers=as_("contributor"), json={"name": "mcx-services"}).status_code == 201
    return c


@pytest.fixture
def client(monkeypatch, tmp_path, snaps):
    yield setup(monkeypatch, tmp_path, snaps)
    dispose_engines()


def decide(client, fact_list, subject="mcx-services", supersedes=None, eng=ENG, assert_it=True):
    body = {"subject": subject, "decision": "Topology", "rationale": "Availability target.", "reversibility": "costly", "facts": fact_list}
    if supersedes:
        body["supersedes"] = supersedes
    res = client.post(f"/api/engagements/{eng}/decisions", headers=as_("contributor"), json=body)
    assert res.status_code in (200, 201), res.text
    d = res.json()["data"]["decision"]
    if not assert_it:
        return d, None
    out = client.post(f"/api/engagements/{eng}/decisions/{d['id']}/assert", headers=as_("admin"))
    assert out.status_code == 200, out.text
    return d, out.json()["data"]


def lineage(client, eng=ENG):
    res = client.get(f"/api/engagements/{eng}/lineage", headers=as_("reader"))
    assert res.status_code == 200, res.text
    return res.json()["data"]


def by_rule(data):
    return {i["trigger_id"]: i for i in data["derived"]}


TWO_DC_RULES = {"TRG-multisite-replication", "TRG-active-active-split-brain", "TRG-active-active-traffic-failover"}


# --- the scenario: topology ----------------------------------------------------------------------------------------


def test_two_active_active_sites_open_replication_split_brain_and_failover(client):
    _, out = decide(client, facts(2))
    assert sorted(out["cascade"]["created"]) == ["active-active-split-brain", "active-active-traffic-failover", "multisite-replication"]
    items = by_rule(lineage(client))
    assert set(items) == TWO_DC_RULES  # the distribution rule needs three sites
    split = items["TRG-active-active-split-brain"]
    assert split["foundation"] == "sound" and split["cause"] is None and split["resolved"] is True
    assert [p["subject"] for p in split["parents"]] == ["mcx-services"] and split["suggested_role"] == "architect"
    assert {f["key"]: f["value"] for f in split["facts"]} == {"topology.dc_count": 2, "topology.mode": "active-active"}
    assert split["kb_snapshot"]["snapshot_id"].startswith("snapshot-") and split["knowledge_ref"]["knowledgeKey"] == "trigger:TRG-active-active-split-brain"
    assert split["mandatory"] is False and split["question_id"] is None


def test_replacing_two_sites_by_three_contests_the_witness_and_opens_the_distribution(client):
    first, _ = decide(client, facts(2))
    _, out = decide(client, facts(3), supersedes=first["id"])
    assert out["cascade"]["created"] == ["multisite-distribution"]
    assert out["cascade"]["contested"] == ["active-active-split-brain"]
    items = by_rule(lineage(client))
    split = items["TRG-active-active-split-brain"]
    assert split["foundation"] == "foundation_contested"
    assert split["cause"] == {"unsatisfied": [{"key": "topology.dc_count", "op": "eq", "value": 2, "current": 3}]}
    assert items["TRG-multisite-replication"]["foundation"] == "sound"  # still holds with three sites
    assert items["TRG-active-active-traffic-failover"]["foundation"] == "sound"
    assert items["TRG-multisite-distribution"]["foundation"] == "sound"
    levels = client.get(f"{BASE}/facts", headers=as_("reader")).json()["data"]
    assert [f["value"] for f in levels["items"] if f["key"] == "topology.dc_count"] == [3]


def test_nothing_derived_is_deleted_and_the_mark_is_lifted_when_the_condition_holds_again(client):
    first, _ = decide(client, facts(2))
    second, _ = decide(client, facts(3), supersedes=first["id"])
    _, out = decide(client, facts(2), supersedes=second["id"])
    assert out["cascade"]["restored"] == ["active-active-split-brain"] and out["cascade"]["contested"] == ["multisite-distribution"]
    items = by_rule(lineage(client))
    assert len(items) == 4  # nothing was deleted along the way
    assert items["TRG-active-active-split-brain"]["foundation"] == "sound" and items["TRG-active-active-split-brain"]["cause"] is None
    assert items["TRG-multisite-distribution"]["foundation"] == "foundation_contested"


def test_withdrawing_the_asserted_decision_contests_what_it_opened_without_deleting(client):
    d, _ = decide(client, facts(2))
    res = client.post(f"{BASE}/decisions/{d['id']}/withdraw", headers=as_("admin"))
    assert res.status_code == 200 and sorted(res.json()["data"]["cascade"]["contested"]) == [
        "active-active-split-brain", "active-active-traffic-failover", "multisite-replication"]
    items = by_rule(lineage(client))
    assert len(items) == 3 and all(i["foundation"] == "foundation_contested" for i in items.values())
    assert items["TRG-multisite-replication"]["cause"]["unsatisfied"][0]["current"] is None  # no fact in force any more


def test_a_proposed_decision_opens_nothing(client):
    _, out = decide(client, facts(2), assert_it=False)
    assert out is None and lineage(client)["derived"] == []


# --- idempotence and determinism -----------------------------------------------------------------------------------


def test_running_the_engine_again_creates_nothing_more(client, snaps, monkeypatch):
    decide(client, facts(2))
    from mcp_server.core.db import get_engagement_path
    from pipelines.engagement.cascade import Cascade
    from tools.elicitation.repository import ElicitationRepository

    repo = ElicitationRepository(db_path=get_engagement_path(ENG))
    try:
        again = Cascade(repo, get_access(), ENG, snaps, "@ada").run()
        assert again["created"] == [] and again["contested"] == [] and again["restored"] == []
    finally:
        repo.close()
    assert len(lineage(client)["derived"]) == 3


def test_the_same_state_and_pinned_base_give_the_same_subjects_and_seal(monkeypatch, tmp_path, snaps):
    sections = []
    for eng in ("eng-one", "eng-two"):
        c = setup(monkeypatch, tmp_path, snaps, eng)
        first, _ = decide(c, facts(2), eng=eng)
        decide(c, facts(3), supersedes=first["id"], eng=eng)
        ref = c.post(f"/api/engagements/{eng}/exports", headers=as_("admin"))
        assert ref.status_code in (200, 201), ref.text
        sid = ref.json()["data"]["snapshotRef"]["snapshotId"]
        env = c.get(f"/api/engagements/{eng}/exports/{sid}", headers=as_("reader")).json()
        assert verify(env) == []
        lin = copy.deepcopy(env["data"]["lineage"])  # the identifiers of decisions derive from the engagement: set them aside
        for item in lin["items"]:
            item["parents"] = [p["subject"] for p in item["parents"]]
            item["facts"] = [{k: v for k, v in f.items() if k != "decision"} for f in item["facts"]]
        sections.append(canonical.sha256(lin))
        dispose_engines()
    assert sections[0] == sections[1]


def test_an_import_creates_the_subjects_once_and_a_replay_adds_none(client):
    batch = {"batch_id": "b-1", "subjects": [{"name": "core-network"}], "decisions": [{
        "key": "d-1", "subject": "core-network", "decision": "2 DC", "rationale": "r", "reversibility": "costly", "facts": facts(2),
        "author": "@carl", "validated_by": "@ada", "validated_at": "2026-01-07T09:00:00"}]}
    first = client.post(f"{BASE}/import", headers=as_("admin"), json=batch)
    assert first.status_code == 200, first.text
    assert sorted(first.json()["data"]["cascade"]["created"]) == sorted(["multisite-replication", "active-active-split-brain", "active-active-traffic-failover"])
    replay = client.post(f"{BASE}/import", headers=as_("admin"), json={**batch, "batch_id": "b-2"})
    assert replay.json()["data"]["cascade"]["created"] == [] and len(lineage(client)["derived"]) == 3


def test_a_key_asserted_with_two_values_is_not_usable(client):
    assert client.post(f"{BASE}/subjects", headers=as_("contributor"), json={"name": "core-network"}).status_code == 201
    decide(client, facts(2, mode=None))
    _, out = decide(client, facts(3, mode=None), subject="core-network")
    items = by_rule(lineage(client))
    assert items["TRG-multisite-replication"]["foundation"] == "foundation_contested"  # dc_count is contradicted: nothing picks a winner
    assert items["TRG-multisite-replication"]["cause"]["unsatisfied"][0]["contradiction"] is True
    assert "TRG-multisite-distribution" not in items and out["cascade"]["contested"] == ["multisite-replication"]


# --- a question, not an assertion ----------------------------------------------------------------------------------


def test_a_derived_subject_is_a_question_the_engine_alone_can_create(client):
    decide(client, facts(2))
    forged = client.post(f"{BASE}/subjects", headers=as_("contributor"), json={"name": "forged", "origin": "derived"})
    assert forged.status_code == 201
    ref = client.post(f"{BASE}/exports", headers=as_("admin"))
    env = client.get(f"{BASE}/exports/{ref.json()['data']['snapshotRef']['snapshotId']}", headers=as_("reader")).json()
    origin = {s["name"]: s["origin"] for s in env["data"]["subjects"]}
    assert origin["forged"] == "declared" and origin["multisite-replication"] == "derived"
    assert {s["name"]: s["maturity"] for s in env["data"]["subjects"]}["multisite-replication"] == "L1_framed"
    assert all(d["decision"] == "Topology" for d in env["data"]["decisions"])  # the engine derived no decision


def test_a_person_never_owns_a_name_the_engine_takes(client):
    assert client.post(f"{BASE}/subjects", headers=as_("contributor"), json={"name": "multisite-replication"}).status_code == 201
    _, out = decide(client, facts(2, mode=None))
    assert out["cascade"]["created"] == ["multisite-replication-derived"]


# --- mandatory questions -------------------------------------------------------------------------------------------


def test_a_mandatory_question_is_closed_by_a_decider_with_a_justification(client):
    sovereign = [{"key": "hosting.sovereignty", "value": "sovereign-cloud", "source_excerpt": "SecNumCloud hosting"}]
    _, out = decide(client, sovereign)
    assert out["cascade"]["created"] == ["sovereign-hosting-jurisdiction"]
    item = by_rule(lineage(client))["TRG-sovereign-hosting-jurisdiction"]
    assert item["mandatory"] is True and item["suggested_role"] == "security-architect" and item["question_status"] == "open"
    qid = item["question_id"]
    answer = {"value": "Provider is SecNumCloud qualified", "confidence": "stated-by-client"}
    contributor = client.post(f"{BASE}/questions/{qid}/answers", headers=as_("contributor"), json=answer)
    assert contributor.status_code == 403 and contributor.json()["error"] == "mandatory_question"
    bare = client.post(f"{BASE}/questions/{qid}/answers", headers=as_("decider"), json=answer)
    assert bare.status_code == 400 and bare.json()["argument"] == "justification"
    ok = client.post(f"{BASE}/questions/{qid}/answers", headers=as_("decider"), json={**answer, "justification": "Qualification certificate checked"})
    assert ok.status_code == 201, ok.text
    assert by_rule(lineage(client))["TRG-sovereign-hosting-jurisdiction"]["question_status"] == "answered"


def test_an_ordinary_question_is_still_answered_by_a_contributor(client):
    q = client.post(f"{BASE}/questions", headers=as_("contributor"), json={"question": "Which redundancy model?", "subject": "mcx-services"})
    qid = q.json()["data"]["question"]["id"]
    assert client.post(f"{BASE}/questions/{qid}/answers", headers=as_("contributor"), json={"value": "Two sites", "confidence": "stated-by-client"}).status_code == 201


# --- the pinned base -----------------------------------------------------------------------------------------------


def test_the_first_derivation_pins_the_base_and_only_an_admin_moves_it(client, snaps):
    assert lineage(client)["kb_snapshot"] is None
    decide(client, facts(2))
    pin = lineage(client)["kb_snapshot"]
    latest = json.loads((snaps / "latest.json").read_text(encoding="utf-8"))
    assert pin == {"snapshot_id": latest["snapshot_id"], "checksum": latest["payload_sha256"]}
    other = copy.deepcopy(latest)
    other["snapshot_id"] = "snapshot-2026-10-05-abcdef1"
    other["question_triggers"]["items"] = [i for i in other["question_triggers"]["items"] if i["trigger_id"] != "TRG-active-active-split-brain"]
    (snaps / "snapshot-2026-10-05-abcdef1.json").write_text(json.dumps(other), encoding="utf-8")
    assert client.put(f"{BASE}/kb-pin", headers=as_("decider"), json={"snapshot_id": other["snapshot_id"]}).status_code == 403
    assert client.put(f"{BASE}/kb-pin", headers=as_("admin"), json={"snapshot_id": "snapshot-2026-01-01-0000000"}).status_code == 400
    moved = client.put(f"{BASE}/kb-pin", headers=as_("admin"), json={"snapshot_id": other["snapshot_id"]})
    assert moved.status_code == 200 and moved.json()["data"]["cascade"]["contested"] == ["active-active-split-brain"]
    items = by_rule(lineage(client))
    assert items["TRG-active-active-split-brain"]["cause"] == {"rule_missing": True}
    assert lineage(client)["kb_snapshot"]["snapshot_id"] == other["snapshot_id"]


def test_without_a_usable_base_the_assertion_still_succeeds_and_says_why(monkeypatch, tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    c = setup(monkeypatch, tmp_path, empty)
    d = c.post(f"{BASE}/decisions", headers=as_("contributor"), json={"subject": "mcx-services", "decision": "x", "rationale": "x", "reversibility": "reversible"}).json()["data"]["decision"]
    out = c.post(f"{BASE}/decisions/{d['id']}/assert", headers=as_("admin"))
    assert out.status_code == 200 and out.json()["data"]["cascade"]["skipped"] == "snapshot_unavailable"
    dispose_engines()


# --- reading --------------------------------------------------------------------------------------------------------


def test_the_lineage_tree_goes_from_the_decision_to_the_subjects_it_opened(client):
    d, _ = decide(client, facts(2))
    tree = lineage(client)["tree"]
    assert [n["subject"] for n in tree] == ["mcx-services"]
    node = tree[0]["decisions"][0]
    assert node["decision"] == d["id"] and sorted(c["rule"] for c in node["derived"]) == sorted(TWO_DC_RULES)
    assert client.get(f"{BASE}/lineage", headers=OPERATOR).status_code == 403


# --- the sealed snapshot --------------------------------------------------------------------------------------------


def export(client):
    ref = client.post(f"{BASE}/exports", headers=as_("admin"))
    assert ref.status_code in (200, 201), ref.text
    return client.get(f"{BASE}/exports/{ref.json()['data']['snapshotRef']['snapshotId']}", headers=as_("reader")).json()


def test_the_snapshot_carries_the_lineage_and_each_derived_subject_resolves_its_rule(client):
    first, _ = decide(client, facts(2))
    decide(client, facts(3), supersedes=first["id"])
    env = export(client)
    assert env["schemaVersion"] == "1.4" and verify(env) == []
    items = {i["trigger_id"]: i for i in env["data"]["lineage"]["items"]}
    assert items["TRG-active-active-split-brain"]["foundation"] == "foundation_contested" and all(i["resolved"] for i in items.values())
    assert env["data"]["lineage"]["kb_snapshot"] == env["data"]["pins"]["kb_snapshot"]


def test_the_verification_stops_a_lineage_the_base_cannot_resolve(client):
    decide(client, facts(2))
    env = export(client)

    def codes(mutate):
        data = copy.deepcopy(env["data"])
        mutate(data)
        return {p.code for p in verify(seal(data, ENG, "2026-10-04T00:00:00Z", "x"))}

    assert "DERIVED_RULE_UNRESOLVED" in codes(lambda d: d["lineage"]["items"][0].update(resolved=False))
    assert "LINEAGE_SUBJECT" in codes(lambda d: [s.update(origin="declared") for s in d["subjects"] if s["name"] == "multisite-replication"])
    assert "DERIVED_WITHOUT_LINEAGE" in codes(lambda d: d["lineage"]["items"].pop())
    assert "CONTESTED_WITHOUT_CAUSE" in codes(lambda d: d["lineage"]["items"][0].update(foundation="foundation_contested", cause=None))
    assert "DANGLING" in codes(lambda d: d["lineage"]["items"][0]["parents"].append({"subject": "x", "decision": "D-none"}))
