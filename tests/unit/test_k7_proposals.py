"""K7 (ADR-KH-01 amendment KH-1): proposals reach the Hub as a sealed snapshot the Hub reads, never as a direct call."""

import copy
import json
import shutil
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from mcp_server.core.config import server_config
from pipelines.kb_candidates.proposals import ProposalSnapshotError, import_snapshot, seal, verify
from pipelines.kb_candidates.repository import FileCandidateRepository
from pipelines.kb_candidates.service import CandidateService

ROOT = Path(__file__).resolve().parents[2]
PATTERN = (ROOT / "data/kb/patterns/PAT-001.md").read_text(encoding="utf-8")
EXAMPLE = ROOT / "schemas" / "examples" / "proposal_snapshot.example.json"


def proposal(ref="cand-1", title="Supervised closed loop (variant)", content=PATTERN, **over):
    return {"id": ref, "suggestedDestination": "knowledge-hub-reference",
            "sourceFragment": {"id": f"frag-{ref}", "documentId": "doc-1", "documentVersion": "1", "sectionPath": ["3"],
                               "originalText": "…", "hash": "sha256:" + "0" * 64},
            "proposal": {"kind": "new_asset", "asset_type": "pattern", "title": title, "rationale": "Seen twice.",
                         "proposed_content": content, "domain": ["network-automation"], **over}}


def snapshot(*candidates, source="document-studio", snapshot_id="ds-proposals-1"):
    return seal(list(candidates) or [proposal()], source, snapshot_id, "2026-10-15T09:00:00Z")


@pytest.fixture
def kb(tmp_path):
    target = tmp_path / "kb"
    shutil.copytree(ROOT / "data/kb", target)
    return target


@pytest.fixture
def service(kb, tmp_path):
    return CandidateService(repository=FileCandidateRepository(tmp_path / "candidates"), kb_dir=kb,
                            notify_owner=lambda *a: [], notify_consumers=lambda *a: [])


def test_a_proposal_becomes_a_candidate_with_the_provenance_of_the_channel(service):
    env = snapshot()
    res = import_snapshot(service, env, actor="@maintainer")
    created = service.get(res["imported"][0]["id"])
    assert created["status"] in ("in_review", "checks_failed")  # never active: a person reviews it
    assert created["source"]["system"] == "document-studio"
    assert (created["source"]["snapshot_id"], created["source"]["snapshot_checksum"], created["source"]["candidate_ref"]) == (
        "ds-proposals-1", env["checksum"], "cand-1")
    assert created["source"]["production_mode"] == "llm-derived"  # extracted proposals stay unreviewed until a person says otherwise


def test_an_altered_snapshot_is_refused_whole_and_nothing_is_created(service):
    env = snapshot(proposal("a"), proposal("b", title="Another variant"))
    env["data"]["candidates"][1]["proposal"]["title"] = "Tampered after sealing"
    with pytest.raises(ProposalSnapshotError) as err:
        import_snapshot(service, env, actor="@maintainer")
    assert [p.code for p in err.value.problems] == ["SEAL"]
    assert service.find() == []


def test_a_snapshot_that_does_not_follow_the_channel_is_refused():
    env = snapshot()
    wrong_destination = copy.deepcopy(env)
    wrong_destination["data"]["candidates"][0]["suggestedDestination"] = "somewhere-else"
    assert {p.code for p in verify(wrong_destination)} == {"SCHEMA"}
    assert {p.code for p in verify(snapshot(source="knowledge-hub"))} == {"SCHEMA"}  # the Hub is not a publisher of proposals
    assert {p.code for p in verify(snapshot(proposal("a"), proposal("a")))} == {"DUPLICATE_ID"}
    amendment = snapshot(proposal("a", kind="amendment"))
    assert {p.code for p in verify(amendment)} == {"AMENDMENT_WITHOUT_TARGET"}


def test_reading_the_same_snapshot_twice_creates_nothing_twice(service):
    env = snapshot(proposal("a"), proposal("b", title="Another variant"))
    first = import_snapshot(service, env, actor="@maintainer")
    second = import_snapshot(service, env, actor="@maintainer")
    assert len(first["imported"]) == 2 and second["imported"] == [] and len(second["skipped"]) == 2
    assert len(service.find()) == 2


def test_a_dry_run_creates_nothing(service):
    res = import_snapshot(service, snapshot(), actor="@maintainer", dry_run=True)
    assert res["dry_run"] and res["imported"][0]["would_be_status"] in ("in_review", "checks_failed")
    assert service.find() == []


def test_the_ordinary_checks_still_apply_to_a_proposal(service):
    leaky = PATTERN.replace("# PAT-001", "# PAT-001\n\nObserved by jane.doe@client-corp.example on 10.20.30.40.")
    res = import_snapshot(service, snapshot(proposal("leak", content=leaky)), actor="@maintainer")
    assert res["imported"][0]["status"] == "checks_failed"  # anonymisation (K13) is not bypassed by the channel


def test_the_published_example_is_a_valid_sealed_snapshot():
    env = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    assert verify(env) == []


@pytest.fixture
def client(monkeypatch, kb, service):
    from mcp_server.knowledge import tools
    from mcp_server.main import create_starlette_app

    monkeypatch.setenv("SERVER_TOKEN", "demo-token")
    monkeypatch.setattr(server_config, "kb_dir", kb)
    monkeypatch.setattr(tools, "_candidate_service", lambda: service)
    return TestClient(create_starlette_app(), raise_server_exceptions=False)


AUTH = {"Authorization": "Bearer demo-token"}


def test_the_rest_route_reads_a_snapshot_and_refuses_an_altered_one(client, service):
    ok = client.post("/api/knowledge/proposals/import", headers=AUTH, json=snapshot())
    assert ok.status_code == 201 and ok.json()["data"]["imported"][0]["candidate_ref"] == "cand-1"
    altered = snapshot(proposal("zzz"))
    altered["data"]["candidates"][0]["proposal"]["title"] = "Tampered"
    refused = client.post("/api/knowledge/proposals/import", headers=AUTH, json=altered)
    assert refused.status_code == 400 and refused.json()["problems"][0]["code"] == "SEAL"
    assert len(service.find()) == 1


def test_the_example_is_what_the_code_rebuilds():
    from scripts.export_proposal_example import build_example

    assert json.loads(EXAMPLE.read_text(encoding="utf-8")) == build_example(), "regenerate with: poetry run python scripts/export_proposal_example.py"
