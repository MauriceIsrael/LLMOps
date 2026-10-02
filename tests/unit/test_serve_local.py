"""scripts/serve_local.py: local defaults never override the environment; the service token is stable and delegating."""

import importlib.util
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("serve_local", Path(__file__).parents[2] / "scripts" / "serve_local.py")
serve_local = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(serve_local)  # type: ignore[union-attr]


def test_defaults_do_not_override_the_environment(tmp_path, monkeypatch):
    monkeypatch.setattr(serve_local, "TOKEN_FILE", tmp_path / "token")
    env = {"CANDIDATES_BACKEND": "file", "SERVER_TOKEN": "mine", "ENGAGEMENT_TOKENS": "t:kb:review"}
    applied = serve_local.configure(env)
    assert env["CANDIDATES_BACKEND"] == "file" and env["SERVER_TOKEN"] == "mine" and env["ENGAGEMENT_TOKENS"] == "t:kb:review"
    assert "ENGAGEMENT_TOKENS" not in applied and "SERVER_TOKEN" not in applied


def test_service_token_is_stable_across_restarts_and_delegating(tmp_path, monkeypatch):
    monkeypatch.setattr(serve_local, "TOKEN_FILE", tmp_path / "token")
    first, second = {}, {}
    serve_local.configure(first)
    serve_local.configure(second)
    assert first["LLMOPS_SERVICE_TOKEN"] == second["LLMOPS_SERVICE_TOKEN"]  # a restart does not break Archinex
    assert first["ENGAGEMENT_TOKENS"] == f"{first['LLMOPS_SERVICE_TOKEN']}:kb:review,kb:delegate,*"
    assert first["CANDIDATES_BACKEND"] == "sql" and first["GOVERNANCE_DATABASE_URL"].startswith("sqlite:///")


def test_explicit_service_token_is_used(tmp_path, monkeypatch):
    monkeypatch.setattr(serve_local, "TOKEN_FILE", tmp_path / "token")
    env = {"LLMOPS_SERVICE_TOKEN": "chosen"}
    serve_local.configure(env)
    assert env["ENGAGEMENT_TOKENS"].startswith("chosen:kb:review,kb:delegate")
    assert not (tmp_path / "token").exists()
