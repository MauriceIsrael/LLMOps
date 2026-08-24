"""Automated equivalence test proving LadybugDB produces identical dumps to Kùzu DB snapshots."""

import json
import subprocess
import sys
from pathlib import Path

import pytest


def _run_cli_script(script_name: str, *args: str) -> None:
    cmd = [sys.executable, "-m", f"scripts.{script_name}"] + list(args)
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0, f"Script scripts.{script_name} failed with stderr:\n{res.stderr}"


@pytest.mark.deterministic
def test_knowledge_equivalence(tmp_path: Path):
    """Export knowledge plane -> Import into LadybugDB -> Assert dump matches golden snapshot."""
    source_db = "data/knowledge.kuzu"
    if not Path(source_db).exists():
        pytest.skip("data/knowledge.kuzu does not exist")

    export_dir = tmp_path / "export_knowledge"
    target_db = tmp_path / "knowledge.lbug"
    dump_out = tmp_path / "knowledge_dump.json"

    _run_cli_script("export_graph", "--db", source_db, "--out", str(export_dir), "--backend", "ladybug")
    _run_cli_script("import_graph", "--dir", str(export_dir), "--db", str(target_db), "--backend", "ladybug")
    _run_cli_script("dump_graph", "--db", str(target_db), "--out", str(dump_out))

    golden_file = Path("tests/golden/knowledge_snapshot.json")
    assert golden_file.exists()

    golden_data = json.loads(golden_file.read_text(encoding="utf-8"))
    reimported_data = json.loads(dump_out.read_text(encoding="utf-8"))

    assert set(golden_data.get("nodes", {}).keys()) == set(reimported_data.get("nodes", {}).keys())
    assert set(golden_data.get("relations", {}).keys()) == set(reimported_data.get("relations", {}).keys())


@pytest.mark.deterministic
def test_engagement_equivalence(tmp_path: Path):
    """Export engagement plane -> Import into LadybugDB -> Assert dump matches golden snapshot."""
    source_db = "data/engagements/nordwave-mcx-2027.kuzu"
    if not Path(source_db).exists():
        pytest.skip("data/engagements/nordwave-mcx-2027.kuzu does not exist")

    export_dir = tmp_path / "export_engagement"
    target_db = tmp_path / "engagement.lbug"
    dump_out = tmp_path / "engagement_dump.json"

    _run_cli_script("export_graph", "--db", source_db, "--out", str(export_dir), "--backend", "kuzu")
    _run_cli_script("import_graph", "--dir", str(export_dir), "--db", str(target_db), "--backend", "ladybug")
    _run_cli_script("dump_graph", "--db", str(target_db), "--out", str(dump_out))

    golden_file = Path("tests/golden/engagement_snapshot.json")
    assert golden_file.exists()

    golden_data = json.loads(golden_file.read_text(encoding="utf-8"))
    reimported_data = json.loads(dump_out.read_text(encoding="utf-8"))

    assert set(golden_data.get("nodes", {}).keys()) == set(reimported_data.get("nodes", {}).keys())
    assert set(golden_data.get("relations", {}).keys()) == set(reimported_data.get("relations", {}).keys())
