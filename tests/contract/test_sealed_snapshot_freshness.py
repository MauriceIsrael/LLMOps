"""K2: the published sealed snapshot is the one the code rebuilds, byte for byte (``rebuiltByEmitterTest``).

The emitter's freshness test must *rebuild* the golden file rather than read it (suite channel registry,
``witness.rebuiltByEmitterTest``). The knowledge database is rebuilt here from ``data/kb`` in a scratch directory, so the
test does not depend on whatever local database a developer happens to hold.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from pipelines import canonical
from pipelines.snapshot_envelope import EMITTER, REGENERATE_COMMAND
from scripts.export_sealed_snapshot import export_sealed_snapshot

ROOT = Path(__file__).resolve().parents[2]
PAYLOAD_KEYS = ("applicability_index", "assets", "glossary", "frameworks", "controls", "compliance_index")
PROVENANCE_KEYS = ("snapshot_id", "created_at", "source_revision")  # change with every build, by design


@pytest.fixture(scope="module")
def rebuilt(tmp_path_factory):
    work = tmp_path_factory.mktemp("sealed")
    db = work / "knowledge.lbug"
    subprocess.run(
        [sys.executable, "-m", "pipelines.cli", "ingest", "--kb-dir", str(ROOT / "data/kb"), "--db-path", str(db)],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    envelope = export_sealed_snapshot(
        output_fixtures_path=work / "sealed_snapshot.json", output_snapshot_dir=work / "snapshots", db_path=db
    )
    return envelope, db


def _load(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


@pytest.mark.parametrize("path", ["fixtures/sealed_snapshot.json", "data/snapshots/latest.json"])
def test_published_snapshot_is_what_the_code_rebuilds(rebuilt, path):
    rebuilt, _ = rebuilt
    published = _load(path)
    stable = lambda doc: {k: v for k, v in doc.items() if k not in PROVENANCE_KEYS}  # noqa: E731
    assert canonical.dumps(stable(published)) == canonical.dumps(stable(rebuilt)), (
        f"{path} is stale. Regenerate it with: {REGENERATE_COMMAND}"
    )


def test_channel_envelope_of_the_published_snapshot():
    doc = _load("fixtures/sealed_snapshot.json")
    payload = {k: doc[k] for k in PAYLOAD_KEYS}
    assert doc["emitter"] == EMITTER == "knowledge-hub"
    assert doc["checksum"] == doc["payload_sha256"] == canonical.sha256(payload)
    assert doc["rebuiltByEmitterTest"] is True
    assert doc["regenerate"] == REGENERATE_COMMAND
    assert doc["is_provisional"] is False
    assert doc["provisional_reasons"] == {"unripe_subjects": 0, "open_conflicts": 0}


def test_rebuild_is_deterministic(rebuilt, tmp_path):
    """Two builds of the same database give the same payload (the framework version no longer depends on row order)."""
    first, db = rebuilt
    again = export_sealed_snapshot(output_fixtures_path=tmp_path / "f.json", output_snapshot_dir=tmp_path / "s", db_path=db)
    assert again["payload_sha256"] == first["payload_sha256"]


def test_the_export_refuses_content_that_changed_without_a_new_revision(rebuilt, tmp_path):
    """K3: the same {knowledgeKey, version} must always resolve to the same bytes."""
    from pipelines.knowledge_ref import LEDGER_NAME, VersionLedgerError, load_ledger, write_ledger

    _, db = rebuilt
    ledger = load_ledger(ROOT / "data/kb" / LEDGER_NAME)
    ledger["decision:ADR-0001"]["1"] = "sha256:" + "0" * 64  # the ledger remembers other bytes for this revision
    forged = tmp_path / LEDGER_NAME
    write_ledger(forged, ledger)
    with pytest.raises(VersionLedgerError, match="decision:ADR-0001 revision 1"):
        export_sealed_snapshot(
            output_fixtures_path=tmp_path / "f.json", output_snapshot_dir=tmp_path / "s", db_path=db, ledger_path=forged
        )


def test_the_export_refuses_a_revision_the_ledger_does_not_know(rebuilt, tmp_path):
    from pipelines.knowledge_ref import LEDGER_NAME, VersionLedgerError, load_ledger, write_ledger

    _, db = rebuilt
    ledger = load_ledger(ROOT / "data/kb" / LEDGER_NAME)
    del ledger["decision:ADR-0001"]
    short = tmp_path / LEDGER_NAME
    write_ledger(short, ledger)
    with pytest.raises(VersionLedgerError, match="not in the version ledger"):
        export_sealed_snapshot(
            output_fixtures_path=tmp_path / "f.json", output_snapshot_dir=tmp_path / "s", db_path=db, ledger_path=short
        )
    # regenerating (recording) is what adds it, and the ledger file then holds it
    export_sealed_snapshot(
        output_fixtures_path=tmp_path / "f.json", output_snapshot_dir=tmp_path / "s", db_path=db, ledger_path=short,
        record_revisions=True,
    )
    assert "decision:ADR-0001" in load_ledger(short)
