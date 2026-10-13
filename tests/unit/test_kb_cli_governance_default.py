"""kb CLI: the governance database is found by default, like scripts/serve_local.py (issue #102)."""

from pipelines import kb_cli


def test_defaults_to_the_governance_database_when_it_exists(tmp_path, monkeypatch):
    db = tmp_path / "governance.db"
    db.write_text("")
    monkeypatch.setattr(kb_cli, "GOVERNANCE_DB", db)
    env: dict[str, str] = {}
    assert kb_cli.apply_governance_defaults(env) is True
    assert env["CANDIDATES_BACKEND"] == "sql"
    assert env["GOVERNANCE_DATABASE_URL"] == f"sqlite:///{db.as_posix()}"


def test_nothing_is_configured_when_the_database_is_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(kb_cli, "GOVERNANCE_DB", tmp_path / "absent.db")
    env: dict[str, str] = {}
    assert kb_cli.apply_governance_defaults(env) is False
    assert env == {}


def test_an_explicit_setting_always_wins(tmp_path, monkeypatch):
    db = tmp_path / "governance.db"
    db.write_text("")
    monkeypatch.setattr(kb_cli, "GOVERNANCE_DB", db)
    env = {"CANDIDATES_BACKEND": "file"}
    assert kb_cli.apply_governance_defaults(env) is False
    assert env == {"CANDIDATES_BACKEND": "file"}
    env = {"GOVERNANCE_DATABASE_URL": "postgresql://x/y"}
    assert kb_cli.apply_governance_defaults(env) is True
    assert env == {"GOVERNANCE_DATABASE_URL": "postgresql://x/y"}