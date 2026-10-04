"""K18 (ADR-KH-01 A10): architecture facts carried by decisions, in the shared vocabulary of the knowledge base."""

import copy
import json
import shutil
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from mcp_server.core.config import server_config
from pipelines import canonical
from pipelines.engagement import facts as fact_module
from pipelines.engagement.access import get_access
from pipelines.engagement.snapshot import seal, verify
from pipelines.governance.store import dispose_engines
from pipelines.knowledge_ref import PAYLOAD_KEYS

ROOT = Path(__file__).resolve().parents[2]
ARCHINEX = "arx-token"
OPERATOR = {"Authorization": "Bearer demo-token"}
EMAILS = {"admin": "ada@example.org", "decider": "dan@example.org", "contributor": "carl@example.org", "reader": "rita@example.org"}
ENG = "eng-f"
BASE = f"/api/engagements/{ENG}"
TWO_DC = [{"key": "topology.dc_count", "value": 2, "source_excerpt": "two data centres"},
          {"key": "topology.mode", "value": "active-active", "source_excerpt": "active-active"}]
DECISION = {"subject": "mcx-services", "decision": "2 DC active-active", "rationale": "Meets the availability target.",
            "reversibility": "costly", "facts": TWO_DC}


def as_(role):
    return {"Authorization": f"Bearer {ARCHINEX}", "X-Actor-Email": EMAILS[role]}


def make_client(monkeypatch, tmp_path, with_kb: bool):
    monkeypatch.setenv("SERVER_TOKEN", "demo-token")
    monkeypatch.setenv("ENGAGEMENT_TOKENS", f"{ARCHINEX}:*,eng:delegate")
    monkeypatch.setenv("GOVERNANCE_DATABASE_URL", f"sqlite:///{tmp_path}/gov.db")
    monkeypatch.setattr(server_config, "engagements_dir", tmp_path)
    from mcp_server.knowledge import tools as knowledge_tools

    snaps = tmp_path / "snaps"
    snaps.mkdir()
    if with_kb:  # the knowledge snapshot an engagement pins: it carries the facts vocabulary
        shutil.copy(ROOT / "data/snapshots/latest.json", snaps / "latest.json")
    monkeypatch.setattr(knowledge_tools, "SNAPSHOTS_DIR", snaps)
    dispose_engines()
    from mcp_server.main import create_starlette_app

    c = TestClient(create_starlette_app(), raise_server_exceptions=False)
    assert c.post("/api/engagements", headers=OPERATOR, json={
        "engagement": ENG, "confidentiality": "internal", "admin_email": EMAILS["admin"], "admin_handle": "@ada"}).status_code == 201
    get_access().replace_members(ENG, [
        {"email": EMAILS["admin"], "handle": "@ada", "role": "admin"},
        {"email": EMAILS["decider"], "handle": "@dan", "role": "decider"},
        {"email": EMAILS["contributor"], "handle": "@carl", "role": "contributor"},
        {"email": EMAILS["reader"], "handle": "@rita", "role": "reader"}], "test")
    assert c.post(f"{BASE}/subjects", headers=as_("contributor"), json={"name": "mcx-services"}).status_code == 201
    return c


@pytest.fixture
def client(monkeypatch, tmp_path):
    yield make_client(monkeypatch, tmp_path, with_kb=True)
    dispose_engines()


@pytest.fixture
def client_without_kb(monkeypatch, tmp_path):
    yield make_client(monkeypatch, tmp_path, with_kb=False)
    dispose_engines()


def propose(client, **over):
    res = client.post(f"{BASE}/decisions", headers=as_("contributor"), json={**DECISION, **over})
    assert res.status_code in (200, 201), res.text
    return res.json()["data"]["decision"]


def assert_(client, did):
    res = client.post(f"{BASE}/decisions/{did}/assert", headers=as_("admin"))
    assert res.status_code == 200, res.text
    return res


def in_force(client):
    res = client.get(f"{BASE}/facts", headers=as_("reader"))
    assert res.status_code == 200, res.text
    return res.json()["data"]


# --- the vocabulary ------------------------------------------------------------------------------------------------


def test_the_vocabulary_of_the_knowledge_base_is_valid_and_covers_the_scenario():
    voc = fact_module.load(ROOT / "data/kb/vocabulary/facts.yaml")
    for key in ("topology.dc_count", "topology.mode", "data.rpo_target_s", "data.rto_target_s", "hosting.sovereignty"):
        assert key in voc["keys"]
    for k in voc["keys"].values():  # a cited asset exists: nothing is invented
        if k.get("asset"):
            assert list((ROOT / "data/kb").glob(f"*/{k['asset']}.md")), k


