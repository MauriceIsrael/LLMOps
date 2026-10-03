"""K11 (ADR-KH-01 A10): the Hub emits the sealed snapshot of an engagement toward the suite."""

import copy
import json
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from mcp_server.core.config import server_config
from pipelines import canonical
from pipelines.engagement.access import get_access
from pipelines.engagement.snapshot import build_data, seal, snapshot_ref, verify
from pipelines.governance.store import dispose_engines
from scripts.export_engagement_example import EXAMPLE, build_example, scenario

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_TEXT = EXAMPLE.read_text(encoding="utf-8")


def codes(problems):
    return {p.code for p in problems}


# --- the emitter's own test rebuilds the example ------------------------------------------------------------------


def test_the_committed_example_is_what_the_code_rebuilds():
    assert json.loads(EXAMPLE_TEXT) == build_example(), "regenerate with: poetry run python scripts/export_engagement_example.py"
    assert verify(json.loads(EXAMPLE_TEXT)) == []


def test_the_seal_is_the_suite_profile_over_data_alone_and_the_identifier_derives_from_it():
    env = json.loads(EXAMPLE_TEXT)
    assert env["checksum"] == canonical.sha256(env["data"])
    assert env["snapshotId"] == f"eng-example-eng-{env['checksum'][7:19]}"
    assert env["sourceSystem"] == env["emitter"] == "knowledge-hub"
    ref = snapshot_ref(env)
    assert ref == {"sourceSystem": "knowledge-hub", "snapshotId": env["snapshotId"], "checksum": env["checksum"], "producedAt": env["createdAt"]}


def test_the_same_state_gives_the_same_checksum_whatever_the_row_order():
    raw, kb = scenario()
    shuffled = copy.deepcopy(raw)
    for key in ("statements", "subjects", "requirements", "conflicts", "questions"):
        shuffled[key].reverse()
    a = canonical.sha256(build_data(raw, "e", "internal", kb))
    assert a == canonical.sha256(build_data(shuffled, "e", "internal", kb))


def test_lowering_the_confidence_of_a_statement_changes_the_checksum():
    raw, kb = scenario()
    other = copy.deepcopy(raw)
    other["statements"][0]["confidence"] = "assumed"
    assert canonical.sha256(build_data(raw, "e", "internal", kb)) != canonical.sha256(build_data(other, "e", "internal", kb))


# --- content -------------------------------------------------------------------------------------------------------


def test_assertion_levels_are_derived_from_the_status_and_provisional_from_the_graph():
    data = json.loads(EXAMPLE_TEXT)["data"]
    assert {s["id"]: s["assertion_level"] for s in data["statements"]} == {"S-0001": "asserted", "S-0002": "superseded", "S-0003": "proposed"}
    assert data["is_provisional"] is True and data["provisional_reasons"] == {"unripe_subjects": 1, "open_conflicts": 0}
    assert [g["id"] for g in data["gaps"]] == ["G1-core-network", "Q-0001"]
    assert {g["id"]: g["blocking"] for g in data["gaps"]} == {"G1-core-network": False, "Q-0001": True}


def test_a_ripe_conflict_free_engagement_is_not_provisional_and_an_open_conflict_makes_it_provisional():
    raw, kb = scenario()
    raw["subjects"][0]["level"] = "L3_decided"
    assert build_data(raw, "e", "internal", kb)["is_provisional"] is False
    raw["conflicts"][0]["status"] = "open"
    data = build_data(raw, "e", "internal", kb)
    assert data["is_provisional"] is True and data["provisional_reasons"] == {"unripe_subjects": 0, "open_conflicts": 1}


def test_citations_resolve_against_the_pinned_knowledge_snapshot_and_unknown_ones_are_listed():
    data = json.loads(EXAMPLE_TEXT)["data"]
    assert data["kb_references"][0]["knowledge_ref"] == {"sourceId": "knowledge-hub", "knowledgeKey": "decision:ADR-0001", "version": "1"}
    assert data["unresolved_references"] == [{"statement_id": "S-0003", "id": "ADR-9999"}]
    assert data["pins"]["kb_snapshot"]["snapshot_id"] == "snapshot-2026-10-03-0000000"


