"""Governance bootstrap at server start and the seeded contract server."""

from pathlib import Path

from pipelines.governance.bootstrap import ensure_governance_ready
from pipelines.governance.store import dispose_engines

ROOT = Path(__file__).parent.parent.parent
DATASET = ROOT / "tests" / "evals" / "datasets" / "check_option_v1.jsonl"


def test_nothing_happens_without_a_database(monkeypatch):
    monkeypatch.delenv("GOVERNANCE_DATABASE_URL", raising=False)
    monkeypatch.setenv("CANDIDATES_BACKEND", "file")
    assert ensure_governance_ready(ROOT / "data" / "kb", DATASET) is None


def test_bootstrap_seeds_once_and_never_overwrites(tmp_path, monkeypatch):
    dispose_engines()
    monkeypatch.setenv("GOVERNANCE_DATABASE_URL", f"sqlite:///{tmp_path / 'g.db'}")
    first = ensure_governance_ready(ROOT / "data" / "kb", DATASET)
    assert first["owners_seeded"] is True and first["eval_cases"] == {"imported": 30, "skipped": 0}
    from pipelines.governance.registry import load_registry_from_db, save_registry

    reg = load_registry_from_db()
    assert reg is not None
    reg.owners["@maintainers"] = reg.owner("@maintainers").__class__(handle="@maintainers", email="m@example.org")
    save_registry(reg)
    again = ensure_governance_ready(ROOT / "data" / "kb", DATASET)
    assert again["owners_seeded"] is False and again["eval_cases"] == {"imported": 0, "skipped": 30}
    assert load_registry_from_db().owner("@maintainers").email == "m@example.org"
    dispose_engines()


def test_bootstrap_failure_is_logged_not_raised(monkeypatch, tmp_path):
    dispose_engines()
    monkeypatch.setenv("GOVERNANCE_DATABASE_URL", f"sqlite:///{tmp_path / 'g.db'}")

    def boom(*args, **kwargs):
        raise RuntimeError("database unreachable")

    monkeypatch.setattr("pipelines.governance.migrate.migrate_governance", boom)
    assert ensure_governance_ready(ROOT / "data" / "kb", DATASET) is None  # logged, the server still starts
    dispose_engines()


def test_contract_server_personas_are_consistent(tmp_path):
    import importlib.util

    spec = importlib.util.spec_from_file_location("contract_server", ROOT / "scripts" / "contract_server.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    env = module.prepare(tmp_path)
    import yaml

    assert Path(env["LLMOPS_KB_DIR"]) == tmp_path / "data" / "kb"  # the relative path data/kb works from the scratch cwd
    assert (tmp_path / "data" / "kb" / "controls").is_dir()
    owners = yaml.safe_load((Path(env["LLMOPS_KB_DIR"]) / "owners.yaml").read_text())["owners"]
    assert owners["@maintainers"]["roles"] == ["kb:maintain", "kb:admin"]
    assert owners["@security-compliance-team"]["email"] == "sec@example.org"
    assert "kb:delegate" in env["ENGAGEMENT_TOKENS"] and env["CANDIDATES_BACKEND"] == "sql"
