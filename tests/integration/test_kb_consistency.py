"""Issue #85 — the judge reads the compiled graph, not the files: a clause changed in a file must be reported until the
graph is rebuilt, and the check must not mistake a different line ending for a change.

A small knowledge base is copied from the repository, ingested into a scratch graph, then modified.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mcp_server.core.db import ReadOnlyKuzuClient
from pipelines.doctrine import load_index
from pipelines.kb_cli import app
from pipelines.kb_consistency import check_compiled_base

ROOT = Path(__file__).resolve().parents[2]
FILES = ("principles/P-001.md", "controls/NIS2/NIS2-ART21-2A.md", "decisions/ADR-0001.md")


def _ingest(kb: Path, db: Path) -> None:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    subprocess.run([sys.executable, "-m", "pipelines.cli", "ingest", "--kb-dir", str(kb), "--db-path", str(db)],
                   cwd=ROOT, check=True, capture_output=True, env=env)


def _check(kb: Path, db: Path) -> dict:
    client = ReadOnlyKuzuClient(db_path=db)
    return check_compiled_base(kb, lambda q, p: client.execute_cypher(q, p))


@pytest.fixture
def base(tmp_path):
    kb = tmp_path / "kb"
    for rel in FILES:
        (kb / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / "data" / "kb" / rel, kb / rel)
    db = tmp_path / "knowledge.lbug"
    _ingest(kb, db)
    return kb, db


def test_a_graph_just_built_from_the_files_is_consistent(base):
    kb, db = base
    report = _check(kb, db)
    assert report["status"] == "ok", report
    assert report["files"] == report["assets_in_base"] == len(FILES)
    assert report["changed_since_build"]["count"] == 0 and "reason" not in report


def test_a_clause_changed_in_a_file_is_reported_and_the_judge_still_uses_the_old_one(base):
    """The defect of issue #85: the file says one thing, the judge another, and nothing said so."""
    kb, db = base
    path = kb / "principles" / "P-001.md"
    text = path.read_text(encoding="utf-8")
    assert "terms_any: [manual configuration change" in text
    path.write_text(text.replace("terms_any: [manual configuration change", "terms_any: [a term the judge has never seen"),
                    encoding="utf-8")
    client = ReadOnlyKuzuClient(db_path=db)
    judged = load_index(lambda q, p: client.execute_cypher(q, p), kb).get("P-001")
    assert any("manual configuration change" in c.when.terms_any for c in judged.checks)  # the old clause
    report = _check(kb, db)
    assert report["status"] == "stale"
    assert report["changed_since_build"]["ids"] == ["P-001"]
    assert "ingest" in report["reason"]


def test_a_new_file_and_a_removed_file_are_reported(base):
    kb, db = base
    (kb / "principles" / "P-900.md").write_text(
        "---\nid: P-900\ntitle: A new principle\ntype: principle\nstatus: active\nconfidence: verified\n"
        "phase: [BUILD]\ndomain: [network-automation]\nowner: core-owner-architecture\nlast_reviewed: '2026-10-17'\n---\n\n"
        "# P-900\n\n## Statement\nNew.\n", encoding="utf-8")
    (kb / "decisions" / "ADR-0001.md").unlink()
    report = _check(kb, db)
    assert report["status"] == "stale"
    assert report["not_in_base"]["ids"] == ["P-900"] and report["removed_from_files"]["ids"] == ["ADR-0001"]


def test_another_line_ending_is_not_a_change(base):
    kb, db = base
    for rel in FILES:
        path = kb / rel
        path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))  # as checked out on Windows
    assert _check(kb, db)["status"] == "ok"


def test_a_graph_without_fingerprint_is_unverified_not_ok(base):
    from tools.adapters.ladybug_store import LadybugGraphStore

    kb, db = base
    store = LadybugGraphStore(db_path=db, read_only=False)
    store.execute_cypher("MATCH (n:Asset) SET n.file_sha256 = ''")
    store.execute_cypher("MATCH (n:Control) SET n.file_sha256 = ''")
    store.close()
    LadybugGraphStore.clear_cache(str(db))
    report = _check(kb, db)
    assert report["status"] == "unverified" and report["unverified"]["count"] == len(FILES)
    assert "built before issue #85" in report["reason"]


def test_kb_check_command_exit_codes(base):
    kb, db = base
    runner = CliRunner()
    args = ["check", "--kb-dir", str(kb), "--db-path", str(db)]
    assert runner.invoke(app, args).exit_code == 0
    path = kb / "principles" / "P-001.md"
    path.write_text(path.read_text(encoding="utf-8").replace("Generalized GitOps", "Generalised GitOps"), encoding="utf-8")
    result = runner.invoke(app, args)
    assert result.exit_code == 1 and "STALE" in result.output


def test_the_graph_committed_with_the_files_describes_them(tmp_path):
    """A publication that changes `data/kb` must commit the rebuilt `data/knowledge.lbug` with it (issue #85).

    A graph that no longer matches the files fails here: it turns a forgotten rebuild into a red CI instead of a judge
    working on another knowledge base. A graph built before the fingerprint existed cannot be compared: the test says so
    and skips; it becomes strict as soon as a publication (`kb publish`) rebuilds and commits the graph.
    Fix for a failure: `poetry run ingest --kb-dir data/kb`, from a clean copy, then commit the graph with the files."""
    db = tmp_path / "knowledge.lbug"
    shutil.copy(ROOT / "data" / "knowledge.lbug", db)
    report = _check(ROOT / "data" / "kb", db)
    if report["status"] == "unverified":
        pytest.skip(f"the committed graph has no file fingerprint yet ({report['unverified']['count']} assets): "
                    "the next `kb publish` rebuilds it and this check becomes strict")
    assert report["status"] == "ok", {k: report[k] for k in report if k not in ("files", "assets_in_base")}