# --- verification refuses ------------------------------------------------------------------------------------------


def mutate(fn):
    env = json.loads(EXAMPLE_TEXT)
    fn(env["data"])
    return seal(env["data"], "example-eng", env["createdAt"], env["sourceRevision"])


@pytest.mark.parametrize(("name", "fn", "expected"), [
    ("active without a validator", lambda d: d["statements"][0].update(validated_by="", validated_at=""), "ASSERTED_WITHOUT_PERSON"),
    ("self validation", lambda d: d["statements"][0].update(validated_by="@carl"), "SELF_VALIDATION"),
    ("author is a name", lambda d: d["statements"][2].update(author="Carl Dupont"), "AUTHOR_NOT_A_HANDLE"),
    ("validator on a proposed statement", lambda d: d["statements"][2].update(validated_by="@ada"), "VALIDATOR_ON_PROPOSED"),
    ("e-mail in a value", lambda d: d["statements"][2].update(value="Ask carl@client.example for the plan"), "EMAIL"),
    ("e-mail in a requirement", lambda d: d["requirements"][0].update(text="Contact ops@client.example"), "EMAIL"),
    ("dangling conflict", lambda d: d["conflicts"][0].update(statement_ids=["S-0001", "S-9999"]), "DANGLING"),
    ("duplicate statement id", lambda d: d["statements"].append(dict(d["statements"][2])), "DUPLICATE_ID"),
    ("declared provisional", lambda d: d.update(is_provisional=False), "PROVISIONAL"),
    ("arbitrated by nobody", lambda d: d["conflicts"][0].update(arbitrated_by=""), "ARBITRATED_WITHOUT_PERSON"),
    ("gap on an unknown subject", lambda d: d["gaps"][1].update(subject="nowhere"), "DANGLING"),
])
def test_the_verification_refuses(name, fn, expected):
    assert expected in codes(verify(mutate(fn))), name


def test_a_tampered_content_or_identifier_is_refused():
    env = json.loads(EXAMPLE_TEXT)
    env["data"]["requirements"][0]["text"] = "forged"
    assert "SEAL" in codes(verify(env))
    env = json.loads(EXAMPLE_TEXT)
    env["snapshotId"] = "eng-example-eng-000000000000"
    assert "SNAPSHOT_ID" in codes(verify(env))


def test_the_schema_refuses_an_unknown_field_and_an_unknown_confidence():
    env = json.loads(EXAMPLE_TEXT)
    env["data"]["statements"][0]["confidence"] = "certain"
    assert "SCHEMA" in codes(verify(env))
    env = json.loads(EXAMPLE_TEXT)
    env["data"]["engagement"]["owner_email"] = "x"
    assert "SCHEMA" in codes(verify(env))


# --- end to end through the REST routes ---------------------------------------------------------------------------

ARCHINEX = "arx-token"
OPERATOR = {"Authorization": "Bearer demo-token"}
EMAILS = {"admin": "ada@example.org", "decider": "dan@example.org", "contributor": "carl@example.org", "reader": "rita@example.org"}
ENG = "eng-x"
BASE = f"/api/engagements/{ENG}"


