"""K3 (ADR-KH-01 D8): the same {knowledgeKey, version} always resolves to the same bytes, from a sealed snapshot."""

import json
import shutil
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from pipelines import canonical
from pipelines.knowledge_ref import (
    LEDGER_NAME,
    PAYLOAD_KEYS,
    ResolutionError,
    VersionLedgerError,
    bump_revision,
    check_revisions,
    content_sha256,
    knowledge_ref,
    load_ledger,
    load_snapshot,
    resolve,
    revision_of,
    write_ledger,
)

ROOT = Path(__file__).resolve().parents[2]
SHA_A, SHA_B = "sha256:" + "a" * 64, "sha256:" + "b" * 64


def doc(revision=None):
    fm = "" if revision is None else f"revision: {revision}\n"
    return f"---\nid: ADR-9\ntitle: t\n{fm}---\n\n# body\n"


# --- revision ------------------------------------------------------------------------------------------------------


def test_revision_defaults_to_one_and_reads_the_front_matter():
    assert revision_of(doc()) == 1 and revision_of(doc(4)) == 4
    assert bump_revision(doc()) == 2 and bump_revision(doc(4)) == 5


@pytest.mark.parametrize("bad", ["0", "-1", "'2'", "true", "1.5"])
def test_an_invalid_revision_is_refused_not_defaulted(bad):
    with pytest.raises(ValueError):
        revision_of(f"---\nid: X\nrevision: {bad}\n---\nbody")


def test_the_legacy_version_field_is_not_the_revision():
    assert revision_of("---\nid: C\nversion: 2022/2555\n---\nbody") == 1  # a control's regulatory text revision


# --- ledger --------------------------------------------------------------------------------------------------------


def test_a_published_revision_cannot_change_content():
    ledger = {"decision:ADR-9": {"1": SHA_A}}
    with pytest.raises(VersionLedgerError, match="changed without a new revision"):
        check_revisions(ledger, {"decision:ADR-9": (1, SHA_B)}, record=True)  # even when recording


def test_a_new_revision_is_refused_until_recorded():
    ledger = {"decision:ADR-9": {"1": SHA_A}}
    with pytest.raises(VersionLedgerError, match="not in the version ledger"):
        check_revisions(ledger, {"decision:ADR-9": (2, SHA_B)}, record=False)
    updated = check_revisions(ledger, {"decision:ADR-9": (2, SHA_B)}, record=True)
    assert updated["decision:ADR-9"] == {"1": SHA_A, "2": SHA_B}


def test_a_removed_element_stays_in_the_ledger_and_its_identifier_cannot_be_recycled():
    ledger = {"decision:ADR-9": {"1": SHA_A}, "decision:GONE": {"1": SHA_A}}
    updated = check_revisions(ledger, {"decision:ADR-9": (1, SHA_A)}, record=True)
    assert "decision:GONE" in updated  # retired, still recorded
    with pytest.raises(VersionLedgerError):  # the same identifier reused for other content at the same revision
        check_revisions(updated, {"decision:GONE": (1, SHA_B)}, record=True)


def test_the_committed_ledger_covers_every_published_revision():
    ledger = load_ledger(ROOT / "data/kb" / LEDGER_NAME)
    snap = json.loads((ROOT / "fixtures/sealed_snapshot.json").read_text(encoding="utf-8"))
    assert snap["assets"]
    for a in snap["assets"]:
        assert ledger[a["typed_id"]][str(a["revision"])] == a["content_sha256"], a["typed_id"]


def test_ledger_roundtrip_is_stable(tmp_path):
    path = tmp_path / LEDGER_NAME
    write_ledger(path, {"b:2": {"10": SHA_B, "2": SHA_A}, "a:1": {"1": SHA_A}})
    first = path.read_text(encoding="utf-8")
    write_ledger(path, load_ledger(path))
    assert path.read_text(encoding="utf-8") == first
    assert list(json.loads(first)["revisions"]) == ["a:1", "b:2"] and list(json.loads(first)["revisions"]["b:2"]) == ["2", "10"]


# --- the published snapshot ----------------------------------------------------------------------------------------


@pytest.fixture
def snapshots(tmp_path):
    d = tmp_path / "snapshots"
    d.mkdir()
    shutil.copy(ROOT / "data/snapshots/latest.json", d / "latest.json")
    return d


def test_every_published_asset_has_a_complete_citable_reference(snapshots):
    snap = load_snapshot(snapshots)
    keys = [a["typed_id"] for a in snap["assets"]]
    assert len(keys) == len(set(keys))  # identifiers are unique
    for a in snap["assets"]:
        assert a["knowledge_ref"] == knowledge_ref(a["typed_id"], a["revision"])
        assert set(a["knowledge_ref"]) == {"sourceId", "knowledgeKey", "version"} and a["knowledge_ref"]["sourceId"] == "knowledge-hub"
        assert a["content_sha256"] == content_sha256(a["content"])
        assert "source_path" not in a and "source_path" not in a["provenance"]


# --- resolution ----------------------------------------------------------------------------------------------------