@pytest.mark.parametrize("text,reason", [
    ("version: 0\nkeys: []", "version"),
    ("version: 1\nkeys: []", "no key"),
    ("version: 1\nkeys: [{key: bad, type: int, label: {fr: a, en: b}}]", "domain.name"),
    ("version: 1\nkeys: [{key: a.b, type: float, label: {fr: a, en: b}}]", "type"),
    ("version: 1\nkeys: [{key: a.b, type: enum, label: {fr: a, en: b}}]", "enum"),
    ("version: 1\nkeys: [{key: a.b, type: int, label: {fr: a}}]", "label"),
    ("version: 1\nkeys: [{key: a.b, type: int, label: {fr: a, en: b}},{key: a.b, type: int, label: {fr: a, en: b}}]", "twice"),
])
def test_a_bad_vocabulary_is_refused(text, reason):
    with pytest.raises(fact_module.VocabularyError, match=reason):
        fact_module.parse(text)


def test_the_sealed_knowledge_snapshot_carries_the_vocabulary_without_changing_its_checksum():
    doc = json.loads((ROOT / "data/snapshots/latest.json").read_text(encoding="utf-8"))
    vocab = doc["fact_vocabulary"]
    live = fact_module.load(ROOT / "data/kb/vocabulary/facts.yaml")
    assert vocab["version"] == live["version"] and vocab["content_sha256"] == live["content_sha256"]
    assert vocab["knowledge_ref"] == {"sourceId": "knowledge-hub", "knowledgeKey": "vocabulary:facts", "version": str(live["version"])}
    # a consumer that recomputes the seal over the six payload sections keeps verifying: the section sits outside of it
    assert doc["payload_sha256"] == canonical.sha256({k: doc[k] for k in PAYLOAD_KEYS})
    ledger = json.loads((ROOT / "data/kb/version-ledger.json").read_text(encoding="utf-8"))["revisions"]
    assert ledger["vocabulary:facts"][str(live["version"])] == live["content_sha256"]


# --- refusals ------------------------------------------------------------------------------------------------------


def refused(client, facts, code, where):
    res = client.post(f"{BASE}/decisions", headers=as_("contributor"), json={**DECISION, "facts": facts})
    assert res.status_code == 400, res.text
    body = res.json()
    assert body["code"] == code and body["argument"] == where, body
    return body


def test_an_unknown_key_is_refused_with_its_path(client):
    refused(client, [TWO_DC[0], {"key": "topology.sites", "value": 2, "source_excerpt": "x"}], "UNKNOWN_FACT_KEY", "facts[1].key")


@pytest.mark.parametrize("fact", [
    {"key": "topology.dc_count", "value": True},          # a boolean is not an integer
    {"key": "topology.dc_count", "value": "2"},
    {"key": "topology.dc_count", "value": 0},             # below the minimum
    {"key": "topology.mode", "value": "triple"},          # not in the enum
    {"key": "data.rpo_target_s", "value": -1},            # a duration is not negative
    {"key": "data.rpo_target_s", "value": 1.5},
    {"key": "continuity.nis2_in_scope", "value": "yes"},
])
def test_a_value_of_the_wrong_type_is_refused(client, fact):
    refused(client, [{**fact, "source_excerpt": "x"}], "FACT_TYPE", "facts[0].value")


def test_shape_refusals(client):
    refused(client, [{"key": "topology.dc_count", "value": 2}], "FACT_SHAPE", "facts[0].source_excerpt")
    refused(client, [TWO_DC[0], TWO_DC[0]], "FACT_DUPLICATE", "facts[1].key")
    refused(client, {"key": "x"}, "FACT_SHAPE", "facts")


def test_nothing_was_written_by_a_refusal(client):
    refused(client, [{"key": "nope.nope", "value": 1, "source_excerpt": "x"}], "UNKNOWN_FACT_KEY", "facts[0].key")
    assert in_force(client)["items"] == []
    assert propose(client)["status"] == "proposed"  # no pending decision was left behind


# --- a fact counts only while its decision is asserted -------------------------------------------------------------


def test_a_proposed_decision_brings_no_fact_and_asserting_it_does(client):
    d = propose(client)
    assert d["facts"] == sorted(TWO_DC, key=lambda f: f["key"])
    assert in_force(client)["items"] == []
    assert_(client, d["id"])
    data = in_force(client)
    assert [(f["key"], f["value"], f["decision"], f["subject"]) for f in data["items"]] == [
        ("topology.dc_count", 2, d["id"], "mcx-services"), ("topology.mode", "active-active", d["id"], "mcx-services")]
    assert data["items"][0]["unit"] == "datacentres" and data["items"][0]["source_excerpt"] == "two data centres"
    assert data["contradictions"] == [] and data["vocabulary"]["knowledge_ref"]["knowledgeKey"] == "vocabulary:facts"


def test_superseding_a_decision_removes_its_facts(client):
    first = propose(client)
    assert_(client, first["id"])
    second = propose(client, supersedes=first["id"], decision="3 DC",
                     facts=[{"key": "topology.dc_count", "value": 3, "source_excerpt": "three data centres"}])
    assert [f["value"] for f in in_force(client)["items"] if f["key"] == "topology.dc_count"] == [2]  # still the first one
    assert_(client, second["id"])
    items = in_force(client)["items"]
    assert [(f["key"], f["value"], f["decision"]) for f in items] == [("topology.dc_count", 3, second["id"])]


