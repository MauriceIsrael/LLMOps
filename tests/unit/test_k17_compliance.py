"""K17, contract 1.30: the declared coverage requirement → control in the sealed engagement snapshot.

The chain is requirement ← subject ← decision → asset → control, read in the pinned knowledge snapshot. Nothing is ever
``verified``, no origin is taken from a caller, and lowering a decision from asserted to proposed changes the section and the seal.
"""

import copy
import json
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from mcp_server.core.config import server_config
from pipelines import canonical
from pipelines.engagement import compliance
from pipelines.engagement.access import get_access
from pipelines.engagement.snapshot import build_data, seal, verify
from pipelines.governance.store import dispose_engines
from scripts.export_engagement_example import scenario

ROOT = Path(__file__).resolve().parents[2]
ARCHINEX = "arx-token"
OPERATOR = {"Authorization": "Bearer demo-token"}
EMAILS = {"admin": "ada@example.org", "decider": "dan@example.org", "contributor": "carl@example.org"}
ENG = "eng-k17"
BASE = f"/api/engagements/{ENG}"
R1 = "SRC-1a2b3c4d:4.1"


def as_(role):
    return {"Authorization": f"Bearer {ARCHINEX}", "X-Actor-Email": EMAILS[role]}


def sealed(raw, kb):
    return seal(build_data(raw, "example-eng", "confidential", kb), "example-eng", "2026-10-03T12:00:00Z", "test")


def codes(env):
    return {p.code for p in verify(env)}


def example():
    raw, kb = scenario()
    return raw, kb


# --- the pure derivation --------------------------------------------------------------------------------------------


def test_an_asserted_decision_citing_an_asset_that_implements_a_control_allocates_it():
    raw, kb = example()
    env = sealed(raw, kb)
    assert verify(env) == []
    assert env["data"]["compliance"] == [{
        "id": "CMP:REQ-001:SNC-REQ-01", "requirement_id": "REQ-001", "control_ref": "SNC-REQ-01", "framework": "SecNumCloud",
        "control_version": "3.2", "status": "allocated", "assertion_level": "asserted", "basis": "declared_by_decision",
        "decision_ids": ["D-0001"], "via_assets": ["decision:ADR-0001"]}]


def test_lowering_the_decision_from_asserted_to_proposed_changes_the_coverage_and_the_seal():
    raw, kb = example()
    before = sealed(raw, kb)
    lowered = copy.deepcopy(raw)
    d = next(d for d in lowered["decisions"] if d["id"] == "D-0001")
    d.update(status="proposed", validated_by="", validated_at="")
    next(s for s in lowered["subjects"] if s["name"] == "gateway-services")["level"] = "L2_decomposed"  # no longer decided
    after = sealed(lowered, kb)
    assert verify(after) == []
    assert after["data"]["compliance"][0]["status"] == "proposed"
    assert after["data"]["compliance"][0]["assertion_level"] == "proposed"
    assert after["checksum"] != before["checksum"]


@pytest.mark.parametrize("status", ["superseded", "withdrawn"])
def test_a_decision_that_is_no_longer_standing_brings_no_coverage(status):
    raw, kb = example()
    raw["decisions"][0]["status"] = status
    assert "compliance" not in build_data(raw, "example-eng", "confidential", kb)


def test_a_requirement_the_people_decided_not_to_deliberate_is_out_of_the_chain():
    raw, kb = example()
    req = raw["requirements"][0]
    req.update(disposition="evacuated", disposition_reason="Out of the technical scope of the offer")
    raw["subject_requirements"] = {}  # an evacuated requirement is carried by no subject (REQ_NOT_DELIBERATED)
    assert "compliance" not in build_data(raw, "example-eng", "confidential", kb)


def test_a_subject_that_carries_no_requirement_declares_nothing():
    raw, kb = example()
    raw["subject_requirements"] = {}
    assert "compliance" not in build_data(raw, "example-eng", "confidential", kb)


def test_an_asset_that_implements_no_control_declares_nothing():
    raw, kb = example()
    kb["compliance_index"] = {}
    assert "compliance" not in build_data(raw, "example-eng", "confidential", kb)


