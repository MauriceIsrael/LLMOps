"""K17, contract 1.33 (issue #123): a requirement written through the API — which never carries ``matched_controls`` — reaches the
controls its decisions declare, on the real knowledge snapshot, without any matching of text."""

import json
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from mcp_server.core.config import server_config
from pipelines.engagement.access import get_access
from pipelines.engagement.snapshot import verify
from pipelines.governance.store import dispose_engines

ROOT = Path(__file__).resolve().parents[2]
ARCHINEX = "arx-token"
OPERATOR = {"Authorization": "Bearer demo-token"}
EMAILS = {"admin": "ada@example.org", "decider": "dan@example.org", "contributor": "carl@example.org"}
ENG = "eng-declared-chain"
BASE = f"/api/engagements/{ENG}"
R1 = "SRC-1a2b3c4d:4.1"
# What the real snapshot says ADR-0007 implements (compliance_index), read from the snapshot itself so that the test follows the base.
KB = json.loads((ROOT / "data/snapshots/latest.json").read_text(encoding="utf-8"))
IMPLEMENTED_BY_ADR_0007 = {c["id"] for c in KB["controls"] if "ADR-0007" in (c.get("implemented_by") or [])}


def as_(role):
    return {"Authorization": f"Bearer {ARCHINEX}", "X-Actor-Email": EMAILS[role]}


@pytest.fixture
def client(monkeypatch, tmp_path):
    from mcp_server.knowledge import tools as knowledge_tools

    monkeypatch.setenv("SERVER_TOKEN", "demo-token")
    monkeypatch.setenv("ENGAGEMENT_TOKENS", f"{ARCHINEX}:*,eng:delegate;suite-token:*,eng:service")
    monkeypatch.setenv("GOVERNANCE_DATABASE_URL", f"sqlite:///{tmp_path}/gov.db")
    monkeypatch.setenv("LLMOPS_ENV", "development")
    monkeypatch.setattr(server_config, "engagements_dir", tmp_path)
    snapshots = tmp_path / "snapshots"
    snapshots.mkdir()
    (snapshots / "latest.json").write_text((ROOT / "data/snapshots/latest.json").read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(knowledge_tools, "SNAPSHOTS_DIR", snapshots)
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


def test_the_precondition_holds_adr_0007_implements_controls_in_the_real_snapshot():
    assert IMPLEMENTED_BY_ADR_0007, "the test needs an asset that implements controls"


def test_a_requirement_written_through_the_api_reaches_the_controls_its_decision_declares(client):
    assert snapshot(client)["data"]["compliance"]["items"] == []  # nothing declared yet: no decision, no matched control

    did = client.post(f"{BASE}/decisions", headers=as_("contributor"), json=DECISION).json()["data"]["decision"]["id"]
    proposed = snapshot(client)
    assert verify(proposed) == []
    items = proposed["data"]["compliance"]["items"]
    assert {i["control_id"] for i in items} == IMPLEMENTED_BY_ADR_0007
    assert all(i["status"] == "proposed" and i["basis"] == "declared_by_decision" and i["decisions"] == [did] for i in items)
    assert all(i["requirement_id"] == R1 and i["assets"] == ["ADR-0007"] for i in items)

    assert client.post(f"{BASE}/decisions/{did}/assert", headers=as_("decider")).status_code == 200
    asserted = snapshot(client)
    assert verify(asserted) == []
    assert {i["status"] for i in asserted["data"]["compliance"]["items"]} == {"allocated"}
    assert asserted["checksum"] != proposed["checksum"]
    assert asserted["data"]["compliance"]["origin"] == "knowledge-hub"
    assert "verified" not in json.dumps(asserted["data"]["compliance"])


def test_withdrawing_the_decision_removes_the_declared_rows(client):
    did = client.post(f"{BASE}/decisions", headers=as_("contributor"), json=DECISION).json()["data"]["decision"]["id"]
    assert client.post(f"{BASE}/decisions/{did}/withdraw", headers=as_("contributor")).status_code == 200
    assert snapshot(client)["data"]["compliance"]["items"] == []


def test_a_decision_that_cites_nothing_declares_nothing(client):
    client.post(f"{BASE}/decisions", headers=as_("contributor"), json={**DECISION, "based_on": []})
    assert snapshot(client)["data"]["compliance"]["items"] == []