def test_a_withdrawn_decision_brings_no_fact(client):
    d = propose(client)
    assert client.post(f"{BASE}/decisions/{d['id']}/withdraw", headers=as_("contributor")).status_code == 200
    assert in_force(client)["items"] == []


def test_reading_needs_the_read_role_only_for_members(client):
    assert client.get(f"{BASE}/facts", headers=OPERATOR).status_code == 403  # the operator does not read the content
    assert client.get(f"{BASE}/facts", headers={"Authorization": f"Bearer {ARCHINEX}", "X-Actor-Email": "x@example.org"}).status_code == 403


def test_two_decisions_in_force_with_different_values_are_reported_not_resolved(client):
    assert client.post(f"{BASE}/subjects", headers=as_("contributor"), json={"name": "core-network"}).status_code == 201
    a = propose(client)
    b = propose(client, subject="core-network", decision="One site",
                facts=[{"key": "topology.dc_count", "value": 1, "source_excerpt": "one site"}])
    assert_(client, a["id"])
    assert_(client, b["id"])
    data = in_force(client)
    assert data["contradictions"] == [{"key": "topology.dc_count", "decisions": sorted([a["id"], b["id"]])}]
    assert len([f for f in data["items"] if f["key"] == "topology.dc_count"]) == 2


# --- the sealed snapshot -------------------------------------------------------------------------------------------


def export(client):
    ref = client.post(f"{BASE}/exports", headers=as_("admin"))
    assert ref.status_code in (200, 201), ref.text
    sid = ref.json()["data"]["snapshotRef"]["snapshotId"]
    return client.get(f"{BASE}/exports/{sid}", headers=as_("reader")).json()


def test_the_snapshot_carries_the_facts_of_asserted_decisions_only(client):
    d = propose(client)
    env = export(client)
    assert env["schemaVersion"] == "1.3" and verify(env) == []
    assert env["data"]["facts"]["items"] == [] and env["data"]["decisions"][0]["facts"], "the decision carries them, none is in force"
    before = env["checksum"]
    assert_(client, d["id"])
    env = export(client)
    assert verify(env) == [] and [f["key"] for f in env["data"]["facts"]["items"]] == ["topology.dc_count", "topology.mode"]
    assert env["checksum"] != before  # lowering the decision back to proposed would change it again
    assert env["data"]["facts"]["vocabulary"]["version"] == 1
    assert export(client)["checksum"] == env["checksum"]  # the same state, the same checksum


def test_facts_in_force_that_their_decision_does_not_support_stop_the_verification(client):
    d = propose(client)
    assert_(client, d["id"])
    env = export(client)
    forged = copy.deepcopy(env["data"])
    forged["decisions"][0]["status"] = "proposed"
    forged["decisions"][0]["validated_by"] = ""
    assert "FACT_NOT_ASSERTED" in {p.code for p in verify(seal(forged, ENG, "2026-10-04T00:00:00Z", "x"))}
    forged = copy.deepcopy(env["data"])
    forged["facts"]["items"][0]["value"] = 9
    assert "FACT_NOT_IN_DECISION" in {p.code for p in verify(seal(forged, ENG, "2026-10-04T00:00:00Z", "x"))}
    forged = copy.deepcopy(env["data"])
    forged["facts"]["items"].pop()
    assert "FACTS_INCOMPLETE" in {p.code for p in verify(seal(forged, ENG, "2026-10-04T00:00:00Z", "x"))}


def test_the_export_is_refused_when_the_pinned_knowledge_snapshot_has_no_vocabulary(client_without_kb):
    c = client_without_kb
    d = propose(c)
    assert_(c, d["id"])
    res = c.post(f"{BASE}/exports", headers=as_("admin"))
    assert res.status_code == 422 and res.json()["error"] == "kb_snapshot_unavailable"
    assert c.get(f"{BASE}/exports", headers=as_("reader")).json()["data"]["exports"] == []  # nothing stored


# --- import --------------------------------------------------------------------------------------------------------


def test_an_import_carries_facts_and_refuses_an_unknown_key(client):
    batch = {"batch_id": "b-1", "subjects": [{"name": "core-network"}],
             "decisions": [{"key": "d-1", "subject": "core-network", "decision": "2 DC", "rationale": "r", "reversibility": "costly",
                            "facts": TWO_DC, "author": "@carl", "validated_by": "@ada", "validated_at": "2026-01-07T09:00:00"}]}
    ok = client.post(f"{BASE}/import", headers=as_("admin"), json=batch)
    assert ok.status_code == 200, ok.text
    assert [f["key"] for f in in_force(client)["items"]] == ["topology.dc_count", "topology.mode"]
    bad = copy.deepcopy(batch)
    bad["batch_id"] = "b-2"
    bad["decisions"][0].update(key="d-2", facts=[{"key": "x.y", "value": 1, "source_excerpt": "x"}])
    res = client.post(f"{BASE}/import?dry_run=true", headers=as_("admin"), json=bad)
    rejected = res.json()["data"]["rejected"]
    assert rejected and rejected[0]["code"] == "UNKNOWN_FACT_KEY" and "facts[0].key" in rejected[0]["path"]