def test_without_a_pinned_knowledge_snapshot_nothing_is_derived():
    raw, _ = example()
    assert compliance.derive([], [], raw["decisions"], None) == []


def test_the_section_is_deterministic_and_independent_of_the_order_of_the_rows():
    raw, kb = example()
    kb["compliance_index"]["NIS2"] = {"NIS2-ART21-2C": {"title": "t", "version": "2022/2555", "severity": "mandatory", "implemented_by": ["ADR-0001"]}}
    first = sealed(raw, kb)
    shuffled = copy.deepcopy(raw)
    shuffled["decisions"].reverse()
    assert [r["id"] for r in first["data"]["compliance"]] == ["CMP:REQ-001:NIS2-ART21-2C", "CMP:REQ-001:SNC-REQ-01"]
    assert sealed(shuffled, kb)["checksum"] == first["checksum"]


def test_an_engagement_that_declares_nothing_is_sealed_as_before():
    raw, kb = example()
    raw["decisions"][0]["based_on"] = []
    assert "compliance" not in build_data(raw, "example-eng", "confidential", kb)


# --- what is never said ---------------------------------------------------------------------------------------------


def test_no_status_is_verified_and_no_origin_is_declared():
    raw, kb = example()
    row = sealed(raw, kb)["data"]["compliance"][0]
    assert row["status"] in compliance.STATUSES and "verified" not in json.dumps(row)
    assert not {"origin", "source", "sourceSystem", "evidence"} & set(row)


def test_a_caller_cannot_make_a_row_verified_nor_name_its_origin():
    env = sealed(*example())
    for field, value in (("status", "verified"), ("origin", "architecture-studio"), ("basis", "text_match")):
        mutated = copy.deepcopy(env)
        mutated["data"]["compliance"][0][field] = value
        assert "SCHEMA" in codes(mutated), field


# --- the verification -----------------------------------------------------------------------------------------------


def mutate(env, edit):
    out = copy.deepcopy(env)
    edit(out["data"])
    out["checksum"] = canonical.sha256(out["data"])
    out["snapshotId"] = f"eng-example-eng-{out['checksum'][len('sha256:'):][:12]}"
    return out


@pytest.mark.parametrize(
    ("edit", "code"),
    [
        (lambda d: d["compliance"][0].update(requirement_id="REQ-404", id="CMP:REQ-404:SNC-REQ-01"), "DANGLING"),
        (lambda d: d["compliance"][0].update(decision_ids=["D-404"]), "DANGLING"),
        (lambda d: d["compliance"][0].update(id="CMP:wrong"), "COMPLIANCE_ID"),
        (lambda d: d["compliance"][0].update(status="proposed", assertion_level="proposed"), "COMPLIANCE_STATUS"),
        (lambda d: d["compliance"][0].update(assertion_level="proposed"), "COMPLIANCE_STATUS"),
        (lambda d: d["compliance"][0].update(decision_ids=["D-0002"]), "COMPLIANCE_NOT_ASSERTED"),
        (lambda d: d["compliance"][0].update(via_assets=["decision:NOT-IN-THE-BASE"]), "COMPLIANCE_ASSET_NOT_CITED"),
        (lambda d: d["pins"].update(kb_snapshot=None), "COMPLIANCE_UNPINNED"),
        (lambda d: d["compliance"].append(copy.deepcopy(d["compliance"][0])), "DUPLICATE_ID"),
        (lambda d: next(s for s in d["subjects"] if s["name"] == "gateway-services").pop("requirement_ids"), "COMPLIANCE_NOT_CARRIED"),
    ],
)
def test_the_verification_refuses_an_inconsistent_section(edit, code):
    env = sealed(*example())
    assert verify(env) == []
    assert code in codes(mutate(env, edit))


# --- through the API, in the real knowledge snapshot -----------------------------------------------------------------