def as_(role):
    return {"Authorization": f"Bearer {ARCHINEX}", "X-Actor-Email": EMAILS[role]}


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("SERVER_TOKEN", "demo-token")
    monkeypatch.setenv("ENGAGEMENT_TOKENS", f"{ARCHINEX}:*,eng:delegate;suite-token:*,eng:service")
    monkeypatch.setenv("GOVERNANCE_DATABASE_URL", f"sqlite:///{tmp_path}/gov.db")
    monkeypatch.setattr(server_config, "engagements_dir", tmp_path)
    from mcp_server.knowledge import tools as knowledge_tools

    kb = tmp_path / "snapshots"
    kb.mkdir()
    (kb / "latest.json").write_text((ROOT / "data/snapshots/latest.json").read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(knowledge_tools, "SNAPSHOTS_DIR", kb)
    dispose_engines()
    from mcp_server.main import create_starlette_app

    c = TestClient(create_starlette_app(), raise_server_exceptions=False)
    assert c.post("/api/engagements", headers=OPERATOR, json={
        "engagement": ENG, "confidentiality": "confidential", "admin_email": EMAILS["admin"], "admin_handle": "@ada"}).status_code == 201
    get_access().replace_members(ENG, [
        {"email": EMAILS["admin"], "handle": "@ada", "role": "admin"},
        {"email": EMAILS["decider"], "handle": "@dan", "role": "decider"},
        {"email": EMAILS["contributor"], "handle": "@carl", "role": "contributor"},
        {"email": EMAILS["reader"], "handle": "@rita", "role": "reader"}], "test")
    yield c
    dispose_engines()


def deliberate(client, value="Gateway is active-active", based_on=None):
    st = client.post(f"{BASE}/statements", headers=as_("contributor"), json={
        "subject": "mcx-services", "value": value, "confidence": "designed", "based_on": based_on or []}).json()["data"]["statement"]
    client.post(f"{BASE}/statements/{st['id']}/assert", headers=as_("decider"))
    return st["id"]


def test_only_an_admin_issues_the_snapshot(client):
    for role in ("reader", "contributor", "decider"):
        res = client.post(f"{BASE}/exports", headers=as_(role))
        assert res.status_code == 403 and res.json()["reason"] == "role_insufficient", role
    assert client.post(f"{BASE}/exports", headers=OPERATOR).status_code == 403  # the operator does not read the content
    assert client.post(f"{BASE}/exports", headers={"Authorization": "Bearer suite-token"}).status_code == 403


def test_an_unmanaged_engagement_has_no_snapshot(client):
    res = client.post("/api/engagements/legacy-eng/exports", headers=as_("admin"))
    assert res.status_code == 409 and res.json()["error"] == "engagement_not_managed"


def test_issue_then_fetch_with_the_reference_and_verify_it_as_a_consumer_would(client):
    sid = deliberate(client, based_on=[{"id": "ADR-0001"}])
    issued = client.post(f"{BASE}/exports", headers=as_("admin"))
    assert issued.status_code == 201, issued.text
    data = issued.json()["data"]
    ref = data["snapshotRef"]
    assert data["created"] is True and ref["sourceSystem"] == "knowledge-hub"
    fetched = client.get(f"{BASE}/exports/{ref['snapshotId']}", headers={"Authorization": "Bearer suite-token"})  # a service reads
    assert fetched.status_code == 200
    env = fetched.json()
    assert canonical.sha256(env["data"]) == ref["checksum"] == env["checksum"]  # the reference proves it is that one
    assert verify(env) == []
    assert fetched.headers["ETag"] == ref["checksum"]
    st = next(s for s in env["data"]["statements"] if s["id"] == sid)
    assert st["author"] == "@carl" and st["validated_by"] == "@dan" and st["assertion_level"] == "asserted"
    assert env["data"]["kb_references"][0]["knowledge_ref"]["knowledgeKey"] == "decision:ADR-0001"
    assert "example.org" not in json.dumps(env) and "archinex" not in json.dumps(env).lower()
    assert env["data"]["engagement"] == {"id": ENG, "confidentiality": "confidential"}


def test_the_same_state_gives_the_same_snapshot_and_a_new_state_a_new_one(client):
    deliberate(client)
    first = client.post(f"{BASE}/exports", headers=as_("admin"))
    again = client.post(f"{BASE}/exports", headers=as_("admin"))
    assert (first.status_code, again.status_code) == (201, 200)
    assert first.json()["data"]["snapshotRef"] == again.json()["data"]["snapshotRef"]  # same id, same producedAt: nothing rewritten
    deliberate(client, value="Management plane is out-of-band")
    third = client.post(f"{BASE}/exports", headers=as_("admin"))
    assert third.status_code == 201 and third.json()["data"]["snapshotRef"]["snapshotId"] != first.json()["data"]["snapshotRef"]["snapshotId"]
    listing = client.get(f"{BASE}/exports", headers=as_("reader")).json()["data"]["exports"]
    assert len(listing) == 2
    old = client.get(f"{BASE}/exports/{first.json()['data']['snapshotRef']['snapshotId']}", headers=as_("reader"))
    assert old.json()["checksum"] == first.json()["data"]["snapshotRef"]["checksum"]  # the earlier one still resolves to the same bytes


def test_provisional_follows_the_deliberation(client):
    client.post(f"{BASE}/subjects", headers=as_("contributor"), json={"name": "mcx-services"})
    deliberate(client)
    d1 = client.get(f"{BASE}/exports/{client.post(f'{BASE}/exports', headers=as_('admin')).json()['data']['snapshotRef']['snapshotId']}",
                    headers=as_("reader")).json()["data"]
    assert d1["is_provisional"] is True and d1["provisional_reasons"]["unripe_subjects"] == 1
    client.post(f"{BASE}/subjects/mcx-services/maturity", headers=as_("decider"), json={"level": "L3_decided"})
    ref = client.post(f"{BASE}/exports", headers=as_("admin")).json()["data"]
    assert ref["is_provisional"] is False


def test_an_email_in_a_statement_stops_the_export_and_stores_nothing(client):
    deliberate(client, value="Escalate to cto@client.example when the gateway fails")
    res = client.post(f"{BASE}/exports", headers=as_("admin"))
    assert res.status_code == 422 and res.json()["error"] == "verification_failed"
    problems = res.json()["problems"]
    assert [p["code"] for p in problems] == ["EMAIL"] and "client.example" not in res.text  # where, never the value
    assert client.get(f"{BASE}/exports", headers=as_("admin")).json()["data"]["exports"] == []


def test_a_legacy_asserted_statement_without_a_person_stops_the_export(client):
    from tools.elicitation.repository import ElicitationRepository

    repo = ElicitationRepository(db_path=server_config.engagements_dir / f"{ENG}.lbug")
    repo.save_statement({"engagement": ENG, "subject": "core", "value": "old fact", "author": "@carl", "confidence": "designed", "status": "active"})
    repo.close()
    res = client.post(f"{BASE}/exports", headers=as_("admin"))
    assert res.status_code == 422 and "ASSERTED_WITHOUT_PERSON" in {p["code"] for p in res.json()["problems"]}


def test_citing_the_knowledge_base_needs_a_usable_snapshot(client, tmp_path):
    from mcp_server.knowledge import tools as knowledge_tools

    deliberate(client, based_on=[{"id": "ADR-0001"}])
    (knowledge_tools.SNAPSHOTS_DIR / "latest.json").unlink()
    res = client.post(f"{BASE}/exports", headers=as_("admin"))
    assert res.status_code == 422 and res.json()["error"] == "kb_snapshot_unavailable"


def test_a_snapshot_of_another_engagement_is_not_disclosed_and_a_corrupt_one_is_reported(client):
    deliberate(client)
    sid = client.post(f"{BASE}/exports", headers=as_("admin")).json()["data"]["snapshotRef"]["snapshotId"]
    other = client.post("/api/engagements", headers=OPERATOR, json={
        "engagement": "eng-y", "confidentiality": "internal", "admin_email": "yan@example.org", "admin_handle": "@yan"})
    assert other.status_code == 201
    stolen = client.get(f"/api/engagements/eng-y/exports/{sid}", headers={"Authorization": f"Bearer {ARCHINEX}", "X-Actor-Email": "yan@example.org"})
    assert stolen.status_code == 404
    from sqlalchemy import update

    from pipelines.governance.store import engagement_exports

    access = get_access()
    row = access.get_export(sid)["envelope"]
    row["data"]["requirements"] = [{"id": "X", "text": "forged", "section": "", "category": "c", "criticality": "m", "status": "gap"}]
    with access.engine.begin() as conn:
        conn.execute(update(engagement_exports).where(engagement_exports.c.snapshot_id == sid).values(envelope=canonical.dumps(row)))
    bad = client.get(f"{BASE}/exports/{sid}", headers=as_("reader"))
    assert bad.status_code == 500 and bad.json()["error"] == "snapshot_corrupt"


def test_the_export_is_audited_by_handle(client):
    deliberate(client)
    client.post(f"{BASE}/exports", headers=as_("admin"))
    events = client.get(f"{BASE}/audit", headers=as_("admin")).json()["data"]["events"]
    assert any(e["action"] == "export" and e["outcome"] == "allowed" and e["actor"] == "@ada" for e in events)
