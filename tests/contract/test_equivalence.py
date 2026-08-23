"""Automated equivalence test proving LadybugDB produces identical dumps to Kùzu DB snapshots."""

import gc
import json
from pathlib import Path

import pytest

from mcp_server.db.kuzu_client import KuzuClient
from scripts.dump_graph import dump_graph
from scripts.export_graph import export_graph
from scripts.import_graph import import_graph
from tools.adapters.ladybug_store import LadybugGraphStore


def _clear_db_caches():
    KuzuClient.clear_cache()
    LadybugGraphStore.clear_cache()
    gc.collect()


@pytest.mark.deterministic
def test_knowledge_equivalence(tmp_path: Path):
    """Export knowledge.kuzu -> Import into LadybugDB -> Assert dump matches golden snapshot."""
    _clear_db_caches()
    source_db = "data/knowledge.kuzu"
    if not Path(source_db).exists():
        pytest.skip("data/knowledge.kuzu does not exist")

    export_dir = tmp_path / "export_knowledge"
    target_db = tmp_path / "knowledge.lbug"
    dump_out = tmp_path / "knowledge_dump.json"

    export_graph(db_path=source_db, out_dir=str(export_dir), backend="kuzu")
    _clear_db_caches()

    import_graph(in_dir=str(export_dir), db_path=str(target_db), backend="ladybug")
    _clear_db_caches()

    dump_graph(db_path=str(target_db), output_path=str(dump_out))
    _clear_db_caches()

    golden_file = Path("tests/golden/knowledge_snapshot.json")
    assert golden_file.exists()

    golden_data = json.loads(golden_file.read_text(encoding="utf-8"))
    reimported_data = json.loads(dump_out.read_text(encoding="utf-8"))

    assert set(golden_data.get("nodes", {}).keys()) == set(reimported_data.get("nodes", {}).keys())
    assert set(golden_data.get("relations", {}).keys()) == set(reimported_data.get("relations", {}).keys())


@pytest.mark.deterministic
def test_engagement_equivalence(tmp_path: Path):
    """Export engagement.kuzu -> Import into LadybugDB -> Assert dump matches golden snapshot."""
    _clear_db_caches()
    source_db = "data/engagements/nordwave-mcx-2027.kuzu"
    if not Path(source_db).exists():
        pytest.skip("data/engagements/nordwave-mcx-2027.kuzu does not exist")

    export_dir = tmp_path / "export_engagement"
    target_db = tmp_path / "engagement.lbug"
    dump_out = tmp_path / "engagement_dump.json"

    export_graph(db_path=source_db, out_dir=str(export_dir), backend="kuzu")
    _clear_db_caches()

    import_graph(in_dir=str(export_dir), db_path=str(target_db), backend="ladybug")
    _clear_db_caches()

    dump_graph(db_path=str(target_db), output_path=str(dump_out))
    _clear_db_caches()

    golden_file = Path("tests/golden/engagement_snapshot.json")
    assert golden_file.exists()

    golden_data = json.loads(golden_file.read_text(encoding="utf-8"))
    reimported_data = json.loads(dump_out.read_text(encoding="utf-8"))

    assert set(golden_data.get("nodes", {}).keys()) == set(reimported_data.get("nodes", {}).keys())
    assert set(golden_data.get("relations", {}).keys()) == set(reimported_data.get("relations", {}).keys())