@pytest.fixture
def client(monkeypatch, tmp_path):
    from mcp_server.knowledge import tools as knowledge_tools

    monkeypatch.setenv("SERVER_TOKEN", "demo-token")
    monkeypatch.setenv("ENGAGEMENT_TOKENS", f"{ARCHINEX}:*,eng:delegate;suite-token:*,eng:service")
    monkeypatch.setenv("GOVERNANCE_DATABASE_URL", f"sqlite:///{tmp_path}/gov.db")
    monkeypatch.setenv("LLMOPS_ENV", "development")
    monkeypatch.setattr(server_config, "engagements_dir", tmp_path)
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
        {"email": EMAILS["contributor"], "handle": "@carl", "role": "contributor"}], "test")
    assert c.post(f"{BASE}/requirements", headers=as_("contributor"), json={"requirements": [
        {"id": R1, "text": "Mission-critical data shall be recoverable after the loss of a site.", "section": "4", "criticality": "bloquant"}]}).status_code == 200
    assert c.post(f"{BASE}/subjects", headers=as_("contributor"), json={"name": "recovery", "requirement_ids": [R1]}).status_code in (200, 201)
    assert c.post(f"{BASE}/requirements/{R1}/disposition", headers=as_("contributor"), json={"disposition": "deliberated"}).status_code == 201
    assert c.post(f"{BASE}/requirements/{R1}/disposition/assert", headers=as_("decider")).status_code == 200
    yield c
    dispose_engines()


DECISION = {"subject": "recovery", "decision": "Mirror the data to a second site", "rationale": "Meets the recovery objective.",
            "reversibility": "costly", "rejected": [{"option": "Nightly backups only", "reason": "Recovery point too far."}],
            "based_on": [{"id": "ADR-0007"}]}


def snapshot(client):
    res = client.post(f"{BASE}/exports", headers=as_("admin"))
    assert res.status_code == 201, res.text
    return client.get(f"{BASE}/exports/{res.json()['data']['snapshotRef']['snapshotId']}", headers={"Authorization": "Bearer suite-token"}).json()


def test_a_decision_through_the_api_declares_the_controls_the_cited_asset_implements(client):
    res = client.post(f"{BASE}/decisions", headers=as_("contributor"), json=DECISION)
    assert res.status_code == 201, res.text
    did = res.json()["data"]["decision"]["id"]

    proposed = snapshot(client)
    assert verify(proposed) == []
    rows = proposed["data"]["compliance"]
    implemented = {"3GPP-TS28104-MDA", "3GPP-TS33179-ISOLATED", "3GPP-TS37579-ICS", "CER-ART13-RESIL", "ISO-22301-BCP", "NIS2-ART21-2C",
                   "SNC-REQ-02", "SNC-REQ-06", "TELCO-RESIL-GNSS-HOLDOVER", "TELCO-RESIL-TIER4"}
    assert {r["control_ref"] for r in rows} == implemented
    assert rows and all(r["status"] == "proposed" and r["decision_ids"] == [did] for r in rows)

    assert client.post(f"{BASE}/decisions/{did}/assert", headers=as_("decider")).status_code == 200
    asserted = snapshot(client)
    assert verify(asserted) == []
    assert {r["control_ref"] for r in asserted["data"]["compliance"]} == {r["control_ref"] for r in rows}
    assert all(r["status"] == "allocated" and r["assertion_level"] == "asserted" for r in asserted["data"]["compliance"])
    assert asserted["checksum"] != proposed["checksum"]
    assert "example.org" not in json.dumps(asserted)


def test_withdrawing_the_decision_removes_the_coverage(client):
    did = client.post(f"{BASE}/decisions", headers=as_("contributor"), json=DECISION).json()["data"]["decision"]["id"]
    assert client.post(f"{BASE}/decisions/{did}/withdraw", headers=as_("contributor")).status_code == 200
    assert "compliance" not in snapshot(client)["data"]


def test_a_decision_citing_nothing_declares_nothing(client):
    client.post(f"{BASE}/decisions", headers=as_("contributor"), json={**DECISION, "based_on": []})
    assert "compliance" not in snapshot(client)["data"]