def test_the_same_reference_resolves_to_the_same_bytes(snapshots):
    snap = load_snapshot(snapshots)
    one = resolve(snap, "decision:ADR-0001", "1")
    two = resolve(load_snapshot(snapshots), "ADR-0001", "1")  # by bare identifier too
    assert one["content"] == two["content"] and one["content_sha256"] == two["content_sha256"]
    assert one["knowledge_ref"] == {"sourceId": "knowledge-hub", "knowledgeKey": "decision:ADR-0001", "version": "1"}
    assert one["snapshot"]["snapshot_id"] == snap["snapshot_id"] and "source_path" not in one


def test_an_absent_version_is_refused_never_answered_with_the_current_content(snapshots):
    snap = load_snapshot(snapshots)
    with pytest.raises(ResolutionError) as err:
        resolve(snap, "decision:ADR-0001", "7")
    assert err.value.reason == "version_not_in_snapshot" and err.value.detail["available_version"] == "1"


def test_unknown_key_is_refused(snapshots):
    with pytest.raises(ResolutionError) as err:
        resolve(load_snapshot(snapshots), "decision:NOPE", None)
    assert err.value.reason == "unknown_key"


def _tamper(snapshots, mutate, reseal):
    path = snapshots / "latest.json"
    d = json.loads(path.read_text(encoding="utf-8"))
    mutate(d)
    if reseal:
        d["payload_sha256"] = d["checksum"] = canonical.sha256({k: d[k] for k in PAYLOAD_KEYS})
    path.write_text(json.dumps(d), encoding="utf-8")


def test_a_snapshot_altered_after_sealing_is_refused(snapshots):
    _tamper(snapshots, lambda d: d["assets"][0].update(title="forged"), reseal=False)
    with pytest.raises(ResolutionError) as err:
        load_snapshot(snapshots)
    assert err.value.reason == "snapshot_corrupt"


def test_content_that_does_not_match_its_hash_is_refused_even_in_a_resealed_snapshot(snapshots):
    _tamper(snapshots, lambda d: d["assets"][0].update(content="forged"), reseal=True)
    with pytest.raises(ResolutionError) as err:
        resolve(load_snapshot(snapshots), "decision:ADR-0001", "1")
    assert err.value.reason == "content_corrupt"


@pytest.mark.parametrize("bad", ["../latest", "snapshot-x", "snapshot-2026-10-03-zzz", "latest", "../../etc/passwd"])
def test_a_snapshot_identifier_cannot_escape_the_directory(snapshots, bad):
    with pytest.raises(ResolutionError) as err:
        load_snapshot(snapshots, bad)
    assert err.value.reason == "invalid_snapshot_id"


def test_a_named_snapshot_that_is_not_available_is_refused(snapshots):
    with pytest.raises(ResolutionError) as err:
        load_snapshot(snapshots, "snapshot-2020-01-01-abcdef0")
    assert err.value.reason == "snapshot_unavailable"


# --- REST route and MCP tool ---------------------------------------------------------------------------------------


@pytest.fixture
def client(monkeypatch, snapshots):
    monkeypatch.setenv("SERVER_TOKEN", "demo-token")
    monkeypatch.delenv("ENGAGEMENT_TOKENS", raising=False)
    from mcp_server.knowledge import tools
    from mcp_server.main import create_starlette_app

    monkeypatch.setattr(tools, "SNAPSHOTS_DIR", snapshots)
    return TestClient(create_starlette_app(), raise_server_exceptions=False)


AUTH = {"Authorization": "Bearer demo-token"}


def test_rest_resolves_a_reference_from_the_snapshot(client):
    res = client.get("/api/knowledge/assets/decision:ADR-0001", params={"version": "1"}, headers=AUTH)
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["knowledge_ref"]["knowledgeKey"] == "decision:ADR-0001" and data["content"].startswith("---")
    assert "source_path" not in res.text


def test_rest_without_version_resolves_the_latest_snapshot_not_the_live_base(client):
    res = client.get("/api/knowledge/assets/ADR-0001", headers=AUTH)
    assert res.status_code == 200 and res.json()["data"]["snapshot"]["snapshot_id"]


def test_rest_refusals(client):
    missing = client.get("/api/knowledge/assets/decision:ADR-0001", params={"version": "9"}, headers=AUTH)
    assert missing.status_code == 404 and missing.json()["reason"] == "version_not_in_snapshot"
    assert missing.json()["available_version"] == "1" and "content" not in missing.text
    assert client.get("/api/knowledge/assets/decision:NOPE", headers=AUTH).status_code == 404
    bad = client.get("/api/knowledge/assets/ADR-0001", params={"snapshot": "../x"}, headers=AUTH)
    assert bad.status_code == 400
    assert client.get("/api/knowledge/assets/ADR-0001").status_code == 401


def test_mcp_get_asset_resolves_from_the_snapshot_when_a_version_is_given(client):
    from mcp_server.knowledge.tools import get_asset

    res = get_asset("decision:ADR-0001", version="1")
    assert res["status"] == "ok" and res["data"]["version"] == "1"
    assert get_asset("decision:ADR-0001", version="2")["status"] == "not_found"
    live = get_asset("ADR-0001")
    assert live["status"] == "ok" and live["data"]["resolved_from"] == "live-base"  # current state, not citable
