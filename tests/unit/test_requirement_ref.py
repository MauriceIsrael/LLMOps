"""Tests for RequirementRef normalization (LLMOps #150, contract 1.41)."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from mcp_server.core.config import server_config
from pipelines.compliance_mapper import to_conformity_snapshot
from pipelines.engagement.access import get_access
from pipelines.engagement.snapshot import build_data
from pipelines.governance.store import dispose_engines
from pipelines.requirement_ref import (
    SOURCE_ID_PATTERN,
    RequirementRefError,
    bump_requirement_version,
    hub_source_id,
    requirement_ref,
    try_requirement_ref,
    validate_requirement_ref,
)
from scripts.export_engagement_example import scenario
from tools.elicitation.repository import ElicitationRepository

ARCHINEX = "arx-token"
OPERATOR = {"Authorization": "Bearer demo-token"}
EMAILS = {"admin": "ada@example.org", "contributor": "carl@example.org"}
ENG = "eng-ref"
BASE = f"/api/engagements/{ENG}"


def as_(role: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {ARCHINEX}", "X-Actor-Email": EMAILS[role]}


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("SERVER_TOKEN", "demo-token")
    monkeypatch.setenv("ENGAGEMENT_TOKENS", f"{ARCHINEX}:*,eng:delegate")
    monkeypatch.setenv("GOVERNANCE_DATABASE_URL", f"sqlite:///{tmp_path}/gov.db")
    monkeypatch.setenv("LLMOPS_ENV", "development")
    monkeypatch.setattr(server_config, "engagements_dir", tmp_path)
    dispose_engines()
    from mcp_server.main import create_starlette_app

    c = TestClient(create_starlette_app(), raise_server_exceptions=False)
    assert c.post("/api/engagements", headers=OPERATOR, json={
        "engagement": ENG, "confidentiality": "confidential", "admin_email": EMAILS["admin"], "admin_handle": "@ada",
    }).status_code == 201
    get_access().replace_members(ENG, [
        {"email": EMAILS["admin"], "handle": "@ada", "role": "admin"},
        {"email": EMAILS["contributor"], "handle": "@carl", "role": "contributor"},
    ], "test")
    yield c
    dispose_engines()


# --- Unit tests for pipelines.requirement_ref --------------------------------------------------------------------


def test_hub_source_id_normalizes_and_matches_adr_suite_04():
    assert hub_source_id("nordwave-mcx-2027") == "knowledge-hub:nordwave-mcx-2027"
    assert hub_source_id("NIS2") == "knowledge-hub:nis2"
    assert hub_source_id("My_Project 01") == "knowledge-hub:my-project-01"
    assert SOURCE_ID_PATTERN.match(hub_source_id("NIS2"))
    with pytest.raises(RequirementRefError) as exc:
        hub_source_id("!!!")
    assert exc.value.reason == "invalid_source_id"


def test_requirement_ref_enforces_three_fields_or_nothing():
    ref = requirement_ref("tuleap:proj-1", "REQ-001", 3)
    assert ref == {"sourceId": "tuleap:proj-1", "requirementKey": "REQ-001", "version": "3"}

    for bad_source in ("knowledge-hub", "https://tuleap.local/proj", "Tuleap:Proj", ""):
        with pytest.raises(RequirementRefError):
            requirement_ref(bad_source, "REQ-001", "1")

    for bad_key in ("", "   "):
        with pytest.raises(RequirementRefError):
            requirement_ref("tuleap:proj-1", bad_key, "1")

    for bad_ver in ("", "  ", None, True, 0, -1):
        with pytest.raises(RequirementRefError):
            requirement_ref("tuleap:proj-1", "REQ-001", bad_ver)  # type: ignore[arg-type]


def test_validate_requirement_ref_rejects_partial_and_extra_fields():
    assert validate_requirement_ref({"sourceId": "tuleap:proj", "requirementKey": "REQ-1", "version": "5"}) == {
        "sourceId": "tuleap:proj",
        "requirementKey": "REQ-1",
        "version": "5",
    }
    with pytest.raises(RequirementRefError) as exc:
        validate_requirement_ref({"sourceId": "tuleap:proj", "requirementKey": "REQ-1"})
    assert exc.value.reason == "partial_ref"

    with pytest.raises(RequirementRefError):
        validate_requirement_ref({"sourceId": "tuleap:proj", "requirementKey": "REQ-1", "version": "5", "extra": "x"})


def test_try_requirement_ref_never_emits_partial_ref():
    assert try_requirement_ref("knowledge-hub:eng", "REQ-1", "") is None
    assert try_requirement_ref("knowledge-hub:eng", "REQ-1", None) is None
    assert try_requirement_ref("knowledge-hub:eng", "", "1") is None
    assert try_requirement_ref("invalid-no-colon", "REQ-1", "1") is None
    assert try_requirement_ref("knowledge-hub:eng", "REQ-1", "1") == {
        "sourceId": "knowledge-hub:eng",
        "requirementKey": "REQ-1",
        "version": "1",
    }


def test_bump_requirement_version():
    assert bump_requirement_version("1") == "2"
    assert bump_requirement_version("v1") == "v2"
    assert bump_requirement_version("2022/2555") == "2022/2555.1"


# --- Acceptance tests: engagement write, import, modification & snapshot -----------------------------------------


def test_modified_requirement_changes_version_and_snapshot_reflects_it(tmp_path):
    repo = ElicitationRepository(db_path=str(tmp_path / "eng.lbug"))
    repo.save_requirement({
        "id": "REQ-100",
        "engagement": "eng-mod",
        "text": "Initial requirement text.",
        "source_id": "knowledge-hub:eng-mod",
        "requirement_key": "REQ-100",
        "version": "1",
    })
    before = repo.get_requirement("REQ-100")
    assert before is not None and before["version"] == "1"

    # Re-saving identical text preserves version
    repo.save_requirement({"id": "REQ-100", "engagement": "eng-mod", "text": "Initial requirement text."})
    same = repo.get_requirement("REQ-100")
    assert same is not None and same["version"] == "1"

    # Modifying text bumps version
    repo.save_requirement({"id": "REQ-100", "engagement": "eng-mod", "text": "Updated requirement text."})
    after = repo.get_requirement("REQ-100")
    assert after is not None and after["version"] == "2"

    # Snapshot emits the bumped version
    raw, kb = scenario()
    raw["requirements"] = [after]
    data = build_data(raw, "eng-mod", "confidential", kb)
    assert data["requirements"][0]["ref"] == {
        "sourceId": "knowledge-hub:eng-mod",
        "requirementKey": "REQ-100",
        "version": "2",
    }


def test_requirement_without_known_version_emits_no_partial_ref():
    raw, kb = scenario()
    raw["requirements"] = [
        {"id": "REQ-KNOWN", "text": "With version", "source_id": "knowledge-hub:eng", "requirement_key": "REQ-KNOWN", "version": "1"},
        {"id": "REQ-UNKNOWN", "text": "Without version", "source_id": "knowledge-hub:eng", "requirement_key": "REQ-UNKNOWN", "version": ""},
    ]
    data = build_data(raw, "eng", "confidential", kb)
    by_id = {r["id"]: r for r in data["requirements"]}
    assert by_id["REQ-KNOWN"]["ref"] == {"sourceId": "knowledge-hub:eng", "requirementKey": "REQ-KNOWN", "version": "1"}
    assert "ref" not in by_id["REQ-UNKNOWN"]


def test_rest_write_and_import_validate_requirement_ref(client):
    # Default Hub-assigned RequirementRef when ref is omitted
    res = client.post(f"{BASE}/requirements", headers=as_("contributor"), json={
        "requirements": [
            {"id": "REQ-HUB-1", "text": "System shall log all admin actions."},
            {"id": "REQ-EXT-1", "text": "System shall support OIDC.",
             "ref": {"sourceId": "tuleap:proj-42", "requirementKey": "TLP-99", "version": "7"}},
        ],
    })
    assert res.status_code == 200, res.text

    # Partial ref is rejected (three fields or nothing)
    bad = client.post(f"{BASE}/requirements", headers=as_("contributor"), json={
        "requirements": [{"id": "REQ-BAD", "text": "Partial ref", "ref": {"sourceId": "tuleap:proj-42", "requirementKey": "TLP-100"}}],
    })
    assert bad.status_code == 400
    assert bad.json()["status"] == "invalid_argument"

    # Import rejects partial ref cleanly
    imp = client.post(f"{BASE}/import", headers=as_("admin"), json={
        "batch_id": "batch-ref-1",
        "requirements": [
            {"id": "REQ-IMP-BAD", "text": "No version", "ref": {"sourceId": "tuleap:proj-42", "requirementKey": "TLP-101"}},
        ],
    })
    assert imp.status_code == 422, imp.text
    assert any(r["code"] == "invalid_argument" and r["ref"] == "REQ-IMP-BAD" for r in imp.json()["data"]["rejected"])

    # Sealed engagement snapshot includes the valid RequirementRefs
    exp = client.post(f"{BASE}/exports", headers=as_("admin"))
    assert exp.status_code == 201
    snap_id = exp.json()["data"]["snapshotRef"]["snapshotId"]
    fetched = client.get(f"{BASE}/exports/{snap_id}", headers=as_("admin"))
    assert fetched.status_code == 200
    reqs = {r["id"]: r for r in fetched.json()["data"]["requirements"]}
    assert reqs["REQ-HUB-1"]["ref"] == {"sourceId": f"knowledge-hub:{ENG}", "requirementKey": "REQ-HUB-1", "version": "1"}
    assert reqs["REQ-EXT-1"]["ref"] == {"sourceId": "tuleap:proj-42", "requirementKey": "TLP-99", "version": "7"}


def test_conformity_snapshot_emits_ref_only_when_version_is_known(tmp_path):
    ctrl_dir = tmp_path / "controls" / "NIS2"
    ctrl_dir.mkdir(parents=True)
    (ctrl_dir / "NIS2-WITH-VER.md").write_text(
        "---\nid: NIS2-WITH-VER\ntitle: With version\nframework: NIS2\nversion: '2022/2555'\ndomain: [security]\n---\n",
        encoding="utf-8",
    )
    (ctrl_dir / "NIS2-NO-VER.md").write_text(
        "---\nid: NIS2-NO-VER\ntitle: No version\nframework: NIS2\nversion: ''\ndomain: [security]\n---\n",
        encoding="utf-8",
    )
    snap = to_conformity_snapshot(engagement="eng-test", framework="NIS2", controls_dir=tmp_path / "controls")
    by_id = {r["id"]: r for r in snap["data"]["requirements"]}
    assert by_id["NIS2-WITH-VER"]["ref"] == {
        "sourceId": "knowledge-hub:nis2",
        "requirementKey": "NIS2-WITH-VER",
        "version": "2022/2555",
    }
    assert "ref" not in by_id["NIS2-NO-VER"]
